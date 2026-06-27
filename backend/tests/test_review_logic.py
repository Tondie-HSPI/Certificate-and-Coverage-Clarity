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

