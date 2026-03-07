# Ontology Graph: Load, Store, and Save — Technical Rundown

**Purpose:** This document provides a thorough breakdown of how ontology graphs are loaded, stored in memory, and saved to disk. It is intended for a reasoning model to analyze and elaborate a plan for **faster loading speeds**, especially for large graphs (e.g. 52MB JSON, 1.9M lines, 1169 nodes, 4199 relations, 2573 data properties).

**Reference graph:** `48b4cdedaae54059a460b2b96ddc42a4` (Reha, mobalytics-based) — too large to load and use comfortably.

---

## 1. File Layout and Storage Format

### 1.1 Directory Structure

```
documents/ontology_graphs/
├── .last_active              # Plain text: last active KB ID (for restore on startup)
├── {kb_id}.json              # Main graph data (compact node-link JSON, embeddings stripped)
├── {kb_id}.meta.json         # Metadata sidecar (name, description, stats, documents)
└── {kb_id}_index.npz         # QA index cache (embeddings, records) — optional, for fast activate
```

### 1.2 Main Graph File (`{kb_id}.json`)

**Format:** NetworkX node-link JSON, extended with ontology-specific fields.

**Top-level keys:**
- `directed`, `multigraph`, `graph` — NetworkX metadata (usually empty)
- `nodes` — Array of node objects
- `links` or `edges` — Array of edge objects (NetworkX uses `links` in node_link_data)
- `axioms` — Array of axiom dicts
- `data_properties` — Array of `{entity, attribute, value, datatype, source_documents?}`
- `stats` — `{classes, instances, relations, axioms, data_properties}` counts
- `embedding_cache` — **Not persisted** in saved JSON; embeddings stripped for compact export. QA index stores embeddings in `{kb_id}_index.npz`.

**Node structure (per node):**
```json
{
  "id": "EntityName",
  "type": "Class" | "Champion" | ...,
  "kind": "class" | "instance",
  "description": "...",
  "synonyms": ["...", "..."],
  "chunk_ids": [0, 2, 3, ...],
  "vote_count": 15,
  "source_documents": ["doc.md"]
}
```

**Link structure (per edge):**
```json
{
  "source": 0 | "EntityId",
  "target": 1 | "EntityId",
  "relation": "subClassOf" | "related_to" | ...,
  "key": "source: relation",
  "value": "target",
  "full": "source: relation -> target",
  "confidence": 1.0,
  "vote_count": 1,
  "chunk_ids": [...],
  "correctness_score": ...,
  "cross_chunk_votes": ...,
  "derivation_path_length": ...,
  "source_documents": [...]
}
```

### 1.3 Metadata File (`{kb_id}.meta.json`)

```json
{
  "id": "48b4cdedaae54059a460b2b96ddc42a4",
  "name": "Reha",
  "description": "Based on mobalytics",
  "created_at": 1772825337.75936,
  "stats": { "classes": 194, "instances": 709, "relations": 4199, "axioms": 370, "data_properties": 2573 },
  "documents": ["mobalytics-lol-guides-full.md"],
  "ontology_language": "en"
}
```

### 1.4 Size Characteristics (Reference Graph)

| Metric | Value |
|--------|-------|
| File size | ~52 MB |
| Line count | ~1,901,151 |
| Nodes | 1,169 |
| Links | 4,199 |
| Axioms | 370 |
| Data properties | 2,573 |
| Embedding cache entries | 1,169 |

**Note:** JSON is written in compact form (`separators=(',', ':')`) with embeddings stripped; QA index persisted to `{kb_id}_index.npz` for fast load.

---

## 2. Save Flow

### 2.1 Entry Points

- **After build:** `save_to_path_with_metadata()` — called when a new ontology is built or extended.
- **Location:** `ontology_builder.storage.graph_store`

### 2.2 Save Sequence

1. **Get export:** `data = get_export()` — returns node-link dict with embeddings stripped (`_strip_embeddings_for_export()` removes `embedding_cache` and node `embedding` attributes).
2. **Write JSON:** `path.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False), encoding="utf-8")`
   - Compact format (no indent) to reduce file size.
3. **Write metadata:** `save_to_path_with_metadata()` also writes `{kb_id}.meta.json` with stats, name, description, documents, etc.

### 2.3 Export Generation (`OntologyGraph.export()`)

**Location:** `ontology_builder.storage.graphdb.OntologyGraph.export()`

```python
data = nx.node_link_data(self.graph)
data["axioms"] = self._axioms
data["data_properties"] = self._data_properties
data["stats"] = { ... }
# embedding_cache NOT included in saved JSON; stripped by _strip_embeddings_for_export()
return data
```

- NetworkX `node_link_data()` converts the DiGraph to a dict with `nodes` and `links`.
- For API responses, `get_export_for_api()` strips embeddings; for save, `_strip_embeddings_for_export()` removes `embedding_cache` and node `embedding` / `*_embedding` attributes.

---

## 3. Load Flow

### 3.1 Entry Points

