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
    assert result.overall_confidence >= 0.9


def test_confidence_uses_detected_requirements_not_unmatched_rule_placeholders():
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
                        "Commercial General Liability insurance with limits of $1,000,000 "
                        "each occurrence and $2,000,000 aggregate is required.\n"
                        "Waiver of subrogation is required."
                    ),
                ),
                UploadDescriptor(
                    document_id="certificate",
                    document_type="coi",
                    file_name="certificate.txt",
                    content=(
                        "Commercial General Liability coverage with limits of $1,000,000 "
                        "each occurrence and $2,000,000 aggregate."
                    ),
                ),
            ],
        )
    )

    assert 0.8 <= result.overall_confidence <= 0.95


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


def test_public_sample_pdfs_extract_and_compare_end_to_end():
    from pathlib import Path

    from app.schemas.analysis import IntakeRequest, UploadDescriptor
    from app.services.analysis_service import AnalysisService

    samples = Path(__file__).resolve().parents[2] / "public" / "samples"
    requirements_name = "requester-requirements-sample.pdf"
    certificate_name = "certificate-sample.pdf"
    result = AnalysisService().run(
        IntakeRequest(
            account_role="reviewer",
            requirements_document_id=f"0-{requirements_name}",
            documents=[
                UploadDescriptor(
                    document_id=f"0-{requirements_name}",
                    document_type="contract",
                    file_name=requirements_name,
                    binary_payload=(samples / requirements_name).read_bytes(),
                ),
                UploadDescriptor(
                    document_id=f"1-{certificate_name}",
                    document_type="coi",
                    file_name=certificate_name,
                    binary_payload=(samples / certificate_name).read_bytes(),
                ),
            ],
        )
    )

    states = {item.obligation_type: item.state for item in result.items}
    assert result.overall_confidence >= 0.9
    assert {document.extraction_method for document in result.parsed_documents} == {"embedded_pdf_text"}
    assert states["General Liability"] == "met"
    assert states["Additional Insured"] == "met"
    assert states["Waiver of Subrogation"] == "missing"
    assert states["Umbrella / Excess"] == "met"
    assert result.email_draft is not None
    assert "Waiver of Subrogation" in result.email_draft.body


def test_confidence_measures_reading_quality_not_alignment():
    from app.schemas.analysis import IntakeRequest, UploadDescriptor
    from app.services.analysis_service import AnalysisService

    service = AnalysisService()
    requirements = UploadDescriptor(
        document_id="requirements",
        document_type="contract",
        file_name="requirements.txt",
        content="Commercial General Liability insurance of $1,000,000 each occurrence is required.",
    )
    matching = service.run(IntakeRequest(
        account_role="reviewer",
        requirements_document_id="requirements",
        documents=[
            requirements,
            UploadDescriptor(
                document_id="matching",
                document_type="coi",
                file_name="matching.txt",
                content="Commercial General Liability insurance of $1,000,000 each occurrence is shown.",
            ),
        ],
    ))
    missing = service.run(IntakeRequest(
        account_role="reviewer",
        requirements_document_id="requirements",
        documents=[
            requirements,
            UploadDescriptor(
                document_id="missing",
                document_type="coi",
                file_name="missing.txt",
                content="This readable certificate contains no matching general liability evidence.",
            ),
        ],
    ))

    assert matching.overall_confidence == missing.overall_confidence
    assert matching.overall_confidence >= 0.9


def test_failed_pdf_extraction_never_returns_raw_pdf_bytes(monkeypatch):
    from app.extraction_layer.insurance_parser import DocumentExtractionError, InsuranceDocumentParser
    from app.extraction_layer.textract_client import TextractExtractionError

    parser = InsuranceDocumentParser()
    monkeypatch.setattr(parser, "_extract_embedded_pdf_text", lambda _: ("", 1))
    monkeypatch.setattr(
        parser.textract,
        "analyze_pdf",
        lambda *_: (_ for _ in ()).throw(TextractExtractionError("test failure")),
    )

    try:
        parser._parse_pdf_bytes(b"%PDF-1.4 invalid", "document", "document.pdf", "coi")
        assert False, "Unreadable PDFs must not silently fall back to raw bytes"
    except DocumentExtractionError as exc:
        assert "could not be read reliably" in str(exc)


