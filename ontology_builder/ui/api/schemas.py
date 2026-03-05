"""Pydantic request/response models for ontology API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineReportResponse(BaseModel):
    """Pipeline execution report with extraction and reasoning stats."""

    document_path: str = Field("", description="Path to source document")
    total_chunks: int = Field(0, description="Number of text chunks processed")
    totals: dict[str, int] = Field(default_factory=dict, description="Final graph counts")
    extraction_totals: dict[str, int] = Field(default_factory=dict, description="Counts before reasoning")
    llm_inferred_relations: int = Field(0, description="Relations inferred by LLM")
    reasoning: dict[str, Any] = Field(default_factory=dict, description="OWL 2 RL reasoning stats")
    elapsed_seconds: float = Field(0.0, description="Total pipeline duration")
    extraction_mode: str = Field("sequential", description="legacy, parallel, or sequential")
    chunk_stats: list[dict[str, Any]] = Field(default_factory=list, description="Per-chunk extraction stats")
    ontology_name: str = Field("", description="Display name of the ontology")


class BuildOntologyResponse(BaseModel):
    """Response from build_ontology with graph and pipeline report."""

    graph: dict[str, Any] = Field(default_factory=dict, description="Node-link graph export")
    pipeline_report: PipelineReportResponse = Field(default_factory=PipelineReportResponse)
    kb_id: str | None = Field(None, description="ID of created knowledge base")


class QASourceResponse(BaseModel):
    """QA answer with fact-level attribution."""

    answer: str = Field(..., description="Generated answer text")
    sources: list[str] = Field(default_factory=list, description="Retrieved fact strings")
    source_refs: list[str] = Field(default_factory=list, description="Source reference IDs")
    source_labels: list[str] = Field(default_factory=list, description="Human-readable source labels")
    ontological_context: str = Field("", description="OntoRAG taxonomy context")
    num_facts_used: int = Field(0, description="Number of facts used in answer")
    kb_id: str | None = Field(None, description="Ontology that was queried")


class GraphExportResponse(BaseModel):
    """Graph export with node-link data and stats."""

    graph: dict[str, Any] = Field(default_factory=dict, description="Node-link JSON")
    stats: dict[str, int] = Field(default_factory=dict, description="Class/instance/edge counts")


class ReasoningResponse(BaseModel):
    """OWL 2 RL reasoning result with trace."""

    inferred_edges: int = Field(0, description="Number of edges inferred")
    iterations: int = Field(0, description="Fixpoint iterations")
    consistency_violations: list[str] = Field(default_factory=list, description="Disjointness violations")
    inference_trace: list[dict[str, str]] = Field(default_factory=list, description="Step-by-step trace")
    graph: dict[str, Any] = Field(default_factory=dict, description="Updated graph export")


class KnowledgeBaseItem(BaseModel):
    """Single knowledge base metadata."""

    id: str = Field(..., description="Unique KB ID")
    name: str = Field(..., description="Display name")
    description: str = Field("", description="Optional description")
    created_at: float = Field(..., description="Unix timestamp")
    stats: dict[str, int] = Field(default_factory=dict, description="Graph stats")
    documents: list[str] = Field(default_factory=list, description="Source document filenames")


class KnowledgeBasesResponse(BaseModel):
    """List of knowledge bases with active ID."""

    items: list[KnowledgeBaseItem] = Field(default_factory=list)
    active_id: str | None = Field(None, description="Currently active KB ID")


class QAAskRequest(BaseModel):
    """Request body for QA ask endpoint."""

    question: str
    kb_id: str | None = Field(
        None,
        description="Ontology/knowledge base ID to query. If provided and different from active, activates it first.",
    )


class SettingsResponse(BaseModel):
    """Current LLM settings for the UI."""

    model: str = ""
    workers: int = 2
    chunk_size: int = 1200
    chunk_overlap: int = 200
    temperature: float = 0.1
    available_models: list[str] = Field(default_factory=list)


class KBUpdateRequest(BaseModel):
    """Request body for KB update endpoint."""

    name: str | None = Field(None, description="New name for the knowledge base")
    description: str | None = Field(None, description="New description")