| Context | Function | File |
|---------|----------|------|
| App startup (restore last KB) | `load_from_path(path)` | `app.main` lifespan |
| Activate KB (sidebar) | `load_from_path(path)` | `ontology_builder.ui.api.activate_kb` |
| Extend KB (merge new docs) | `load_from_path(kb_path)` | `ontology_builder.ui.api` extend endpoint |
| QA ask (different KB) | `load_from_path(path)` | `ontology_builder.ui.api.qa_ask` |
| Graph viewer | `load_from_path(path)` | `ontology_builder.ui.api.graph_viewer` |
| Health / evaluate | `load_from_path(path, seed_canonicalizer=False)` | `ontology_builder.ui.api`, `evaluation` |
| Repair CLI | `load_from_path(path)` | `ontology_builder.repair.__main__` |

### 3.2 Load Sequence (`load_from_path`)

**Location:** `ontology_builder.storage.graph_store.load_from_path(path, seed_canonicalizer=True)`

```
1. data = json.loads(path.read_text(encoding="utf-8"))   # Parse entire file into memory
2. graph = _graph_from_export(data)                      # Reconstruct OntologyGraph
3. if seed_canonicalizer:
       entity_names = list(graph.get_graph().nodes())
       seed_from_entities(entity_names)                   # Pre-populate canonicalizer cache
4. return graph
```

### 3.3 Graph Reconstruction (`_graph_from_export`)

**Location:** `ontology_builder.storage.graph_store._graph_from_export(data)`

**Order of operations:**

1. **Nodes:** `graph._loading_mode = True`; for each node, `graph.add_entity(...)`. `add_entity` **skips encoding** when `_loading_mode` is True — no redundant encodes.
2. **Relations:** Build `relations_to_add`, then `graph.add_relations_batch(relations_to_add)`.
3. **Axioms:** `graph.add_axiom(axiom)` for each axiom.
4. **Embedding cache:** Restored from `data["embedding_cache"]` if present. Saved JSON has embeddings stripped, so cache is empty on load; graph works without it (canonicalizer/repair use their own models).
5. **Data properties:** `graph.add_data_property(...)` for each.
6. **Done:** `graph._loading_mode = False`.

### 3.4 Post-Load: Canonicalizer Seeding (`seed_from_entities`)

**Location:** `ontology_builder.ontology.canonicalizer.seed_from_entities(entity_names, kind="entity")`

- **Purpose:** Pre-populate the canonicalizer cache so that future enrichment (e.g. extending the KB) matches against existing entities.
- **Cost:** One `model.encode(normalized_name)` call **per entity** (1,169 calls for the reference graph).
- **When skipped:** `seed_canonicalizer=False` for read-only operations (health, evaluate) to avoid this cost.

### 3.5 Post-Load: QA Index Build (`build_qa_index`)

**Location:** `ontology_builder.qa.graph_index.build_index(graph, verbose)`

**Triggered after load by:**
- App startup (background task)
- `activate_kb` (blocking)
- `qa_ask` when switching KB (blocking)
- Extend KB (blocking)

**What it does:**
1. **Load from cache (if present):** If `kb_path` provided and `{kb_id}_index.npz` exists, load from disk → skip recomputation (near-instant activate).
2. **Otherwise build from scratch:**
   - `_graph_to_records(graph)` — Build records from nodes + edges + data properties (relation records append `" | Evidence: {evidence}"` when available).
   - `_build_hyperedges(records)` — Group records by node for OG-RAG.
   - `build_hypergraph(factual_blocks)` — Build hypergraph structure.
   - **Encode records:** Batches of `ENCODE_BATCH_SIZE` (64); dual retrieval (key + value).
   - Persist to `{kb_id}_index.npz` when `kb_path` provided.

**Note:** The QA index does **not** reuse the graph’s `embedding_cache` — it encodes different strings (e.g. `"EntityName type"`, `"EntityName relation"`) for retrieval.

### 3.6 QA Index Build — Log Pipeline Rundown

When building the QA index from scratch, logs appear in this order:

| Step | Log | Meaning |
|------|-----|---------|
| 1 | `[QAIndex] Building index from graph \| nodes=N \| edges=E` | Start; graph has N nodes, E edges |
| 2 | `[QAIndex] Converted to R retrieval records` | Graph → records (nodes + edges + data properties) |
| 3 | `[Hypergraph] Hypergraph structure ready \| hypernodes=H \| hyperedges=G (OG-RAG; embedding encoding next)` | OG-RAG hypergraph built; **not** the final index — slow encoding follows |
| 4 | `[QAIndex] Encoding R records (key + value embeddings, B batches)...` | Start of embedding encoding; this is the slow step (1–3 min for 5000+ records) |
| 5 | `[QAIndex] Index ready \| records=R \| hyperedges=G` | Embedding encoding done; index is ready for retrieval |
| 6 | `[QAIndex] Persisted to disk \| {kb_id}_index.npz` | Index saved (if `kb_path` provided) |
| — | `[QAIndex] Loaded from cache \| {kb_id}_index.npz` | Index loaded from disk; skip recomputation |

