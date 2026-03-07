"""Clearence-Technical.pdf — 20-slide technical deep-dive presentation.

Theme matches ontology_builder.ui.theme (Void #1a0f12, Magenta #b81365, Gold #f8c630, Ice #b1ddf1).
"""

import sys
from pathlib import Path

# Ensure presentations dir and project root are on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from reportlab.pdfgen import canvas as rl_canvas
from presentations.slide_theme import *  # noqa: F403, F401

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "presentations" / "Clearence-Technical.pdf"
TOTAL = 20


def new_slide(c, n, top_color=ACCENT):
    draw_bg(c)
    draw_top_bar(c, top_color, height=5)
    draw_footer(c, n, TOTAL)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1 — Title
# ─────────────────────────────────────────────────────────────────────────────
def s01(c):
    new_slide(c, 1, ACCENT)
    draw_glow_circle(c, W * 0.78, H * 0.48, 230, ACCENT, 0.06)
    draw_glow_circle(c, W * 0.82, H * 0.55, 150, GOLD, 0.04)

    draw_tag(c, MARGIN, H - 52, "TECHNICAL DEEP-DIVE  ·  ENGINEERING EDITION", a(ACCENT, 0.18), ACCENT_BRIGHT, 7.5)

    c.setFillColor(GHOST)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 52)
    c.drawString(MARGIN, H - 118, "Clearence")
    c.setFillColor(TEXT_PINK)
    c.setFont("Helvetica-Bold", 48)
    c.drawString(MARGIN + c.stringWidth("Clearence", _font(FONT_SYNE, "Helvetica-Bold"), 52) + 8, H - 118, ".")

    draw_accent_rule(c, MARGIN, H - 132, 360, GOLD, 3)

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 14)
    c.drawString(MARGIN, H - 160, "Ontology Expansion & Utilization")
    c.setFillColor(ACCENT_BRIGHT)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, H - 180, "for Retrieval-Augmented Generation")

    c.setFillColor(TEXT_MUTED2)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, H - 210, "A Multi-Approach Framework  ·  v0.1.0")

    draw_divider(c, MARGIN, H - 228, 360, BORDER)

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, H - 246, "Reda Sarehane  ·  Ontology Graph Research Team  ·  March 2026")

    # right — 4 tech stats
    stats = [("7", "Methodologies"), ("8", "Pipeline Stages"), ("20", "Max OWL Iter."), ("0.9", "Canon. Threshold τ")]
    bw, bh = 124, 74
    for i, (val, lbl) in enumerate(stats):
        bx = W * 0.60 + i * (bw + 14) if i < 2 else W * 0.60 + (i - 2) * (bw + 14)
        by = H / 2 + 8 if i < 2 else H / 2 - bh - 8
        draw_metric(c, bx, by, bw, bh, val, lbl, GOLD if i % 2 == 0 else ICE, ACCENT)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2 — Overview
# ─────────────────────────────────────────────────────────────────────────────
def s02(c):
    new_slide(c, 2, GOLD)
    draw_slide_title(c, "Overview")
    draw_accent_rule(c, 48, width=120)
    draw_subtitle(c, "What Clearence is, what it solves, and where it fits")

    draw_tag(c, 48, H - 116, "PURPOSE")
    draw_bullets(c, [
        "A unified framework for expanding formal ontologies and using them to improve RAG pipelines",
        "Addresses the structural blindness of flat dense-vector retrieval — surfaces relational knowledge",
        "Integrates 7 methodologies: LLM extraction, majority voting, taxonomy building, canonicalization, OWL 2 RL reasoning, hybrid retrieval, and OG-RAG hypergraph",
    ], 48, H - 138, size=9.5, max_width=W - 120)

    draw_tag(c, 48, H - 246, "WHERE IT FITS", a(GOLD, 0.18), GOLD)
    # pipeline chain diagram
    stages = ["Documents", "Extract", "Taxonomy", "Canon.", "Graph", "Reason", "Retrieve", "Answer"]
    colors = [PENDING, ACCENT, GOLD, ACCENT_BRIGHT, ICE, GOLD_DIM, ACCENT, ICE]
    sw = (W - 96 - 7 * 12) / 8
    for i, (s, col) in enumerate(zip(stages, colors)):
        bx = 48 + i * (sw + 12)
        by = H - 348
        draw_card(c, bx, by, sw, 40, col, 0.12)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 7.5)
        tw = c.stringWidth(s, "Helvetica-Bold", 7.5)
        c.drawString(bx + (sw - tw) / 2, by + 14, s)
        if i < 7:
            c.setFillColor(a(col, 0.5))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(bx + sw + 3, by + 12, "›")

    draw_card(c, 48, H - 400, W - 96, 38, ICE, 0.08)
    c.setFillColor(ICE)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(64, H - 375, "Result:  Context Recall  0.61 → 0.78   ·   Answer Faithfulness  0.72 → 0.83  over flat-retrieval baseline")
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3 — System Context
# ─────────────────────────────────────────────────────────────────────────────
def s03(c):
    new_slide(c, 3, ACCENT)
    draw_slide_title(c, "System Context")
    draw_accent_rule(c, 48, width=170)
    draw_subtitle(c, "Role in architecture · Dependencies · Integration")

    cx, cw = 48, (W - 96 - 18) / 2

    # Left — role
    draw_tag(c, cx, H - 114, "ROLE")
    rows = [
        ("FastAPI / SSE", "REST API, streaming progress, CORS, cancellation hooks"),
        ("run_pipeline.py", "Top-level orchestrator; calls all 8 stages sequentially"),
        ("ontology_builder.*", "All extraction, taxonomy, schema, reasoning, QA sub-packages"),
        ("NetworkX DiGraph", "In-memory graph store for O={C,R,I,P} entities and edges"),
        ("Docker", "Containerised deployment; supports LM Studio & OpenAI-compat. APIs"),
    ]
    for i, (comp, desc) in enumerate(rows):
        ry = H - 142 - i * 38
        draw_card(c, cx, ry, cw, 32, ACCENT, 0.08)
        draw_left_accent_bar(c, cx, ry, 32, ACCENT, 4)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(cx + 12, ry + 18, comp)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(cx + 12, ry + 6, desc)

    # Right — deps
    rx = cx + cw + 18
    draw_tag(c, rx, H - 114, "KEY DEPENDENCIES", a(GOLD, 0.18), GOLD)
    deps = [
        ("sentence-transformers", "Embedding canonicalization  all-MiniLM-L6-v2"),
        ("networkx", "Directed labeled graph storage and traversal"),
        ("pysbd", "Sentence-boundary detection for semantic chunking"),
        ("ragas", "Reference-free RAG evaluation metrics"),
        ("numpy", "Cosine similarity, nearest-neighbour scoring"),
    ]
    for i, (lib, role) in enumerate(deps):
        ry = H - 142 - i * 38
        draw_card(c, rx, ry, cw, 32, GOLD, 0.08)
        draw_left_accent_bar(c, rx, ry, 32, GOLD, 4)
        c.setFillColor(ICE)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(rx + 12, ry + 18, lib)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(rx + 12, ry + 6, role)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — High-Level Architecture
