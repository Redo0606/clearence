# Clearence — Full Codebase Transcript

**Version:** 0.1.0  
**Author:** Reda Sarehane  
**Date:** March 6, 2025

---

## 1. Overview

**Clearence** is a Python application that builds formal, theory-grounded ontologies from documents using:

- **LLM extraction** — Sequential extraction (Bakker Approach B): classes → instances → relations
- **OWL 2 RL reasoning** — Transitive subsumption, inheritance, domain/range propagation, disjointness
- **Ontology-grounded RAG** — OntoRAG + OG-RAG dual retrieval with greedy set cover

It supports **LM Studio** (local) and **OpenAI** cloud for LLMs, and **SentenceTransformers** or **OpenAI** for embeddings.

---

## 2. Project Structure

```
clearence/
├── app/                    # FastAPI web API and PDF→OWL flow
│   ├── main.py             # Entry point, lifespan, routers
│   ├── config.py           # Re-exports core.config
│   ├── logging_config.py   # Table-style logging
│   ├── pdf.py              # PDF text extraction
│   ├── llm_extract.py      # LLM schema extraction (PDF→OWL)
│   ├── ontology.py         # rdflib graph build & serialize
│   ├── schemas.py          # Pydantic models (ClassDef, OntologySchema)
│   └── routers/
│       └── ontology.py     # POST /api/v1/ontology/from-pdf
├── core/                   # Shared configuration
│   ├── config.py           # Pydantic Settings (LLM, embeddings, chunking)
│   └── constants.py        # SIMILARITY_THRESHOLD, MAX_REASONING_ITERATIONS, etc.
├── ontology_builder/       # Main ontology pipeline
│   ├── pipeline/           # Load → chunk → extract → merge → taxonomy → reasoning
│   ├── ontology/           # Schema (O={C,R,I,P}), canonicalizer, candidate
│   ├── storage/            # OntologyGraph, HyperGraph, graph_store
│   ├── llm/                # Client, prompts, json_repair
│   ├── reasoning/          # OWL 2 RL engine
│   ├── qa/                 # Graph index, answer generation
│   ├── quality/            # Structural metrics, consistency, enrichment
│   ├── evaluation/         # Metrics, graph health, eval pipeline
│   ├── export/             # OWL/RDF exporter
│   ├── repair/             # Graph repair (orphans, components)
│   ├── ui/                 # API routes, chat UI, graph viewer
│   └── embeddings.py       # SentenceTransformer or OpenAI
├── documents/              # Raw uploads, ontology_graphs, reports
├── docs/                   # ADR documentation
├── scripts/                # Utility scripts
├── tests/                  # pytest suite
├── pyproject.toml
├── requirements.txt
├── Makefile
├── Dockerfile
└── docker-compose.yml
```

---

## 3. Application Layer (`app/`)

### 3.1 `main.py` — FastAPI Entry Point

- **Lifespan:**
  - Startup: Configure table logging, preload embedding model (if SentenceTransformers), restore last active KB from `documents/ontology_graphs/.last_active`, load graph, build QA index in background
  - Shutdown: Clear graph store, clear QA index
- **CORS:** Allow all origins, credentials, methods, headers
- **Static:** Mount `/static` from `ontology_builder/ui/static`
- **Routers:** `ontology.router` (PDF→OWL), `graph_router` (living ontology API)
- **Endpoints:**
  - `GET /` — Service info (name, docs, health, app)
  - `GET /app` — Chat UI HTML (no-cache headers)
  - `GET /app/theme` — Theme preview (injects `:root` from theme.py)
  - `GET /health` — Health check
- **Entry:** `run()` starts uvicorn on `0.0.0.0:8000` (CLI `clearence`)

### 3.2 `routers/ontology.py` — PDF-to-OWL API