def test_textract_table_rows_preserve_labels_and_values():
    from app.extraction_layer.textract_client import TextractClient

    def word(block_id: str, text: str) -> dict:
        return {"Id": block_id, "BlockType": "WORD", "Text": text}

    def cell(block_id: str, row: int, column: int, child_ids: list[str]) -> dict:
        return {
            "Id": block_id,
            "BlockType": "CELL",
            "RowIndex": row,
            "ColumnIndex": column,
            "Relationships": [{"Type": "CHILD", "Ids": child_ids}],
        }

    blocks = [
        {
            "Id": "table",
            "BlockType": "TABLE",
            "Page": 1,
            "Relationships": [{"Type": "CHILD", "Ids": ["c1", "c2", "c3", "c4"]}],
        },
        cell("c1", 1, 1, ["w1", "w2"]),
        cell("c2", 1, 2, ["w3", "w4", "w5"]),
        cell("c3", 2, 1, ["w6", "w7"]),
        cell("c4", 2, 2, ["w8", "w9", "w10"]),
        word("w1", "Certificate"),
        word("w2", "holder"),
        word("w3", "Northbridge"),
        word("w4", "Development"),
        word("w5", "LLC"),
        word("w6", "General"),
        word("w7", "Liability"),
        word("w8", "$1,000,000"),
        word("w9", "each"),
        word("w10", "occurrence"),
    ]

    assert TextractClient()._extract_table_rows(blocks) == [
        "Certificate holder: Northbridge Development LLC",
        "General Liability | $1,000,000 each occurrence",
    ]


def test_textract_normalized_rows_compare_image_only_documents(monkeypatch):
    from app.extraction_layer.textract_client import TextractResult
    from app.schemas.analysis import IntakeRequest, UploadDescriptor
    from app.services.analysis_service import AnalysisService

    requirements_text = """Certificate holder: Northbridge Development LLC
Address: 100 Main Street, Rochester, NY 14604
Requester-required wording: None
Requirement | Requested evidence
Commercial General Liability | $1,000,000 each occurrence and $2,000,000 general aggregate. Coverage must apply on an occurrence basis.
Additional Insured | Northbridge Development LLC must be included as an additional insured by endorsement.
Waiver of Subrogation | A waiver of subrogation in favor of Northbridge Development LLC is required where permitted by law.
Umbrella or Excess Liability | A limit of not less than $5,000,000 is required."""
    certificate_text = """Coverage | Policy number | Limits shown
Commercial General Liability | CGL-2026-1042 | $1,000,000 each occurrence $2,000,000 general aggregate
Umbrella Liability | UMB-2026-1042 | $5,000,000 each occurrence $5,000,000 aggregate
Northbridge Development LLC is shown as an additional insured for ongoing operations.
A separate waiver of subrogation endorsement is not shown in this sample.
Certificate holder
Northbridge Development LLC
100 Main Street
Rochester, NY 14604
Special wording: None"""

    service = AnalysisService()
    parser = service.extraction.parser
    monkeypatch.setattr(parser, "_extract_embedded_pdf_text", lambda _: ("", 1))

    def fake_textract(_payload: bytes, file_name: str) -> TextractResult:
        text = requirements_text if "requirements" in file_name else certificate_text
        return TextractResult(
            text=text,
            confidence=0.99,
            page_count=1,
            block_count=200,
            model_version="1.0",
            table_rows=text.splitlines()[:4],
        )

    monkeypatch.setattr(parser.textract, "analyze_pdf", fake_textract)

    result = service.run(
        IntakeRequest(
            account_role="reviewer",
            requirements_document_id="requirements",
            documents=[
                UploadDescriptor(
                    document_id="requirements",
                    document_type="contract",
                    file_name="requester-requirements-scanned.pdf",
                    binary_payload=b"image-only requirements PDF",
                ),
                UploadDescriptor(
                    document_id="certificate",
                    document_type="coi",
                    file_name="certificate-scanned.pdf",
                    binary_payload=b"image-only certificate PDF",
                ),
            ],
        )
    )

    states = {item.obligation_type: item.state for item in result.items}
    assert result.overall_confidence == 0.99
    assert {document.extraction_method for document in result.parsed_documents} == {"amazon_textract"}
    assert states["General Liability"] == "met"
    additional_insured = next(item for item in result.items if item.obligation_type == "Additional Insured")
    assert states["Additional Insured"] == "met", additional_insured.model_dump()
    assert states["Waiver of Subrogation"] == "missing"
    assert states["Umbrella / Excess"] == "met"
    assert states["Certificate Holder"] == "met"
    assert result.email_draft is not None
    assert result.email_draft.requested_items == [
        "Waiver of Subrogation: provide evidence meeting the contract requirement (Northbridge Development LLC | waiver wording)."
    ]
    assert "Certificate holder name: Northbridge Development LLC" in result.email_draft.body
    assert "Certificate holder address: 100 Main Street, Rochester, NY 14604" in result.email_draft.body
    assert "Wording required by requester: None" in result.email_draft.body