# ─────────────────────────────────────────────────────────────────────────────
def s04(c):
    new_slide(c, 4, GOLD)
    draw_slide_title(c, "High-Level Architecture")
    draw_accent_rule(c, 48, width=230)
    draw_subtitle(c, "Layered modular pipeline — 8 functional layers")

    layers = [
        ("API", "FastAPI routers · SSE streaming · CORS · PipelineCancelledError", ACCENT),
        ("Pipeline", "run_pipeline.py orchestration · progress callbacks · cancel_check()", GOLD),
        ("Extraction", "3-stage Bakker B · majority vote N=3 · JSON repair · hallucination guard", ACCENT_BRIGHT),
        ("Taxonomy", "OntoGen-style · 2-stage grounding · batched LLM · reconciliation pass", GOLD_DIM),
        ("Ontology", "Guarino O={C,R,I,P} schema · NLTK lemmatization · embedding canon. τ=0.9", ICE),
        ("Storage", "OntologyGraph (NetworkX DiGraph) · HyperGraph · graph_store", PENDING),
        ("Reasoning", "OWL 2 RL fixpoint · 6 production rules · MAX_ITER=20 · cycle detection", ACCENT),
        ("RAG / QA", "Dual-retrieval index · OntoRAG enrichment · OG-RAG greedy set cover · LLM gen", GOLD),
    ]

    lh = 34
    lw = W - 96
    for i, (name, desc, col) in enumerate(layers):
        ly = H - 112 - i * (lh + 4)
        draw_card(c, 48, ly, lw, lh, col, 0.10, radius=4)
        draw_left_accent_bar(c, 48, ly, lh, col, 4)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(60, ly + lh / 2 - 4, name)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawString(148, ly + lh / 2 - 4, desc)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5 — File / Module Structure
