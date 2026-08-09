import re

from app.schemas.analysis import DecisionItem, EmailDraft, ParsedDocument


class CoiRequestService:
    def build_email_draft(
        self,
        items: list[DecisionItem],
        certificate_holder_name: str = "Not found - review required",
        certificate_holder_address: str = "Not found - review required",
        requester_wording: str = "Not found - review required",
    ) -> EmailDraft | None:
        requested_items = [
            self._request_line(item)
            for item in items
            if item.state in {"missing", "unmet", "needs_review"}
        ]
        requested_items = [item for item in requested_items if item]

        if not requested_items:
            if items and all(item.state == "met" for item in items):
                body = (
                    "Hello,\n\n"
                    "The attached insurance documents appear to address the requirements you "
                    "provided. Please review the documents and let us know if you need any "
                    "additional certificate wording, endorsements, or policy evidence.\n\n"
                    "This message reflects a document comparison and is subject to human review. "
                    "It does not confirm or certify coverage.\n\n"
                    "Thank you,"
                )
                return EmailDraft(
                    subject="Insurance documents for your review",
                    body=body,
                    requested_items=[],
                )
            return None

        bullets = "\n".join(f"- {item}" for item in requested_items)
        body = (
            "Hello,\n\n"
            "Please review the insurance requirements below and provide a revised certificate "
            "of insurance and any applicable policy endorsements needed to support them:\n\n"
            f"{bullets}\n\n"
            "Certificate request details:\n"
            f"- Certificate holder name: {certificate_holder_name}\n"
            f"- Certificate holder address: {certificate_holder_address}\n"
            f"- Wording required by requester: {requester_wording}\n\n"
            "Please attach the requester's requirements to this email for reference.\n\n"
            "Please confirm that the certificate holder details, requested wording, coverage "
            "limits, and endorsement requirements shown above are accurate. Please identify any "
            "corrections or items that require clarification.\n\n"
            "Please confirm whether each requested item is included by endorsement and provide "
            "copies of the applicable endorsement forms where available. Certificate wording "
            "alone may not be sufficient evidence of coverage.\n\n"
            "Please let us know if any requested item cannot be provided or requires additional "
            "information from the insured.\n\n"
            "Thank you,"
        )

        return EmailDraft(
            subject="Request for revised COI and supporting endorsements",
            body=body,
            requested_items=requested_items,
        )

    def extract_request_details(
        self,
        parsed_documents: list[ParsedDocument],
        requirements_document_name: str | None,
    ) -> dict[str, str]:
        source = next(
            (
                document
                for document in parsed_documents
                if document.file_name == requirements_document_name
            ),
            None,
        )
        if source is None:
            return {}

        text = source.markdown
        holder_name = self._line_value(
            text,
            [r"certificate holder name\s*:\s*([^\r\n]+)", r"certificate holder\s*:\s*([^\r\n]+)"],
        )
        holder_address = self._line_value(
            text,
            [
                r"certificate holder address\s*:\s*([^\r\n|]+)",
                r"holder address\s*:\s*([^\r\n|]+)",
                r"(?m)^address\s*:\s*([^\r\n|]+)",
            ],
        )
        wording = self._line_value(
            text,
            [
                r"wording required by requester\s*:\s*([^\r\n]+)",
                r"requester-required wording\s*:\s*([^\r\n|]+)",
                r"required wording\s*:\s*([^\r\n]+)",
                r"special wording\s*:\s*([^\r\n]+)",
            ],
        )
        if not wording and re.search(
            r"\b(?:no|none)\s+(?:special|additional|specific|required)?\s*wording\b",
            text,
            re.IGNORECASE,
        ):
            wording = "None"

        return {
            "certificate_holder_name": holder_name or "Not found - review required",
            "certificate_holder_address": holder_address or "Not found - review required",
            "requester_wording": wording or "Not found - review required",
        }

    def _line_value(self, text: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .:-")
                if value:
                    return value
        return None

    def _request_line(self, item: DecisionItem) -> str:
        requirement = item.requirement.strip()
        if item.state == "missing":
            return f"{item.obligation_type}: provide evidence meeting the contract requirement ({requirement})."
        if item.obligation_type == "Cyber Liability" and item.state == "unmet":
            return (
                "Cyber Liability / Tech E&O: provide evidence that the required limit and coverage components are included "
                f"({requirement}). Current evidence: {item.evidence_requirement or 'not confirmed'}."
            )
        if item.state == "unmet":
            evidence = item.evidence_requirement or "current evidence does not meet the requirement"
            return (
                f"{item.obligation_type}: correct or provide supporting evidence for "
                f"{requirement}. Current evidence: {evidence}."
            )
        return f"{item.obligation_type}: confirm and provide supporting documentation for {requirement}."
