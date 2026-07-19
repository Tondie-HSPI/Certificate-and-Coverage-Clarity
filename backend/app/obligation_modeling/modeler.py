import re
from collections import OrderedDict

from app.endorsement_layer.parser import EndorsementParser
from app.rules.loader import load_obligation_rules
from app.schemas.analysis import Obligation, ParsedDocument


class ObligationModeler:
    def __init__(self) -> None:
        self.rules = load_obligation_rules()
        self.endorsements = EndorsementParser()

    def build(self, parsed_documents: list[ParsedDocument]) -> list[Obligation]:
        obligations: list[Obligation] = []
        for document in parsed_documents:
            sections = document.extracted_sections or ([document.markdown] if document.markdown else [])

            for rule in self.rules["obligations"]:
                obligation_type = rule["obligation_type"]
                if obligation_type == "Certificate Holder" and document.certificate_holder_text:
                    obligations.append(
                        Obligation(
                            obligation_type=obligation_type,
                            document_type=document.document_type,
                            requirement=document.certificate_holder_text,
                            source=document.file_name or document.document_id,
                            search_terms=self._build_search_terms(rule, document.certificate_holder_text),
                            confidence=0.92,
                            raw_status="detected",
                            source_excerpt=document.certificate_holder_text,
                            dependency=None
                        )
                    )
                    continue

                if obligation_type == "Additional Coverage Notes" and document.description_box_lines:
                    notes = self._extract_additional_coverage_lines(document.description_box_lines)
                    if notes:
                        notes_text = " | ".join(notes)
                        obligations.append(
                            Obligation(
                                obligation_type=obligation_type,
                                document_type=document.document_type,
                                requirement=notes_text,
                                source=document.file_name or document.document_id,
                                search_terms=self._build_search_terms(rule, notes_text),
                                confidence=0.84,
                                raw_status="detected",
                                source_excerpt="\n".join(notes),
                                dependency=None
                            )
                        )
                        continue

                patterns = rule["patterns"]
                match = self._find_requirement_match(patterns, sections)
                if match is None:
                    obligations.append(
                        Obligation(
                            obligation_type=obligation_type,
                            document_type=document.document_type,
                            requirement=f"{obligation_type} not found",
                            source=document.file_name or document.document_id,
                            search_terms=self._build_search_terms(rule, ""),
                            confidence=0.05 if sections else 0.0,
                            raw_status="missing",
                            source_excerpt="",
                            dependency=None
                        )
                    )
                    continue

                section_text, confidence, status = match
                if self._is_negated(obligation_type, section_text):
                    obligations.append(
                        Obligation(
                            obligation_type=obligation_type,
                            document_type=document.document_type,
                            requirement=f"{obligation_type} not found",
                            source=document.file_name or document.document_id,
                            search_terms=self._build_search_terms(rule, section_text),
                            confidence=0.9,
                            raw_status="missing",
                            source_excerpt=section_text.strip(),
                            dependency=None
                        )
                    )
                    continue

                obligations.append(
                    Obligation(
                        obligation_type=obligation_type,
                        document_type=document.document_type,
                        requirement=self._build_requirement(obligation_type, section_text, status),
                        source=document.file_name or document.document_id,
                        search_terms=self._build_search_terms(rule, section_text),
                        confidence=confidence,
                        raw_status=status,
                        source_excerpt=section_text.strip(),
                        dependency=self._build_dependency(obligation_type, status)
                    )
                )

        return obligations

    def _is_negated(self, obligation_type: str, section_text: str) -> bool:
        negation_terms = {
            "Additional Insured": ["additional insured"],
            "Waiver of Subrogation": ["waiver of subrogation"],
            "Directors and Officers Liability": ["directors and officers", "d&o"],
            "Employment Practices Liability": ["employment practices", "epli"],
            "Fiduciary Liability": ["fiduciary"],
            "Crime / Fidelity": ["crime", "fidelity", "employee dishonesty"],
            "Cyber Liability": ["cyber", "privacy liability", "network security"],
        }
        terms = negation_terms.get(obligation_type)
        if not terms:
            return False

        for term in terms:
            negative_patterns = [
                rf"\bno\s+{term}\b",
                rf"\b{term}\s+(?:is|are)\s+not\b",
                rf"\b{term}\s+(?:coverage\s+)?(?:is\s+)?not\s+(?:included|shown|required|provided)\b",
                rf"\bwithout\s+{term}\b",
            ]
            if any(re.search(pattern, section_text, re.IGNORECASE) for pattern in negative_patterns):
                return True
        return False

    def _find_requirement_match(self, patterns: list[str], sections: list[str]) -> tuple[str, float, str] | None:
        best_match: tuple[str, float, str] | None = None

        for section in sections:
            confidence = 0.0
            for pattern in patterns:
                if re.search(pattern, section, re.IGNORECASE):
                    confidence = max(confidence, 0.86)

            if confidence == 0.0:
                continue

            status = (
                "unclear"
                if any(re.search(pattern, section, re.IGNORECASE) for pattern in self.rules["unclear_hints"])
                else "detected"
            )
            if status == "unclear":
                confidence = min(confidence, 0.72)

            if best_match is None or confidence > best_match[1]:
                best_match = (section, confidence, status)

        return best_match

    def _build_requirement(self, obligation_type: str, section_text: str, status: str) -> str:
        if status == "missing":
            if obligation_type == "Waiver of Subrogation":
                return "Not required"
            return f"{obligation_type} not found"

        if obligation_type == "General Liability":
            occurrence = self._extract_limit(section_text, ["each occurrence", "per occurrence", "occurrence"])
            aggregate = self._extract_limit(section_text, ["aggregate", "general aggregate"])
            if occurrence and aggregate:
                return f"{occurrence} / {aggregate}"
            if occurrence:
                return occurrence
            return "GL detected"

        if obligation_type == "Additional Insured":
            parties = self._extract_parties(section_text)
            ai_details = self.endorsements.parse(obligation_type, section_text)
            parts = [", ".join(parties)] if parties else ["AI required"]
            if ai_details:
                parts.append(", ".join(ai_details))
            return " | ".join([part for part in parts if part])

        if obligation_type == "Waiver of Subrogation":
            parties = self._extract_parties(section_text)
            wos_details = self.endorsements.parse(obligation_type, section_text)
            parts = [", ".join(parties)] if parties else ["WOS required"]
            if wos_details:
                parts.append(", ".join(wos_details))
            return " | ".join([part for part in parts if part])

        if obligation_type == "Umbrella / Excess":
            limit = self._extract_limit(section_text, ["umbrella", "excess", "limit"])
            return limit or "Umbrella / Excess detected"

        if obligation_type == "Automobile Liability":
            limit = self._extract_limit(section_text, ["combined single limit", "auto", "automobile"])
            return limit or "Automobile Liability shown"

        if obligation_type == "Workers Compensation":
            if re.search(r"\bstatutory\b", section_text, re.IGNORECASE):
                return "Statutory"
            return "Workers Compensation shown"

        if obligation_type == "Employers Liability":
            each_accident = self._extract_limit(section_text, ["each accident", "e.l. each accident"])
            disease_employee = self._extract_limit(section_text, ["ea employee", "employee"])
            disease_policy = self._extract_limit(section_text, ["policy limit"])
            parts = [part for part in [each_accident, disease_employee, disease_policy] if part]
            return " / ".join(parts) if parts else "Employers Liability shown"

        if obligation_type in {
            "Directors and Officers Liability",
            "Employment Practices Liability",
            "Fiduciary Liability",
            "Crime / Fidelity",
        }:
            limit = self._extract_limit(section_text, ["limit", "liability", "aggregate", "each claim", "policy"])
            retention = self._extract_retention(section_text)
            parts = [limit or f"{obligation_type} shown"]
            if retention:
                parts.append(f"retention {retention}")
            return " / ".join(parts)

        if obligation_type == "Cyber Liability":
            limit = self._extract_limit(section_text, ["limit", "liability", "aggregate", "each claim", "policy"])
            retention = self._extract_retention(section_text)
            components = self._extract_cyber_components(section_text)
            parts = [limit or "Cyber Liability shown"]
            if components:
                parts.append("components: " + ", ".join(components))
            if retention:
                parts.append(f"retention {retention}")
            return " / ".join(parts)

        if obligation_type == "Certificate Holder":
            holder = self._extract_certificate_holder(section_text)
            return holder or "Certificate holder shown"

        if obligation_type == "Additional Coverage Notes":
            return section_text.strip()

        return obligation_type

    def _extract_retention(self, section_text: str) -> str | None:
        patterns = [
            r"(?:retention|deductible)\s+(?:of\s+)?(\$[\d,]+(?:\.\d+)?\s*(?:million|thousand|m)?)",
            r"(\$[\d,]+(?:\.\d+)?\s*(?:million|thousand|m)?)\s+(?:retention|deductible)",
        ]
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_cyber_components(self, section_text: str) -> list[str]:
        component_patterns = OrderedDict(
            {
                "Technology E&O": r"\btechnology\s+(?:errors?\s+(?:and|&)\s+omissions|E&O)\b|\btech\s+E&O\b|\btechnology\s+professional\s+liabilit\w*\b",
                "Privacy Liability": r"\bprivacy\s+liabilit\w*\b|\bpersonal\s+information\b|\bprivacy\s+breach\b",
                "Network Security": r"\bnetwork\s+security\b|\bsecurity\s+failure\b|\bunauthorized\s+access\b",
                "Data Breach": r"\bdata\s+breach\b|\bbreach\s+response\b|\bsecurity\s+breach\s+response\b|\bnotification\s+costs?\b",
                "PCI / Payment Card": r"\bPCI\b|\bpayment\s+card\b|\bcardholder\s+data\b",
                "Media Liability": r"\bmedia\s+liabilit\w*\b|\bcontent\s+liabilit\w*\b|\bcopyright\b|\bdefamation\b",
                "Cyber Extortion / Ransomware": r"\bcyber\s+extortion\b|\bransomware\b|\bextortion\s+threat\b",
                "Business Interruption": r"\bbusiness\s+interruption\b|\bdependent\s+business\s+interruption\b|\bsystem\s+failure\b",
                "Computer Fraud": r"\bcomputer\s+fraud\b|\bfunds\s+transfer\s+fraud\b|\bsocial\s+engineering\b",
                "Regulatory": r"\bregulatory\s+(?:proceeding|fines?|penalties|defense)\b",
            }
        )
        components: list[str] = []
        compact_text = re.sub(r"\s+", " ", section_text).strip()
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", compact_text)
            if sentence.strip()
        ]
        for component, pattern in component_patterns.items():
            for sentence in sentences:
                if not re.search(pattern, sentence, re.IGNORECASE):
                    continue
                if self._is_negative_component_sentence(sentence):
                    continue
                components.append(component)
                break
        return components

    def _is_negative_component_sentence(self, sentence: str) -> bool:
        negative_patterns = [
            r"\bnot\s+(?:shown|included|provided|covered|confirmed)\b",
            r"\bno\s+(?:coverage|evidence|endorsement)\b",
            r"\bwithout\b",
            r"\bexcluded\b",
        ]
        return any(re.search(pattern, sentence, re.IGNORECASE) for pattern in negative_patterns)

    def _build_dependency(self, obligation_type: str, status: str) -> str | None:
        if obligation_type == "Additional Insured" and status != "missing":
            return "Requires endorsement confirmation"
        return None

    def _extract_limit(self, section_text: str, nearby_terms: list[str]) -> str | None:
        money_matches = re.findall(r"\$[\d,]+(?:\.\d+)?\s*(?:million|thousand|m)?|\b\d+(?:\.\d+)?\s*million\b", section_text, re.IGNORECASE)
        if not money_matches:
            return None

        lowered = section_text.lower()
        for term in nearby_terms:
            term_index = lowered.find(term.lower())
            if term_index == -1:
                continue
            later_matches = [
                match for match in money_matches
                if lowered.find(match.lower(), term_index) != -1
            ]
            if later_matches:
                return later_matches[0]

        return money_matches[0]

    def _extract_parties(self, section_text: str) -> list[str]:
        party_patterns = OrderedDict(self.rules["parties"])
        return [party for party, pattern in party_patterns.items() if re.search(pattern, section_text, re.IGNORECASE)]

    def _extract_certificate_holder(self, section_text: str) -> str | None:
        patterns = [
            r"certificate holder name[:\s]+([^\n\r]+)",
            r"certificate holder[:\s]+([^\n\r]+)",
            r"holder[:\s]+([^\n\r]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                return match.group(1).strip(" .:-")

        parties = self._extract_parties(section_text)
        if parties:
            return ", ".join(parties)
        return None

    def _build_search_terms(self, rule: dict, section_text: str) -> list[str]:
        terms: list[str] = list(rule.get("search_terms", []))

        terms.extend(self._extract_parties(section_text))
        terms.extend(self.endorsements.parse(rule["obligation_type"], section_text))

        unique_terms: list[str] = []
        for term in terms:
            if term and term not in unique_terms:
                unique_terms.append(term)
        return unique_terms[:6]

    def _extract_additional_coverage_lines(self, description_box_lines: list[str]) -> list[str]:
        standard_markers = {
            "additional insured",
            "waiver of subrogation",
            "certificate holder",
            "commercial general liability",
            "automobile liability",
            "workers compensation",
            "employers liability",
            "umbrella",
            "excess",
            "directors and officers",
            "d&o",
            "employment practices liability",
            "epli",
            "fiduciary liability",
            "crime",
            "fidelity",
            "cyber",
            "technology e&o",
            "technology errors",
            "privacy liability",
            "network security",
            "data breach",
            "breach response",
            "pci",
            "payment card",
            "media liability",
            "ransomware",
            "cyber extortion",
            "business interruption",
            "computer fraud",
            "social engineering",
            "regulatory defense",
        }
        notes: list[str] = []
        for line in description_box_lines:
            lowered = line.lower()
            if any(marker in lowered for marker in standard_markers):
                continue
            if "$" in line or "liability" in lowered or "passengers" in lowered:
                notes.append(line)
        return notes[:8]