# ─────────────────────────────────────────────────────────────────────────────
def s05(c):
    new_slide(c, 5, ACCENT)
    draw_slide_title(c, "Module Structure")
    draw_accent_rule(c, 48, width=180)
    draw_subtitle(c, "ontology_builder package layout")

    modules = [
        ("ontology_builder/", "Root package", ACCENT),
        ("  pipeline/run_pipeline.py", "process_document() — top-level orchestrator", GOLD),
        ("  pipeline/extractor.py", "extract_ontology_sequential() · majority_vote()", ACCENT_BRIGHT),
        ("  pipeline/taxonomy_builder.py", "build_taxonomy() · corpus_frequency_check()", GOLD_DIM),
        ("  ontology/schema.py", "Pydantic v2 models: OntologyClass, Instance, ObjectProperty …", ICE),
        ("  ontology/canonicalizer.py", "canonicalize() · canonicalize_batch() · seed_from_entities()", ICE),
        ("  storage/graphdb.py", "OntologyGraph wrapping NetworkX DiGraph", PENDING),
        ("  reasoning/engine.py", "run_inference() · 6 OWL 2 RL production rules", GOLD),
        ("  qa/graph_index.py", "build_index() · retrieve_with_context() · retrieve_hyperedges()", ACCENT),
        ("  evaluation/metrics.py", "context_recall() · entity_recall() · answer_correctness() · RAGAS", GOLD),
        ("  llm/client.py", "complete() — unified LM Studio / OpenAI-compat. wrapper", TEXT_PINK),
        ("  llm/json_repair.py", "repair_json() — robust malformed-JSON recovery", TEXT_MUTED),
    ]

    for i, (mod, desc, col) in enumerate(modules):
        my = H - 112 - i * 29
        indent = mod.startswith("  ")
        mx = 64 if indent else 48
        mw = W - 96 - (16 if indent else 0)
        draw_card(c, mx, my, mw, 24, col, 0.08 if indent else 0.14, radius=3)
        if not indent:
            draw_left_accent_bar(c, mx, my, 24, col, 3)
        c.setFillColor(col if not indent else GHOST)
        c.setFont("Courier-Bold" if not indent else "Courier", 8)
        c.drawString(mx + 8, my + 7, mod.strip())
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawRightString(mx + mw - 8, my + 7, desc)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6 — Formal Ontology Model
# ─────────────────────────────────────────────────────────────────────────────
def s06(c):
    new_slide(c, 6, GOLD)
    draw_slide_title(c, "Formal Ontology Model")
    draw_accent_rule(c, 48, width=200)
    draw_subtitle(c, "Guarino et al.  O = {C, R, I, P}")

    comps = [
        ("C", "Concepts", "Classes / universals in CamelCase.\nCarry: name, parent, description,\nsynonyms, source_document,\nsource_chunk, extraction_confidence", ACCENT),
        ("R", "Relations", "ObjectProperty: source, relation,\ntarget, domain, range,\nsymmetric, transitive, confidence.\nDataProperty: entity, attribute, value.", GOLD),
        ("I", "Instances", "OntologyInstance: name, class_name,\ndescription, source_document.\nExtracted conditioned on C\n(Bakker Stage 2).", ICE),
        ("P", "Axioms", "AxiomType enum: subclass,\ndisjointness, symmetry,\ntransitivity, asymmetry,\ninverse, functional.", PENDING),
    ]

    bw = (W - 96 - 36) / 4
    bh = 200
    by = H - 345

    for i, (sym, name, desc, col) in enumerate(comps):
        bx = 48 + i * (bw + 12)
        draw_card(c, bx, by, bw, bh, col, 0.10)
        # big symbol (ghost layer then real)
        c.setFillColor(a(col, 0.15))
        c.setFont("Helvetica-Bold", 56)
        sw = c.stringWidth(sym, "Helvetica-Bold", 56)
        c.drawString(bx + (bw - sw) / 2, by + bh - 68, sym)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 56)
        c.drawString(bx + (bw - sw) / 2 - 1, by + bh - 67, sym)
        # name
        c.setFillColor(GHOST)
        c.setFont("Helvetica-Bold", 10.5)
        nw = c.stringWidth(name, "Helvetica-Bold", 10.5)
        c.drawString(bx + (bw - nw) / 2, by + bh - 84, name)
        # desc
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        for j, line in enumerate(desc.split("\n")):
            lw = c.stringWidth(line, "Helvetica", 7.5)
            c.drawString(bx + (bw - lw) / 2, by + bh - 104 - j * 11, line)

    c.setFillColor(TEXT_MUTED2)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(48, by - 16, "Collapses TBox/ABox distinction. OWL 2 RL forward-chaining runs over the unified graph.  All elements carry full provenance.")
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7 — Core Logic: 8-Stage Pipeline
# ─────────────────────────────────────────────────────────────────────────────
def s07(c):
    new_slide(c, 7, ACCENT)
    draw_slide_title(c, "8-Stage Pipeline")
    draw_accent_rule(c, 48, width=160)
    draw_subtitle(c, "End-to-end ontology construction workflow")

    steps = [
        ("1", "Doc Processing", "pysbd chunking\nCHUNK_SIZE=1200\nOVERLAP=200", ACCENT),
        ("2", "LLM Extraction", "Bakker B ×3\nmajority vote\nmin_votes=2", GOLD),
        ("3", "Taxonomy", "OntoGen-style\nLLM yes/no\nmin_freq=3", ACCENT_BRIGHT),
        ("4", "Aggregation", "vote_count\nchunk_ids\nbatch canon.", GOLD_DIM),
        ("5", "Graph Merge", "update_graph\n_from_aggregated\nincremental repair", ICE),
        ("6", "Relation Infer.", "cross-component\nbridging\nenrichment", PENDING),
        ("7", "OWL 2 RL", "fixpoint iter.\nMAX_ITER=20\ncycle guard", ACCENT),
        ("8", "Quality", "Grade A-F\nconsistency\nhierarchy enrich", GOLD),
    ]

    sw = (W - 96 - 7 * 10) / 8
    sh = 165
    sy = H - 308

    for i, (num, title, desc, col) in enumerate(steps):
        sx = 48 + i * (sw + 10)
        draw_card(c, sx, sy, sw, sh, col, 0.10)
        # circle num
        c.setFillColor(col)
        c.circle(sx + sw / 2, sy + sh - 18, 12, fill=1, stroke=0)
        c.setFillColor(VOID)
        c.setFont("Helvetica-Bold", 9.5)
        nw = c.stringWidth(num, "Helvetica-Bold", 9.5)
        c.drawString(sx + sw / 2 - nw / 2, sy + sh - 22, num)
        # title
        c.setFillColor(GHOST)
        c.setFont("Helvetica-Bold", 7.5)
        tw = c.stringWidth(title, "Helvetica-Bold", 7.5)
        c.drawString(sx + (sw - tw) / 2, sy + sh - 42, title)
        # desc
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 6.5)
        for j, ln in enumerate(desc.split("\n")):
            lw = c.stringWidth(ln, "Helvetica", 6.5)
            c.drawString(sx + (sw - lw) / 2, sy + sh - 60 - j * 11, ln)
        # arrow
        if i < 7:
            c.setFillColor(a(col, 0.5))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(sx + sw + 1, sy + sh / 2 - 6, "›")

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 8 — Key Class: OntologyGraph
# ─────────────────────────────────────────────────────────────────────────────
def s08(c):
    new_slide(c, 8, GOLD)
    draw_slide_title(c, "Key Class: OntologyGraph")
    draw_accent_rule(c, 48, width=230)
    draw_subtitle(c, "ontology_builder/storage/graphdb.py  ·  NetworkX DiGraph wrapper")

    lx, rx = 48, W / 2 + 12
    cw = W / 2 - 72

    # Attributes
    draw_tag(c, lx, H - 112, "ATTRIBUTES")
    attrs = [
        ("graph", "nx.DiGraph()", "Core directed labeled graph"),
        ("node: type", "class | instance", "Entity kind discriminator"),
        ("node: synonyms", "List[str]", "Surface-form variants"),
        ("node: vote_count", "int", "Extraction consensus count"),
        ("edge: relation", "str", "Semantic relation type"),
        ("edge: confidence", "float", "Extraction confidence score"),
        ("edge: chunk_ids", "List[int]", "Provenance tracking"),
    ]
    for i, (attr, typ, desc) in enumerate(attrs):
        ry = H - 138 - i * 32
        draw_card(c, lx, ry, cw, 27, ACCENT, 0.08, radius=3)
        c.setFillColor(GOLD)
        c.setFont("Courier-Bold", 8)
        c.drawString(lx + 8, ry + 10, attr)
        c.setFillColor(ICE)
        c.setFont("Courier", 7.5)
        c.drawString(lx + 8 + c.stringWidth(attr, "Courier-Bold", 8) + 6, ry + 10, typ)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawRightString(lx + cw - 6, ry + 10, desc)

    # Methods
    draw_tag(c, rx, H - 112, "KEY METHODS", a(GOLD, 0.18), GOLD)
    methods = [
        ("add_relation()", "source, relation, target, confidence, vote_count, chunk_ids"),
        ("get_parents(n)", "Immediate superclasses via subClassOf out-edges"),
        ("get_children(n)", "Direct subclasses via subClassOf in-edges"),
        ("to_factual_blocks()", "Returns OG-RAG [{subject, attributes:[...]}] list"),
        ("add_relations_batch()", "Bulk edge insertion from list[dict]"),
        ("add_axiom()", "Inserts AxiomType constraint with entity set"),
        ("add_data_property()", "entity, attribute, value, datatype insertion"),
    ]
    for i, (meth, desc) in enumerate(methods):
        ry = H - 138 - i * 32
        draw_card(c, rx, ry, cw, 27, GOLD, 0.08, radius=3)
        c.setFillColor(GOLD)
        c.setFont("Courier-Bold", 8)
        c.drawString(rx + 8, ry + 10, meth)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        drop = c.stringWidth(meth, "Courier-Bold", 8) + 16
        c.drawString(rx + drop, ry + 10, desc)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 9 — Sequential Extraction Algorithm