- **POST `/api/v1/ontology/from-pdf`**
  - Params: `file` (UploadFile), `output_format` (owl|turtle|json-ld), `response_type` (file|json)
  - Pipeline: PDF text extraction → LLM schema extraction → rdflib graph → serialize
  - Validates file type (PDF), size (max `upload_max_size_mb` MB)
  - Returns: file download or JSON with `namespace`, `format`, counts, `content`

### 3.3 `pdf.py` — PDF Text Extraction

- Uses `pdfminer.six` (same as `ontology_builder/pipeline/loader.py`)
- `extract_text_from_pdf(content: bytes) -> str`
- Raises `PDFExtractionError` for empty, encrypted, or corrupt PDFs

### 3.4 `llm_extract.py` — LLM Ontology Schema Extraction

- Truncates text to `MAX_TEXT_CHARS` (100,000)
- System prompt: extract `namespace_prefix`, `namespace_uri`, `classes`, `object_properties`, `datatype_properties`
- Calls `ontology_builder.llm.client.complete()` with temperature 0.1
- Strips markdown code fences from response, parses JSON, validates via `OntologySchema`

### 3.5 `ontology.py` — rdflib Graph Build & Serialize

- `build_ontology(schema: OntologySchema) -> Graph`: builds rdflib Graph with OWL classes, subClassOf, object/datatype properties, XSD range mapping
- `serialize_ontology(graph, format)`: supports `owl`, `turtle`, `json-ld`

### 3.6 `schemas.py` — Pydantic Models

- `ClassDef`: name, parent
- `ObjectProperty`: name, domain, range
- `DatatypeProperty`: name, domain, range
- `OntologySchema`: namespace_prefix, namespace_uri, classes, object_properties, datatype_properties
- `OntologyFromPdfResponse`: API response model

### 3.7 `logging_config.py` — Table Logging

- `TableFormatter`: `TIME | COMPONENT | LEVEL | MESSAGE` columns
- `FlushingStreamHandler`: flushes on INFO+ for Docker
- Component map: short labels for pipeline loggers (Loader, Chunker, Extractor, etc.)

---

## 4. Core Configuration (`core/`)

### 4.1 `config.py` — Pydantic Settings

- **Domain profiles:** biomedical, legal, technical, general (chunk_size, similarity_threshold, confidence_threshold)
- **LLM:** `openai_base_url` (default LM Studio `http://localhost:1234/v1`), `ontology_llm_model`, `openai_api_key`
- **Docker:** Rewrites localhost → host.docker.internal for LM Studio
- **Chunking:** chunk_size, chunk_overlap, chunk_mode (fixed|semantic)
- **LLM limits:** llm_max_chunk_chars, llm_max_prompt_tokens, llm_max_graph_chars, llm_max_taxonomy_chars, llm_max_classes_json_chars, llm_max_instances_json_chars
- **Embeddings:** embedding_provider (sentence_transformers|openai), embedding_openai_model, embedding_openai_batch_size
- **Batching:** aggregation_batch_size, canonicalizer_batch_size, graph_write_batch_size, taxonomy_batch_size
- **gpt-4o-mini defaults:** Larger chunk sizes and token budgets when model name contains gpt-4o-mini
- `get_llm_api_key()`: returns key or "lm-studio" for local
- `get_llm_parallel_workers()`: 2 for local, 30 for cloud (override via LLM_PARALLEL_WORKERS)

### 4.2 `constants.py`

- `CHARS_PER_TOKEN = 4`
- `SIMILARITY_THRESHOLD = 0.85`
- `MAX_REASONING_ITERATIONS = 20`
- `CONFIDENCE_THRESHOLD = 0.65`
- `ENCODE_BATCH_SIZE = 64`
- `MAX_RETRIEVAL_FACTS = 20`

---

## 5. Ontology Builder — Pipeline (`ontology_builder/pipeline/`)

### 5.1 `run_pipeline.py` — Orchestrator

**`process_document(path, ...)`** — Main pipeline:

1. **Load** — `load_document(path)` → text
2. **Chunk** — `chunk_text(text, size, overlap, mode)` → chunks
3. **Extract** — Sequential (Bakker B) or legacy:
   - Sequential: `extract_ontology_sequential` per chunk (parallel or sequential), `build_taxonomy`, `_aggregate_extractions`, `update_graph_from_aggregated`, `repair_graph_incremental`
   - Legacy: `extract_ontology` per chunk, `update_graph` per extraction
4. **Cross-component inference** — `infer_cross_component_relations` (connect disconnected components)
5. **LLM relation inference** — `infer_relations` (optional)
6. **OWL 2 RL reasoning** — `run_owl_inference` (optional)
7. **Repair** — `repair_graph` (root concept, orphans, bridge components) (optional)
8. **Quality** — `compute_structural_metrics`, `compute_reliability_score`, `evaluate_relation_correctness`, `check_relation_consistency`, optional `enrich_hierarchy`, `boost_population`, `_print_quality_summary`

**`_aggregate_extractions`** — Pre-aggregates triples across chunks with vote counts, chunk_ids, confidence; batch canonicalizes class/instance names; merges classes/instances with descriptions and synonyms.

**`PipelineCancelledError`** — Raised when `cancel_check()` returns True.

### 5.2 `loader.py` — Document Loading

- Supports `.pdf`, `.docx`, `.txt`, `.md`
- PDF: `pdfminer_extract_text(path)`
- DOCX: `docx.Document(path)`, join paragraphs
- TXT/MD: `Path.read_text(encoding="utf-8", errors="replace")`

### 5.3 `chunker.py` — Text Chunking

- **Semantic mode (default):** Sentence-boundary chunking via regex `(?<=[.!?])\s+(?=[A-Z])`; accumulate until size; overlap uses last N sentences
- **Section-aware:** `detect_sections=True` — Markdown `#`, DOCX headings, PDF-style titles; finalize chunk at section boundary
- **Fixed mode:** `chunk_text_fixed` — sliding window (legacy)
- Fallback: if fewer than 2 chunks in semantic mode, use fixed window

### 5.4 `extractor.py` — LLM Extraction

**Legacy `extract_ontology(chunk)`** — Single-shot: entities + relations. Uses `LEGACY_EXTRACTION_RESPONSE_FORMAT` (json_schema). Fallback to text mode if structured output unsupported.

**Sequential `extract_ontology_sequential(chunk)`** — 3 stages:
1. **Classes** — EXTRACT_CLASSES_SYSTEM/USER, parse `classes`, hallucination guard (token overlap with chunk), truncate by priority (richer descriptions first)
2. **Instances** — EXTRACT_INSTANCES_SYSTEM/USER given classes_json, parse `instances`, truncate by priority
3. **Relations** — EXTRACT_RELATIONS_SYSTEM/USER given classes_json + instances_json, parse object_properties, data_properties, axioms

- Token budget: `_fit_chunk_to_budget` shrinks chunk to fit prompt
- JSON repair via `ontology_builder.llm.json_repair.repair_json`

### 5.5 `taxonomy_builder.py` — OntoGen-Style Taxonomy

- `_deduplicate_classes` — Merge by case-insensitive name, keep richer (parent, longer description, union synonyms)
- `_grounding_check` — Filter classes not fuzzy-matched in source text (SequenceMatcher ratio >= 0.6)
- `_batch_taxonomy` — Batched LLM calls for large class sets
- `_reconciliation_pass` — Unify top-level roots (max 10) via short LLM call
- `build_taxonomy(classes, source_text)` — Returns classes with updated `parent` hierarchy

### 5.6 `ontology_builder.py` — Graph Merge

- `update_graph(graph, extraction, verbose)` — Legacy dict or OntologyExtraction; canonicalizes entities, adds classes/instances/relations/data_properties/axioms
- `update_graph_from_aggregated(graph, aggregated)` — Batch add from pre-aggregated data (relations with vote_count, chunk_ids; classes/instances with chunk_ids)

