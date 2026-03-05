"""Settings endpoint for ontology API."""

from fastapi import APIRouter

from core.config import get_settings

from ontology_builder.ui.api.schemas import SettingsResponse

router = APIRouter(tags=["ontology-builder"])

_AVAILABLE_MODELS = ["gpt-4.1o-mini", "gpt-4o-mini", "phi-3-mini-4k-instruct", "gpt-4o", "gpt-4-turbo"]


@router.get("/settings", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    """Return current LLM settings for the UI (model, workers, chunk params)."""
    s = get_settings()
    return SettingsResponse(
        model=s.ontology_llm_model,
        workers=s.get_llm_parallel_workers(),
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        temperature=s.llm_temperature,
        available_models=_AVAILABLE_MODELS,
    )