# ─────────────────────────────────────────────────────────────────────────────
def s09(c):
    new_slide(c, 9, ACCENT)
    draw_slide_title(c, "Sequential Extraction")
    draw_accent_rule(c, 48, width=220)
    draw_subtitle(c, "Bakker et al. Approach B  ·  extract_ontology_sequential()")

    stages = [
        ("Stage 1 — Class Extraction", ACCENT,
         "LLM1(EXTRACT_CLASSES_SYSTEM, chunk)  →  classes_raw",
         "temperature=0.1  ·  hallucination guard  ·  richness truncation"),
        ("Stage 2 — Instance Extraction", GOLD,
         "LLM2(EXTRACT_INSTANCES_SYSTEM, classes_json, chunk)  →  instances_raw",
         "Conditioned on Stage 1 output — prevents class/instance confusion"),
        ("Stage 3 — Relation & Axiom Extraction", ICE,
         "LLM3(EXTRACT_RELATIONS_SYSTEM, classes_json, instances_json, chunk)",
         "JSONDecodeError caught per-chunk — returns partial extraction, never fails pipeline"),
    ]

    for i, (title, col, code, note) in enumerate(stages):
        sy = H - 148 - i * 116
        draw_card(c, 48, sy, W - 96, 100, col, 0.09)
        draw_left_accent_bar(c, 48, sy, 100, col, 5)
        draw_tag(c, 62, sy + 84, title, a(col, 0.20), col)
        c.setFillColor(GHOST)
        c.setFont("Courier", 9)
        c.drawString(62, sy + 66, code)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawString(62, sy + 50, note)
        # JSON repair note
        c.setFillColor(a(col, 0.7))
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(62, sy + 34, "repair_json() applied to every LLM response")

    draw_card(c, 48, H - 496, W - 96, 38, GOLD, 0.08)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(64, H - 469, "Majority Voting Wrapper  (optional):")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(64, H - 483, "N=3 independent runs  ·  retain element iff count >= min_votes=2  ·  reduces temperature variance")
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 10 — Embedding Canonicalization Algorithm
# ─────────────────────────────────────────────────────────────────────────────
def s10(c):
    new_slide(c, 10, GOLD)
    draw_slide_title(c, "Embedding Canonicalization")
    draw_accent_rule(c, 48, width=250)
    draw_subtitle(c, "Surface deduplication  ·  ontology_builder/ontology/canonicalizer.py")

    lx, rx = 48, W / 2 + 12
    cw = W / 2 - 72

    # Algorithm steps
    draw_tag(c, lx, H - 112, "ALGORITHM")
    alg = [
        ("1", "Normalize", "lowercase → strip → replace hyphens/underscores → remove possessives → NLTK WordNet lemmatize"),
        ("2", "Exact match", "If normalized form in _normalized_cache[kind] → return canonical without embedding"),
        ("3", "Encode", "SentenceTransformer all-MiniLM-L6-v2  ·  encode(name, convert_to_numpy=True)"),
        ("4", "Scan", "Cosine similarity vs all existing vectors in entity_vectors[kind]"),
        ("5", "Merge", "sim >= τ=0.9 → map to existing canonical, update _normalized_cache"),
        ("6", "Register", "New canonical → store emb in entity_vectors, update cache"),
    ]

    for i, (num, title, desc) in enumerate(alg):
        ry = H - 138 - i * 42
        draw_card(c, lx, ry, cw, 36, ICE if i % 2 == 0 else ACCENT, 0.08, radius=4)
        c.setFillColor(ICE if i % 2 == 0 else ACCENT_BRIGHT)
        c.circle(lx + 16, ry + 18, 9, fill=1, stroke=0)
        c.setFillColor(VOID)
        c.setFont("Helvetica-Bold", 8)
        nw = c.stringWidth(num, "Helvetica-Bold", 8)
        c.drawString(lx + 16 - nw / 2, ry + 14, num)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(lx + 30, ry + 22, title)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(lx + 30, ry + 10, desc)

    # Right — design notes
    draw_tag(c, rx, H - 112, "DESIGN DECISIONS", a(GOLD, 0.18), GOLD)
    notes = [
        ("τ = 0.9", "Tuned on held-out dev corpus. Lower collapses semantically distinct concepts; higher misses punctuation/order variants."),
        ("Kind namespaces", "Separate class / instance / entity caches prevent cross-kind merges (e.g. class 'Animal' never merges with instance 'animal')."),
        ("Embedding cache", "Serialized with graph JSON — zero re-embedding on KB reload."),
        ("Batch API", "canonicalize_batch() encodes names together for speed."),
        ("O(n^2) complexity", "Current pairwise scan; reducible to near-linear with FAISS ANN (planned)."),
        ("seed_from_entities()", "Pre-populates cache from existing KB entities on disk load."),
    ]
    for i, (title, desc) in enumerate(notes):
        ry = H - 138 - i * 42
        draw_card(c, rx, ry, cw, 36, GOLD, 0.08, radius=4)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(rx + 10, ry + 22, title)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        wrap_text(c, desc, rx + 10, ry + 10, cw - 18, 7.5, TEXT_MUTED)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 11 — Taxonomy Construction