### 5.7 `relation_inferer.py` — LLM Relation Inference

- **EntityCandidate:** `build_entity_candidates(graph)`; prompts use full aggregated context per entity
- **Co-occurrence:** `build_cooccurrence_pairs(candidates)` — prioritize pairs sharing chunks (min_shared_chunks=2); inferred before batch pass
- `infer_relations(graph)` — Stratify batches by component; parse JSON; `normalize_relation_name()` on parsed relations; vote-count bonus (3+ batches)
- `infer_cross_component_relations(graph)` — Representative per non-largest component; LLM suggests relations; normalized before merge

---

## 6. Ontology Schema & Canonicalizer (`ontology_builder/ontology/`)

### 6.1 `schema.py` — Guarino O = {C, R, I, P}

- **Provenance:** source_document, source_chunk, extraction_confidence
- **AxiomType:** disjointness, symmetry, transitivity, asymmetry, inverse, functional, subclass
- **OntologyClass:** name, parent, description, synonyms, salience, domain_tags
- **OntologyInstance:** name, class_name, description, attributes (→ DataProperties)
- **ObjectProperty:** source, relation, target, domain, range, symmetric, transitive, confidence, evidence, relation_type, bidirectional
- **RELATION_TAXONOMY**, **CANONICAL_RELATION_NAMES**, `normalize_relation_name()` — maps aliases to canonical relation names
- **DataProperty:** entity, attribute, value, datatype
- **Axiom:** axiom_type, entities, description
- **OntologyExtraction:** classes, instances, object_properties, data_properties, axioms
- `entity_names()`, `merge()`, `to_legacy_dict()`

### 6.2 `canonicalizer.py` — Hybrid 3-Stage Deduplication

- **Stage 1 — Exact:** Normalize (lowercase, strip punctuation); if identical to cached → match
- **Stage 2 — Lexical:** Token overlap ratio ≥ 0.8 → match
- **Stage 3 — Embedding:** Encode and compare to SIMILARITY_THRESHOLD (0.85); batched
- `canonicalize(entity_name, kind)`, `canonicalize_batch(names, kind)` — kind = class|instance|entity
- `seed_from_entities(entity_names)` — Batch encode when loading KB

### 6.3 `candidate.py` — EntityCandidate for Inference

- `EntityCandidate` — name, kind, description, relations, data_props, chunk_ids, co_occurring
- `build_entity_candidates(graph)` — Full context per entity (description, relations, data props)
- `build_cooccurrence_pairs(candidates, min_shared_chunks=2)` — Pairs sharing chunks, sorted by shared count; excludes existing relations

---

## 7. Storage (`ontology_builder/storage/`)

### 7.1 `graphdb.py` — OntologyGraph

- NetworkX DiGraph wrapper
- **Nodes:** type, kind (class|instance), description, synonyms, source_documents, chunk_ids, vote_count
- **Edges:** relation, key, value, full (OG-RAG factual block format), confidence, provenance, vote_count, chunk_ids
- **Methods:** add_entity, add_class, add_instance, add_relation, add_relations_batch, add_axiom, add_data_property
- **OG-RAG:** `to_factual_blocks()` — subject + attributes (relation, target, key, value, full)
- **Query:** get_classes, get_instances, get_parents, get_children, get_node_description, get_node_synonyms, has_edge
- **Export:** node-link JSON with axioms, data_properties, stats; embeddings stripped for save (`_strip_embeddings_for_export`); `get_export_for_api()` for API responses

### 7.2 `hypergraph.py` — OG-RAG Hypergraph

- **HyperNode:** (key, value, full)
- **HyperGraph:** nodes, edges (frozensets of node indices)
- `flatten_factual_block(block)` → (key, value, full) triples
- `build_hypergraph(factual_blocks)` — One hyperedge per factual block linking its atomic facts

