from pathlib import Path

from fastapi import HTTPException
from fastapi import UploadFile

from app.extraction_layer.insurance_parser import DocumentExtractionError
from app.schemas.analysis import AnalysisResponse, IntakeRequest, UploadDescriptor
from app.services.analysis_service import AnalysisService


class UploadAnalysisService:
    max_files = 2
    max_file_size = 10 * 1024 * 1024
    allowed_extensions = {".pdf", ".docx", ".txt"}

    def __init__(self) -> None:
        self.analysis_service = AnalysisService()

    async def run_uploads(
        self,
        account_role: str,
        files: list[UploadFile],
        document_types: list[str] | None = None,
        requirements_document_id: str | None = None,
        requirements_text: str | None = None,
    ) -> AnalysisResponse:
        if not files or len(files) > self.max_files:
            raise HTTPException(status_code=400, detail="Upload one or two documents.")
        if requirements_text and len(requirements_text) > 20_000:
            raise HTTPException(status_code=400, detail="Entered requirements must be under 20,000 characters.")

        documents: list[UploadDescriptor] = []

        if requirements_text and requirements_text.strip():
            documents.append(
                UploadDescriptor(
                    document_id="manual-requirements",
                    document_type="contract",
                    file_name="Confirmed requester requirements",
                    content=requirements_text.strip(),
                )
            )
            requirements_document_id = "manual-requirements"

        for index, file in enumerate(files):
            file_name = file.filename or ""
            extension = Path(file_name).suffix.lower()
            if extension not in self.allowed_extensions:
                raise HTTPException(status_code=400, detail=f"{file_name or 'The file'} must be a PDF, DOCX, or TXT document.")
            content = await file.read()
            if len(content) > self.max_file_size:
                raise HTTPException(status_code=413, detail=f"{file_name or 'The file'} must be smaller than 10 MB.")
            if document_types and index < len(document_types):
                document_type = document_types[index]
            else:
                document_type = self._infer_document_type(file_name)
                if document_type == "supporting_doc" and len(files) > 1:
                    document_type = "contract" if index == 0 else "coi"
            documents.append(
                UploadDescriptor(
                    document_id=f"{index}-{file_name}",
                    document_type=document_type,
                    file_name=file_name,
                    content=content.decode("utf-8", errors="ignore"),
                    binary_payload=content
                )
            )

        payload = IntakeRequest(
            account_role=account_role,
            documents=documents,
            requirements_document_id=requirements_document_id,
        )
        try:
            return self.analysis_service.run(payload)
        except DocumentExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _infer_document_type(self, file_name: str) -> str:
        lowered = file_name.lower()
        if "coi" in lowered or "certificate" in lowered:
            return "coi"
        if "policy" in lowered or "endorsement" in lowered:
            return "policy"
        if "contract" in lowered or "agreement" in lowered:
            return "contract"
        return "supporting_doc"