**When cache exists:** `build_index` loads `_index.npz` and skips steps 2–5; logs "QA index loaded from cache, skipping recomputation".

---

## 4. In-Memory Representation

### 4.1 Graph Store (Module-Level Globals)

**Location:** `ontology_builder.storage.graph_store`

| Variable | Type | Description |
|----------|------|-------------|
| `_current_graph` | `OntologyGraph \| None` | Active graph instance |
| `_current_export` | `dict \| None` | Cached node-link export (for save, API responses) |
| `_document_subject` | `str \| None` | Optional domain/subject |
| `_current_kb_id` | `str \| None` | Active KB ID |

### 4.2 OntologyGraph Structure

**Location:** `ontology_builder.storage.graphdb.OntologyGraph`

- **`self.graph`:** NetworkX `DiGraph` — nodes are entity IDs, edges carry relation metadata.
- **`self._axioms`:** List of axiom dicts.
- **`self._data_properties`:** List of data property dicts.
- **`self.embedding_cache`:** `dict[str, np.ndarray]` — node name → embedding vector.

### 4.3 QA Index (Module-Level)

**Location:** `ontology_builder.qa.graph_index`

- `_records`, `_key_embeddings`, `_value_embeddings`, `_node_to_record_indices`, `_hyperedges`, `_graph_ref`, `_hypergraph_ref`.

---

## 5. Identified Bottlenecks (for Load Speed)

### 5.1 I/O and Parsing

- **Single `path.read_text()`:** Entire file read into a string.
- **`json.loads()`:** Full parse — CPU-bound, no streaming.
- **Compact JSON:** Saved with `separators=(',', ':')` (no indent) to reduce file size and parse time.

### 5.2 Redundant Embedding During Load

- **Addressed:** Embeddings are stripped from saved JSON; `embedding_cache` is not persisted. QA index is persisted to `{kb_id}_index.npz` and loaded from cache when present, avoiding rebuild on activate.

### 5.3 Canonicalizer Seeding

- **1,169 `model.encode()` calls** when `seed_canonicalizer=True` (default for most load paths).
- Each call is individual (no batching in `seed_from_entities`).
- **Fix idea:** Batch encode in `seed_from_entities`, or make it lazy/on-demand for extend-only flows.

### 5.4 QA Index Build

- **Addressed:** QA index persisted to `{kb_id}_index.npz`; on activate, if file exists, load from cache (near-instant). Rebuild only when extending or when cache missing.

### 5.5 Sequential Processing

- Nodes added one-by-one; relations in batches but still sequential.
- No parallelization of JSON parsing, graph construction, or embedding.

### 5.6 Memory Pressure

- Full graph + export + QA index + embeddings held in memory.
- For 52MB JSON, parsed structure can be 2–3× larger in memory; embeddings add more.

---

## 6. Data Flow Summary

```
SAVE:
  OntologyGraph.export() → _strip_embeddings_for_export() (remove embedding_cache, node embeddings)
  → json.dumps(data, separators=(',', ':'), ensure_ascii=False)
  → path.write_text(...)
  → .meta.json written separately
  → build_index persists to {kb_id}_index.npz when kb_path provided

LOAD:
  path.read_text() → json.loads() → _graph_from_export()
    → add_entity × N → add_relations_batch → add_axiom × A → add_data_property × D
  → seed_from_entities (batch encode) if seed_canonicalizer
  → build_index: load from {kb_id}_index.npz if present, else rebuild and persist
```

---

## 7. Key Files Reference

| Purpose | File |
|---------|------|
| Load / save / store | `ontology_builder/storage/graph_store.py` |
| Graph structure, export, add_entity | `ontology_builder/storage/graphdb.py` |
| Canonicalizer, seed_from_entities | `ontology_builder/ontology/canonicalizer.py` |
| QA index build | `ontology_builder/qa/graph_index.py` |
| Startup, activate KB | `app/main.py`, `ontology_builder/ui/api.py` |

---

## 8. Suggested Directions for a Load-Speed Plan

1. ~~**Avoid redundant node encoding:**~~ Embeddings stripped from JSON; QA index in `_index.npz`.
2. ~~**Compact JSON:**~~ Implemented: `separators=(',', ':')`.
3. **Streaming / chunked JSON:** Use `ijson` or similar for incremental parse if full-doc parse is too slow.
4. **Lazy or batched canonicalizer seeding:** Batch encode in `seed_from_entities`, or defer until first extend.
5. ~~**Persist QA index:**~~ Implemented: `{kb_id}_index.npz`; load on activate when present.
6. **Parallelization:** Parallel node/edge processing where safe; parallel encode batches.
7. **Binary format:** Consider MessagePack, Parquet, or custom binary for faster load than JSON.
8. **Subgraph loading:** For viewer/QA, load only required subgraph (e.g. by depth) instead of full graph.
