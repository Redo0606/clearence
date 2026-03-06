# UI Implementation Plan — Plan 2 (P2-9 to P2-15)

Follow this plan in order. Backend and API are already implemented; this document covers **frontend only**.

---

## Context: What’s Already Done

- **Plan 1** (chunking, canonicalizer, extraction, taxonomy, relation inference, OWL reasoning, repair, answer generator, embedding cache, provenance, domain profiles) is implemented.
- **Plan 2 backend** (P2-1–P2-8) is implemented:
  - `ontology_builder/quality/` — structural scorer, reliability score, relation evaluator, consistency checker, hierarchy enricher, population booster, `OntologyQualityReport`.
  - Pipeline calls quality steps after repair and sets `report.quality`.
  - `PipelineReportResponse` and `_build_report_dict()` include `quality` (structural_metrics, reliability_score, relation_scores_top20, consistency_report, recommended_actions, etc.).
- **SSE streaming** already emits steps: `load`, `load_done`, `chunk`, `chunk_done`, `extract`, `merge_done`, `taxonomy`/`taxonomy_done`, `inference`/`inference_done`, `reasoning`/`reasoning_done`, `repair` (with `phase`), `repair_done`, and now `quality` / `quality_done` (with `grade`, `score`).

**Key files:**

| Purpose | Path |
|--------|------|
| HTML shell, sidebar, modals | `ontology_builder/ui/chat_ui.py` |
| Frontend logic, jobs, SSE, job detail modal | `ontology_builder/ui/static/js/app.bundle.js` |
| API, SSE events, pipeline_report.quality | `ontology_builder/ui/api.py` |
| Theme (yellow secondary `#EAB308`) | `ontology_builder/ui/theme.py` |
| CSS (status badges, cards) | `ontology_builder/ui/static/css/components.css`, `base.css`, `layout.css` |
| Graph viewer (node/edge selection) | `ontology_builder/ui/graph_viewer.py` (if relation table / detail panel need graph integration) |

**Data available after pipeline complete:**

- `job.pipeline_report.quality` (when present):
  - `quality.structural_metrics` — depth_variance, breadth_variance, max_depth, max_breadth, instance_to_class_ratio, named_relation_ratio, num_classes, num_instances, etc.
  - `quality.reliability_score` — score, grade (A–F), reasons[]
  - `quality.relation_scores_top20` — [{ source, relation, target, correctness_score }, ...]
  - `quality.consistency_report` — is_consistent, critical_count, warning_count (and backend has full critical_conflicts / warning_conflicts with entity_a, entity_b, suggested_resolution)
  - `quality.recommended_actions` — string[]
- Repair report (from pipeline or repair endpoint): edges_added, orphans_linked, components_bridged, health_before, health_after. Plan 1 also has `health_report_before` / `health_report_after` with total_nodes, total_edges, orphan_count, component_count, orphan_ratio, repair_target_met (on `RepairReport` from repair endpoint; for build stream the same data may be in `report.quality` or needs to be added to the complete event if you want Repair Health in the dashboard).

---

## Step 1 — Pipeline stage progress bar (P2-9)

**Goal:** One row per stage with status tag and optional count badge. Stages: Load → Chunk → Extract → Taxonomy → Merge → Infer → Reason → Repair → Quality.

**Where:**

- Reuse/extend the existing “Pipeline Breakdown” list in the job detail modal (`app.bundle.js`: `showJobDetailModal`, the `<ol>` with steps 1–7). Add **step 8. Quality** and ensure all 9 stages are represented.
- Optionally add a **compact pipeline progress bar** on the job card (not only in the modal): e.g. 9 small pills or a single bar with 9 segments that fill as steps complete.

**Details:**