# ─────────────────────────────────────────────────────────────────────────────
def s11(c):
    new_slide(c, 11, ACCENT)
    draw_slide_title(c, "Taxonomy Construction")
    draw_accent_rule(c, 48, width=210)
    draw_subtitle(c, "OntoGen-style  ·  ontology_builder/pipeline/taxonomy_builder.py")

    # Three stage flow
    stages = [
        ("LLM Taxonomy Inference", ACCENT,
         "build_taxonomy() calls LLM with TAXONOMY_SYSTEM prompt",
         "Returns (child, parent) pairs for all candidate classes",
         "Uses repair_json() for malformed responses"),
        ("Stage 1 Grounding — LLM yes/no", GOLD,
         "_grounding_check(): LLM confirms each subclass relation is semantically warranted",
         "Also filters via SequenceMatcher ratio >= 0.6 against source text",
         "Prevents hallucinated hierarchies from pretraining distribution"),
        ("Stage 2 Grounding — Corpus Frequency", ICE,
         "corpus_frequency_check(): count occurrences of child concept in lowercased source",
         "Threshold min_freq=3 — rejects concepts not grounded in the document",
         "Simple substring count on source.lower()"),
        ("Reconciliation Pass", PENDING,
         "_reconciliation_pass(): unify poly-rooted ontologies",
         "Max 10 top-level roots via short LLM call",
         "Assigns parent to roots that share semantic cluster"),
    ]

    for i, (title, col, l1, l2, l3) in enumerate(stages):
        sy = H - 130 - i * 96
        draw_card(c, 48, sy, W - 96, 84, col, 0.09)
        draw_left_accent_bar(c, 48, sy, 84, col, 5)
        draw_tag(c, 62, sy + 68, title, a(col, 0.20), col)
        c.setFillColor(GHOST)
        c.setFont("Helvetica", 8.5)
        c.drawString(62, sy + 50, l1)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(62, sy + 36, l2)
        c.drawString(62, sy + 22, l3)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 12 — OWL 2 RL Reasoning Engine
# ─────────────────────────────────────────────────────────────────────────────
def s12(c):
    new_slide(c, 12, GOLD)
    draw_slide_title(c, "OWL 2 RL Reasoning Engine")
    draw_accent_rule(c, 48, width=240)
    draw_subtitle(c, "ontology_builder/reasoning/engine.py  ·  run_inference()")

    lx, rx = 48, W / 2 + 12
    cw = W / 2 - 72

    # 6 rules
    draw_tag(c, lx, H - 112, "6 PRODUCTION RULES")
    rules = [
        ("Transitive Subsumption", "A subClassOf B, B subClassOf C  =>  A subClassOf C", ACCENT),
        ("Inheritance", "A subClassOf B, x:A  =>  x:B", GOLD),
        ("Domain Propagation", "dom(p)=C, p(x,y)  =>  type(x,C)", ICE),
        ("Range Propagation", "rng(p)=C, p(x,y)  =>  type(y,C)", ICE),
        ("Symmetric Closure", "sym(p), p(x,y)  =>  p(y,x)", PENDING),
        ("Transitive Closure", "trans(p), p(x,y), p(y,z)  =>  p(x,z)", ACCENT_BRIGHT),
    ]
    for i, (name, formula, col) in enumerate(rules):
        ry = H - 136 - i * 36
        draw_card(c, lx, ry, cw, 30, col, 0.09, radius=3)
        c.setFillColor(GHOST)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(lx + 10, ry + 17, name)
        c.setFillColor(a(col, 0.9))
        c.setFont("Courier", 7.5)
        c.drawString(lx + 10, ry + 5, formula)

    # Fixpoint + guards
    draw_tag(c, rx, H - 112, "FIXPOINT & GUARDS", a(GOLD, 0.18), GOLD)
    notes = [
        ("MAX_REASONING_ITERATIONS=20", "Hard cap prevents infinite loops in pathological graphs"),
        ("per-iteration max_new_facts", "Guards against O(n^2) edge explosion from sym+trans combos"),
        ("Circular subclass detection", "nx.find_cycle(graph.subclass_view()) checked each iteration"),
        ("Disjointness check", "_check_disjointness() run post-fixpoint"),
        ("Convergence", "Typically reaches fixpoint within 10 iterations on tested corpora"),
        ("ReasoningResult", "Returns graph, trace list, and consistency_violations"),
    ]
    for i, (title, desc) in enumerate(notes):
        ry = H - 136 - i * 42
        draw_card(c, rx, ry, cw, 36, GOLD, 0.08, radius=3)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(rx + 10, ry + 22, title)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        wrap_text(c, desc, rx + 10, ry + 10, cw - 18, 7.5, TEXT_MUTED)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 13 — Data Flow
