# Ontology Graph Build and Generation: Technical and Scientific Explanation

**Purpose:** This document describes how the ontology graph is built and generated in the current stack. It is written for an AI (e.g. Claude Sonnet) to parse and use when creating a plan to improve the pipeline.

**Stack:** Python, NetworkX (in-memory directed graph), LLM (OpenAI-compatible API), SentenceTransformer (embeddings), OWL 2 RL–style reasoning, and graph repair.

---

## 1. High-Level Pipeline Overview

The pipeline turns a single document (PDF, DOCX, TXT, or MD) into a **formal ontology graph**: a directed graph of **classes** (concepts), **instances** (individuals), **relations** (object properties), **data properties**, and **axioms** (meaning postulates). The flow is:

1. **Load** — Extract raw text from the document.
2. **Chunk** — Split text into overlapping segments for LLM context.
3. **Extract** — Per-chunk LLM extraction (sequential 3-stage or legacy single-shot).
4. **Merge** — Deduplicate and merge extractions into one graph (with canonicalization).
5. **Taxonomy** — (Sequential only) Organize classes into an is-a hierarchy via LLM.
6. **LLM inference** — Cross-component then batch relation inference.
7. **OWL 2 RL reasoning** — Fixpoint application of formal rules.
8. **Repair** — Root concept, orphan linking, component bridging.

**Entry point:** `ontology_builder.pipeline.run_pipeline.process_document(path, ...)` → returns `(OntologyGraph, PipelineReport)`.

---

## 2. Formal Ontology Model (Schema)

The system follows **Guarino-style** ontology structure **O = {C, R, I, P}** plus axioms (see `ontology_builder.ontology.schema`):

- **C (Classes):** Concepts/universals. Model: `OntologyClass(name, parent, description, synonyms, salience, domain_tags)`.
- **I (Instances):** Individuals/particulars typed by a class. Model: `OntologyInstance(name, class_name, description, attributes)` — `attributes` become DataProperties.
- **R (Object properties):** Binary relations. Model: `ObjectProperty(source, relation, target, ..., evidence, relation_type, bidirectional)`. Relation names normalized via `RELATION_TAXONOMY` / `CANONICAL_RELATION_NAMES`.
- **P (Data properties):** Attribute–value pairs on entities. Model: `DataProperty(entity, attribute, value, datatype)`.
- **Axioms:** Meaning postulates. Model: `Axiom(axiom_type, entities, description)`. Types: `disjointness`, `symmetry`, `transitivity`, `asymmetry`, `inverse`, `functional`, `subclass`.

All extracted elements carry **provenance** (source_document, source_chunk, extraction_confidence) for reproducibility.

---

## 3. Stage-by-Stage Technical Description

### 3.1 Load (`ontology_builder.pipeline.loader`)

- **Input:** File path (PDF, DOCX, TXT, MD).
- **Process:** PDF via `pdfminer.high_level.extract_text`, DOCX via `python-docx` (paragraphs joined), TXT/MD via `Path.read_text`.
- **Output:** Single string of document text.
- **Failure modes:** Unsupported format, extraction errors → `ValueError` / `RuntimeError`.

### 3.2 Chunk (`ontology_builder.pipeline.chunker`)

- **Function:** `chunk_text(text, size, overlap, mode="semantic", detect_sections=True)`.
- **Algorithm (semantic mode, default):** Sentence-boundary chunking. Split on `.?!` followed by capital; accumulate sentences until `size` chars; overlap uses last N sentences (overlap char budget). Falls back to fixed window if fewer than 2 chunks.
- **Section-aware:** When `detect_sections=True`, detects Markdown `#`, DOCX ALL-CAPS headings, lines ending with `:`, PDF-style short titles; finalizes chunk at section boundary and starts new chunk with header.
- **Fixed mode:** Sliding window (legacy): start at 0, take `size` chars, advance by `size - overlap`.
- **Defaults:** `chunk_size=2000`, `chunk_overlap=300` (from `core.config.Settings`). For gpt-4o-mini, config can override to 10000/2000.
- **Rationale:** Sentence boundaries avoid cutting mid-sentence; section detection prevents context bleed across topics.

### 3.3 Extract (`ontology_builder.pipeline.extractor`)

Two modes:

**Legacy (single-shot):** `extract_ontology(chunk)` → one LLM call per chunk. Expected JSON: `{ "entities": [{name, type, description}], "relations": [{source, relation, target, confidence}] }`. Prompt: `ONTOLOGY_EXTRACTION_PROMPT` in `ontology_builder.llm.prompts`. Uses `LEGACY_EXTRACTION_RESPONSE_FORMAT` (JSON schema) when supported; falls back to text + `repair_json` on schema errors.

**Sequential (Bakker Approach B, default):** `extract_ontology_sequential(chunk, source_document)` — three LLM stages per chunk:

1. **Stage 1 — Classes:** System `EXTRACT_CLASSES_SYSTEM`, user `EXTRACT_CLASSES_USER.format(chunk=s1_chunk)`. Output: `{"classes": [{name, parent, description, synonyms}]}` (or bare array). Chunk may be trimmed with `_fit_chunk_to_budget` to respect `llm_max_prompt_tokens` (default 3000).
2. **Stage 2 — Instances:** Input: chunk + `classes_json` (truncated to `llm_max_classes_json_chars`). Prompt: `EXTRACT_INSTANCES_USER`. Output: `{"instances": [{name, class_name, description}]}`. Instances must reference known classes.
3. **Stage 3 — Relations, data properties, axioms:** Input: chunk + `classes_json` + `instances_json` (truncated to `llm_max_instances_json_chars`). Prompt: `EXTRACT_RELATIONS_USER`. Output: `object_properties`, `data_properties`, `axioms` (with axiom_type, entities, description).

**Token/chars handling:** `llm_max_chunk_chars` truncates chunk; `_fit_chunk_to_budget` shrinks chunk so system+user fit token budget. JSON lists (classes/instances) are truncated by character limits when passed to the next stage.

**Output:** `OntologyExtraction(classes, instances, object_properties, data_properties, axioms)` with provenance attached.

### 3.4 Merge and canonicalization (`ontology_builder.pipeline.ontology_builder`, `ontology_builder.ontology.canonicalizer`)

- **Merge:** `update_graph(graph, extraction)` adds classes, instances, relations, data properties, axioms into the shared `OntologyGraph`. For structured extraction it uses `add_class`, `add_instance`, `add_relation`, `add_data_property`, `add_axiom`; for legacy dict it uses `add_entity` and `add_relation`.
- **Canonicalization:** Hybrid 3-stage pipeline in `ontology_builder.ontology.canonicalizer`:
  - **Stage 1 — Exact:** Normalize (lowercase, strip punctuation); if identical to cached → match.
  - **Stage 2 — Lexical:** Token overlap ratio ≥ 0.8 → match.
  - **Stage 3 — Embedding:** Encode and compare to `SIMILARITY_THRESHOLD` (0.85, configurable); batched via `canonicalize_batch()`.
  - `seed_from_entities()` batch-encodes when loading KB.
- **Relation normalization:** `normalize_relation_name()` maps aliases to canonical names (subClassOf, hasPart, hasAbility, causes, relatedTo) via `CANONICAL_RELATION_NAMES` in `schema.py`.

### 3.5 Taxonomy (sequential mode only) (`ontology_builder.pipeline.taxonomy_builder`)

- **When:** After all chunks are extracted (sequential path), before merging each extraction into the graph. All classes from all extractions are collected; taxonomy is built once.
- **Steps:**
  1. **Deduplicate:** `_deduplicate_classes(classes)` — merge by case-insensitive name; keep the one with parent or longer description.
  2. **LLM hierarchy:** Single call with `TAXONOMY_SYSTEM` / `TAXONOMY_USER`. Input: JSON list of `{name, description}`. Output: `{"taxonomy": [{name, parent, description}]}`. Constraint: every input class must appear; no invented classes; parent must be null or in the input list.
  3. **Grounding filter:** `_grounding_check(taxonomy_raw, source_text, threshold=0.6)` — drop classes whose name is not in the source text, has no token >3 chars in the text, or has SequenceMatcher ratio to source < 0.6. Reduces hallucinated classes.
- **Result:** Each class gets an updated `parent`. Then each extraction’s classes are updated with this parent map and merged via `update_graph`.

### 3.6 Graph storage (`ontology_builder.storage.graphdb`)