### 7.3 `graph_store.py` — In-Memory Store

- `set_graph`, `get_graph`, `get_export`, `get_export_for_api`, `get_subject`, `clear`
- `set_current_kb_id`, `get_current_kb_id`, `get_last_active_kb`, `save_last_active_kb`, `clear_last_active_kb`
- `save_to_path`, `save_to_path_with_metadata` — compact JSON (`separators=(',', ':')`), embeddings stripped
- `update_kb_metadata`, `list_knowledge_bases`
- `load_from_path` — Reconstruct from node-link JSON; optionally seed canonicalizer (batch)

---

## 8. LLM (`ontology_builder/llm/`)

### 8.1 `client.py` — Unified LLM Client

- OpenAI client (LM Studio or OpenAI cloud)
- `complete(system, user, temperature, response_format, force_text_mode)` — Retries with tenacity, no retry on context overflow
- `complete_batch(items, system_fn, user_fn, ...)` — ThreadPoolExecutor, parallel or sequential

### 8.2 `prompts.py` — Extraction & Inference Prompts

- **Stage 1 (classes):** EXTRACT_CLASSES_SYSTEM/USER — CamelCase, synonyms, parent only when explicit, max 20 per chunk, no hallucination
- **Stage 2 (instances):** EXTRACT_INSTANCES_SYSTEM/USER — class_name must be from known classes
- **Stage 3 (relations):** EXTRACT_RELATIONS_SYSTEM/USER — object_properties, data_properties, axioms (disjointness, symmetry, transitivity, etc.)
- **Taxonomy:** TAXONOMY_SYSTEM/USER — Organize classes into is-a hierarchy
- **Inference:** INFERENCE_PROMPT, CROSS_COMPONENT_INFERENCE_PROMPT
- **Language:** `ontology_language_instruction(lang)`, `inference_language_instruction(lang)` for multilingual output

### 8.3 `json_repair.py` — JSON Repair

- Repairs malformed JSON from LLM output (handles trailing commas, unquoted keys, etc.)

---

## 9. Reasoning (`ontology_builder/reasoning/`)

### 9.1 `engine.py` — OWL 2 RL Fixpoint

- **Pre-reasoning:** `detect_relation_properties(graph)` — auto-detects transitive/symmetric from graph structure (>3 open chains → transitive; >70% symmetric pairs → symmetric)
- **Transitive subsumption:** A subClassOf B, B subClassOf C → A subClassOf C
- **Inheritance:** A subClassOf B, x type A → x type B
- **Domain/range propagation:** From axioms
- **Transitive/symmetric closure:** From axioms + auto-detected
- **Disjointness check:** Flag instances typed as both disjoint classes
- Iterates until fixpoint (max MAX_REASONING_ITERATIONS)
- Returns `ReasoningResult`: inferred_edges, consistency_violations, inference_trace, iterations

### 9.2 `rules.py` — Rule Definitions

- TRANSITIVE_RELATIONS, SYMMETRIC_RELATIONS, DOMAIN_RULES (per subject)
- InferenceStep, RuleType enum

---

## 10. QA / RAG (`ontology_builder/qa/`)

### 10.1 `graph_index.py` — OntoRAG + OG-RAG Index

- **Records:** key, value, full (relation records append `" | Evidence: {evidence}"` when available)
- **Hyperedges:** Group records by node
- **build_index(graph, kb_path=None)** — Load from `{kb_id}_index.npz` when present (skip recomputation); else encode, build hypergraph, persist to `_index.npz`
- **retrieve(query, top_k)** — Dual retrieval (key + value similarity), concept-matched indices (query words vs nodes/synonyms)
- **retrieve_with_context(query, top_k)** — Same + ontological context (parents, children, definitions for matched nodes)
- **retrieve_hyperedges(query, k_nodes, max_hyperedges)** — Greedy set cover over hyperedges (OG-RAG Algorithm 2)

