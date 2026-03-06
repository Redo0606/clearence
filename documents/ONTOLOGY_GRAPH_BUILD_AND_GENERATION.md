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

- **C (Classes):** Concepts/universals. Model: `OntologyClass(name, parent, description, synonyms)`.
- **I (Instances):** Individuals/particulars typed by a class. Model: `OntologyInstance(name, class_name, description)`.
- **R (Object properties):** Binary relations. Model: `ObjectProperty(source, relation, target, domain, range, symmetric, transitive, confidence)`.
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

- **Function:** `chunk_text(text, size=settings.chunk_size, overlap=settings.chunk_overlap)`.
- **Algorithm:** Sliding window: start at 0, take `size` chars, then advance by `size - overlap`. Overlap is capped so `overlap < size`.
- **Defaults:** `chunk_size=1200`, `chunk_overlap=200` (from `core.config.Settings`). For gpt-4o-mini, config can override to 10000/2000.
- **Rationale:** Overlap reduces boundary effects (entities/relations split across chunks). Chunk size trades context quality vs. number of LLM calls.

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
- **Canonicalization:** Before adding, every entity name (class, instance, relation endpoint) is passed through `canonicalize(name)` in `ontology_builder.ontology.canonicalizer`:
  - Embedding: `get_embedding_model()` (SentenceTransformer `all-MiniLM-L6-v2`) encodes the name.
  - Cache: In-memory `entity_vectors: dict[str, np.ndarray]` stores one vector per canonical name.
  - Rule: If cosine similarity between the new name’s vector and any cached vector ≥ `SIMILARITY_THRESHOLD` (0.9, in `core.constants`), the existing canonical name is returned; otherwise the new name is added to the cache and returned. Thread-safe via a module-level lock.
- **Effect:** Reduces duplicate nodes for paraphrased or typo-variant names (e.g. "Vehicle" vs "Vehicles") at the cost of depending on embedding quality and threshold.

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

Two passes:

**Cross-component:** `infer_cross_component_relations(graph)`:
- Compute connected components of the undirected version of the graph.
- If there is more than one component: pick a representative (max degree) from the largest component and from up to `CROSS_COMPONENT_MAX_PAIRS` (30) other components; form pairs (rep_small, rep_largest).
- One LLM call with `CROSS_COMPONENT_INFERENCE_PROMPT`: graph summary (truncated to `_get_effective_max_graph_chars`, larger for graphs with >500 nodes) + list of pairs. Asks for relations that could connect these pairs.
- Parsed relations (source, relation, target, confidence) are added to the graph via `update_graph`.

**Batch relation inference:** `infer_relations(graph)`:
- Entities = instances if any, else classes. Partition into batches (size chosen so that with `get_llm_parallel_workers()` workers we cover all entities). Batches are stratified by connected component so each batch mixes entities from different components.
- For each batch, LLM call with `INFERENCE_PROMPT` + full graph text (truncated) + "Focus on inferring relations involving these entities: ...".
- `complete_batch` runs these calls in parallel (workers: 2 for local LLM, 30 for cloud).
- Responses parsed for `relations` array; only relations with `confidence >= CONFIDENCE_THRESHOLD` (0.5) and non-empty source/target are kept. Deduplicated by (source, relation, target) and merged into the graph.

### 3.8 OWL 2 RL reasoning (`ontology_builder.reasoning.engine`, `ontology_builder.reasoning.rules`)

- **Entry:** `run_inference(graph)` → `ReasoningResult(inferred_edges, consistency_violations, inference_trace, iterations)`.
- **Loop:** Up to `MAX_REASONING_ITERATIONS` (20). Each iteration applies in order:
  1. **Transitive subsumption:** If A subClassOf B and B subClassOf C, add A subClassOf C (transitive closure on subClassOf edges).
  2. **Inheritance:** If A subClassOf B and x type A, add x type B.
  3. **Domain/range propagation:** From axioms (axiom_type domain/range), for each edge with that relation, add type edges for source (domain) or target (range).
  4. **Transitive closure:** For relation names in `TRANSITIVE_RELATIONS` (e.g. part_of, depends_on, subClassOf, has_part), compute transitive closure and add missing edges.
  5. **Symmetric closure:** For relation names in `SYMMETRIC_RELATIONS` (e.g. related_to, equivalent_to), add reverse edges where missing.
- **Consistency:** After fixpoint, `_check_disjointness`: for each disjointness axiom (C1, C2), flag any instance typed as both C1 and C2; append to `consistency_violations` (no automatic removal).
- **Trace:** Every added edge is recorded in `inference_trace` with rule type and description (explainability).