- **Structure:** `OntologyGraph` wraps a NetworkX `DiGraph`. Nodes: entity names. Node attributes: `type`, `kind` ("class" | "instance"), `description`, optional `synonyms`, `source_documents` (list). Edges: directed; edge data includes `relation`, `key`, `value`, `full` (OG-RAG factual block fields), `confidence`, `source_documents`.
- **Special relations:** `subClassOf` (class hierarchy), `type` (instance → class). Others are free-form (e.g. `part_of`, `related_to`).
- **Axioms and data properties:** Stored in `_axioms` and `_data_properties` lists; not as graph edges. Used by the reasoning engine (domain/range, disjointness) and for export.
- **Export:** `export()` returns node-link JSON plus `axioms`, `data_properties`, and stats (class count, instance count, edge count, etc.).

### 3.7 LLM relation inference (`ontology_builder.pipeline.relation_inferer`)

**EntityCandidate system:** `build_entity_candidates(graph)` assembles full context per entity (description, known relations, data properties, co-occurring entities). Used in prompts instead of raw graph JSON.

**Co-occurrence prioritization:** `build_cooccurrence_pairs(candidates, min_shared_chunks=2)` returns pairs sharing chunks, sorted by shared count; excludes pairs with existing relations. Inferred first before batch pass.

Two passes:

**Cross-component:** `infer_cross_component_relations(graph)`:
- Compute connected components; pick representative per non-largest; pair with largest.
- One LLM call with graph summary + pairs. Relations normalized via `normalize_relation_name()`.

**Batch relation inference:** `infer_relations(graph)`:
- Build candidates; prioritize co-occurring pairs; then batch inference with EntityCandidate profiles in prompt.
- Relation names normalized before merge. Deduplicated by (source, relation, target); vote-count bonus for 3+ batches.

### 3.8 OWL 2 RL reasoning (`ontology_builder.reasoning.engine`, `ontology_builder.reasoning.rules`)

- **Pre-reasoning:** `detect_relation_properties(graph)` auto-detects transitive/symmetric relations from graph structure (>3 open chains → transitive; >70% symmetric pairs → symmetric). Adds axioms; logs "Auto-detected transitivity/symmetry for relation: X".
- **Entry:** `run_inference(graph)` → `ReasoningResult(inferred_edges, consistency_violations, inference_trace, iterations)`.
- **Loop:** Up to `MAX_REASONING_ITERATIONS` (20). Each iteration applies: transitive subsumption, inheritance, domain/range propagation, transitive closure (from axioms + auto-detected), symmetric closure, inverse propagation.
- **Consistency:** `_check_disjointness` flags instances typed as both disjoint classes.
- **Trace:** Every added edge recorded in `inference_trace` (explainability).

### 3.9 Repair (`ontology_builder.repair.repairer`)

- **Config:** `RepairConfig`: similarity_threshold (0.75), max_orphan_links (5), max_component_bridges (50), add_root_concept (True), run_reasoning_after (True).
- **Steps:**
  1. **Root concept:** Add "Thing" if missing; link orphan classes to Thing via subClassOf.
  2. **Orphan linking (semantic):** Build combined text (description + data property values + relation targets). If non-empty, embed combined text; else fall back to name-only. Cosine ≥ 0.75 (semantic) or `similarity_threshold` (name-only). Link orphan to matched node's parent (subClassOf target) when available to preserve hierarchy.
  3. **Component bridging (multi-hop):** For each rep–target pair, find intermediate node with `(sim(node,A) + sim(node,B))/2 >= 0.6`. If found: add rep → intermediate → target (relatedTo). Else: direct bridge. Logs "Multi-hop bridge: A → intermediate → B".
  4. **Reasoning:** If `run_reasoning_after` and edges added, run `run_inference(graph)`.
- **Reporting:** `RepairReport`: edges_added, orphans_linked, components_bridged, health_before, health_after, inferred_edges.

---

## 4. Key Constants and Configuration