# ─────────────────────────────────────────────────────────────────────────────
def s13(c):
    new_slide(c, 13, ACCENT)
    draw_slide_title(c, "Data Flow")
    draw_accent_rule(c, 48, width=140)
    draw_subtitle(c, "How data moves through the full pipeline")

    flow = [
        ("Raw Document", "PDF / DOCX / TXT / MD", PENDING),
        ("Semantic Chunks", "pysbd sentences, stride 1200 tokens, overlap 200", PENDING),
        ("OntologyExtraction", "Pydantic v2: classes, instances, object_properties, data_properties, axioms", GOLD),
        ("Aggregated Triples", "vote_count, chunk_ids, confidence per triple across chunks", GOLD),
        ("OntologyGraph", "NetworkX DiGraph nodes+edges with full provenance metadata", ICE),
        ("Expanded Graph", "OWL 2 RL inferred edges added to graph; consistency violations logged", ICE),
        ("Factual Blocks", "to_factual_blocks() → [{subject, attributes:[{relation,target,full}]}]", ACCENT),
        ("RAG Context", "Hybrid retrieval result + ontological context block → LLM generator", ACCENT),
        ("Final Answer", "LLM response grounded in ontology-enriched retrieved context", GOLD),
    ]

    arr_x = 48 + 8
    for i, (stage, detail, col) in enumerate(flow):
        fy = H - 120 - i * 44
        fw = W - 96
        draw_card(c, 48, fy, fw, 38, col, 0.09, radius=3)
        draw_left_accent_bar(c, 48, fy, 38, col, 4)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(60, fy + 22, stage)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(60, fy + 8, detail)
        if i < len(flow) - 1:
            c.setFillColor(a(col, 0.5))
            c.setFont("Helvetica-Bold", 10)
            c.drawString(arr_x, fy - 8, "↓")

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 14 — Retrieval: Hybrid + OG-RAG
# ─────────────────────────────────────────────────────────────────────────────
def s14(c):
    new_slide(c, 14, GOLD)
    draw_slide_title(c, "Retrieval Mechanisms")
    draw_accent_rule(c, 48, width=200)
    draw_subtitle(c, "Hybrid ontology-guided retrieval  +  OG-RAG hypergraph greedy set cover")

    lx, rx = 48, W / 2 + 12
    cw = W / 2 - 72

    # Hybrid
    draw_tag(c, lx, H - 112, "HYBRID RETRIEVAL")
    draw_bullets(c, [
        "Identify ontology entities Eq in query q",
        "Expand: E* = Eq U Nk(Eq)  (k-hop graph walk)",
        "score(d) = alpha*sim(q,d) + (1-alpha)*overlap(E*,d)",
        "Fallback alpha=1.0 when no entity matched (pure semantic)",
        "Ontological context block prepended to generator prompt",
    ], lx, H - 136, size=9, spacing=22, max_width=cw, dot_color=ACCENT_BRIGHT)

    draw_card(c, lx, H - 358, cw, 44, ICE, 0.08)
    c.setFillColor(ICE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(lx + 10, H - 324, "score(d) = alpha * sim(q,d) + (1-alpha) * overlap(E*, d)")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(lx + 10, H - 340, "alpha=1 fallback prevents silent failure on out-of-domain queries")

    # OG-RAG
    draw_tag(c, rx, H - 112, "OG-RAG HYPERGRAPH", a(GOLD, 0.18), GOLD)
    draw_bullets(c, [
        "Hypernodes: atomic facts as subject+predicate+object strings",
        "Dual scoring: key_score(s+a) and value_score(v) via embedding",
        "union = top_by_key | top_by_value | concept_matched_indices",
        "Greedy set cover: pick hyperedge covering most uncovered nodes",
        "(1-1/e) approx guarantee  O(k*|E|) per query",
        "max_hyperedges=5 cap prevents retrieval dilution",
    ], rx, H - 136, size=9, spacing=20, max_width=cw, dot_color=GOLD)

    draw_card(c, rx, H - 372, cw, 44, GOLD, 0.08)
    c.setFillColor(GOLD_DIM)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(rx + 10, H - 334, "OG-RAG (Sharma et al., EMNLP 2025):")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(rx + 10, H - 350, "+55% fact recall  ·  +40% response correctness  ·  +27% deductive accuracy")

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 15 — Configuration & Parameters
# ─────────────────────────────────────────────────────────────────────────────
def s15(c):
    new_slide(c, 15, ACCENT)
    draw_slide_title(c, "Configuration & Parameters")
    draw_accent_rule(c, 48, width=230)
    draw_subtitle(c, "All configurable knobs and their defaults")

    params = [
        ("CHUNK_SIZE", "1200", "Max token size per semantic chunk (pysbd)", GOLD),
        ("CHUNK_OVERLAP", "200", "Overlap between adjacent chunks", GOLD),
        ("majority_vote N", "3", "Number of independent extraction runs", ACCENT_BRIGHT),
        ("min_votes", "2", "Minimum votes for element retention", ACCENT_BRIGHT),
        ("temperature", "0.1", "LLM sampling temperature for all extraction stages", ICE),
        ("SIMILARITY_THRESHOLD (tau)", "0.9", "Cosine threshold for entity canonicalization", ICE),
        ("min_freq", "3", "Minimum corpus occurrences for taxonomy grounding", PENDING),
        ("SequenceMatcher ratio", "0.6", "Minimum fuzzy-match score for class grounding check", PENDING),
        ("MAX_REASONING_ITERATIONS", "20", "Hard cap on OWL 2 RL forward-chaining iterations", ACCENT),
        ("confidence theta", "0.5", "Minimum confidence for inferred relations", ACCENT),
        ("k_nodes", "10", "Top-k nodes scored in OG-RAG dual embedding", GOLD),
        ("max_hyperedges", "5", "Greedy set cover cap to prevent retrieval dilution", GOLD),
        ("matched entities cap", "5", "Max entities in ontological context block for generator", ICE),
        ("reconciliation roots", "10", "Maximum top-level taxonomy roots after reconciliation pass", PENDING),
    ]

    cols = 2
    pw = (W - 96 - 12) / 2
    ph = 26
    for i, (name, val, desc, col) in enumerate(params):
        col_idx = i % 2
        row_idx = i // 2
        px = 48 + col_idx * (pw + 12)
        py = H - 116 - row_idx * (ph + 4)
        draw_card(c, px, py, pw, ph, col, 0.09, radius=3)
        c.setFillColor(col)
        c.setFont("Courier-Bold", 8)
        c.drawString(px + 8, py + ph / 2 + 2, name)
        c.setFillColor(GHOST)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawRightString(px + pw - 8, py + ph / 2 + 2, val)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7)
        c.drawString(px + 8, py + ph / 2 - 8, desc)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 16 — Error Handling
