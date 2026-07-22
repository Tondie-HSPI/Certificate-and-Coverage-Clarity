import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import boto3

logger = logging.getLogger(__name__)


class TextractExtractionError(RuntimeError):
    """Raised when Textract cannot return usable document text."""


@dataclass
class TextractResult:
    text: str
    confidence: float
    page_count: int
    block_count: int
    model_version: str | None = None
    table_rows: list[str] = field(default_factory=list)


class TextractClient:
    """Runs asynchronous Textract analysis against a short-lived private S3 object."""

    def __init__(self) -> None:
        self.bucket = os.getenv(
            "COVERAGE_CLARITY_TEXTRACT_BUCKET",
            "certificate-coverage-clarity-temp-177712846877-us-east-2",
        ).strip()
        self.region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-2"))
        self._s3 = None
        self._textract = None

    def analyze_pdf(self, payload: bytes, file_name: str) -> TextractResult:
        if not self.bucket:
            raise TextractExtractionError("Textract temporary storage is not configured.")

        safe_name = Path(file_name).name.replace(" ", "-") or "document.pdf"
        object_key = f"temporary-uploads/{uuid4()}-{safe_name}"
        s3 = self._s3_client()
        textract = self._textract_client()

        try:
            s3.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=payload,
                ContentType="application/pdf",
                ServerSideEncryption="AES256",
            )
            start_response = textract.start_document_analysis(
                DocumentLocation={"S3Object": {"Bucket": self.bucket, "Name": object_key}},
                FeatureTypes=["FORMS", "TABLES", "LAYOUT"],
                JobTag="certificate-coverage-clarity",
            )
            return self._wait_for_result(textract, start_response["JobId"])
        except TextractExtractionError:
            raise
        except Exception as exc:
            logger.exception("Textract failed for %s", file_name)
            raise TextractExtractionError(
                f"{file_name} could not be read by Amazon Textract."
            ) from exc
        finally:
            try:
                s3.delete_object(Bucket=self.bucket, Key=object_key)
            except Exception:
                logger.exception("Could not delete temporary Textract object %s", object_key)

    def _wait_for_result(self, textract, job_id: str) -> TextractResult:
        deadline = time.monotonic() + 180
        response = None

        while time.monotonic() < deadline:
            response = textract.get_document_analysis(JobId=job_id)
            status = response["JobStatus"]
            if status == "SUCCEEDED":
                break
            if status in {"FAILED", "PARTIAL_SUCCESS"}:
                message = response.get("StatusMessage", "Textract could not analyze the document.")
                raise TextractExtractionError(message)
            time.sleep(1)
        else:
            raise TextractExtractionError("Textract analysis did not finish within three minutes.")

        blocks = list(response.get("Blocks", []))
        next_token = response.get("NextToken")
        while next_token:
            page = textract.get_document_analysis(JobId=job_id, NextToken=next_token)
            blocks.extend(page.get("Blocks", []))
            next_token = page.get("NextToken")

        line_blocks = [block for block in blocks if block.get("BlockType") == "LINE" and block.get("Text")]
        line_blocks.sort(
            key=lambda block: (
                block.get("Page", 1),
                block.get("Geometry", {}).get("BoundingBox", {}).get("Top", 0),
                block.get("Geometry", {}).get("BoundingBox", {}).get("Left", 0),
            )
        )
        if not line_blocks:
            raise TextractExtractionError("Amazon Textract did not find readable text in the document.")

        table_rows = self._extract_table_rows(blocks)
        line_text = "\n".join(block["Text"] for block in line_blocks)
        normalized_text = "\n".join(table_rows)
        text = f"{normalized_text}\n\n{line_text}" if normalized_text else line_text

        confidence_values = [block["Confidence"] / 100 for block in line_blocks if "Confidence" in block]
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        page_count = max((block.get("Page", 1) for block in blocks), default=1)
        return TextractResult(
            text=text,
            confidence=round(min(0.99, confidence), 2),
            page_count=page_count,
            block_count=len(blocks),
            model_version=response.get("AnalyzeDocumentModelVersion"),
            table_rows=table_rows,
        )

    def _extract_table_rows(self, blocks: list[dict]) -> list[str]:
        """Preserve Textract table relationships before the rule engine sees text."""
        block_map = {
            block["Id"]: block
            for block in blocks
            if block.get("Id")
        }
        tables = [block for block in blocks if block.get("BlockType") == "TABLE"]
        tables.sort(
            key=lambda block: (
                block.get("Page", 1),
                block.get("Geometry", {}).get("BoundingBox", {}).get("Top", 0),
                block.get("Geometry", {}).get("BoundingBox", {}).get("Left", 0),
            )
        )

        normalized_rows: list[str] = []
        for table in tables:
            cell_ids = self._relationship_ids(table, "CHILD")
            cells = [
                block_map[cell_id]
                for cell_id in cell_ids
                if cell_id in block_map and block_map[cell_id].get("BlockType") == "CELL"
            ]
            rows: dict[int, list[dict]] = {}
            for cell in cells:
                rows.setdefault(int(cell.get("RowIndex", 0)), []).append(cell)

            for row_index in sorted(rows):
                row_cells = sorted(rows[row_index], key=lambda cell: int(cell.get("ColumnIndex", 0)))
                values = [self._cell_text(cell, block_map) for cell in row_cells]
                values = [value for value in values if value]
                # Single-cell table rows are usually headings or merged narrative boxes.
                # The normal LINE output preserves them more accurately.
                if len(values) < 2:
                    continue
                row_text = self._format_table_row(values)
                if row_text and row_text not in normalized_rows:
                    normalized_rows.append(row_text)
        return normalized_rows

    def _cell_text(self, cell: dict, block_map: dict[str, dict]) -> str:
        parts: list[str] = []
        for child_id in self._relationship_ids(cell, "CHILD"):
            child = block_map.get(child_id, {})
            if child.get("BlockType") == "WORD" and child.get("Text"):
                parts.append(child["Text"])
            elif child.get("BlockType") == "SELECTION_ELEMENT" and child.get("SelectionStatus") == "SELECTED":
                parts.append("Selected")
        return " ".join(parts).strip()

    def _relationship_ids(self, block: dict, relationship_type: str) -> list[str]:
        for relationship in block.get("Relationships", []):
            if relationship.get("Type") == relationship_type:
                return list(relationship.get("Ids", []))
        return []

    def _format_table_row(self, values: list[str]) -> str:
        label = values[0].strip()
        normalized_label = label.lower().rstrip(":")
        labeled_fields = {
            "certificate holder",
            "certificate holder name",
            "address",
            "certificate holder address",
            "requester-required wording",
            "wording required by requester",
            "required wording",
            "special wording",
        }
        if len(values) == 2 and normalized_label in labeled_fields:
            return f"{label.rstrip(':')}: {values[1].strip()}"
        return " | ".join(value.strip() for value in values)

    def _s3_client(self):
        if self._s3 is None:
            self._s3 = boto3.client("s3", region_name=self.region)
        return self._s3

    def _textract_client(self):
        if self._textract is None:
            self._textract = boto3.client("textract", region_name=self.region)
        return self._textract
