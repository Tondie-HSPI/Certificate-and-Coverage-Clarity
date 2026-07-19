from typing import Any

from pydantic import BaseModel, Field


class UploadDescriptor(BaseModel):
    document_id: str
    document_type: str
    file_name: str | None = None
    content: str | None = None
    binary_payload: bytes | None = None


class IntakeRequest(BaseModel):
    account_role: str = Field(..., description="contractor, broker, reviewer, or admin")
    documents: list[UploadDescriptor]
    requirements_document_id: str | None = Field(
        default=None,
        description="User-selected document containing the certificate requester's requirements",
    )


class SourceOfTruth(BaseModel):
    authority: str = "Certificate requester"
    basis: str = "Requirements provided by the certificate requester"
    document_id: str | None = None
    document_name: str | None = None
    selection_status: str


class ParsedDocument(BaseModel):
    document_id: str
    document_type: str
    file_name: str | None = None
    markdown: str
    structured_json: dict[str, Any]
    extracted_sections: list[str]
    description_box_lines: list[str] = []
    certificate_holder_text: str | None = None
    matched_keywords: list[str] = []
    failed_matches: list[str] = []


class Obligation(BaseModel):
    obligation_type: str
    document_type: str
    requirement: str
    source: str
    search_terms: list[str]
    confidence: float
    raw_status: str
    dependency: str | None = None
    source_excerpt: str = ""


class ValidationResult(BaseModel):
    obligation_type: str
    matched_evidence: list[str]
    missing_fields: list[str]
    comparison_notes: list[str]


class DecisionItem(BaseModel):
    obligation_type: str
    requirement: str
    evidence_requirement: str | None = None
    state: str
    search_terms: list[str]
    source: str
    evidence_source: str | None = None
    source_excerpt: str
    explanation: str
    next_action: str


class EmailDraft(BaseModel):
    recipient: str = ""
    subject: str
    body: str
    requested_items: list[str]
    requires_human_review: bool = True


class AnalysisResponse(BaseModel):
    workflow_id: str
    overall_confidence: float
    analysis_mode: str
    items: list[DecisionItem]
    parsed_documents: list[ParsedDocument]
    validations: list[ValidationResult]
    email_draft: EmailDraft | None = None
    source_of_truth: SourceOfTruth


class AnalysisJob(BaseModel):
    job_id: str
    account_role: str
    documents: list[UploadDescriptor]
    status: str


class JobEnqueueResponse(BaseModel):
    job_id: str
    status: str


class BusinessProfile(BaseModel):
    business_name: str = ""
    industry: str = ""
    services_provided: str = ""
    revenue: float | None = None
    payroll: float | None = None
    number_of_employees: int | None = None
    customers_served: str = ""
    provides_professional_or_technology_services: bool = False
    stores_customer_data: bool = False
    uses_subcontractors: bool = False
    subcontractor_percentage: float | None = None
    collects_subcontractor_cois: bool = False
    contracts_require_insurance_coverage: bool = False


class SourceDocument(BaseModel):
    document_id: str
    document_name: str
    document_type: str
    source_note: str = ""


class IntakeQuestion(BaseModel):
    question_id: str
    prompt: str
    purpose: str
    trigger: str = "base_intake"


class IntakeAnswer(BaseModel):
    question_id: str
    answer: str
    source: str = "user_input"


class OperationalActivity(BaseModel):
    activity: str
    percentage: int
    category: str = "technology_services"


class WebsiteContext(BaseModel):
    website_url: str = ""
    pasted_website_text: str = ""
    review_note: str = ""


class Citation(BaseModel):
    source_type: str
    source_label: str
    source_text: str


class RiskFlag(BaseModel):
    flag_id: str
    severity: str
    source_field: str
    reason: str
    suggested_next_action: str


class FollowUpQuestion(BaseModel):
    question_id: str
    prompt: str
    reason: str
    triggered_by: str
    priority: str = "medium"
    answer: str = ""


class ApplicationQuestion(BaseModel):
    question_id: str
    section: str
    original_question: str
    carrier_form: str = "Tech E&O / Professional Liability Application"


class SuggestedAnswer(BaseModel):
    application_question_id: str
    original_application_question: str
    suggested_answer: str
    confidence_level: str
    pulled_from: str
    source_text_or_field: str
    plain_english_explanation: str
    risk_flag: str | None = None
    human_review_needed: bool
    final_answer: str | None = None
    review_action: str = "pending_review"
    citations: list[Citation] = []


class AuditLog(BaseModel):
    timestamp: str
    user_input: str
    application_question: str
    suggested_answer: str
    source_used: str
    confidence_level: str
    user_action: str = "pending_review"
    final_answer_submitted: str | None = None


class ApplicationAnswer(BaseModel):
    question_id: str
    question: str
    answer: str = ""
    required: bool = True


class ApplicationSupportRequest(BaseModel):
    account_role: str = Field(..., description="applicant, agent, csr, account_manager, reviewer, or admin")
    business_profile: BusinessProfile
    application_answers: list[ApplicationAnswer] = []
    source_documents: list[SourceDocument] = []
    intake_answers: list[IntakeAnswer] = []
    operational_activities: list[OperationalActivity] = []
    website_context: WebsiteContext | None = None


class QuestionGuidance(BaseModel):
    question_id: str
    question: str
    what_it_means: str
    why_insurer_asks: str
    information_needed: list[str]
    human_review_recommended: bool


class InformationFlag(BaseModel):
    flag_type: str
    source_field: str
    reason: str
    confidence_score: float
    suggested_next_action: str


class ReadinessScore(BaseModel):
    completion_percentage: int
    confidence_score: float
    risk_level: str
    human_review_required: bool


class Recommendation(BaseModel):
    recommendation: str
    source_field: str
    reason: str
    confidence_score: float
    suggested_next_action: str


class AuditEntry(BaseModel):
    event_type: str
    detail: dict[str, Any]
    timestamp: str


class ReviewAction(BaseModel):
    action_id: str
    label: str
    status: str = "pending"


class SubmissionReadinessReport(BaseModel):
    business_profile_summary: str
    missing_information: list[InformationFlag]
    risk_flags: list[InformationFlag]
    recommendations: list[Recommendation]
    readiness_score: ReadinessScore
    human_review_items: list[Recommendation]
    audit_trail_summary: list[str]


class ApplicationSupportResponse(BaseModel):
    workflow_id: str
    source_documents: list[SourceDocument] = []
    intake_questions: list[IntakeQuestion] = []
    intake_answers: list[IntakeAnswer] = []
    operational_activities: list[OperationalActivity] = []
    website_context: WebsiteContext | None = None
    application_questions: list[ApplicationQuestion] = []
    suggested_answers: list[SuggestedAnswer] = []
    citations: list[Citation] = []
    risk_flags: list[RiskFlag] = []
    follow_up_questions: list[FollowUpQuestion] = []
    audit_log: list[AuditLog] = []
    skipped_sections: list[str] = []
    guidance: list[QuestionGuidance]
    missing_information: list[InformationFlag]
    readiness_score: ReadinessScore
    recommendations: list[Recommendation]
    audit_trail: list[AuditEntry]
    review_actions: list[ReviewAction]
    report: SubmissionReadinessReport