# ─────────────────────────────────────────────────────────────────────────────
def s16(c):
    new_slide(c, 16, GOLD)
    draw_slide_title(c, "Error Handling")
    draw_accent_rule(c, 48, width=170)
    draw_subtitle(c, "Failure modes and recovery strategies")

    cases = [
        ("JSONDecodeError in Stage 3", ACCENT,
         "try/except around LLM3 call in extract_ontology_sequential()",
         "Returns partial extraction (classes + instances only); pipeline continues",
         "repair_json() applied first — JSONDecodeError is last resort fallback"),
        ("Hallucinated concepts", GOLD,
         "corpus_frequency_check(): concepts < min_freq=3 in source are dropped",
         "_grounding_check(): SequenceMatcher ratio < 0.6 also drops candidates",
         "Combined filter suppresses LLM pretraining distribution drift"),
        ("Reasoning explosion (sym + trans)", ICE,
         "MAX_REASONING_ITERATIONS=20 terminates forward-chaining runaway",
         "per-iteration max_new_facts guard limits edge explosion per pass",
         "Observed case: related_to sym+trans generated 40k edges before cap"),
        ("Circular subclass chains", PENDING,
         "nx.find_cycle(graph.subclass_view()) checked after each iteration",
         "Cycle detected -> append to consistency_violations and break loop",
         "Prevents infinite subClassOf chains corrupting graph traversal"),
        ("Pipeline cancellation", ERROR,
         "cancel_check() lambda polled cooperatively at each pipeline stage",
         "PipelineCancelledError raised on True return; SSE stream notified",
         "Partial results available in OntologyGraph up to cancellation point"),
    ]

    for i, (title, col, l1, l2, l3) in enumerate(cases):
        sy = H - 124 - i * 82
        draw_card(c, 48, sy, W - 96, 72, col, 0.09)
        draw_left_accent_bar(c, 48, sy, 72, col, 5)
        draw_tag(c, 62, sy + 56, title, a(col, 0.20), col)
        c.setFillColor(GHOST)
        c.setFont("Helvetica", 8.5)
        c.drawString(62, sy + 40, l1)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(62, sy + 27, l2)
        c.drawString(62, sy + 14, l3)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 17 — Performance & Complexity
# ─────────────────────────────────────────────────────────────────────────────
def s17(c):
    new_slide(c, 17, ACCENT)
    draw_slide_title(c, "Performance & Complexity")
    draw_accent_rule(c, 48, width=230)
    draw_subtitle(c, "Complexity analysis and known bottlenecks")

    ops = [
        ("Canonicalization (current)", "O(n^2)", "Pairwise cosine scan over all entity vectors", "FAISS ANN → near-linear (planned)", ACCENT),
        ("OWL 2 RL Reasoning", "O(k * |rules| * m)", "k <= 20 iters, 6 rules, m = edge count", "Converges in <= 10 iters on all tested ontologies", GOLD),
        ("Graph Retrieval (BFS)", "O(|V| + |E|)", "k-hop neighbourhood expansion", "Linear in graph size; no known bottleneck", ICE),
        ("Greedy Set Cover", "O(k * |E|)", "Per query; k = max_hyperedges=5", "Tractable for hypergraphs up to thousands of nodes", PENDING),
        ("Majority Voting Extraction", "O(N * pipeline)", "N=3 independent full extraction passes", "Wall-clock cost: 3x single extraction + merge", ACCENT_BRIGHT),
        ("Embedding Encoding", "O(n * d)", "n entities, d = embedding dim (384 for MiniLM)", "Batch encoding amortises model load cost", GOLD_DIM),
    ]

    bw = (W - 96 - 12) / 2
    for i, (op, big_o, detail, note, col) in enumerate(ops):
        col_idx = i % 2
        row_idx = i // 2
        ox = 48 + col_idx * (bw + 12)
        oy = H - 116 - row_idx * 108
        draw_card(c, ox, oy, bw, 96, col, 0.09)
        draw_left_accent_bar(c, ox, oy, 96, col, 4)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(ox + 12, oy + 76, op)
        c.setFillColor(GOLD if col != GOLD else ICE)
        c.setFont("Courier-Bold", 14)
        c.drawString(ox + 12, oy + 54, big_o)
        c.setFillColor(GHOST)
        c.setFont("Helvetica", 8)
        c.drawString(ox + 12, oy + 38, detail)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(ox + 12, oy + 24, note)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 18 — Code Quality & Design Patterns
# ─────────────────────────────────────────────────────────────────────────────
def s18(c):
    new_slide(c, 18, GOLD)
    draw_slide_title(c, "Design Patterns & Code Quality")
    draw_accent_rule(c, 48, width=260)
    draw_subtitle(c, "Architectural decisions and software engineering practices")

    patterns = [
        ("Pipeline / Chain of Responsibility",
         "8 sequential stages each receive and transform the same ontology object. cancel_check() hook propagates cleanly.", ACCENT),
        ("Strategy Pattern",
         "LLM backend is interchangeable (LM Studio / OpenAI-compat) via unified complete() in llm/client.py.", GOLD),
        ("Decorator / Wrapper",
         "majority_vote() wraps extract_ontology_sequential() transparently — N runs without changing extractor interface.", ICE),
        ("Repository Pattern",
         "OntologyGraph abstracts all graph storage; callers never touch nx.DiGraph directly.", PENDING),
        ("Factory / Builder",
         "_build_extraction() constructs OntologyExtraction from raw LLM dicts with validation.", ACCENT_BRIGHT),
        ("Schema-First (Pydantic v2)",
         "All ontology entities are Pydantic v2 BaseModel subclasses — runtime type validation, .model_copy(), .merge().", GOLD_DIM),
        ("Provenance Tracking",
         "Every node and edge carries source_document, source_chunk, vote_count — full audit trail.", ICE),
        ("Cooperative Cancellation",
         "cancel_check() lambda passed down entire call stack — no thread kills, clean partial state.", PENDING),
    ]

    pw = (W - 96 - 12) / 2
    ph = 58
    for i, (title, desc, col) in enumerate(patterns):
        col_idx = i % 2
        row_idx = i // 2
        px = 48 + col_idx * (pw + 12)
        py = H - 116 - row_idx * (ph + 8)
        draw_card(c, px, py, pw, ph, col, 0.09, radius=4)
        draw_left_accent_bar(c, px, py, ph, col, 4)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(px + 12, py + ph - 16, title)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        wrap_text(c, desc, px + 12, py + ph - 30, pw - 22, 7.5, TEXT_MUTED)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 19 — Ablation Study & Evaluation