- Status tag colors: **Pending** = gray, **Running** = yellow (`#EAB308` / `var(--accent-secondary)`), **Done** = green, **Warning** = amber, **Error** = red (use existing CSS vars: `--success`, `--warning`, `--error-bright`).
- For **Extract**, show sub-step labels `[Classes]` `[Instances]` `[Relations]` if you have per-stage progress (backend currently sends `extract` with chunk index; you could add sub-step in progress_callback if needed).
- For **Repair**, show sub-steps `[Incremental]` `[Orphans]` `[Bridges]` `[Missing Rels]` when `progress.repair` has `phase` (e.g. `phase: "orphans"`).
- Once a step is done, show a **count badge** next to the label (e.g. “Extract ✓  47 classes · 112 instances · 203 relations”) using `report.totals` / `report.extraction_totals` and repair stats from `progress.repair_done`.
- Backend already emits step transitions via existing `progress_callback`; ensure **quality** and **quality_done** are handled in the same way as other steps (e.g. in the step label map and in the pipeline breakdown list).

**Files to edit:** `ontology_builder/ui/static/js/app.bundle.js` (and optionally `ontology_builder/ui/chat_ui.py` if you add a new container for the compact bar).

---

## Step 2 — Graph Health Dashboard panel (P2-10)

**Goal:** After pipeline completion, show a “Graph Health” panel with (1) **Repair Health** and (2) **Structural Quality**.

**Where:**

- Add a new section in the job detail modal below “Pipeline Breakdown”, or a separate “Health” tab/card that appears when `job.pipeline_report.quality` exists.
- If the ontology viewer has a dedicated “after build” view, the dashboard can also live there.

**Repair Health (from Plan 1):**

- Data: repair report (e.g. from `/knowledge-bases/{id}/repair` response or from build stream). If the build stream does not currently send `health_report_before` / `health_report_after`, you can either (a) add them to the pipeline complete event (backend already computes them in `repair_graph`), or (b) show only what’s in `report.quality.structural_metrics` (total_nodes, total_edges) and derive orphan_ratio/component_count from quality if exposed there.
- Four stat cards: **Total Nodes**, **Total Edges** (with optional “+N from repair” if you have before/after), **Orphan Ratio** (%), **Components** (count). Color rules: orphan ratio green &lt; 5%, amber 5–15%, red &gt; 15%; components green ≤ 3, amber 4–10, red &gt; 10.
- **Repair Target** badge: “✓ Target Met” (green) or “⚠ Target Not Met” (amber) from `repair_target_met`.
- Small table: Orphans Linked, Bridges Added, Missing Relations Added, Inferred Edges (from repair report).

**Structural Quality (from Plan 2):**

- **Reliability Grade** badge: letter A/B/C/D/F + numeric score (e.g. “B · 0.72”). Colors: A=green, B=teal, C=yellow, D=orange, F=red.
- Six metric bars with threshold tick and color:
  - Depth Variance — green ≥ 0.9, amber ≥ 0.5, red &lt; 0.5
  - Breadth Variance — green ≥ 20, amber ≥ 5, red &lt; 5
  - Max Depth — green ≥ 5, amber ≥ 3, red &lt; 3
  - Max Breadth — green ≥ 100, amber ≥ 30, red &lt; 30
  - Instance/Class Ratio — green ≥ 1.0, amber ≥ 0.3, red &lt; 0.3
  - Named Relation Ratio — green ≥ 0.3, amber ≥ 0.15, red &lt; 0.15
- Collapsible **Score breakdown**: list `quality.reliability_score.reasons` with ✓ for positive and ✗ for penalties.

**Files to edit:** `ontology_builder/ui/static/js/app.bundle.js` (and possibly `ontology_builder/ui/chat_ui.py` for a new panel container). Use existing CSS vars and component patterns from `components.css`.

---

## Step 3 — Relation Quality table (P2-11)

**Goal:** A table of edges with correctness score, votes, path, and origin. Shown as a tab or section in the ontology viewer / job detail.

**Data:**

