from app.comparison_layer.comparator import ComparisonLayer
from app.schemas.analysis import Obligation
from app.services.coi_request_service import CoiRequestService


def obligation(obligation_type: str, document_type: str, requirement: str, raw_status: str = "detected") -> Obligation:
    return Obligation(
        obligation_type=obligation_type,
        document_type=document_type,
        requirement=requirement,
        source=f"{document_type}.txt",
        search_terms=[obligation_type.lower()],
        confidence=0.9,
        raw_status=raw_status,
        source_excerpt=requirement,
    )


def test_general_liability_limit_comparison_marks_supported_evidence_met():
    comparator = ComparisonLayer()
    items = comparator.compare([
        obligation("General Liability", "contract", "$1,000,000 each occurrence / $2,000,000 aggregate"),
        obligation("General Liability", "coi", "$1,000,000 each occurrence / $2,000,000 aggregate"),
    ])

    assert len(items) == 1
    assert items[0].state == "met"
    assert items[0].next_action == "No immediate action needed."


def test_missing_required_waiver_creates_missing_review_item_and_email_request():
    comparator = ComparisonLayer()
    items = comparator.compare([
        obligation("Waiver of Subrogation", "contract", "Waiver of Subrogation required where permitted by law"),
    ])

    assert items[0].state == "missing"
    assert "no matching COI or policy evidence" in items[0].explanation

    email = CoiRequestService().build_email_draft(items)
    assert email is not None
    assert email.requires_human_review is True
    assert "Waiver of Subrogation" in email.body
    assert "Please attach the requester's requirements" in email.body
    assert "Certificate holder name" in email.body
    assert "Certificate holder address" in email.body
    assert "Wording required by requester" in email.body
    assert "Not found - review required" in email.body
    assert "Please confirm that the certificate holder details" in email.body
    assert "identify any corrections" in email.body


def test_lower_evidence_limit_is_unmet():
    comparator = ComparisonLayer()
    items = comparator.compare([
        obligation("Umbrella / Excess", "contract", "$5,000,000 limit"),
        obligation("Umbrella / Excess", "policy", "$2,000,000 limit"),
    ])

    assert items[0].state == "unmet"
    assert items[0].next_action == "Escalate to reviewer and request corrected supporting evidence."

def test_governance_converts_ungrounded_met_state_to_needs_review():
    from app.governance.constraints import GovernanceLayer
    from app.schemas.analysis import DecisionItem

    item = DecisionItem(
        obligation_type="General Liability",
        requirement="$1,000,000 each occurrence",
        evidence_requirement="$1,000,000 each occurrence",
        state="met",
        search_terms=["general liability"],
        source="contract vs coi",
        evidence_source="coi.txt",
        source_excerpt="",
        explanation="Requirement is supported.",
        next_action="No immediate action needed.",
    )

    reviewed = GovernanceLayer().validate_outputs([item])[0]

    assert reviewed.state == "needs_review"
    assert "Source grounding" in reviewed.explanation
    assert "Human review required" in reviewed.next_action


def test_governance_sanitizes_overconfident_language():
    from app.governance.constraints import GovernanceLayer
    from app.schemas.analysis import DecisionItem

    item = DecisionItem(
        obligation_type="Additional Insured",
        requirement="AI required",
        evidence_requirement="AI wording shown",
        state="unmet",
        search_terms=["additional insured"],
        source="contract vs coi",
        evidence_source="coi.txt",
        source_excerpt="Contract: AI required",
        explanation="This certifies compliance.",
        next_action="Coverage confirmed.",
    )

    reviewed = GovernanceLayer().validate_outputs([item])[0]

    assert reviewed.explanation == "System explanation constrained by governance rules."
    assert reviewed.next_action.startswith("Escalate to reviewer")
    assert "Human review required" in reviewed.next_action


def test_source_of_truth_is_the_requesters_requirements_and_records_user_selection():
    from app.schemas.analysis import IntakeRequest, UploadDescriptor
    from app.services.analysis_service import AnalysisService

    payload = IntakeRequest(
        account_role="reviewer",
        requirements_document_id="requirements-1",
        documents=[
            UploadDescriptor(
                document_id="requirements-1",
                document_type="contract",
                file_name="requester-requirements.txt",
                content="General liability of $1,000,000 each occurrence is required.",
            ),
            UploadDescriptor(
                document_id="coi-1",
                document_type="coi",
                file_name="certificate.txt",
                content="General liability $1,000,000 each occurrence.",
            ),
        ],
    )

    result = AnalysisService().run(payload)

    assert result.source_of_truth.authority == "Certificate requester"
    assert result.source_of_truth.document_id == "requirements-1"
    assert result.source_of_truth.selection_status == "user_selected"