# ─────────────────────────────────────────────────────────────────────────────
def s19(c):
    new_slide(c, 19, ACCENT)
    draw_slide_title(c, "Ablation Study & Evaluation")
    draw_accent_rule(c, 48, width=240)
    draw_subtitle(c, "RAGAS-aligned metrics  ·  additive component evaluation")

    rows = [
        ("Baseline RAG", 0.61, 0.52, 0.58, 0.72),
        ("+ Extraction", 0.67, 0.61, 0.64, 0.76),
        ("+ Canonicalization", 0.71, 0.68, 0.68, 0.78),
        ("+ Reasoning", 0.73, 0.71, 0.70, 0.79),
        ("+ Onto Retrieval", 0.76, 0.78, 0.73, 0.81),
        ("+ OG-RAG", 0.78, 0.82, 0.75, 0.83),
    ]
    headers = ["Configuration", "Ctx Recall", "Entity Recall", "Ans. F1", "Faithfulness"]
    col_widths = [200, 100, 110, 90, 100]
    tx = 48
    ty = H - 116
    rh = 36

    # header
    for j, (hdr, cw) in enumerate(zip(headers, col_widths)):
        hx = tx + sum(col_widths[:j])
        c.setFillColor(a(ACCENT, 0.25))
        c.rect(hx, ty - 22, cw, 26, fill=1, stroke=0)
        c.setFillColor(GHOST)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(hx + 8, ty - 10, hdr)

    for i, (cfg, cr, er, af, fa) in enumerate(rows):
        ry = ty - 24 - (i + 1) * rh
        is_last = i == len(rows) - 1
        c.setFillColor(a(GOLD, 0.07) if is_last else a(GHOST, 0.02 + i * 0.01))
        c.rect(tx, ry, sum(col_widths), rh, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.4)
        c.rect(tx, ry, sum(col_widths), rh, fill=0, stroke=1)
        vals = [cfg, f"{cr:.2f}", f"{er:.2f}", f"{af:.2f}", f"{fa:.2f}"]
        for j, (val, cw) in enumerate(zip(vals, col_widths)):
            hx = tx + sum(col_widths[:j])
            if j == 0:
                c.setFillColor(GOLD if is_last else GHOST)
                c.setFont("Helvetica-Bold" if is_last else "Helvetica", 9)
            else:
                fv = float(val)
                c.setFillColor(ICE if fv >= 0.78 else (GOLD if fv >= 0.70 else TEXT_MUTED))
                c.setFont("Helvetica-Bold", 9.5)
            c.drawString(hx + 8, ry + rh / 2 - 4, val)

    # insight
    draw_card(c, 48, H - 432, W - 96, 46, ICE, 0.08)
    c.setFillColor(ICE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(64, H - 404, "Canonicalization delivers ~1/3 of total gain:  CR 0.67→0.71, ER 0.61→0.68")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(64, H - 420, "Duplicate entities fragment the graph — downstream retrieval cannot aggregate evidence across disjoint nodes.")
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 20 — Improvements & Summary
# ─────────────────────────────────────────────────────────────────────────────
def s20(c):
    new_slide(c, 20, GOLD)
    draw_glow_circle(c, W * 0.78, H * 0.48, 200, GOLD, 0.04)

    draw_slide_title(c, "Potential Improvements & Summary")
    draw_accent_rule(c, 48, width=300)
    draw_subtitle(c, "Future roadmap and key engineering takeaways")

    lx, rx = 48, W / 2 + 12
    cw = W / 2 - 72

    draw_tag(c, lx, H - 112, "IMPROVEMENTS")
    improvements = [
        "Replace O(n^2) canonicalization scan with FAISS ANN index — dominant cost above ~5k entities",
        "Domain-specific encoder (BioLM, LegalBERT) — may need different tau and reduce frequency-check dependence",
        "Async / parallel chunk extraction with cancellation propagation to reduce wall-clock pipeline time",
        "Evaluation at scale: larger gold ontologies, multi-domain benchmarks",
        "Direct ILP set cover for OG-RAG on small corpora (exact vs 0.63 greedy approx)",
        "Streaming graph updates via websocket — currently batched per chunk",
    ]
    draw_bullets(c, improvements, lx, H - 136, size=8.5, spacing=22, max_width=cw, dot_color=GOLD)

    draw_tag(c, rx, H - 112, "KEY TAKEAWAYS", a(ICE, 0.18), ICE)
    takeaways = [
        "Canonicalization alone accounts for ~1/3 of the total improvement over baseline",
        "OWL 2 RL reasoning converges in <10 iterations — inexpensive relative to LLM calls",
        "Hybrid retrieval degrades gracefully to pure semantic when no entities matched",
        "Full provenance (source_document, chunk_id, vote_count) on every node and edge",
        "cancel_check() cooperative hook enables safe partial-state extraction in production",
        "Pydantic v2 schema enforces type correctness at every stage boundary",
    ]
    draw_bullets(c, takeaways, rx, H - 136, size=8.5, spacing=22, max_width=cw, dot_color=ICE)

    # final metrics bar
    metrics = [("0.61→0.78", "Context Recall", ICE), ("0.72→0.83", "Faithfulness", GOLD),
               ("~10 iter", "OWL Convergence", ACCENT_BRIGHT), ("O(n^2)→O(n)", "Canon. target", PENDING)]
    mw = (W - 96 - 36) / 4
    for i, (val, lbl, col) in enumerate(metrics):
        draw_metric(c, 48 + i * (mw + 12), H - 430, mw, 56, val, lbl, col, col)

    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(OUTPUT), pagesize=landscape(A4))
    c.setTitle("Clearence — Technical Presentation")
    c.setAuthor("Reda Sarehane · Ontology Graph Research Team")
    for fn in [s01, s02, s03, s04, s05, s06, s07, s08, s09, s10,
               s11, s12, s13, s14, s15, s16, s17, s18, s19, s20]:
        fn(c)
    c.save()
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    build()
