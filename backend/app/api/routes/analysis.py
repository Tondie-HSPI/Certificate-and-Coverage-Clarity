from fastapi import APIRouter, File, Form, UploadFile

from app.schemas.analysis import (
    AnalysisResponse,
    IntakeRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.upload_analysis_service import UploadAnalysisService

router = APIRouter(tags=["coi-review"])
service = AnalysisService()
upload_service = UploadAnalysisService()


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(payload: IntakeRequest) -> AnalysisResponse:
    return service.run(payload)


@router.post("/coi-review", response_model=AnalysisResponse)
def coi_review(payload: IntakeRequest) -> AnalysisResponse:
    return service.run(payload)


@router.post("/analyze-upload", response_model=AnalysisResponse)
async def analyze_upload(
    account_role: str = Form(...),
    files: list[UploadFile] = File(...),
    document_types: list[str] | None = Form(default=None),
    requirements_document_id: str | None = Form(default=None),
    requirements_text: str | None = Form(default=None),
) -> AnalysisResponse:
    return await upload_service.run_uploads(
        account_role=account_role,
        files=files,
        document_types=document_types,
        requirements_document_id=requirements_document_id,
        requirements_text=requirements_text,
    )


@router.post("/coi-review-upload", response_model=AnalysisResponse)
async def coi_review_upload(
    account_role: str = Form(...),
    files: list[UploadFile] = File(...),
    document_types: list[str] | None = Form(default=None),
    requirements_document_id: str | None = Form(default=None),
    requirements_text: str | None = Form(default=None),
) -> AnalysisResponse:
    return await upload_service.run_uploads(
        account_role=account_role,
        files=files,
        document_types=document_types,
        requirements_document_id=requirements_document_id,
        requirements_text=requirements_text,
    )
