from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.analysis import (
    ApplicationAnswer,
    ApplicationQuestion,
    ApplicationSupportRequest,
    ApplicationSupportResponse,
    AuditLog,
    AuditEntry,
    BusinessProfile,
    Citation,
    FollowUpQuestion,
    InformationFlag,
    IntakeAnswer,
    IntakeQuestion,
    OperationalActivity,
    QuestionGuidance,
    ReadinessScore,
    Recommendation,
    ReviewAction,
    RiskFlag,
    SourceDocument,
    SuggestedAnswer,
    SubmissionReadinessReport,
    WebsiteContext,
)


PROFILE_REQUIRED_FIELDS = {
    "business_name": "Business name",
    "industry": "Industry",
    "services_provided": "Services provided",
    "revenue": "Annual revenue",
    "payroll": "Annual payroll",
    "number_of_employees": "Number of employees",
    "customers_served": "Customers served",
}


class ApplicationSupportService:
    def run(self, payload: ApplicationSupportRequest) -> ApplicationSupportResponse:
        workflow_id = str(uuid4())
        source_documents = self._source_documents(payload)
        intake_questions = self._base_intake_questions()
        intake_answers = self._intake_answers(payload)
        operational_activities = self._operational_activities(payload)
        website_context = payload.website_context or WebsiteContext()
        application_questions = self._application_questions()
        risk_flags = self._paperwork_risk_flags(payload.business_profile, intake_answers, operational_activities, website_context)
        follow_up_questions = self._follow_up_questions(payload.business_profile, operational_activities, risk_flags, website_context)
        suggested_answers = self._suggested_answers(
            payload.business_profile,
            intake_answers,
            operational_activities,
            website_context,
            application_questions,
            risk_flags,
        )
        citations = [citation for answer in suggested_answers for citation in answer.citations]
        audit_log = self._suggestion_audit_log(intake_answers, suggested_answers)
        skipped_sections = self._skipped_sections(operational_activities)
        guidance = self._build_question_guidance(payload.application_answers)
        missing_information = self._detect_missing_information(payload.business_profile, payload.application_answers)
        legacy_risk_flags = self._detect_risk_flags(payload.business_profile, payload.application_answers)
        recommendations = self._build_recommendations(payload.business_profile, missing_information, legacy_risk_flags)
        readiness_score = self._score(payload.business_profile, payload.application_answers, missing_information, legacy_risk_flags)
        review_actions = self._build_review_actions(recommendations)
        audit_trail = self._build_audit_trail(payload, missing_information, legacy_risk_flags, recommendations, readiness_score)
        report = self._build_report(
            payload.business_profile,
            missing_information,
            legacy_risk_flags,
            recommendations,
            readiness_score,
            audit_trail,
        )

        return ApplicationSupportResponse(
            workflow_id=workflow_id,
            source_documents=source_documents,
            intake_questions=intake_questions,
            intake_answers=intake_answers,
            operational_activities=operational_activities,
            website_context=website_context,
            application_questions=application_questions,
            suggested_answers=suggested_answers,
            citations=citations,
            risk_flags=risk_flags,
            follow_up_questions=follow_up_questions,
            audit_log=audit_log,
            skipped_sections=skipped_sections,
            guidance=guidance,
            missing_information=missing_information,
            readiness_score=readiness_score,
            recommendations=recommendations,
            audit_trail=audit_trail,
            review_actions=review_actions,
            report=report,
        )

    def _source_documents(self, payload: ApplicationSupportRequest) -> list[SourceDocument]:
        if payload.source_documents:
            return payload.source_documents
        return [
            SourceDocument(
                document_id="pathway-sample-tech-eo",
                document_name="Original Technology E&O Portfolio Questionnaire",
                document_type="sample_questionnaire",
                source_note="Original portfolio example with fictional business data; no insurer form attached.",
            ),
        ]

    def _base_intake_questions(self) -> list[IntakeQuestion]:
        return [
            IntakeQuestion(question_id="business-description", prompt="What does the business do?", purpose="Understand operations in plain English."),
            IntakeQuestion(question_id="services-products", prompt="What services or products does it provide?", purpose="Identify Tech E&O service categories."),
            IntakeQuestion(question_id="customers", prompt="Who are the customers?", purpose="Understand customer type and exposure."),
            IntakeQuestion(question_id="territory", prompt="Where does the business operate?", purpose="Identify operating territory and possible jurisdiction review."),
            IntakeQuestion(question_id="professional-tech-work", prompt="Does the business provide advice, consulting, technology, professional services, or physical work?", purpose="Trigger relevant application sections."),
            IntakeQuestion(question_id="subcontractors", prompt="Does the business use subcontractors?", purpose="Trigger contract and subcontractor follow-up."),
            IntakeQuestion(question_id="data-access", prompt="Does the business store customer data, process payments, or access client systems?", purpose="Trigger cyber, privacy, and system access review."),
            IntakeQuestion(question_id="revenue", prompt="What is annual or projected revenue?", purpose="Map to revenue questions."),
            IntakeQuestion(question_id="prior-claims", prompt="Has the business had prior claims?", purpose="Map to claims and loss history questions."),
            IntakeQuestion(question_id="coverage-requested", prompt="What coverage is being requested?", purpose="Map to requested coverage and limits."),
            IntakeQuestion(question_id="website-context", prompt="Paste website, LinkedIn, quote notes, or public-facing business description if available.", purpose="Give the reviewer a better glimpse into the business."),
        ]

    def _intake_answers(self, payload: ApplicationSupportRequest) -> list[IntakeAnswer]:
        if payload.intake_answers:
            return payload.intake_answers
        profile = payload.business_profile
        return [
            IntakeAnswer(question_id="business-description", answer=profile.services_provided or "Technology consulting business providing IT advisory, implementation, custom software, training, and hardware resale."),
            IntakeAnswer(question_id="services-products", answer=profile.services_provided or "IT consulting/advice, software implementation, custom software development, training, and hardware resale."),
            IntakeAnswer(question_id="customers", answer=profile.customers_served or "Small and midsize business clients."),
            IntakeAnswer(question_id="territory", answer="Operates primarily in the United States."),
            IntakeAnswer(question_id="professional-tech-work", answer="Yes. The business provides technology and professional services."),
            IntakeAnswer(question_id="subcontractors", answer="Yes." if profile.uses_subcontractors else "No subcontractor use indicated."),
            IntakeAnswer(
                question_id="subcontractor-controls",
                answer=(
                    f"Subcontractors perform approximately {profile.subcontractor_percentage}% of work. "
                    f"Subcontractor COIs collected: {'yes' if profile.collects_subcontractor_cois else 'no/not confirmed'}."
                ) if profile.uses_subcontractors else "No subcontractor use indicated.",
            ),
            IntakeAnswer(question_id="data-access", answer="Yes." if profile.stores_customer_data else "Customer data or client system access not confirmed."),
            IntakeAnswer(question_id="revenue", answer=str(profile.revenue or "Revenue not provided.")),
            IntakeAnswer(question_id="prior-claims", answer="No prior claims indicated."),
            IntakeAnswer(question_id="coverage-requested", answer="Technology E&O / Professional Liability with cyber and privacy review."),
        ]

    def _operational_activities(self, payload: ApplicationSupportRequest) -> list[OperationalActivity]:
        if payload.operational_activities:
            return payload.operational_activities
        return [
            OperationalActivity(activity="IT consulting/advice", percentage=40, category="professional_advice"),
            OperationalActivity(activity="Software implementation", percentage=25, category="technology_services"),
            OperationalActivity(activity="Custom software development", percentage=20, category="software_development"),
            OperationalActivity(activity="Training", percentage=10, category="training"),
            OperationalActivity(activity="Hardware resale", percentage=5, category="hardware_resale"),
        ]

    def _application_questions(self) -> list[ApplicationQuestion]:
        return [
            ApplicationQuestion(question_id="applicant-name", section="Applicant Information", original_question="What is the business's legal name?"),
            ApplicationQuestion(question_id="website-url", section="Applicant Information", original_question="What is the business website, if any?"),
            ApplicationQuestion(question_id="business-operations", section="Nature of Operations", original_question="Explain the products and services the business offers in plain language."),
            ApplicationQuestion(question_id="gross-revenue", section="Revenue", original_question="What is the expected annual revenue for the current year?"),
            ApplicationQuestion(question_id="professional-services-percent", section="Professional Services", original_question="List the professional services offered and estimate each service's share of revenue."),
            ApplicationQuestion(question_id="technology-revenue-mix", section="Technology Operations", original_question="How is revenue divided among technology products and services?"),
            ApplicationQuestion(question_id="records-protected-information", section="Cyber and Privacy", original_question="Does the business hold sensitive customer records? If so, how many?"),
            ApplicationQuestion(question_id="internet-hosting-access", section="Cyber and Technology Services", original_question="Does the business host software, process online transactions, or access client systems?"),
            ApplicationQuestion(question_id="client-contracts", section="Contracts", original_question="Does the business use written agreements with clients?"),
            ApplicationQuestion(question_id="subcontractors", section="Subcontractors", original_question="Does the business engage contractors to deliver client work?"),
            ApplicationQuestion(question_id="subcontractor-percentage", section="Subcontractors", original_question="What share of client work or revenue involves contractors?"),
            ApplicationQuestion(question_id="subcontractor-cois", section="Subcontractors", original_question="Does the business request proof of insurance from contractors?"),
            ApplicationQuestion(question_id="prior-claims", section="Loss History", original_question="Have any claims or incidents arisen from the business's services? Give dates and details for reviewer follow-up."),
        ]

    def _paperwork_risk_flags(
        self,
        profile: BusinessProfile,
        intake_answers: list[IntakeAnswer],
        activities: list[OperationalActivity],
        website_context: WebsiteContext,
    ) -> list[RiskFlag]:
        flags: list[RiskFlag] = []
        activity_text = " ".join(activity.activity.lower() for activity in activities)
        website_text = f"{website_context.website_url} {website_context.pasted_website_text}".lower()
        if profile.stores_customer_data or "data" in activity_text or "software" in activity_text:
            flags.append(RiskFlag(
                flag_id="data-system-access",
                severity="high",
                source_field="data-access",
                reason="Customer data, software, or client system access may indicate cyber, privacy, and Tech E&O review needs.",
                suggested_next_action="Ask follow-up questions about data types, records, security controls, and client system access.",
            ))
        if profile.uses_subcontractors:
            flags.append(RiskFlag(
                flag_id="subcontractor-review",
                severity="medium",
                source_field="subcontractors",
                reason="Subcontractor use may affect contracts, quality control, and risk-transfer review.",
                suggested_next_action="Confirm subcontractor percentage, contracts, insurance requirements, and supervision.",
            ))
            if profile.subcontractor_percentage is None:
                flags.append(RiskFlag(
                    flag_id="subcontractor-percentage-missing",
                    severity="medium",
                    source_field="business_profile.subcontractor_percentage",
                    reason="The application asks how much work or revenue is tied to subcontractors, but the percentage is not confirmed.",
                    suggested_next_action="Ask what percentage of work or revenue is performed by subcontractors.",
                ))
            if not profile.collects_subcontractor_cois:
                flags.append(RiskFlag(
                    flag_id="subcontractor-coi-review",
                    severity="medium",
                    source_field="business_profile.collects_subcontractor_cois",
                    reason="Collecting subcontractor COIs helps reviewers confirm subcontractors carry their own coverage and supports risk-transfer review.",
                    suggested_next_action="Confirm whether COIs are collected from subcontractors and whether contracts require insurance.",
                ))
        if any(activity.category in {"professional_advice", "software_development"} and activity.percentage > 0 for activity in activities):
            flags.append(RiskFlag(
                flag_id="professional-services-review",
                severity="medium",
                source_field="operational_activities",
                reason="Advice, consulting, implementation, or custom software work may indicate E&O exposure.",
                suggested_next_action="Review service descriptions and client contract wording with a licensed insurance professional.",
            ))
        if sum(activity.percentage for activity in activities) != 100:
            flags.append(RiskFlag(
                flag_id="activity-total-invalid",
                severity="high",
                source_field="operational_activities",
                reason="Operational percentages must total 100% before application mapping is reliable.",
                suggested_next_action="Adjust activity percentages until the total equals 100%.",
            ))
        if website_context.pasted_website_text.strip():
            if any(term in website_text for term in ["ai", "automation", "integration", "managed service", "msp", "cybersecurity", "payment", "cloud", "hosting", "api", "compliance"]):
                flags.append(RiskFlag(
                    flag_id="website-public-description-review",
                    severity="medium",
                    source_field="website_context.pasted_website_text",
                    reason="Pasted public-facing website text includes technology service terms that may give an underwriter useful context or trigger follow-up.",
                    suggested_next_action="Compare website language against the intake answers and application service descriptions before submission.",
                ))
        return flags

    def _follow_up_questions(
        self,
        profile: BusinessProfile,
        activities: list[OperationalActivity],
        risk_flags: list[RiskFlag],
        website_context: WebsiteContext,
    ) -> list[FollowUpQuestion]:
        follow_ups: list[FollowUpQuestion] = []
        has_technology = any(activity.category in {"technology_services", "software_development"} and activity.percentage > 0 for activity in activities)
        has_advice = any(activity.category == "professional_advice" and activity.percentage > 0 for activity in activities)
        has_physical_or_hardware = any(activity.category == "hardware_resale" and activity.percentage > 0 for activity in activities)
        if has_technology:
            follow_ups.append(FollowUpQuestion(
                question_id="client-system-access",
                prompt="Do you access, administer, host, or integrate with client production systems?",
                reason="Technology work is greater than 0%, so system access may affect Tech E&O and cyber review.",
                triggered_by="operational_activities.technology_services",
                priority="high",
            ))
            follow_ups.append(FollowUpQuestion(
                question_id="security-controls",
                prompt="What security controls are used for data, access, backups, MFA, and incident response?",
                reason="Software or implementation work may create cyber/privacy follow-up needs.",
                triggered_by="operational_activities.software_development",
                priority="high",
            ))
        if profile.uses_subcontractors:
            follow_ups.append(FollowUpQuestion(
                question_id="subcontractor-controls",
                prompt="What percentage of work is performed by subcontractors, are written contracts used, and are COIs collected from them?",
                reason="Subcontractor work was indicated. This matters because underwriters may want to know how much work is outsourced and whether subcontractors carry their own insurance.",
                triggered_by="business_profile.uses_subcontractors",
                priority="medium",
            ))
        if has_advice:
            follow_ups.append(FollowUpQuestion(
                question_id="advice-deliverables",
                prompt="What advice, recommendations, reports, or deliverables are provided to clients?",
                reason="Professional advice is greater than 0%, so E&O exposure should be reviewed.",
                triggered_by="operational_activities.professional_advice",
                priority="medium",
            ))
        if has_physical_or_hardware:
            follow_ups.append(FollowUpQuestion(
                question_id="hardware-risk",
                prompt="Does the business install, configure, maintain, or physically handle hardware at client locations?",
                reason="Hardware resale or physical work may trigger GL or job-site review.",
                triggered_by="operational_activities.hardware_resale",
                priority="medium",
            ))
        if website_context.website_url or website_context.pasted_website_text.strip():
            follow_ups.append(FollowUpQuestion(
                question_id="website-consistency",
                prompt="Does the website describe services, industries, guarantees, platforms, or security claims that are not reflected in the application answers?",
                reason="Underwriters often review public websites, so website language should be consistent with the application.",
                triggered_by="website_context",
                priority="high",
            ))
        return follow_ups

    def _suggested_answers(
        self,
        profile: BusinessProfile,
        intake_answers: list[IntakeAnswer],
        activities: list[OperationalActivity],
        website_context: WebsiteContext,
        questions: list[ApplicationQuestion],
        risk_flags: list[RiskFlag],
    ) -> list[SuggestedAnswer]:
        intake_map = {answer.question_id: answer.answer for answer in intake_answers}
        activity_mix = "; ".join(f"{activity.activity}: {activity.percentage}%" for activity in activities)
        total = sum(activity.percentage for activity in activities)
        risk_by_field = {flag.source_field: flag for flag in risk_flags}
        answers: list[SuggestedAnswer] = []
        for question in questions:
            suggested = ""
            pulled_from = "intake answer"
            source_field = "guided_intake"
            confidence = "Medium"
            explanation = "Suggested from the guided intake. Human review should confirm before submission."
            human_review = True
            risk_flag = None

            if question.question_id == "applicant-name":
                suggested = profile.business_name or "Northbridge Digital Solutions"
                source_field = "business_profile.business_name"
                confidence = "High" if profile.business_name else "Medium"
                explanation = "Maps the plain-English applicant name to the applicant information section."
                human_review = False
            elif question.question_id == "website-url":
                suggested = website_context.website_url or "Website not provided."
                pulled_from = "website context"
                source_field = "website_context.website_url"
                confidence = "High" if website_context.website_url else "Low"
                explanation = "Captures the public website because underwriters may review it to understand the business."
                risk_flag = None if website_context.website_url else "Ask for website URL or note that no public website was provided."
            elif question.question_id == "business-operations":
                if website_context.pasted_website_text.strip():
                    suggested = f"{intake_map.get('business-description', profile.services_provided)} Website context: {website_context.pasted_website_text[:420]}"
                    pulled_from = "intake answer + pasted website context"
                    source_field = "intake.business-description; website_context.pasted_website_text"
                    confidence = "Medium"
                    explanation = "Combines the user's plain-English description with pasted website text so the reviewer can compare the application to the public-facing business description."
                else:
                    suggested = intake_map.get("business-description", profile.services_provided)
                    source_field = "intake.business-description"
                    confidence = "Medium"
                    explanation = "Uses the user's plain-English description instead of asking them to interpret insurance wording."
            elif question.question_id == "gross-revenue":
                suggested = f"${profile.revenue:,.0f}" if profile.revenue else intake_map.get("revenue", "Revenue not provided.")
                source_field = "business_profile.revenue"
                confidence = "High" if profile.revenue else "Low"
                explanation = "Maps annual or projected revenue to the revenue question."
                risk_flag = "Missing or estimated revenue should be confirmed."
            elif question.question_id in {"professional-services-percent", "technology-revenue-mix"}:
                suggested = activity_mix
                pulled_from = "operational percentage"
                source_field = "operational_activities"
                confidence = "High" if total == 100 else "Low"
                explanation = "Maps the activity mix to form sections asking for services and percentage of revenue."
                risk_flag = None if total == 100 else "Activity percentages must equal 100%."
            elif question.question_id == "records-protected-information":
                suggested = "Customer records/data exposure indicated; exact number of protected records needs confirmation." if profile.stores_customer_data else "No stored customer data indicated in intake."
                source_field = "business_profile.stores_customer_data"
                confidence = "Low" if profile.stores_customer_data else "Medium"
                explanation = "The sample questionnaire asks about sensitive customer records. Intake can flag relevance but cannot safely infer the count."
                risk_flag = risk_by_field.get("data-access").reason if "data-access" in risk_by_field else None
            elif question.question_id == "internet-hosting-access":
                suggested = "Follow-up needed on hosting, client system access, online services, and payment/data processing." if profile.stores_customer_data else "Not indicated from intake; confirm if any hosting, portal, online database, payment, or client system access exists."
                source_field = "intake.data-access"
                confidence = "Low"
                explanation = "Technology applications ask detailed online service questions; plain-English intake triggers targeted follow-up instead of silent autofill."
                risk_flag = "Human review recommended for cyber/privacy and system access."
            elif question.question_id == "client-contracts":
                suggested = "Client contracts appear to require insurance or special wording." if profile.contracts_require_insurance_coverage else "No client contract insurance requirements indicated."
                source_field = "business_profile.contracts_require_insurance_coverage"
                confidence = "Medium"
                explanation = "Maps the intake contract answer to the application contract section."
                risk_flag = "Upload contract section for licensed review." if profile.contracts_require_insurance_coverage else None
            elif question.question_id == "subcontractors":
                suggested = "Yes, subcontractors used; percentage and controls need confirmation." if profile.uses_subcontractors else "No subcontractor use indicated."
                source_field = "business_profile.uses_subcontractors"
                confidence = "Medium"
                explanation = "Maps contractor intake to the sample questionnaire's contractor question."
                risk_flag = "Confirm subcontractor contracts and insurance requirements." if profile.uses_subcontractors else None
            elif question.question_id == "subcontractor-percentage":
                if profile.uses_subcontractors and profile.subcontractor_percentage is not None:
                    suggested = f"Approximately {profile.subcontractor_percentage}%."
                    confidence = "Medium"
                    risk_flag = "Reviewer should confirm whether this is percentage of work, revenue, or professional services."
                elif profile.uses_subcontractors:
                    suggested = "Subcontractor percentage not confirmed."
                    confidence = "Low"
                    risk_flag = "Ask the applicant to estimate subcontractor percentage before carrier submission."
                else:
                    suggested = "Not applicable; no subcontractor use indicated."
                    confidence = "High"
                source_field = "business_profile.subcontractor_percentage"
                explanation = "Many professional liability applications ask how much work is performed by independent contractors or subcontractors."
            elif question.question_id == "subcontractor-cois":
                suggested = "Yes, subcontractor COIs are collected." if profile.collects_subcontractor_cois else "No or not confirmed; ask whether subcontractor COIs are collected."
                source_field = "business_profile.collects_subcontractor_cois"
                confidence = "Medium" if profile.collects_subcontractor_cois else "Low"
                explanation = "COI collection helps show whether subcontractors maintain their own insurance and supports risk-transfer review."
                risk_flag = None if profile.collects_subcontractor_cois else "Human review recommended because subcontractor insurance collection is not confirmed."
            elif question.question_id == "prior-claims":
                suggested = intake_map.get("prior-claims", "No prior claims indicated.")
                source_field = "intake.prior-claims"
                confidence = "Medium"
                explanation = "Maps plain-English loss history response to prior claims questions."

            answers.append(SuggestedAnswer(
                application_question_id=question.question_id,
                original_application_question=question.original_question,
                suggested_answer=suggested,
                confidence_level=confidence,
                pulled_from=pulled_from,
                source_text_or_field=source_field,
                plain_english_explanation=explanation,
                risk_flag=risk_flag,
                human_review_needed=human_review or confidence != "High" or bool(risk_flag),
                citations=[
                    Citation(source_type=pulled_from, source_label=source_field, source_text=suggested)
                ],
            ))
        return answers

    def _suggestion_audit_log(
        self,
        intake_answers: list[IntakeAnswer],
        suggested_answers: list[SuggestedAnswer],
    ) -> list[AuditLog]:
        now = datetime.now(timezone.utc).isoformat()
        user_input = " | ".join(f"{answer.question_id}: {answer.answer}" for answer in intake_answers)
        return [
            AuditLog(
                timestamp=now,
                user_input=user_input,
                application_question=answer.original_application_question,
                suggested_answer=answer.suggested_answer,
                source_used=answer.source_text_or_field,
                confidence_level=answer.confidence_level,
            )
            for answer in suggested_answers
        ]

    def _skipped_sections(self, activities: list[OperationalActivity]) -> list[str]:
        categories = {activity.category for activity in activities if activity.percentage > 0}
        skipped: list[str] = []
        if "hardware_resale" not in categories:
            skipped.append("Hardware resale details appear irrelevant based on the current activity mix.")
        if "software_development" not in categories:
            skipped.append("Custom software development details appear irrelevant based on the current activity mix.")
        if "training" not in categories:
            skipped.append("Training-only details appear irrelevant based on the current activity mix.")
        return skipped

    def _build_question_guidance(self, answers: list[ApplicationAnswer]) -> list[QuestionGuidance]:
        if not answers:
            answers = [
                ApplicationAnswer(
                    question_id="technology-services",
                    question="What technology or professional services does the business provide?",
                ),
                ApplicationAnswer(
                    question_id="revenue-breakdown",
                    question="How is annual revenue split across consulting, software, managed services, implementation, or support?",
                ),
                ApplicationAnswer(
                    question_id="customer-data",
                    question="Does the business store, process, host, or access customer data or production systems?",
                ),
                ApplicationAnswer(
                    question_id="contracts-eo",
                    question="Do client contracts require Tech E&O, cyber, professional liability, specific limits, or special wording?",
                ),
                ApplicationAnswer(
                    question_id="loss-history",
                    question="Has the business had prior technology, cyber, privacy, service failure, or professional liability claims?",
                ),
            ]

        return [self._guidance_for_answer(answer) for answer in answers]

    def _guidance_for_answer(self, answer: ApplicationAnswer) -> QuestionGuidance:
        lowered = answer.question.lower()
        if "loss" in lowered or "claim" in lowered:
            return QuestionGuidance(
                question_id=answer.question_id,
                question=answer.question,
                what_it_means="The insurer is asking whether prior technology, cyber, privacy, or professional service issues may affect review.",
                why_insurer_asks="Loss history may indicate service, security, contractual, or operational patterns that need human review.",
                information_needed=["Prior loss runs", "Claim dates", "Claim amounts", "Allegations or incident type", "Current status"],
                human_review_recommended=not bool(answer.answer.strip()),
            )
        if "revenue" in lowered:
            return QuestionGuidance(
                question_id=answer.question_id,
                question=answer.question,
                what_it_means="The insurer is asking how the business earns money across different technology services.",
                why_insurer_asks="Revenue mix may indicate different professional, technology, cyber, implementation, or support exposures.",
                information_needed=["Annual revenue", "Revenue by service line", "Largest client percentage", "Projected revenue if new"],
                human_review_recommended=not bool(answer.answer.strip()),
            )
        if "contract" in lowered or "endorsement" in lowered:
            return QuestionGuidance(
                question_id=answer.question_id,
                question=answer.question,
                what_it_means="The application is asking whether client agreements appear to require Tech E&O, cyber, professional liability, limits, or special wording.",
                why_insurer_asks="Contract requirements may affect underwriting review, policy wording, certificates, and escalation routing.",
                information_needed=["Client contract insurance section", "Required limits", "Required wording", "Indemnity or service-level requirements"],
                human_review_recommended=True,
            )
        if "data" in lowered or "technology" in lowered or "professional" in lowered:
            return QuestionGuidance(
                question_id=answer.question_id,
                question=answer.question,
                what_it_means="The insurer is checking whether the business performs services that may create technology, professional, cyber, privacy, or service-failure exposure.",
                why_insurer_asks="These activities may indicate underwriting questions that need specialized review.",
                information_needed=["Service description", "Systems accessed", "Data stored or processed", "Client contract requirements", "Security controls"],
                human_review_recommended=True,
            )
        return QuestionGuidance(
            question_id=answer.question_id,
            question=answer.question,
            what_it_means="The question helps clarify the business operations for application review.",
            why_insurer_asks="Insurers use this information to route, review, and validate the submission.",
            information_needed=["Accurate business details", "Supporting documents if available"],
            human_review_recommended=answer.required and not bool(answer.answer.strip()),
        )

    def _detect_missing_information(
        self,
        profile: BusinessProfile,
        answers: list[ApplicationAnswer],
    ) -> list[InformationFlag]:
        flags: list[InformationFlag] = []
        for field_name, label in PROFILE_REQUIRED_FIELDS.items():
            value = getattr(profile, field_name)
            if value is None or value == "":
                flags.append(
                    self._flag(
                        "missing_field",
                        field_name,
                        f"{label} is needed before the application appears ready for review.",
                        0.95,
                        f"Add {label.lower()} or mark it for human follow-up.",
                    )
                )

        for answer in answers:
            if answer.required and not answer.answer.strip():
                flags.append(
                    self._flag(
                        "incomplete_answer",
                        f"application_answers.{answer.question_id}",
                        "A required application question has not been answered.",
                        0.9,
                        "Complete the answer or mark it for reviewer follow-up.",
                    )
                )

        if profile.payroll is not None and profile.payroll > 0 and not profile.number_of_employees:
            flags.append(
                self._flag(
                    "inconsistent_answer",
                    "number_of_employees",
                    "Payroll is present, but employee count is missing or zero.",
                    0.82,
                    "Confirm employee count before submission.",
                )
            )

        if profile.revenue is not None and profile.revenue <= 0:
            flags.append(
                self._flag(
                    "unclear_answer",
                    "revenue",
                    "Revenue appears incomplete or unclear.",
                    0.78,
                    "Confirm annual revenue amount with the applicant.",
                )
            )

        return flags

    def _detect_risk_flags(
        self,
        profile: BusinessProfile,
        answers: list[ApplicationAnswer],
    ) -> list[InformationFlag]:
        flags: list[InformationFlag] = []
        if profile.provides_professional_or_technology_services:
            flags.append(
                self._flag(
                    "risk_indicator",
                    "provides_professional_or_technology_services",
                    "Technology or professional services are central to Tech E&O review and may require more detailed underwriting context.",
                    0.86,
                    "Human review recommended with a licensed insurance professional.",
                )
            )
        if profile.stores_customer_data:
            flags.append(
                self._flag(
                    "risk_indicator",
                    "stores_customer_data",
                    "Stored customer data may indicate privacy, cyber, or technology exposure.",
                    0.88,
                    "Confirm data handling details with a licensed professional.",
                )
            )
        if profile.uses_subcontractors:
            flags.append(
                self._flag(
                    "risk_indicator",
                    "uses_subcontractors",
                    "Subcontractor use may indicate service delivery, contract, certificate, or risk-transfer review needs.",
                    0.84,
                    "Collect subcontractor COIs and review contract requirements.",
                )
            )
        if profile.contracts_require_insurance_coverage:
            flags.append(
                self._flag(
                    "risk_indicator",
                    "contracts_require_insurance_coverage",
                    "Client contracts appear to require Tech E&O, cyber, professional liability, limits, or special wording.",
                    0.87,
                    "Review contract requirements with a licensed insurance professional.",
                )
            )

        for answer in answers:
            lowered = f"{answer.question} {answer.answer}".lower()
            if "prior loss" in lowered or "claim" in lowered:
                flags.append(
                    self._flag(
                        "risk_indicator",
                        f"application_answers.{answer.question_id}",
                        "Prior loss or claim language may indicate underwriting follow-up.",
                        0.8,
                        "Upload prior loss history or request loss runs.",
                    )
                )

        return flags

    def _build_recommendations(
        self,
        profile: BusinessProfile,
        missing_information: list[InformationFlag],
        risk_flags: list[InformationFlag],
    ) -> list[Recommendation]:
        recommendations = [
            Recommendation(
                    recommendation="Confirm annual revenue breakdown by technology service line.",
                source_field="revenue",
                reason="Tech E&O review often depends on how revenue is split across consulting, software, managed services, implementation, support, or other services.",
                confidence_score=0.82,
                suggested_next_action="Ask the applicant to confirm annual revenue by service line if available.",
            )
        ]

        if missing_information:
            recommendations.append(
                Recommendation(
                    recommendation="Complete missing application fields before submission.",
                    source_field="missing_information",
                    reason="The application has missing or incomplete inputs.",
                    confidence_score=0.93,
                    suggested_next_action="Resolve the missing fields or route them to a reviewer.",
                )
            )

        if profile.contracts_require_insurance_coverage:
            recommendations.append(
                Recommendation(
                    recommendation="Review client contract requirement with a licensed insurance professional.",
                    source_field="contracts_require_insurance_coverage",
                    reason="The business indicated contracts appear to require Tech E&O, cyber, professional liability, limits, or special wording.",
                    confidence_score=0.88,
                    suggested_next_action="Upload the client contract insurance section for review.",
                )
            )

        if profile.stores_customer_data:
            recommendations.append(
                Recommendation(
                    recommendation="Human review recommended because the business stores customer data.",
                    source_field="stores_customer_data",
                    reason="Stored customer data may indicate privacy, cyber, or professional exposure.",
                    confidence_score=0.9,
                    suggested_next_action="Confirm what customer data is stored and how it is protected.",
                )
            )

        if any("loss" in flag.reason.lower() or "claim" in flag.reason.lower() for flag in risk_flags):
            recommendations.append(
                Recommendation(
                    recommendation="Upload prior loss history.",
                    source_field="application_answers",
                    reason="Prior claim language appears in the application responses.",
                    confidence_score=0.83,
                    suggested_next_action="Attach loss runs or ask the applicant to confirm claim details.",
                )
            )

        return recommendations

    def _score(
        self,
        profile: BusinessProfile,
        answers: list[ApplicationAnswer],
        missing_information: list[InformationFlag],
        risk_flags: list[InformationFlag],
    ) -> ReadinessScore:
        required_total = len(PROFILE_REQUIRED_FIELDS) + len([answer for answer in answers if answer.required])
        missing_count = len([flag for flag in missing_information if flag.flag_type in {"missing_field", "incomplete_answer"}])
        complete_count = max(required_total - missing_count, 0)
        completion_percentage = round((complete_count / required_total) * 100) if required_total else 100

        risk_points = len(risk_flags) + len([flag for flag in missing_information if flag.flag_type in {"inconsistent_answer", "unclear_answer"}])
        if risk_points >= 3:
            risk_level = "High"
        elif risk_points >= 1:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        confidence_score = max(0.35, min(0.97, (completion_percentage / 100) - (risk_points * 0.07)))
        human_review_required = risk_level in {"Medium", "High"} or bool(missing_information)

        return ReadinessScore(
            completion_percentage=completion_percentage,
            confidence_score=round(confidence_score, 2),
            risk_level=risk_level,
            human_review_required=human_review_required,
        )

    def _build_review_actions(self, recommendations: list[Recommendation]) -> list[ReviewAction]:
        actions: list[ReviewAction] = []
        for index, recommendation in enumerate(recommendations, start=1):
            actions.extend(
                [
                    ReviewAction(action_id=f"rec-{index}-approve", label=f"Approve: {recommendation.recommendation}"),
                    ReviewAction(action_id=f"rec-{index}-edit", label=f"Edit: {recommendation.recommendation}"),
                    ReviewAction(action_id=f"rec-{index}-reviewed", label=f"Mark reviewed: {recommendation.recommendation}"),
                    ReviewAction(action_id=f"rec-{index}-escalate", label=f"Escalate: {recommendation.recommendation}"),
                ]
            )
        return actions

    def _build_audit_trail(
        self,
        payload: ApplicationSupportRequest,
        missing_information: list[InformationFlag],
        risk_flags: list[InformationFlag],
        recommendations: list[Recommendation],
        readiness_score: ReadinessScore,
    ) -> list[AuditEntry]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            AuditEntry(
                event_type="user_inputs_received",
                detail={
                    "account_role": payload.account_role,
                    "business_profile": payload.business_profile.model_dump(),
                    "application_answers": [answer.model_dump() for answer in payload.application_answers],
                },
                timestamp=now,
            ),
            AuditEntry(
                event_type="decision_support_generated",
                detail={
                    "missing_information_count": len(missing_information),
                    "risk_flags_count": len(risk_flags),
                    "recommendations_count": len(recommendations),
                    "readiness_score": readiness_score.model_dump(),
                },
                timestamp=now,
            ),
        ]

    def _build_report(
        self,
        profile: BusinessProfile,
        missing_information: list[InformationFlag],
        risk_flags: list[InformationFlag],
        recommendations: list[Recommendation],
        readiness_score: ReadinessScore,
        audit_trail: list[AuditEntry],
    ) -> SubmissionReadinessReport:
        summary_parts = [
            profile.business_name or "Unnamed business",
            profile.industry or "industry not provided",
            profile.services_provided or "services not provided",
        ]
        human_review_items = [
            recommendation
            for recommendation in recommendations
            if "human review" in recommendation.recommendation.lower()
            or "licensed insurance professional" in recommendation.suggested_next_action.lower()
        ]
        return SubmissionReadinessReport(
            business_profile_summary=" | ".join(summary_parts),
            missing_information=missing_information,
            risk_flags=risk_flags,
            recommendations=recommendations,
            readiness_score=readiness_score,
            human_review_items=human_review_items,
            audit_trail_summary=[
                f"{entry.timestamp}: {entry.event_type}"
                for entry in audit_trail
            ],
        )

    def _flag(
        self,
        flag_type: str,
        source_field: str,
        reason: str,
        confidence_score: float,
        suggested_next_action: str,
    ) -> InformationFlag:
        return InformationFlag(
            flag_type=flag_type,
            source_field=source_field,
            reason=reason,
            confidence_score=confidence_score,
            suggested_next_action=suggested_next_action,
        )