### 3.9 Repair (`ontology_builder.repair.repairer`)

- **Config:** `RepairConfig`: similarity_threshold (0.75), max_orphan_links (5), max_component_bridges (50), add_root_concept (True), run_reasoning_after (True), optional small_component_threshold and bridge_similarity_threshold.
- **Steps:**
  1. **Root concept:** If node "Thing" is missing, add it as a class. Link every class that has degree 0 (and ≠ Thing) to Thing via subClassOf (confidence 0.85, source_document "inferred").
  2. **Orphan linking:** Nodes with degree 0 (orphans). Encode orphan names+descriptions and connected nodes with SentenceTransformer; compute cosine similarity matrix. For each orphan, link to up to `max_orphan_links` most similar connected nodes with similarity ≥ threshold using relation "related_to".
  3. **Component bridging:** Undirected connected components. For each non-largest component (or only those smaller than `small_component_threshold` if set), pick representative (max degree), encode rep and all nodes in largest component; link rep to best match in largest component if similarity ≥ threshold (or lower threshold when components > 20). Cap total bridges by `max_component_bridges`.
  4. **Reasoning:** If `run_reasoning_after` and any edges were added, run `run_inference(graph)` again and add inferred edges to the report.
- **Reporting:** `RepairReport`: edges_added, orphans_linked, components_bridged, health_before, health_after, inferred_edges.

---

## 4. Key Constants and Configuration

| Symbol | Location | Value | Role |
|--------|----------|--------|------|
| SIMILARITY_THRESHOLD | core.constants | 0.9 | Canonicalizer: merge entity names above this cosine similarity. |
| CONFIDENCE_THRESHOLD | core.constants | 0.5 | Relation inferer: accept LLM-inferred relations only if confidence ≥ this. |
| MAX_REASONING_ITERATIONS | core.constants | 20 | Cap on OWL 2 RL fixpoint iterations. |
| CHARS_PER_TOKEN | core.constants | 4 | Approximate token count for budget checks. |
| chunk_size / chunk_overlap | core.config | 1200 / 200 | Default chunking (overridable per model, e.g. 10000/2000 for gpt-4o-mini). |
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

- **Chunking:** Fixed character window; no semantic/sentence boundaries. Overlap mitigates split entities but does not guarantee alignment with sentences or paragraphs.
- **Extraction:** Sequential 3-stage reduces confusion between classes and instances and gives explicit taxonomy input to relations stage; cost is 3× LLM calls per chunk. Legacy single-shot is faster but noisier.
- **Canonicalization:** Embedding-based only; no string normalization (e.g. lowercasing, stemming) before embedding. Threshold 0.9 is strict; lower values increase merge risk.
- **Taxonomy:** Single global LLM call over all classes; grounding check is heuristic (substring + token + SequenceMatcher). Truncation by char limit may drop classes from hierarchy.
- **Inference:** Graph serialized to JSON and truncated; large graphs may lose structure. Cross-component pass is limited to 30 pairs; batch inference focuses on entities, not full structure.
- **Reasoning:** Only declared relation names get transitive/symmetric closure; no automatic detection from axioms. Disjointness only reported, not repaired.
- **Repair:** Same embedding model as canonicalizer; "related_to" is generic. Root "Thing" is fixed name; no customization. Orphan/bridge thresholds are global, not domain-adaptive.

---

## 7. File Reference (for implementation changes)

| Concern | Primary files |
|--------|----------------|
| Pipeline orchestration | `ontology_builder.pipeline.run_pipeline` |
| Load | `ontology_builder.pipeline.loader` |
| Chunk | `ontology_builder.pipeline.chunker` |
| Extract (sequential + legacy) | `ontology_builder.pipeline.extractor` |
| Merge + canonicalize | `ontology_builder.pipeline.ontology_builder`, `ontology_builder.ontology.canonicalizer` |
| Taxonomy | `ontology_builder.pipeline.taxonomy_builder` |
| Schema (C, I, R, P, axioms) | `ontology_builder.ontology.schema` |
| Graph storage | `ontology_builder.storage.graphdb` |
| LLM prompts | `ontology_builder.llm.prompts` |
| Relation inference | `ontology_builder.pipeline.relation_inferer` |
| OWL 2 RL reasoning | `ontology_builder.reasoning.engine`, `ontology_builder.reasoning.rules` |
| Repair | `ontology_builder.repair.repairer` |
| Embeddings | `ontology_builder.embeddings` |
| Config / constants | `core.config`, `core.constants` |

---

**End of document.** Use this to create a plan for improving the ontology graph build and generation pipeline (e.g. quality, scalability, robustness, explainability, or domain adaptation).