### 10.2 `answer.py` — Answer Generation

- `answer_question(question, context_snippets, source_refs, ontological_context, answer_language)` — LLM with QA_SYSTEM, JSON response (reasoning, answer), strip raw source IDs
- `answer_questions_batch` — Parallel batch for evaluation
- `source_ref_to_label(ref)` — Human-readable labels (node:X, edge:A-R-B, dp:E-A)

### 10.3 `prompts.py` — QA Prompts

- QA_SYSTEM, build_qa_user_prompt (context, question, ontological_context, answer_language)

---

## 11. Quality (`ontology_builder/quality/`)

- **structural_scorer:** depth_variance, breadth_variance, instance_to_class_ratio, named_relation_ratio, generic_relation_ratio → ReliabilityScore (grade A–F)
- **consistency_checker:** Critical conflicts (e.g. circular subClassOf)
- **relation_evaluator:** Relation correctness scores
- **hierarchy_enricher:** Add missing subClassOf via LLM
- **population_booster:** Add instances via LLM when sparse
- **report:** OntologyQualityReport (structural_metrics, reliability_score, relation_scores, consistency_report, recommended_actions)

---

## 12. Evaluation (`ontology_builder/evaluation/`)

- **metrics:** ChunkStats, PipelineReport, PipelineTimer
- **graph_health:** Structural, semantic, retrieval metrics; badge, overall_score
- **eval_pipeline:** run_evaluation — generate questions, answer, compute P/R/F1, RAGAS
- **question_gen:** LLM-based question generation from graph

---

## 13. Export (`ontology_builder/export/`)

- **owl_exporter:** `ontology_graph_to_rdflib`, `export_ontology_to_rdf` — Turtle, JSON-LD, RDF/XML
- Maps classes, instances, relations, data properties, axioms to OWL/RDF

---

## 14. Repair (`ontology_builder/repair/`)

- **RepairConfig:** similarity_threshold, max_orphan_links, max_component_bridges, add_root_concept, run_reasoning_after
- **Orphan linking (semantic):** Combined text (description + data props + relation targets); embed and cosine ≥ 0.75; link to parent when match has subClassOf
- **Component bridging (multi-hop):** Find intermediate node with `(sim(A,node) + sim(B,node))/2 >= 0.6`; add A → intermediate → B (relatedTo) when found
- **repair_graph:** Root concept, semantic orphans, multi-hop bridges, optional reasoning

---

## 15. UI (`ontology_builder/ui/`)

### 15.1 `api.py` — Living Ontology API Routes

- **POST /build_ontology** — Upload file(s), run pipeline, save KB, return graph + report
- **POST /build_ontology_stream** — Same with SSE progress (load, chunk, extract, merge, inference, reasoning, repair, quality)
- **POST /knowledge-bases/{id}/extend_stream** — Extend KB with new documents, merge, stream progress
- **POST /cancel_job/{job_id}** — Cancel active pipeline
- **GET /knowledge-bases** — List KBs with active_id
- **POST /knowledge-bases/{id}/activate** — Load and set active
- **PATCH /knowledge-bases/{id}** — Update name, description, ontology_language
- **DELETE /knowledge-bases/{id}** — Delete KB
- **GET /knowledge-bases/{id}/health** — Graph health metrics
- **GET /knowledge-bases/{id}/evaluation-records** — Eval records
- **POST /knowledge-bases/{id}/repair** — Repair graph, SSE
- **POST /knowledge-bases/{id}/evaluate** — Run QA evaluation, SSE
- **GET /ontology/export** — Export to Turtle/JSON-LD/XML
- **POST /qa/ask** — Answer question with retrieval_mode (context|hyperedges|snippets)
- **GET /graph** — Current graph export
- **POST /reasoning/apply** — Re-run OWL 2 RL reasoning
- **GET /graph/image** — PNG visualization
- **GET /graph/viewer** — vis.js interactive viewer