- Edges with attributes: from graph export or from a dedicated API. Backend writes `correctness_score`, `cross_chunk_votes`, `derivation_path_length` onto edges and provenance (origin, rule) is on the edge. So you need either (a) graph export in the build response / KB detail that includes link attributes (correctness_score, cross_chunk_votes, derivation_path_length, provenance), or (b) an API that returns edges with these fields (e.g. from `graph.export()` links + node_link_data edge attributes).
- Top-20 summary is in `report.quality.relation_scores_top20`; for full table you need the full graph’s edges with attributes.

**Columns:**

- Source (clickable), Relation (colored tag), Target (clickable)
- Correctness: mini bar 0–1, green/amber/red by score, tooltip with value
- Votes: badge “N×” for cross_chunk_votes
- Path: “direct” (path=1) or “inferred ×N” (path&gt;1)
- Origin: pill by provenance.origin — extraction, inference_llm, inference_owl, repair, enrichment

**Relation tag colors:** subClassOf=blue, instanceOf=purple, part_of/depends_on/causes=teal, related_to=gray, produces/uses/has_property/precedes=indigo.

**Default sort:** correctness_score descending.

**Filters:** relation type (multi-select), origin (checkboxes), “Show low-confidence only” (&lt; 0.3), “Show generic relations only” (related_to).

**Summary row:** total edges, avg correctness, % direct, % inferred, % from repair (derive from edge list).

**Files to edit:** `ontology_builder/ui/static/js/app.bundle.js` (new table component or section), and ensure graph export or API returns edge attributes. If graph is only in node-link form, parse `links` and use `relation`, `correctness_score`, `cross_chunk_votes`, `provenance` from each link object.

---

## Step 4 — Consistency Conflict alert panel (P2-12)

**Goal:** If there are critical relation conflicts, show a red banner; clicking it opens a conflict panel with list and suggested resolution.

**Data:**

- `quality.consistency_report.critical_count` / `warning_count`. Full conflict list is in the backend; if not in the API response, add an endpoint or include `critical_conflicts` and `warning_conflicts` in `quality.consistency_report` in the pipeline report (backend already has `ConsistencyReport` with those lists).
- Each conflict: conflict_type, entity_a, entity_b, relation_a, relation_b, severity, suggested_resolution.

**UI:**

- Red banner at top of ontology viewer / job summary: “⚠ N critical relation conflicts detected — review before use”. Click opens panel.
- Panel: list of conflict cards (red header for CRITICAL, amber for WARNING), entity pair, suggested resolution in gray box, buttons “Resolve Auto” (call backend to run auto_resolve_critical and refresh) and “Ignore”.
- Collapsible Warnings section for warning-level conflicts.
- When no conflicts (or all resolved/ignored): show “✓ No conflicts” green tag.
- In the Reliability Grade badge (Step 2), if critical_conflicts &gt; 0, cap displayed grade at C and add “⚠ conflicts” footnote.

**Files to edit:** `ontology_builder/ui/static/js/app.bundle.js`, `ontology_builder/ui/chat_ui.py` (banner + panel container). Backend: optionally add `critical_conflicts` / `warning_conflicts` to `OntologyQualityReport.to_dict()` and to the API response if not already there, and an endpoint POST `/knowledge-bases/{id}/resolve-conflicts` that sets `auto_resolve_critical=True`, re-runs consistency, and returns updated report.

---

## Step 5 — Recommended Actions feed (P2-13)

**Goal:** Show `quality.recommended_actions` as an actionable list after pipeline completion.

**Data:** `report.quality.recommended_actions` — array of strings (e.g. “Enable population booster (Plan 2 Step P2-5)”).

**UI:**

- Widget (sidebar or post-processing section) that renders each action as a card: icon (🔧 config, 🔁 re-run, ⚠ conflict, 📊 metric), title, optional “Apply & Re-run” button, “Learn more” expandable.
- Group by severity: Critical (red border), Recommended (amber), Optional (gray). You can infer from action text (e.g. “critical” → Critical, “Enable …” → Recommended).
- When `recommended_actions` is empty, show “0 actions needed” green state.
- “Apply & Re-run”: for actions that map to a known config (e.g. “Enable population booster” → set a flag and trigger repair or a partial re-run). Backend may need a small endpoint that accepts flags and re-runs only enrichment/booster/repair if you want to avoid full re-build.

