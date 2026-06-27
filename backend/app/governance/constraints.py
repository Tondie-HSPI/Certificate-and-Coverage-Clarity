from dataclasses import dataclass

from app.rules.loader import load_governance_rules
from app.schemas.analysis import DecisionItem, UploadDescriptor


@dataclass
class GovernanceRefusal(Exception):
    reason: str
    detail: str


class GovernanceLayer:
    def __init__(self) -> None:
        self.rules = load_governance_rules()

    def apply(self, state: dict) -> dict:
        documents = state.get("documents", [])
        role = state.get("role", "")
        input_rules = self.rules["input_guardrails"]

        if role not in input_rules["allowed_roles"]:
            raise GovernanceRefusal(
                reason="invalid_role",
                detail=f"Role '{role}' is outside the supported compliance workflow."
            )

        if not documents:
            raise GovernanceRefusal(
                reason="insufficient_input",
                detail="At least one contract, COI, policy, or supporting document is required."
            )

        if len(documents) > input_rules["max_documents"]:
            raise GovernanceRefusal(
                reason="insufficient_input",
                detail=f"Upload no more than {input_rules['max_documents']} documents in a single review."
            )

        for document in documents:
            self._validate_document(document)

        state["constraints_applied"] = [
            "input_guardrails",
            "deterministic_rules",
            "source_grounding",
            "state_validation",
            "human_review_boundary",
        ]
        return state

    def validate_outputs(self, items: list[DecisionItem]) -> list[DecisionItem]:
        output_rules = self.rules["output_validation"]
        threshold_rules = self.rules.get("thresholds", {})
        required_fields = output_rules["required_decision_fields"]
        prohibited_phrases = [phrase.lower() for phrase in output_rules["prohibited_phrases"]]
        fallback_next_action = output_rules["fallback_next_action"]
        mandatory_review_note = output_rules["mandatory_review_note"]
        allowed_states = set(threshold_rules.get("allowed_decision_states", []))
        review_states = set(threshold_rules.get("require_human_review_states", []))
        require_grounding_for_met = threshold_rules.get("min_source_grounding_for_met_state", True)

        sanitized_items: list[DecisionItem] = []
        for item in items:
            data = item.model_dump()
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                raise GovernanceRefusal(
                    reason="output_validation_failed",
                    detail=f"Decision output is missing required fields: {', '.join(missing_fields)}."
                )

            state = item.state
            if allowed_states and state not in allowed_states:
                state = "needs_review"

            explanation = item.explanation
            next_action = item.next_action

            if require_grounding_for_met and state == "met" and not item.source_excerpt.strip():
                state = "needs_review"
                explanation = "Source grounding was not strong enough to treat this requirement as supported."
                next_action = fallback_next_action

            for phrase in prohibited_phrases:
                if phrase in explanation.lower():
                    explanation = "System explanation constrained by governance rules."
                if phrase in next_action.lower():
                    next_action = fallback_next_action

            if state in review_states and mandatory_review_note.lower() not in next_action.lower():
                next_action = f"{next_action} {mandatory_review_note}"

            sanitized_items.append(
                item.model_copy(
                    update={
                        "state": state,
                        "explanation": explanation,
                        "next_action": next_action,
                    }
                )
            )

        return sanitized_items

    def _validate_document(self, document: UploadDescriptor) -> None:
        input_rules = self.rules["input_guardrails"]
        if document.document_type not in input_rules["allowed_document_types"]:
            raise GovernanceRefusal(
                reason="unsupported_type",
                detail=f"Document type '{document.document_type}' is outside the supported intake types."
            )

        has_content = bool((document.content or "").strip() or document.binary_payload)
        if input_rules["require_document_content"] and not has_content:
            raise GovernanceRefusal(
                reason="insufficient_input",
                detail=f"Document '{document.file_name or document.document_id}' did not contain readable content."
            )

        lowered_content = (document.content or "").lower()

        for topic in input_rules["out_of_scope_topics"]:
            if topic in lowered_content:
                raise GovernanceRefusal(
                    reason="out_of_scope",
                    detail=f"Document '{document.file_name or document.document_id}' appears outside the compliance review scope."
                )

        for indicator in input_rules["injection_indicators"]:
            if indicator in lowered_content:
                raise GovernanceRefusal(
                    reason="injection_attempt",
                    detail=f"Document '{document.file_name or document.document_id}' contains instructions that look like prompt injection."
                )
