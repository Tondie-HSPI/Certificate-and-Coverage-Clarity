from uuid import uuid4

from app.comparison_layer.comparator import ComparisonLayer
from app.decision_support.advisor import DecisionSupportLayer
from app.extraction_layer.parser import ExtractionLayer
from app.governance.constraints import GovernanceLayer
from app.input_layer.intake import IntakeLayer
from app.obligation_modeling.modeler import ObligationModeler
from app.schemas.analysis import AnalysisResponse, DecisionItem, IntakeRequest, Obligation, SourceOfTruth
from app.services.coi_request_service import CoiRequestService
from app.state_engine.engine import StateEngine
from app.validation_layer.validator import ValidationLayer


class AnalysisService:
    def __init__(self) -> None:
        self.intake = IntakeLayer()
        self.extraction = ExtractionLayer()
        self.modeler = ObligationModeler()
        self.validation = ValidationLayer()
        self.state_engine = StateEngine()
        self.comparison = ComparisonLayer()
        self.decision_support = DecisionSupportLayer()
        self.governance = GovernanceLayer()
        self.coi_requests = CoiRequestService()

    def run(self, payload: IntakeRequest) -> AnalysisResponse:
        state = self.intake.create_state(payload)
        state = self.governance.apply(state)
        analysis_mode = self._determine_analysis_mode(payload)

        parsed_documents = self.extraction.parse(payload.documents)
        obligations = self.modeler.build(parsed_documents)
        source_of_truth = self._resolve_source_of_truth(payload)
        if source_of_truth.selection_status == "selection_required":
            analysis_mode = "source_selection_required"
        if source_of_truth.document_id:
            obligations = [
                obligation
                for obligation in obligations
                if obligation.document_type != "contract"
                or obligation.source == source_of_truth.document_name
            ]
        validations = self.validation.validate(obligations)
        if analysis_mode == "source_selection_required":
            decision_items = []
        elif analysis_mode == "comparison":
            decision_items = self.comparison.compare(obligations)
        else:
            decision_items = self.state_engine.assign(obligations, validations)
        decision_items = self.decision_support.refine(decision_items)
        decision_items = self.governance.validate_outputs(decision_items)
        request_details = self.coi_requests.extract_request_details(
            parsed_documents,
            source_of_truth.document_name,
        )
        email_draft = self.coi_requests.build_email_draft(decision_items, **request_details)

        overall_confidence = self._calculate_overall_confidence(
            obligations,
            decision_items,
            source_of_truth,
        )

        return AnalysisResponse(
            workflow_id=str(uuid4()),
            overall_confidence=overall_confidence,
            analysis_mode=analysis_mode,
            items=decision_items,
            parsed_documents=parsed_documents,
            validations=validations,
            email_draft=email_draft,
            source_of_truth=source_of_truth,
        )

    def _calculate_overall_confidence(
        self,
        obligations: list[Obligation],
        decision_items: list[DecisionItem],
        source_of_truth: SourceOfTruth,
    ) -> float:
        """Score analysis quality without treating absent, irrelevant rules as failures."""
        if source_of_truth.selection_status == "selection_required":
            return 0.0

        detected_requirements = [
            obligation
            for obligation in obligations
            if obligation.document_type == "contract"
            and obligation.confidence >= 0.5
            and (
                not source_of_truth.document_name
                or obligation.source == source_of_truth.document_name
            )
        ]

        # A coverage-only review has no requester-requirements document. In that mode,
        # score the substantive fields that were actually extracted from the evidence.
        score_basis = detected_requirements or [
            obligation
            for obligation in obligations
            if obligation.confidence >= 0.5
        ]
        if not score_basis:
            return 0.0

        extraction_score = sum(item.confidence for item in score_basis) / len(score_basis)
        source_bonus = {
            "user_selected": 0.02,
            "single_requirements_document": 0.01,
        }.get(source_of_truth.selection_status, 0.0)

        uncertain_states = {"needs_review", "unclear", "not_extracted"}
        uncertain_count = sum(item.state in uncertain_states for item in decision_items)
        uncertainty_penalty = (
            0.2 * (uncertain_count / len(decision_items))
            if decision_items
            else 0.0
        )

        return round(
            max(0.0, min(0.97, extraction_score + source_bonus - uncertainty_penalty)),
            2,
        )

    def _resolve_source_of_truth(self, payload: IntakeRequest) -> SourceOfTruth:
        selected = next(
            (
                document
                for document in payload.documents
                if document.document_id == payload.requirements_document_id
                or document.file_name == payload.requirements_document_id
            ),
            None,
        )
        if selected:
            return SourceOfTruth(
                document_id=selected.document_id,
                document_name=selected.file_name or selected.document_id,
                selection_status="user_selected",
            )

        requirement_documents = [
            document for document in payload.documents if document.document_type == "contract"
        ]
        if len(requirement_documents) == 1:
            document = requirement_documents[0]
            return SourceOfTruth(
                document_id=document.document_id,
                document_name=document.file_name or document.document_id,
                selection_status="single_requirements_document",
            )

        return SourceOfTruth(selection_status="selection_required")

    def _determine_analysis_mode(self, payload: IntakeRequest) -> str:
        document_types = {document.document_type for document in payload.documents}
        has_contract = "contract" in document_types
        has_evidence_docs = bool(document_types.intersection({"coi", "policy", "supporting_doc"}))

        if has_contract and has_evidence_docs:
            return "comparison"
        if has_contract:
            return "contract_requirements"
        return "document_presence"