| Symbol | Location | Value | Role |
|--------|----------|--------|------|
| SIMILARITY_THRESHOLD | core.constants | 0.85 | Canonicalizer: merge entity names above this cosine similarity (configurable). |
| CONFIDENCE_THRESHOLD | core.constants | 0.5 | Relation inferer: accept LLM-inferred relations only if confidence ≥ this. |
| MAX_REASONING_ITERATIONS | core.constants | 20 | Cap on OWL 2 RL fixpoint iterations. |
| CHARS_PER_TOKEN | core.constants | 4 | Approximate token count for budget checks. |
| chunk_size / chunk_overlap | core.config | 2000 / 300 | Default chunking (semantic mode; overridable per model). |
| llm_max_chunk_chars | core.config | 600 | Hard truncation of chunk length for LLM (0 = no truncation). |
| llm_max_prompt_tokens | core.config | 3000 | Soft token budget for system+user in extraction. |
| llm_max_graph_chars | core.config | 3000 | Max graph JSON chars in inference prompts. |
| llm_max_taxonomy_chars | core.config | 2500 | Max classes JSON chars in taxonomy prompt. |
| llm_max_classes_json_chars | core.config | 1000 | Max classes JSON in stage 2/3. |
| llm_max_instances_json_chars | core.config | 800 | Max instances JSON in stage 3. |
| MODEL_NAME (embeddings) | ontology_builder.embeddings | all-MiniLM-L6-v2 | SentenceTransformer for canonicalizer and repair. |

---

## 5. Data Flow Summary

```
Document (file path)
  → load_document() → raw text
  → chunk_text(size, overlap) → list[str] chunks
  → [extract_ontology_sequential(chunk) per chunk] → list[OntologyExtraction]
  → build_taxonomy(all_classes, full_text) → class_parent_map
  → [update_graph(graph, ext) per extraction, with taxonomy parents] → OntologyGraph (post-merge)
  → infer_cross_component_relations(graph) → cross_rel → update_graph(..., cross_rel)
  → infer_relations(graph) → inferred → update_graph(..., inferred)
  → run_inference(graph) (OWL 2 RL fixpoint)
  → repair_graph(graph, RepairConfig()) (root, orphans, bridges, optional reasoning)
  → final OntologyGraph + PipelineReport
```

---

## 6. Design Decisions and Trade-offs (for improvement planning)

- **Chunking:** Sentence-boundary (default) with section detection; falls back to fixed window for very short docs. Overlap uses sentence budget.
- **Extraction:** Sequential 3-stage; Stage 1 adds salience/domain_tags; Stage 2 adds attributes→DataProperties; Stage 3 adds evidence/relation_type. Relation names normalized to canonical vocabulary.
- **Canonicalization:** Hybrid 3-stage (exact → token overlap 0.8 → embedding 0.9). Batched encoding. Obvious lexical matches (e.g. "Garen"/"garen") caught cheaply.
- **Taxonomy:** Single global LLM call; grounding check heuristic. Truncation by char limit may drop classes.
- **Inference:** EntityCandidate profiles provide full aggregated context; co-occurrence prioritizes pairs with textual evidence. Relation names normalized.
- **Reasoning:** Auto-detects transitive/symmetric from graph structure; disjointness reported, not repaired.
- **Repair:** Semantic orphan linking (description + props + relation targets); multi-hop component bridging when intermediate node exists. Orphan links to parent when match has subClassOf.

---

## 7. File Reference (for implementation changes)

| Concern | Primary files |
|--------|----------------|
| Pipeline orchestration | `ontology_builder.pipeline.run_pipeline` |
| Load | `ontology_builder.pipeline.loader` |
| Chunk | `ontology_builder.pipeline.chunker` |
| Extract (sequential + legacy) | `ontology_builder.pipeline.extractor` |
| Merge + canonicalize | `ontology_builder.pipeline.ontology_builder`, `ontology_builder.ontology.canonicalizer`, `ontology_builder.ontology.schema` (normalize_relation_name) |
| Taxonomy | `ontology_builder.pipeline.taxonomy_builder` |
| Schema (C, I, R, P, axioms) | `ontology_builder.ontology.schema` |
| Graph storage | `ontology_builder.storage.graphdb` |
| LLM prompts | `ontology_builder.llm.prompts` |
| Relation inference | `ontology_builder.pipeline.relation_inferer`, `ontology_builder.ontology.candidate` |
| OWL 2 RL reasoning | `ontology_builder.reasoning.engine`, `ontology_builder.reasoning.rules` |
| Repair | `ontology_builder.repair.repairer` |
| Embeddings | `ontology_builder.embeddings` |
| Config / constants | `core.config`, `core.constants` |

---

**End of document.** Use this to create a plan for improving the ontology graph build and generation pipeline (e.g. quality, scalability, robustness, explainability, or domain adaptation).