### 15.2 `chat_ui.py` — Chat UI HTML

- `generate_chat_ui_html()` — Jinja2 template for ontology chat

### 15.3 `graph_viewer.py` — Visualization

- `visualize(graph)` — Matplotlib PNG
- `generate_visjs_html(graph, pre_select_node, depth, debug)` — vis.js standalone HTML

### 15.4 `theme.py` — Theme/CSS

- `get_css_root_block()` — CSS variables for theme

---

## 16. Embeddings (`ontology_builder/embeddings.py`)

- **SentenceTransformer:** all-MiniLM-L6-v2 (384 dims), lazy load
- **OpenAI:** Batched API, text-embedding-3-small (1536), sanitize control chars
- `get_embedding_model()`, `get_embedding_dimension()`, `preload_embedding_model()`

---

## 17. Data Flow Summary

```
Document (PDF/DOCX/TXT/MD)
    → load_document → text
    → chunk_text (semantic/fixed) → chunks
    → extract_ontology_sequential (per chunk) → OntologyExtraction
    → build_taxonomy → class parent map
    → _aggregate_extractions → aggregated (vote_count, chunk_ids)
    → update_graph_from_aggregated → OntologyGraph
    → infer_cross_component_relations → relations
    → infer_relations → relations
    → run_owl_inference → ReasoningResult
    → repair_graph → RepairReport
    → compute_structural_metrics, check_relation_consistency, etc.
    → save_to_path_with_metadata → documents/ontology_graphs/{kb_id}.json
    → build_qa_index → embedding index + hypergraph
```

---

## 18. API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Service info |
| GET | /app | Chat UI |
| GET | /app/theme | Theme preview |
| GET | /health | Health check |
| POST | /api/v1/ontology/from-pdf | PDF → OWL/Turtle/JSON-LD |
| POST | /api/v1/build_ontology | Build ontology from document(s) |
| POST | /api/v1/build_ontology_stream | Same, SSE progress |
| POST | /api/v1/knowledge-bases/{id}/extend_stream | Extend KB |
| POST | /api/v1/cancel_job/{job_id} | Cancel pipeline |
| GET | /api/v1/knowledge-bases | List KBs |
| POST | /api/v1/knowledge-bases/{id}/activate | Activate KB |
| PATCH | /api/v1/knowledge-bases/{id} | Update KB metadata |
| DELETE | /api/v1/knowledge-bases/{id} | Delete KB |
| GET | /api/v1/knowledge-bases/{id}/health | Graph health |
| POST | /api/v1/knowledge-bases/{id}/repair | Repair graph |
| POST | /api/v1/knowledge-bases/{id}/evaluate | QA evaluation |
| GET | /api/v1/graph | Current graph |
| GET | /api/v1/graph/image | Graph PNG |
| GET | /api/v1/graph/viewer | vis.js viewer |
| POST | /api/v1/reasoning/apply | OWL 2 RL reasoning |
| GET | /api/v1/ontology/export | Export OWL/RDF |
| POST | /api/v1/qa/ask | Ontology-grounded Q&A |

---

## 19. Dependencies (pyproject.toml)

- fastapi, uvicorn, pydantic, pydantic-settings
- rdflib, openai, networkx, sentence-transformers
- pdfminer.six, python-docx, requests, tqdm, jinja2, tenacity
- matplotlib (graph viz)
- Dev: pytest, pytest-asyncio, httpx, ruff

---

## 20. Tests

- `test_extractor`, `test_pipeline`, `test_taxonomy`
- `test_schema`, `test_reasoning`, `test_owl_exporter`
- `test_metrics`, `test_llm_client`, `test_hypergraph`, `test_graphdb`
- `tests/ui/test_graph_viewer`

---

*End of transcript.*
