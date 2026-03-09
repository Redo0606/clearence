# Evaluate Tab UI Unification Plan — Codebase Evaluation

**Date:** 2025-03-07  
**Spec:** Clearence v0.1.0 · FastAPI + Jinja2 · `ontology_builder/ui/`  
**Evaluated against:** Current codebase state

---

## Executive Summary

The UI unification plan is **well-structured and aligns with Clearence's architecture**, but several **API/response mismatches**, **theme conflicts**, and **SSE protocol differences** require adaptation before implementation. The plan can be implemented with targeted adjustments; it does not require a full rewrite.

| Area | Verdict | Action |
|------|---------|--------|
| Theme system | ⚠️ Partial conflict | Map new vars to existing palette or add aliases |
| components.css | ✅ Additive | Extend with spec classes; avoid breaking existing |
| API layer | ⚠️ Gaps | Add response adapters or extend API responses |
| HTML structure | ✅ Feasible | Refactor Evaluate tab to use shared components |
| JavaScript | ⚠️ Protocol fix | Use fetch+stream for evaluate (not EventSource) |
| Modals | ✅ Feasible | Add new modals; reuse existing `.modal-overlay` pattern |

---

## Part 1 — Theme System (`theme.py`)

### Current State

- `get_css_root_block()` dynamically generates `:root` from `get_theme()` (dict → CSS vars).
- Palette: **Gold** (#f8c630), **Magenta** (#b81365), **Ice blue** (#b1ddf1), **Void** (#25171a).
- Variables: `--accent`, `--success`, `--info`, `--warning`, `--error`, `--pending`, `--text-primary`, etc.
- No `--pink`, `--cyan`, `--yellow`, `--green`, `--red`, `--blue` as semantic colors.
- No `--badge-bg-*`, `--accent-expanding`, `--accent-complete`, etc.

### Spec vs. Codebase

| Spec variable | Current equivalent | Notes |
|---------------|-------------------|-------|
| `--pink` | `--accent` | Different hex (#E8186D vs #b81365) |
| `--green` | `--success` (ice blue) | Spec uses green for success; codebase uses ice blue |
| `--yellow` | `--info` / `--accent-secondary` | Spec yellow ≈ gold |
| `--red` | `--error` | Different hex |
| `--bg-app` | `--bg-body` | Similar |
| `--bg-card-inner` | — | Missing |
| `--border-card` | `--border` | Different |
| `--font-sans`, `--font-mono` | — | Not in theme |
| `--radius-*` | — | Hardcoded in components |
| `--shadow-card`, `--shadow-modal` | — | Missing |

### Recommendation

1. **Do not replace** the existing theme; it is used across Documents, chat, modals.
2. **Add aliases** for Evaluate-specific vars that map to existing palette:
   - `--pink` → `--accent`
   - `--green` → `--success` (or add `--green` if you want literal green)
   - `--yellow` → `--accent-secondary`
   - `--red` → `--error`
3. **Add missing structural vars** without changing hex values: `--bg-card-inner`, `--font-sans`, `--font-mono`, `--radius-*`, `--shadow-*`.
4. **Add job-card accent vars** as new entries: `--accent-expanding`, `--accent-complete`, etc., using existing colors.

---

## Part 2 — Shared CSS Component Classes

### Current State

`ontology_builder/ui/static/css/components.css` (853 lines) already has:

- `.job-card` — simpler structure, used for Documents tab
- `.status-card`, `.status-badge` — different from spec `.badge`
- `.modal-overlay`, `.modal` — similar to spec
- `.progress-track`, `.progress-fill` — exists
- `.btn-primary`, `.btn-gold`, `.btn-ghost` — different naming

### Spec Classes Not Present

- `.section-label`, `.badge` (with `.badge-expanding`, `.badge-complete`, etc.)
- `.status-dot` (with `.complete`, `.failed`, `.running`)
- `.meta-line` (with `.sep`, `.val`)
- `.inner-card`
- `.job-card` with `.job-card-header`, `.job-card-title`, `.job-card-body`, `.job-card-meta`, `.job-card-footer`
- `.btn-dismiss`, `.btn-chevron`
- `.section-header` (collapsible)
- `.field-input`, `.metric-row`, `.pipeline-step`, `.action-row`
- `.relation-table`, `.question-table`, `.relation-pill`
- `.stat-grid`, `.alert-box`

### Recommendation

1. **Add** all spec classes to `components.css` as a new section (e.g. `/* ── Evaluate tab components ── */`).
2. **Extend** `.job-card` with `.job-card-header`, `.job-card-body`, etc., or define a new `.job-card-eval` to avoid breaking Documents tab.
3. **Reuse** existing `.progress-track` / `.progress-fill`; add `.m-bar-fill.high/mid/low` for metric rows.
4. **Avoid** overwriting `.status-badge`; add `.badge` as a separate class for Evaluate badges.

---

## Part 3 — API Layer

### Endpoints Present

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /knowledge-bases/{id}/health` | ✅ Exists | Response shape differs |
| `GET /knowledge-bases/{id}/evaluation-records` | ✅ Exists | Returns raw list, not `{ records: [] }` |
| `POST /knowledge-bases/{id}/evaluate` | ✅ Exists | POST only; not EventSource-compatible |
| `POST /knowledge-bases/{id}/repair` | ✅ Exists | SSE event schema differs |
| `GET /knowledge-bases/{id}/repair-records` | ✅ Exists | Returns raw list |

### Health Response Mismatch

**Spec expects (flat):**
```json
{
  "nodes": 1796,
  "edges": 9138,
  "density": 0.002,
  "components": 1,
  "orphans": 0,
  "relation_types": 42,
  "facts_per_node": 5.1,
  "hyperedge_coverage": 1.0,
  "overall_score": 85,
  "badge": "Healthy",
  "disconnected_subgraphs": 0,
  "recommended_actions": [],
  "kb_name": "Pr.Chen"
}
```

**Current returns (nested):**
```json
{
  "structural": {
    "node_count": 1796,
    "edge_count": 9138,
    "density": 0.002,
    "connected_components": 1,
    "orphan_nodes": 0,
    ...
  },
  "semantic": { "unique_relation_types": 42, ... },
  "retrieval": { "facts_per_node": 5.1, "hyperedge_coverage": 1.0, ... },
  "overall_score": 85,
  "badge": "Healthy",
  "kb_id": "..."
}
```

**Gaps:** `nodes`/`edges` vs `node_count`/`edge_count`; `disconnected_subgraphs` = `connected_components - 1` when > 1; `recommended_actions` and `kb_name` not in health response.

**Recommendation:** Add a JS adapter in `evaluate.js` that flattens the health response, or add an optional `?flat=1` query param to the health endpoint that returns the spec shape.

### Evaluation Records Response

**Spec expects:** `{ records: [...] }`  
**Current returns:** `[...]` (raw array)

**Recommendation:** Either (a) wrap in `{ records: data }` in the API when `Accept` or a query param requests it, or (b) adapt in JS: `const records = Array.isArray(data) ? data : (data.records || []);`

### Repair Records Response

**Spec expects:** `{ records: [...] }` with each record having `config`, `before`, `after`, `pipeline_steps`, `recommended_actions`.

**Current returns:** Raw list with `health_before`, `health_after`, `iteration_summaries`, `repair_internet_definitions`, `repair_iterations`, `min_fidelity`, etc.

**Recommendation:** Add a JS adapter that maps `health_before.structural` → `before`, `health_after.structural` → `after`, and builds `config` from `repair_internet_definitions`, `repair_iterations`, `min_fidelity`. Map `iteration_summaries` to `pipeline_steps`.

### Evaluate SSE Protocol

**Spec expects (EventSource GET):**
```json
{ "event": "progress", "data": { "step": "generating_questions", "count": 45, "total": 100 } }
{ "event": "complete", "data": { "metrics": {...}, "questions": [...] } }
```

**Current:** `POST /knowledge-bases/{kb_id}/evaluate` — **EventSource cannot be used** (EventSource is GET-only).

**Current events:**
```json
{ "type": "step", "message": "Loading knowledge base" }
{ "type": "progress", "current": 5, "total": 10, "question": "..." }
{ "type": "complete", "scores": {...}, "health": {...}, "record": {...} }
{ "type": "error", "message": "..." }
```

**Recommendation:** Use `fetch()` with `ReadableStream` (or `response.body.getReader()`) to consume the SSE stream from the POST response. Map `type` → `event` in the handler, and map `scores` to `metrics` plus `record.scores.per_question` to `questions` for the modal.

### Repair SSE Protocol

**Spec expects:**
```json
{ "event": "before_state", "data": { "nodes": 1795, "edges": 7814, "orphans": 0 } }
{ "event": "step", "data": { "name": "Infer", "detail": "148 relations inferred" } }
{ "event": "after_state", "data": { "nodes": 1796, "edges": 9138, "orphans": 0 } }
{ "event": "complete", "data": {...} }
```

**Current events:**
```json
{ "type": "step", "step": "...", "message": "...", "iteration": 1, "iteration_total": 2 }
{ "type": "done", "edges_added": 148, "gaps_repaired": 3, "iterations_completed": 2, "iteration_summaries": [...] }
{ "type": "error", "message": "..." }
```

**Recommendation:** Add a JS adapter that maps `type: "step"` + `message` to `event: "step"` with `data.name` and `data.detail`. The repair endpoint does not emit `before_state`/`after_state`; those would need to be added to the repair pipeline's progress callback, or derived from `iteration_summaries` if available.

---

## Part 4 — HTML Template Structure

### Current Evaluate Tab Structure

- `#tab-evaluate-content` with `#eval-kb-select`, `#eval-panel-state-a`, `#eval-panel-state-b`, `#eval-eval-panel`, `#eval-eval-progress`, `#eval-records-panel`, `#repair-records-panel`.
- Inline styles throughout; no `.job-card`, `.section-header`, or shared component classes.
- Repair modal exists (`#repair-modal`); no Graph Health or Evaluation Detail modals.

### Spec Structure

- Graph Health as a `.job-card` with dismiss, chevron, inner-card, buttons.
- QA Evaluation as a `.job-card` with question count input, Run button, progress.
- Evaluation Records and Repair Records as `.section-header` + `.section-content` collapsible sections.
- Three new modals: Graph Health, Evaluation Record Detail, Repair Record Detail.

### Recommendation

1. **Refactor** the Evaluate tab HTML in `chat_ui.py` to use the spec structure.
2. **Keep** `#eval-kb-select`, `#eval-records-list`, `#repair-records-list` IDs for JS compatibility.
3. **Add** the three modal overlays at the bottom of `<body>` (with existing modals).
4. **Inject** `components.css` (already done) and add `evaluate.js` script tag.

---

## Part 5 — JavaScript

### Current State

- All Evaluate logic lives in `app.bundle.js` (bundled from source).
- Uses `fetch()` for health, evaluation-records, repair-records.
- Uses `fetch()` for evaluate (POST) — not streaming; waits for full response. (Actually the API streams SSE; need to verify if the client reads the stream.)
- Uses `fetch()` or similar for repair — need to check if it reads SSE.

### Spec Assumptions

- `EventSource` for evaluate — **invalid** (POST required).
- Shared utilities: `toggleCard`, `toggleSection`, `dismissCard`, `openModal`, `closeModal`, `metricColorClass`, `evalBadgeClass`, `buildMetaLine`.

### Recommendation

1. **Create** `ontology_builder/ui/static/evaluate.js` (or add to bundle source) with:
   - Shared utilities (can be moved to a shared `ui-utils.js` or kept in evaluate.js).
   - `loadGraphHealth`, `renderGraphHealthCard` with health response adapter.
   - `runEvaluation` using `fetch()` + `response.body.getReader()` to consume SSE from POST.
   - `loadEvaluationRecords`, `loadRepairRecords` with `records` wrapper handling.
   - `buildEvalRecordCard`, `buildRepairRecordCard` with data shape adapters.
   - Modal openers: `openGraphHealthModal`, `openEvaluationModal`, `openRepairDetailModal`.
2. **Ensure** `evaluate.js` is loaded after `app.bundle.js` or that its logic is integrated into the bundle.
3. **Verify** repair SSE consumption — current `runRepair` may use a different pattern.

---

## Part 6 — Detail Modals

### Current Modals

- `#create-modal`, `#job-detail-modal`, `#kb-summary-modal`, `#new-chat-modal`, `#delete-modal`, `#web-enrichment-modal`, `#repair-modal`, `#reasoning-modal`.
- Pattern: `fixed inset-0 z-50 hidden` + `modal-backdrop` + `modal-content` with `modal-enter` animation.
- Spec uses `modal-overlay` + `modal-box` with `open` class.

### Recommendation

1. **Add** `#modal-graph-health`, `#modal-eval-detail`, `#modal-repair-detail` following the spec HTML.
2. **Reuse** `.modal-overlay` and `.modal-box` from components.css (add if not present).
3. **Ensure** `openModal`/`closeModal` toggle the `open` class and `body` overflow.

---

## Part 7 — File Map Verification

| File | Spec | Current | Action |
|------|------|---------|--------|
| `theme.py` | Extend | Exists | Add vars/aliases |
| `chat_ui.py` | Refactor | Exists | Update Evaluate tab HTML + add modals |
| `api.py` | Verify | Exists | Optional: add flat health, records wrapper |
| `static/components.css` | New content | Exists | Add Evaluate component classes |
| `static/evaluate.js` | New | Missing | Create |
| `static/documents.js` | Refactor | N/A (logic in app.bundle.js) | Extract shared utils if desired |

---

## Part 8 — Acceptance Criteria Checklist

### Theme coherence

- [ ] **Every color uses var(--*)** — Requires adding spec vars or aliases to theme.
- [ ] **get_css_root_block() is single source** — Already true; extend with new vars.
- [ ] **components.css is single place for component classes** — Add new classes; avoid duplication.
- [ ] **Documents tab unchanged** — Ensure new classes don't override Documents styles.

### Component parity

- [ ] Badge pills → `.badge .badge-{variant}` — Add to components.css.
- [ ] Status indicators → `.status-dot.{state}` — Add.
- [ ] Monospace data rows → `.meta-line` — Add.
- [ ] Section labels → `.section-label` — Add.
- [ ] Expandable cards → `.job-card` + `.job-card-body` — Extend job-card.
- [ ] Dismiss buttons → `.btn-dismiss` — Add.
- [ ] Section headers → `.section-header` — Add.
- [ ] Buttons → `.btn-primary`, `.btn-outline` — Already exist (different styles); ensure consistency.

### API wiring

- [ ] Graph Health from GET /health — **Adapter needed** for flat shape.
- [ ] Run Evaluation SSE — **Use fetch+stream**, not EventSource.
- [ ] Evaluation records from GET — **Adapter** for `records` wrapper.
- [ ] Repair records from GET — **Adapter** for `records` + record shape.
- [ ] SSE error states → `.status-dot.failed` — Implement in evaluate.js.

### Modals

- [ ] All three modals use `.modal-overlay` + `.modal-box` — Add HTML + styles.
- [ ] Modal open animation — Reuse existing `modal-enter` or spec animation.
- [ ] Click outside closes — Standard pattern.
- [ ] Evaluation modal question log — Implement with `record.scores.per_question`.
- [ ] Repair modal before/after delta — Implement with `health_before`/`health_after` mapping.
- [ ] Graph health modal score bar — Implement with `overall_score`.

---

## Implementation Order

1. **Theme** — Add aliases and missing vars to `theme.py`.
2. **components.css** — Add Evaluate component classes (non-breaking).
3. **API adapters** — Implement in evaluate.js for health, records, SSE.
4. **HTML** — Refactor Evaluate tab in chat_ui.py.
5. **evaluate.js** — Create with all logic + adapters.
6. **Modals** — Add HTML and wire up open/close.
7. **Integration** — Load evaluate.js, test full flow.

---

## Summary of Required Changes

| Change | Location | Effort |
|--------|----------|--------|
| Add theme vars/aliases | theme.py | Low |
| Add component classes | components.css | Medium |
| Health response adapter | evaluate.js | Low |
| Records response adapter | evaluate.js | Low |
| Evaluate: fetch+stream (not EventSource) | evaluate.js | Medium |
| Repair SSE adapter | evaluate.js | Low |
| Refactor Evaluate tab HTML | chat_ui.py | Medium |
| Create evaluate.js | static/evaluate.js | High |
| Add 3 modals | chat_ui.py | Medium |
| Wire evaluate.js in HTML | chat_ui.py | Low |

**Total estimated effort:** Medium–High (2–4 days for a focused implementation).