def test_multiple_requirement_documents_require_user_selection():
    from app.schemas.analysis import IntakeRequest, UploadDescriptor
    from app.services.analysis_service import AnalysisService

    payload = IntakeRequest(
        account_role="reviewer",
        documents=[
            UploadDescriptor(document_id="one", document_type="contract", file_name="contract.txt", content="Insurance required."),
            UploadDescriptor(document_id="two", document_type="contract", file_name="exhibit.txt", content="General liability required."),
            UploadDescriptor(document_id="coi", document_type="coi", file_name="coi.txt", content="General liability shown."),
        ],
    )

    result = AnalysisService().run(payload)

    assert result.analysis_mode == "source_selection_required"
    assert result.source_of_truth.selection_status == "selection_required"
    assert result.items == []


def test_supported_requirements_create_cautious_requester_email():
    items = ComparisonLayer().compare([
        obligation("General Liability", "contract", "$1,000,000 each occurrence"),
        obligation("General Liability", "coi", "$1,000,000 each occurrence"),
    ])

    email = CoiRequestService().build_email_draft(items)

    assert email is not None
    assert email.subject == "Insurance documents for your review"
    assert "appear to address" in email.body
    assert "does not confirm or certify coverage" in email.body


def test_request_details_are_extracted_and_inserted_into_agent_email():
    from app.schemas.analysis import ParsedDocument

    service = CoiRequestService()
    details = service.extract_request_details(
        [
            ParsedDocument(
                document_id="requirements",
                document_type="contract",
                file_name="requirements.txt",
                markdown=(
                    "Certificate holder name: Northbridge Holdings LLC\n"
                    "Certificate holder address: 100 Main Street, Rochester, NY 14604\n"
                    "Special wording: None\n"
                ),
                structured_json={},
                extracted_sections=[],
            )
        ],
        "requirements.txt",
    )
    items = ComparisonLayer().compare([
        obligation("Waiver of Subrogation", "contract", "Waiver required"),
    ])

    email = service.build_email_draft(items, **details)

    assert email is not None
    assert "Northbridge Holdings LLC" in email.body
    assert "100 Main Street, Rochester, NY 14604" in email.body
    assert "Wording required by requester: None" in email.body


def test_upload_service_rejects_unsupported_document_type():
    import asyncio
    from io import BytesIO

    from fastapi import HTTPException, UploadFile

    from app.services.upload_analysis_service import UploadAnalysisService

    upload = UploadFile(file=BytesIO(b"unsafe sample"), filename="sample.exe")

    try:
        asyncio.run(
            UploadAnalysisService().run_uploads(
                account_role="reviewer",
                files=[upload],
                document_types=["contract"],
            )
        )
        assert False, "Unsupported upload should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "PDF, DOCX, or TXT" in exc.detail


def test_upload_service_rejects_more_than_two_documents():
    import asyncio
    from io import BytesIO

    from fastapi import HTTPException, UploadFile

    from app.services.upload_analysis_service import UploadAnalysisService

    uploads = [
        UploadFile(file=BytesIO(b"sample"), filename=f"sample-{index}.txt")
        for index in range(3)
    ]

    try:
        asyncio.run(
            UploadAnalysisService().run_uploads(
                account_role="reviewer",
                files=uploads,
            )
        )
        assert False, "More than two uploads should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "Upload one or two documents."


def test_certificate_holder_name_label_is_not_treated_as_part_of_the_name():
    from app.schemas.analysis import IntakeRequest, UploadDescriptor
    from app.services.analysis_service import AnalysisService

    result = AnalysisService().run(
        IntakeRequest(
            account_role="reviewer",
            requirements_document_id="requirements",
            documents=[
                UploadDescriptor(
                    document_id="requirements",
                    document_type="contract",
                    file_name="requirements.txt",
                    content=(
                        "Certificate holder name: Northbridge Development LLC\n"
                        "Waiver of subrogation is required."
                    ),
                ),
                UploadDescriptor(
                    document_id="certificate",
                    document_type="coi",
                    file_name="certificate.txt",
                    content="CERTIFICATE HOLDER\nNorthbridge Development LLC",
                ),
            ],
        )
    )

    holder = next(item for item in result.items if item.obligation_type == "Certificate Holder")
    waiver = next(item for item in result.items if item.obligation_type == "Waiver of Subrogation")

    assert holder.requirement == "Northbridge Development LLC"
    assert holder.state == "met"
    assert waiver.state == "missing"