**Files to edit:** `ontology_builder/ui/static/js/app.bundle.js`, optionally `ontology_builder/ui/chat_ui.py`. Reuse existing card/button styles.

---

## Step 6 — Enrichment & population progress (P2-14)

**Goal:** When hierarchy enrichment or population booster runs, show progress and resulting metric deltas.

**Data:** Backend already emits `enrichment` and `population` steps and then `quality_done` with updated grade/score. Optionally add to progress payload: `enrichment_added`, `boost_added`, and before/after metrics (e.g. depth_variance, instance_ratio) so the UI can show “+N subClassOf edges · depth_variance 0.31 → 0.87” and “+N instances · instance ratio 0.21 → 0.64”.

**UI:**

- In the pipeline progress (Step 1), add two optional rows when present: **Hierarchy Enrichment** (sub-steps Cluster / LLM / Apply, then delta text) and **Population Boost** (sub-steps Find sparse / LLM / Merge, then delta text).
- In the graph stats header, animate count increments when new nodes/edges are added (optional).
- In the metric bars (Step 2), after enrichment/boost, re-render with animation and show “↑ improved” next to metrics that improved by &gt; 10%.

**Files to edit:** `ontology_builder/ui/static/js/app.bundle.js`. Backend: ensure `progress_callback("enrichment", ...)` and `progress_callback("population", ...)` (and optionally a final step with deltas) are emitted from `run_pipeline`.

---

## Step 7 — Node & edge detail panel with provenance (P2-15)

**Goal:** When a node or edge is selected in the graph viewer, show provenance and quality in the detail panel.

**Node panel:**

- Kind (Class/Instance), source (chunk/document if stored), degree (in/out), optional “embedding similarity to nearest neighbour” if you expose it, list of up to 5 edges with relation type and correctness score, and if the node was added by repair an amber “⚙ Repair” tag with sub-type.

**Edge panel:**

- Relation type (colored tag), correctness score bar, cross-chunk votes, derivation path (direct / inferred ×N), origin pill (extraction, inference_llm, inference_owl, repair, enrichment), confidence. If origin is repair, show which sub-step (orphan_link, component_bridge, etc.); if inference_owl, show rule name.
- “Flag as incorrect” button: mark for review and add to a user-flagged list (could be sent to backend or stored in UI state and shown in Consistency panel as WARNING).

**Data:** Node/edge attributes from the graph viewer’s selection (graph is from export; ensure export includes node and link attributes: description, kind, degree if computed, and for links: relation, confidence, correctness_score, cross_chunk_votes, derivation_path_length, provenance).

**Files to edit:** `ontology_builder/ui/graph_viewer.py` (if detail panel is there) and/or `ontology_builder/ui/static/js/app.bundle.js` if the graph is rendered in JS and selection is handled there. Align with existing graph viewer selection and tooltip/panel behavior.

---

## Checklist summary

| Step | Title | Main files |
|------|--------|------------|
| 1 | Pipeline stage progress bar (P2-9) | `app.bundle.js`, optional `chat_ui.py` |
| 2 | Graph Health Dashboard (P2-10) | `app.bundle.js`, `chat_ui.py` |
| 3 | Relation Quality table (P2-11) | `app.bundle.js`, graph/API edge data |
| 4 | Consistency Conflict panel (P2-12) | `app.bundle.js`, `chat_ui.py`, optional API |
| 5 | Recommended Actions feed (P2-13) | `app.bundle.js`, `chat_ui.py` |
| 6 | Enrichment & population progress (P2-14) | `app.bundle.js`, backend progress payload |
| 7 | Node/edge detail panel (P2-15) | `graph_viewer.py` and/or `app.bundle.js` |

Implement in this order so the job detail modal and pipeline report data (including `quality`) are used consistently across steps.
