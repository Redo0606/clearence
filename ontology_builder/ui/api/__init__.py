"""Ontology API package: assembled router from domain sub-routers."""

from fastapi import APIRouter

from ontology_builder.ui.api.build import router as build_router
from ontology_builder.ui.api.graph import router as graph_router
from ontology_builder.ui.api.knowledge_bases import router as kb_router
from ontology_builder.ui.api.qa import router as qa_router
from ontology_builder.ui.api.reasoning import router as reasoning_router
from ontology_builder.ui.api.settings import router as settings_router

router = APIRouter(tags=["ontology-builder"])
router.include_router(settings_router)
router.include_router(build_router)
router.include_router(kb_router)
router.include_router(graph_router)
router.include_router(reasoning_router)
router.include_router(qa_router)
