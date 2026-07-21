import re

from app.endorsement_layer.parser import EndorsementParser
from app.schemas.analysis import DecisionItem, Obligation


class ComparisonLayer:
    def __init__(self) -> None:
        self.endorsements = EndorsementParser()

    def compare(self, obligations: list[Obligation]) -> list[DecisionItem]:
        contract_map = {
            obligation.obligation_type: obligation
            for obligation in obligations
            if obligation.document_type == "contract"
        }
        evidence_map = {
            obligation.obligation_type: obligation
            for obligation in obligations
            if obligation.document_type != "contract" and obligation.raw_status != "missing"
        }

        items: list[DecisionItem] = []
        for obligation_type, contract_obligation in contract_map.items():
            if contract_obligation.raw_status == "missing":
                continue

            evidence_obligation = evidence_map.get(obligation_type)
            if evidence_obligation is None:
                items.append(
                    DecisionItem(
                        obligation_type=obligation_type,
                        requirement=contract_obligation.requirement,
                        evidence_requirement=None,
                        state="missing",
                        search_terms=contract_obligation.search_terms,
                        source=contract_obligation.source,
                        evidence_source=None,
                        source_excerpt=contract_obligation.source_excerpt,
                        explanation="The contract requires this item, but no matching COI or policy evidence was found.",
                        next_action="Request supporting COI or policy evidence."
                    )
                )
                continue

            state = self._compare_obligations(contract_obligation, evidence_obligation)
            items.append(
                DecisionItem(
                    obligation_type=obligation_type,
                    requirement=contract_obligation.requirement,
                    evidence_requirement=evidence_obligation.requirement,
                    state=state,
                    search_terms=self._merge_search_terms(contract_obligation, evidence_obligation),
                    source=f"{contract_obligation.source} vs {evidence_obligation.source}",
                    evidence_source=evidence_obligation.source,
                    source_excerpt=self._build_excerpt(contract_obligation, evidence_obligation),
                    explanation=self._build_explanation(state, contract_obligation, evidence_obligation),
                    next_action=self._build_next_action(state, contract_obligation)
                )
            )

        return items

    def _compare_obligations(self, required: Obligation, evidence: Obligation) -> str:
        if required.raw_status == "unclear" or evidence.raw_status == "unclear":
            return "unmet"

        obligation_type = required.obligation_type.lower()
        if "cyber" in obligation_type:
            return self._compare_cyber(required.requirement, evidence.requirement)

        if self._is_limit_based_obligation(obligation_type):
            return "met" if self._limits_satisfied(required.requirement, evidence.requirement) else "unmet"

        if "additional insured" in obligation_type or "waiver of subrogation" in obligation_type:
            required_parties = self._extract_parties(required.requirement)
            evidence_parties = self._extract_parties(evidence.requirement)
            if not required_parties:
                return "met" if self.endorsements.compare(required.obligation_type, required.requirement, evidence.requirement) else "unmet"
            parties_match = required_parties.issubset(evidence_parties)
            endorsement_match = self.endorsements.compare(required.obligation_type, required.requirement, evidence.requirement)
            return "met" if parties_match and endorsement_match else "unmet"

        return "met" if required.requirement.strip().lower() == evidence.requirement.strip().lower() else "unmet"

    def _compare_cyber(self, required_text: str, evidence_text: str) -> str:
        if not self._limits_satisfied(required_text, evidence_text):
            return "unmet"

        required_components = self._extract_components(required_text)
        evidence_components = self._extract_components(evidence_text)
        if required_components and not required_components.issubset(evidence_components):
            return "unmet"
        return "met"

    def _is_limit_based_obligation(self, obligation_type: str) -> bool:
        return any(
            marker in obligation_type
            for marker in [
                "general liability",
                "umbrella",
                "excess",
                "directors and officers",
                "employment practices",
                "fiduciary",
                "crime",
                "fidelity",
                "cyber",
            ]
        )

    def _limits_satisfied(self, required_text: str, evidence_text: str) -> bool:
        required_limits = self._extract_numeric_limits(required_text)
        evidence_limits = self._extract_numeric_limits(evidence_text)
        if not required_limits or not evidence_limits:
            return False

        for index, required_limit in enumerate(required_limits):
            if index >= len(evidence_limits):
                return False
            if evidence_limits[index] < required_limit:
                return False
        return True

    def _extract_numeric_limits(self, text: str) -> list[int]:
        values: list[int] = []
        for match in re.findall(r"\$[\d,]+(?:\.\d+)?\s*(?:million|thousand|m)?|\b\d+(?:\.\d+)?\s*million\b", text, re.IGNORECASE):
            normalized = match.lower().replace("$", "").replace(",", "").strip()
            multiplier = 1
            if normalized.endswith("million"):
                normalized = normalized.replace("million", "").strip()
                multiplier = 1_000_000
            elif normalized.endswith("thousand"):
                normalized = normalized.replace("thousand", "").strip()
                multiplier = 1_000
            elif normalized.endswith("m"):
                normalized = normalized[:-1].strip()
                multiplier = 1_000_000

            try:
                values.append(int(float(normalized) * multiplier))
            except ValueError:
                continue
        return values

    def _extract_components(self, text: str) -> set[str]:
        match = re.search(r"components:\s*(.*?)(?:\s*/\s*retention|$)", text, re.IGNORECASE)
        if not match:
            return set()
        return {
            component.strip().lower()
            for component in match.group(1).split(",")
            if component.strip()
        }

    def _extract_parties(self, text: str) -> set[str]:
        organizations = re.findall(
            r"\b[A-Z][A-Za-z0-9&.' -]{2,80}?\s+(?:LLC|L\.L\.C\.|Inc\.?|Corporation|Corp\.?|Company|Co\.?|LLP|LP)\b",
            text,
        )
        if organizations:
            return {organization.strip().lower() for organization in organizations}
        parties = [part.strip().lower() for part in text.split(",") if part.strip()]
        return set(parties)

    def _merge_search_terms(self, required: Obligation, evidence: Obligation) -> list[str]:
        merged: list[str] = []
        for term in [*required.search_terms, *evidence.search_terms]:
            if term not in merged:
                merged.append(term)
        return merged[:8]

    def _build_excerpt(self, required: Obligation, evidence: Obligation) -> str:
        parts = []
        if required.source_excerpt:
            parts.append(f"Contract: {required.source_excerpt}")
        if evidence.source_excerpt:
            parts.append(f"Evidence: {evidence.source_excerpt}")
        return "\n\n".join(parts)

    def _build_explanation(self, state: str, required: Obligation, evidence: Obligation) -> str:
        if state == "met":
            return "Contract requirement is supported by uploaded COI or policy evidence."
        return (
            f"Contract requires '{required.requirement}', but supporting evidence shows "
            f"'{evidence.requirement}'."
        )

    def _build_next_action(self, state: str, required: Obligation) -> str:
        if state == "met":
            return "No immediate action needed."
        if "additional insured" in required.obligation_type.lower():
            return "Request the matching endorsement or corrected certificate."
        return "Escalate to reviewer and request corrected supporting evidence."
