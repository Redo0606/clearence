"""Clearence-Commercial.pdf — 18-slide product/pitch presentation.

Theme matches ontology_builder.ui.theme (Void #1a0f12, Magenta #b81365, Gold #f8c630, Ice #b1ddf1).
"""

import sys
from pathlib import Path

# Ensure project root is on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import landscape, A4
from presentations.slide_theme import *  # noqa: F403, F401

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "presentations" / "Clearence-Commercial.pdf"
TOTAL = 18


def new_slide(c, n, top_color=ACCENT):
    """Draw bg, top bar, and subtle glow. Caller must call draw_footer(c, n, TOTAL) at end before showPage()."""
    draw_bg(c)
    draw_top_bar(c, GOLD, height=6)
    draw_glow_circle(c, W * 0.85, H * 0.15, W * 0.35, ACCENT, alpha=0.04)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1 — Title / Hero (Cover)
# ─────────────────────────────────────────────────────────────────────────────
def s01(c):
    draw_bg(c)
    draw_top_bar(c, GOLD, height=6)
    draw_glow_circle(c, W * 0.85, H * 0.15, W * 0.35, ACCENT, alpha=0.04)

    # Glow behind left text block (magenta)
    draw_glow_circle(c, W * 0.25, H * 0.5, 300, ACCENT, 0.04)
    # Glow behind right metric grid (ice)
    draw_glow_circle(c, W * 0.80, H * 0.5, 220, ICE, 0.03)

    # Left 58% — wordmark, tagline, divider, team/version
    left_x = MARGIN
    c.setFillColor(GHOST)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 52)
    c.drawString(left_x, H - 118, "Clearence")
    c.setFillColor(TEXT_MUTED)
    c.setFont(_font(FONT_SYNE, "Helvetica"), 16)
    c.drawString(left_x, H - 158, "Smarter AI answers. Grounded in your knowledge graph.")
    draw_divider(c, left_x, H * 0.38, W * 0.5 - MARGIN * 1.5, a(GHOST, 0.15))
    draw_tag(c, left_x, H * 0.34, "Ontology Graph Research Team · v0.1.0 · March 2026",
             a(GHOST, 0.08), TEXT_MUTED2, 9)

    # Right 42% — strict 2×2 grid
    right_col_w = W - W * 0.58 - MARGIN - 12
    card_w = (right_col_w - 12) / 2
    card_h = 115
    row1_y = H / 2 + 10
    row2_y = H / 2 + 10 - card_h - 12
    col1_x = W * 0.58
    col2_x = W * 0.58 + card_w + 12
    grid = [
        (col1_x, row1_y, "+28%", "Context Recall", ACCENT_BRIGHT),
        (col2_x, row1_y, "+15%", "Faithfulness", GOLD),
        (col1_x, row2_y, "+55%", "Fact Recall vs RAG", ICE),
        (col2_x, row2_y, "+40%", "Response Correctness", ACCENT),
    ]
    for (x, y, val, label, color) in grid:
        draw_metric(c, x, y, card_w, card_h, val, label, color, color, val_size=36)

    draw_footer(c, 1, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2 — The Problem
# ─────────────────────────────────────────────────────────────────────────────
def s02(c):
    new_slide(c, 2, ACCENT)
    draw_slide_title(c, "THE PROBLEM")
    draw_subtitle(c, "Why AI systems fail on complex enterprise knowledge")

    card_w = (W - 2 * MARGIN - 16) / 2
    card_h = 125
    x_left = MARGIN
    x_right = MARGIN + card_w + 16
    y_top = CONTENT_TOP - 85
    y_bottom = y_top - card_h - 14
    cards_data = [
        (x_left, y_top, "Shallow Retrieval", "Finds similar-sounding docs but misses relational structure and inherited rules.", "link", ACCENT),
        (x_right, y_top, "Hallucinated Answers", "Without structured grounding, AI fills gaps with confident but incorrect pretraining data.", "shield", ERROR),
        (x_left, y_bottom, "Fragmented Evidence", "Duplicate entity names split evidence — 'ML' and 'machine learning' treated as different concepts.", "graph", GOLD),
        (x_right, y_bottom, "No Reasoning Trail", "Black-box retrieval can't explain source or logic — a blocker for compliance and legal use.", "doc", ICE),
    ]
    for (cx, cy, title, desc, picto, col) in cards_data:
        draw_feature_card(c, cx, cy, card_w, card_h, title, desc, col, picto_type=picto)

    draw_footer(c, 2, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3 — Market Need
# ─────────────────────────────────────────────────────────────────────────────
def s03(c):
    new_slide(c, 3, GOLD)
    draw_slide_title(c, "Market Need")
    draw_subtitle(c, "Who faces this problem — and why existing tools fall short")

    lx, rx = MARGIN, W / 2 + 12
    cw = W / 2 - MARGIN - 24

    # Vertical divider
    c.setStrokeColor(a(GHOST, 0.18))
    c.setLineWidth(1)
    c.line(W / 2 - 8, CONTENT_TOP - 70, W / 2 - 8, 80)
    c.setLineWidth(1)

    # Left column — WHO IS AFFECTED (industry pills)
    industries = ["Pharma & Life Sciences", "Legal & Financial", "Engineering & Manufacturing", "Research & Academia", "Enterprise IT & Security"]
    colors = [ACCENT, ICE, ACCENT, ICE, ACCENT]
    for i, (label, col) in enumerate(zip(industries, colors)):
        draw_tag(c, MARGIN + 8, CONTENT_TOP - 115 - i * 32, label, a(col, 0.18), col, 10)

    # Right column — WHY SOLUTIONS FAIL (mini cards, 54px height)
    draw_tag(c, rx, CONTENT_TOP - 8, "WHY SOLUTIONS FAIL", a(GOLD, 0.18), GOLD, 9)
    draw_accent_rule(c, rx, CONTENT_TOP - 24, 56, GOLD, 2)
    failures = [
        ("Plain RAG", "Dense vector search has no concept of subclass, transitivity, or domain constraints."),
        ("Knowledge Graphs Alone", "Can't handle natural language queries or extract knowledge from unstructured documents."),
        ("Fine-tuned LLMs", "Expensive to update, opaque reasoning, no live knowledge updates."),
        ("Manual Curation", "Prohibitively slow, doesn't scale to thousands of document-domains."),
        ("Search Engines", "Return documents not structured facts; no reasoning or inference capability."),
    ]
    fh = 54
    for i, (title, desc) in enumerate(failures):
        fy = CONTENT_TOP - 40 - i * (fh + 6)
        draw_card(c, rx, fy, cw, fh, ERROR, 0.08)
        draw_left_accent_bar(c, rx, fy, fh, ERROR, 4)
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 9)
        c.setFillColor(GHOST)
        c.drawString(rx + 44, fy + fh - 20, title)
        c.setFont(_font(FONT_SYNE, "Helvetica"), 7.5)
        c.setFillColor(TEXT_MUTED)
        wrap_text(c, desc, rx + 44, fy + fh - 34, cw - 52, 7.5, TEXT_MUTED, 2, max_lines=2)

    draw_footer(c, 3, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — The Solution
# ─────────────────────────────────────────────────────────────────────────────
def s04(c):
    new_slide(c, 4, ACCENT)
    draw_slide_title(c, "The Solution")
    draw_subtitle(c, "Clearence — automated ontology-powered RAG")

    # Horizontal 4-step pipeline (explicit x positions)
    gap = 20
    step_w = (W - 2 * MARGIN - 3 * gap) / 4
    step_h = 150
    y_base = H / 2 - step_h / 2 + 20
    steps = [
        ("1", "Auto-Build", "Upload any document. Clearence extracts a formal ontology automatically — concepts, relationships, hierarchy, and constraints."),
        ("2", "Auto-Expand", "Seven algorithms cross-check and enrich the graph. OWL 2 reasoning derives hidden facts."),
        ("3", "Auto-Retrieve", "Hybrid retrieval walks the knowledge graph before searching — surfacing facts pure embedding search would miss."),
        ("4", "Trusted Answers", "Every answer cites its source chunk, vote count, and confidence. Full provenance — no black-box surprises."),
    ]

    # Glow behind step 4
    draw_glow_circle(c, MARGIN + 3 * (step_w + gap) + step_w / 2, y_base + step_h / 2, 60, GOLD, 0.05)

    for i, (num, title, desc) in enumerate(steps):
        x = MARGIN + i * (step_w + gap)
        draw_card(c, x, y_base, step_w, step_h, ACCENT, 0.06)
        # Step number
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 28)
        c.setFillColor(GOLD)
        c.drawString(x + 12, y_base + step_h - 32, num)
        # Title
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 11)
        c.setFillColor(GHOST)
        c.drawString(x + 12, y_base + step_h - 52, title)
        # Description
        wrap_text(c, desc, x + 12, y_base + step_h - 68, step_w - 24, 8, TEXT_MUTED, 2, max_lines=5)
        # Arrow between steps
        if i < 3:
            ax = x + step_w + gap / 2 - 5
            ay = y_base + step_h / 2
            draw_arrow(c, ax, ay, ACCENT_BRIGHT)

    draw_footer(c, 4, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5 — Product Overview
# ─────────────────────────────────────────────────────────────────────────────
def s05(c):
    new_slide(c, 5, GOLD)
    draw_slide_title(c, "Product Overview")
    draw_subtitle(c, "How Clearence works — in plain terms")

    # Vertical timeline — spine and nodes
    spine_x = MARGIN + 20
    c.setStrokeColor(a(ACCENT, 0.25))
    c.setLineWidth(1.5)
    c.line(spine_x, CONTENT_TOP - 55, spine_x, CONTENT_TOP - 295)
    c.setLineWidth(1)

    node_ys = [CONTENT_TOP - 75, CONTENT_TOP - 145, CONTENT_TOP - 215, CONTENT_TOP - 285]
    steps = [
        ("Upload Your Documents", "PDFs, Word docs, text files — anything. Clearence handles the ingestion automatically."),
        ("Clearence Reads & Understands", "Reads every sentence and extracts concepts, relationships, and rules — building a living knowledge map."),
        ("The Knowledge Graph Gets Smarter", "Algorithms cross-validate, deduplicate, and reason over the graph. Hidden connections are surfaced."),
        ("Ask Questions in Plain Language", "Type a question. Clearence walks the knowledge graph, finds the most relevant facts, then generates a grounded answer."),
    ]
    for i, (node_y, (title, desc)) in enumerate(zip(node_ys, steps)):
        draw_glow_circle(c, spine_x, node_y, 12, ACCENT, 0.12)
        c.setFillColor(ACCENT)
        c.circle(spine_x, node_y, 5, fill=1, stroke=0)
        c.setFont(_font(FONT_DM_MONO, "Courier"), 8)
        c.setFillColor(GOLD)
        c.drawCentredString(spine_x, node_y - 4, str(i + 1))
        draw_card(c, MARGIN + 40, node_y - 26, W - 2 * MARGIN - 40, 52, ACCENT, 0.05)
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 11)
        c.setFillColor(GHOST)
        c.drawString(MARGIN + 56, node_y + 4, title)
        wrap_text(c, desc, MARGIN + 56, node_y - 14, W - 2 * MARGIN - 64, 8.5, TEXT_MUTED)

    draw_footer(c, 5, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6 — Key Features
# ─────────────────────────────────────────────────────────────────────────────
def s06(c):
    new_slide(c, 6, ACCENT)
    draw_slide_title(c, "Key Features")
    draw_subtitle(c, "What makes Clearence uniquely capable")

    col_w = (W - 2 * MARGIN - 24) / 3
    card_h = 112
    row1_y = CONTENT_TOP - 88
    row2_y = row1_y - card_h - 12
    xs = [MARGIN, MARGIN + col_w + 12, MARGIN + 2 * (col_w + 12)]

    row1_data = [
        ("Auto Knowledge Extraction", "No manual ontology engineering. Clearence extracts concepts, instances, relationships, and logical rules directly from your documents.", "doc", ACCENT),
        ("Majority-Vote Reliability", "Every extracted fact is cross-checked across multiple AI runs. Only facts confirmed by at least 2 of 3 passes make it into the graph.", "vote", GOLD),
        ("Two-Stage Grounding", "Every proposed concept is verified both by AI judgement and by counting occurrences in your source text. Hallucinated concepts are automatically filtered.", "shield", ICE),
    ]
    for i, (title, desc, picto, col) in enumerate(row1_data):
        draw_feature_card(c, xs[i], row1_y, col_w, card_h, title, desc, col, picto_type=picto)

    row2_data = [
        ("Symbolic Reasoning", "OWL 2 reasoning engine derives facts not explicitly stated. If A is a subtype of B and B has property P, the system knows A also has P.", "reason", ACCENT),
        ("Hybrid Retrieval", "Answers combine dense semantic search with structured graph traversal — finding both similar passages and logically connected facts.", "graph", GOLD),
        ("Full Provenance", "Every answer traces back to its exact source document, chunk, and confidence score. Auditable by design.", "check", ICE),
    ]
    for i, (title, desc, picto, col) in enumerate(row2_data):
        draw_feature_card(c, xs[i], row2_y, col_w, card_h, title, desc, col, picto_type=picto)

    # Full-width bottom card
    bottom_y = row2_y - 68
    draw_card(c, MARGIN, bottom_y, W - 2 * MARGIN, 56, GOLD, 0.09)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 9.5)
    c.setFillColor(GHOST)
    c.drawString(MARGIN + 16, bottom_y + 36, "Local or Cloud LLM — Works with LM Studio and OpenAI-compatible APIs.")
    c.setFont(_font(FONT_SYNE, "Helvetica"), 8.5)
    c.setFillColor(TEXT_MUTED)
    c.drawString(MARGIN + 16, bottom_y + 20, "Your data stays in your infrastructure.")
    draw_tag(c, W - MARGIN - 110, bottom_y + 38, "LLM-Agnostic", a(GOLD, 0.25), VOID, 8)

    draw_footer(c, 6, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7 — How It Works (6-step pipeline)
# ─────────────────────────────────────────────────────────────────────────────
def s07(c):
    new_slide(c, 7, GOLD)
    draw_slide_title(c, "How It Works")
    draw_subtitle(c, "From document to trusted answer — no setup required")

    steps_data = [
        ("Upload", "doc", ACCENT, "Drop in any document — PDF, Word, plain text"),
        ("Extract", "graph", ACCENT, "AI reads and maps every concept, instance, and relationship"),
        ("Validate", "vote", ACCENT, "Facts cross-checked by 3 independent AI passes + source frequency"),
        ("Reason", "reason", GOLD, "Symbolic engine derives hundreds of implicit facts automatically"),
        ("Search", "link", GOLD, "Your query walks the knowledge graph AND searches semantically"),
        ("Answer", "check", GOLD, "Grounded response with full source citation and confidence score"),
    ]
    gap = 8
    step_w = (W - 2 * MARGIN - 5 * gap) / 6
    card_h = 150
    y_base = H / 2 - card_h / 2 + 10

    for i, (name, picto, color, desc) in enumerate(steps_data):
        x = MARGIN + i * (step_w + gap)
        border_color = a(GOLD, 0.4) if i >= 3 else a(ACCENT, 0.35)
        draw_card(c, x, y_base, step_w, card_h, color, 0.07, border_override=border_color)
        draw_picto(c, x + step_w / 2, y_base + card_h - 28, 16, picto, color)
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 9.5)
        c.setFillColor(GHOST)
        c.drawCentredString(x + step_w / 2, y_base + card_h - 50, name)
        draw_accent_rule(c, x + 10, y_base + card_h - 56, step_w - 20, color)
        wrap_text(c, desc, x + 8, y_base + card_h - 68, step_w - 16, 7.5, TEXT_MUTED, 2, max_lines=4)

        # Arrow between cards (path-based triangle)
        if i < 5:
            ax = x + step_w + 1
            ay = y_base + card_h / 2
            p = c.beginPath()
            p.moveTo(ax, ay + 5)
            p.lineTo(ax + 7, ay)
            p.lineTo(ax, ay - 5)
            p.close()
            c.setFillColor(ACCENT_BRIGHT)
            c.drawPath(p, fill=1, stroke=0)

    draw_footer(c, 7, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 8 — Technical Strength
# ─────────────────────────────────────────────────────────────────────────────
def s08(c):
    new_slide(c, 8, ACCENT)
    draw_slide_title(c, "Technical Strength")
    draw_subtitle(c, "What makes the solution robust and production-ready")

    col_w = (W - 2 * MARGIN - 16) / 2
    card_h = 108
    x_l, x_r = MARGIN, MARGIN + col_w + 16
    ys = [CONTENT_TOP - 88, CONTENT_TOP - 88 - card_h - 12, CONTENT_TOP - 88 - 2 * (card_h + 12)]

    strengths = [
        (x_l, ys[0], "Pydantic v2 Validation", "Type-safe at ingestion. No malformed data reaches the graph.", "shield", ACCENT, True),
        (x_r, ys[0], "JSON Repair & Recovery", "Malformed LLM output is salvaged. A single bad chunk never crashes the pipeline.", "check", GOLD, False),
        (x_l, ys[1], "Cooperative Cancellation", "Cancel any long-running pipeline mid-flight. Partial results are preserved.", "stream", ICE, True),
        (x_r, ys[1], "Circular Dependency Guard", "Detects and breaks circular subclass chains before they corrupt the graph.", "graph", ACCENT, False),
        (x_l, ys[2], "Graph Health Monitoring", "Grade A–F quality scoring after every build. Tracks depth, breadth, and instance ratios.", "reason", GOLD, True),
        (x_r, ys[2], "Docker Deployment", "Fully containerised. Bring your own LLM via LM Studio or any OpenAI-compatible endpoint.", "cloud", ICE, False),
    ]
    tag_w = c.stringWidth("PRODUCTION-READY", _font(FONT_DM_MONO, "Courier"), 7) + 20
    for (sx, sy, title, desc, picto, col, has_badge) in strengths:
        draw_feature_card(c, sx, sy, col_w, card_h, title, desc, col, picto_type=picto)
        if has_badge:
            draw_tag(c, sx + col_w - tag_w - 10, sy + card_h - 16, "PRODUCTION-READY", a(ICE, 0.18), ICE, 7)

    draw_footer(c, 8, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 9 — Performance & Efficiency
# ─────────────────────────────────────────────────────────────────────────────
def s09(c):
    new_slide(c, 9, GOLD)
    draw_slide_title(c, "Performance & Efficiency")
    draw_subtitle(c, "Measured improvements over baseline RAG")

    card_w = (W - 2 * MARGIN - 36) / 4
    card_h = 128
    y_cards = CONTENT_TOP - 55 - card_h
    metrics = [
        ("+28%", "Context Recall", "0.61 → 0.78", ACCENT_BRIGHT),
        ("+15%", "Faithfulness", "0.72 → 0.83", GOLD),
        ("+29%", "Entity Recall", "0.52 → 0.82", ICE),
        ("+29%", "Answer F1", "0.58 → 0.75", ACCENT),
    ]
    for i, (val, lbl, sub_text, col) in enumerate(metrics):
        x = MARGIN + i * (card_w + 12)
        draw_metric(c, x, y_cards, card_w, card_h, val, lbl, col, col, sub=sub_text)

    draw_accent_rule(c, MARGIN, y_cards - 18, W - 2 * MARGIN, BORDER, 1)
    draw_tag(c, MARGIN, y_cards - 42, "EFFICIENCY HIGHLIGHTS", a(GOLD, 0.18), GOLD)
    effs = [
        "Reasoning converges in fewer than 10 iterations on all tested ontologies — inexpensive relative to LLM inference cost",
        "Embedding cache is serialized to disk — zero re-encoding cost on knowledge base reload for previously seen entities",
        "Greedy set cover (vs exact ILP) delivers 63% quality guarantee with linear time complexity, tractable at thousands of nodes",
        "Majority voting adds 3x extraction cost but eliminates downstream retrieval failures from hallucinated graph nodes",
        "Chunking with overlap (200 token stride) ensures boundary facts are captured without duplication in the final graph",
    ]
    draw_bullets(c, effs, MARGIN, y_cards - 58, size=9, spacing=22, max_width=W - 2 * MARGIN, dot_color=GOLD)

    draw_footer(c, 9, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 10 — Competitive Advantages
# ─────────────────────────────────────────────────────────────────────────────
def s10(c):
    new_slide(c, 10, ACCENT)
    draw_slide_title(c, "Competitive Advantages")
    draw_subtitle(c, "Why Clearence outperforms alternative approaches")

    cap_w = (W - 2 * MARGIN) * 0.30
    other_w = ((W - 2 * MARGIN) * 0.70) / 4
    cols_x = [MARGIN, MARGIN + cap_w, MARGIN + cap_w + other_w, MARGIN + cap_w + 2 * other_w, MARGIN + cap_w + 3 * other_w]
    col_ws = [cap_w, other_w, other_w, other_w, other_w]
    row_h = 28
    header_y = CONTENT_TOP - 72

    draw_card(c, MARGIN, header_y, W - 2 * MARGIN, row_h, GOLD, 0.14)
    headers = ["Capability", "Plain RAG", "Manual KG", "Fine-tuned LLM", "Clearence"]
    for j, hdr in enumerate(headers):
        cx = cols_x[j] + col_ws[j] / 2
        c.setFont(_font(FONT_DM_MONO, "Courier"), 9)
        c.setFillColor(GOLD)
        c.drawCentredString(cx, header_y + row_h / 2 - 4, hdr)

    draw_left_accent_bar(c, cols_x[4] - 2, header_y - 8 * row_h, 9 * row_h, GOLD, 3)

    rows = [
        ("Automatic knowledge extraction", "No", "No", "Partial", "Yes"),
        ("Formal ontology reasoning", "No", "Yes", "No", "Yes"),
        ("Source provenance per answer", "Partial", "Yes", "No", "Yes"),
        ("Handles new documents live", "Yes", "No", "No", "Yes"),
        ("Hallucination guard", "Weak", "N/A", "Weak", "3-layer"),
        ("Deduplication / canonicalization", "No", "Manual", "No", "Auto"),
        ("API-first + streaming", "Varies", "No", "Varies", "Yes"),
        ("Open LLM backend support", "Varies", "N/A", "No", "Yes"),
    ]

    tag_styles = {
        "Yes": (a(ACCENT, 0.2), ACCENT_BRIGHT),
        "No": (a(ERROR, 0.15), ERROR),
        "Partial": (a(GOLD, 0.15), GOLD_DIM),
        "Varies": (a(GOLD, 0.15), GOLD_DIM),
        "Manual": (a(GOLD, 0.15), GOLD_DIM),
        "N/A": (a(GOLD, 0.15), GOLD_DIM),
        "Weak": (a(ERROR, 0.1), GOLD_DIM),
        "3-layer": (a(ICE, 0.2), ICE),
        "Auto": (a(ICE, 0.2), ICE),
    }

    for r, row in enumerate(rows):
        ry = header_y - (r + 1) * row_h
        if r % 2 == 1:
            draw_card(c, MARGIN, ry, W - 2 * MARGIN, row_h, ACCENT, 0.04)
        c.setFont(_font(FONT_SYNE, "Helvetica"), 8.5)
        c.setFillColor(GHOST)
        c.drawString(cols_x[0] + 8, ry + row_h / 2 - 3, row[0])
        for j, val in enumerate(row[1:], 1):
            bg, fg = tag_styles.get(val, (a(GHOST, 0.1), TEXT_MUTED))
            tw = len(val) * 5.5 + 14
            tx = cols_x[j] + (col_ws[j] - tw) / 2
            draw_tag(c, tx, ry + row_h - 8, val, bg, fg, 7.5)

    draw_footer(c, 10, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 11 — Scalability
# ─────────────────────────────────────────────────────────────────────────────
def s11(c):
    new_slide(c, 11, GOLD)
    draw_slide_title(c, "Scalability")
    draw_subtitle(c, "How Clearence grows with your knowledge base")

    lx = MARGIN
    cw_left = (W - 2 * MARGIN) * 0.60
    rx = W - MARGIN - (W - 2 * MARGIN) * 0.36

    draw_tag(c, lx, CONTENT_TOP - 8, "WHAT SCALES TODAY", a(ACCENT, 0.18), ACCENT_BRIGHT)
    current = [
        "Parallel chunk extraction — multiple document segments processed concurrently",
        "Incremental graph merge — new documents extend existing KB without full rebuild",
        "Embedding cache — previously seen entities never re-encoded on reload",
        "Batch canonicalization — entity deduplication grouped for encoding efficiency",
        "Optimised for 1,000–10,000 concept range typical of domain-specific extraction",
        "Docker containerisation — horizontal scaling via orchestration platforms",
    ]
    draw_bullets(c, current, lx, CONTENT_TOP - 110, size=8.5, spacing=16, max_width=cw_left, dot_color=ACCENT)

    draw_divider(c, lx, CONTENT_TOP - 280, cw_left, a(GHOST, 0.15))

    draw_tag(c, lx, CONTENT_TOP - 295, "ROADMAP FOR SCALE", a(GOLD, 0.18), GOLD)
    roadmap = [
        "FAISS ANN index — replaces O(n^2) canonicalization scan with near-linear lookup",
        "Async pipeline stages — parallel execution of independent extraction sub-tasks",
        "Distributed graph store — swap NetworkX for a production graph database (Neo4j, Amazon Neptune)",
        "Multi-domain KB federation — separate graphs per domain with cross-graph query routing",
        "Domain-specific encoders — higher canonicalization precision at specialist vocabulary",
    ]
    draw_bullets(c, roadmap, lx, CONTENT_TOP - 310, size=8.5, spacing=16, max_width=cw_left, dot_color=GOLD)

    # Right column — 4 metric cards stacked vertically
    mini_w = (W - 2 * MARGIN) * 0.36
    mini_h = 72
    x_metrics = W - MARGIN - mini_w
    metric_ys = [CONTENT_TOP - 88, CONTENT_TOP - 88 - 84, CONTENT_TOP - 88 - 168, CONTENT_TOP - 88 - 252]
    scale_stats = [
        ("1k–10k", "Concepts per domain ontology (current sweet spot)", ACCENT),
        ("<10 iter", "OWL reasoning convergence on all tested ontologies", GOLD),
        ("3×", "Extraction cost of majority voting vs single pass", ICE),
        ("0.63", "Greedy set cover approximation quality guarantee", ACCENT),
    ]
    for (val, lbl, col), my in zip(scale_stats, metric_ys):
        draw_metric(c, x_metrics, my, mini_w, mini_h, val, lbl, col, col)

    draw_footer(c, 11, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 12 — Use Cases
# ─────────────────────────────────────────────────────────────────────────────
def s12(c):
    new_slide(c, 12, ACCENT)
    draw_slide_title(c, "Use Cases")
    draw_subtitle(c, "Real-world applications of Clearence")

    card_w = (W - 2 * MARGIN - 16) / 2
    card_h = 130
    x_l, x_r = MARGIN, MARGIN + card_w + 16
    y_top = CONTENT_TOP - 88
    y_bot = y_top - card_h - 14
    cases = [
        (x_l, y_top, "Clinical Decision Support", "Upload clinical guidelines, drug databases, trial protocols. Clinicians ask natural-language questions and receive grounded, citable answers.", "shield", ACCENT),
        (x_r, y_top, "Legal Research & Due Diligence", "Feed case law, regulations, contract templates. The knowledge graph captures statutory hierarchies. Associates query in plain English.", "doc", GOLD),
        (x_l, y_bot, "Technical Docs Q&A", "Ingest engineering manuals, API docs, specs. Clearence extracts component relationships. Engineers get answers that traverse the full hierarchy.", "graph", ICE),
        (x_r, y_bot, "Competitive Intelligence", "Process research papers, patent filings, market reports. Clearence maps concept relationships across documents.", "link", ACCENT),
    ]
    for (cx, cy, title, desc, picto, col) in cases:
        draw_feature_card(c, cx, cy, card_w, card_h, title, desc, col, picto_type=picto)

    draw_footer(c, 12, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 13 — Target Users
# ─────────────────────────────────────────────────────────────────────────────
def s13(c):
    new_slide(c, 13, GOLD)
    draw_slide_title(c, "Target Users")
    draw_subtitle(c, "Who benefits most from Clearence")

    col_w = (W - 2 * MARGIN - 16) / 2
    card_h = 96
    xs = [MARGIN, MARGIN + col_w + 16]
    ys = [CONTENT_TOP - 88, CONTENT_TOP - 88 - card_h - 10, CONTENT_TOP - 88 - 2 * (card_h + 10)]
    personas = [
        ("AI/ML Engineers", "Building RAG pipelines who need structured knowledge to ground LLM responses — without manual ontology engineering.", ACCENT, "Plug-in pipeline module"),
        ("Knowledge Engineers", "Who want automated ontology population from documents instead of manual triple authoring.", GOLD, "Full extraction suite"),
        ("Enterprise Architects", "Deploying AI Q&A systems that require auditability, provenance, and compliance-friendly source attribution.", ICE, "Provenance by design"),
        ("Research Teams", "Working with dense technical literature who need to surface cross-paper conceptual relationships automatically.", ACCENT, "Literature mapping"),
        ("Product Teams", "Building domain-specific AI assistants that must stay accurate and up-to-date as source documents evolve.", GOLD, "Incremental updates"),
        ("Compliance Officers", "Who need AI systems that can demonstrate exactly which source text produced each answer, with confidence scores.", ICE, "Audit trail"),
    ]
    for i, (name, desc, col, tag_lbl) in enumerate(personas):
        ci, ri = i % 2, i // 2
        px, py = xs[ci], ys[ri]
        draw_feature_card(c, px, py, col_w, card_h, name, desc, col, picto_type="doc")
        tw = c.stringWidth(tag_lbl, _font(FONT_DM_MONO, "Courier"), 8) + 16
        draw_tag(c, px + col_w - tw - 10, py + card_h - 18, tag_lbl, a(col, 0.20), col, 8)

    draw_footer(c, 13, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 14 — Integration
# ─────────────────────────────────────────────────────────────────────────────
def s14(c):
    new_slide(c, 14, ACCENT)
    draw_slide_title(c, "Integration")
    draw_subtitle(c, "How Clearence fits into your existing stack")

    lx, rx = MARGIN, W / 2 + 8
    card_w = (W - 2 * MARGIN) * 0.46
    card_h = 52

    draw_tag(c, lx, CONTENT_TOP - 80, "API SURFACE", a(ACCENT, 0.18), ACCENT_BRIGHT, 9)
    api_items = [
        ("REST / FastAPI", "HTTP endpoints for document upload, pipeline trigger, status polling, and Q&A"),
        ("SSE Streaming", "Real-time progress events as ontology builds — integrate into any UI"),
        ("process_document()", "Python SDK entry point — embed Clearence directly in your codebase"),
        ("build_index()", "Creates RAG-ready query index from any OntologyGraph object"),
        ("cancel_check() hook", "Cooperative cancellation — safe for long-running automation pipelines"),
    ]
    for i, (name, desc) in enumerate(api_items):
        ry = CONTENT_TOP - 100 - i * (card_h + 8)
        draw_card(c, lx, ry, card_w, card_h, ACCENT, 0.09)
        draw_left_accent_bar(c, lx, ry, card_h, ACCENT, 4)
        c.setFont(_font(FONT_DM_MONO, "Courier"), 9.5)
        c.setFillColor(GHOST)
        c.drawString(lx + 12, ry + 34, name)
        c.setFont(_font(FONT_SYNE, "Helvetica"), 8)
        c.setFillColor(TEXT_MUTED)
        c.drawString(lx + 12, ry + 18, desc)

    draw_tag(c, rx, CONTENT_TOP - 80, "STACK COMPATIBILITY", a(GOLD, 0.18), GOLD, 9)
    compat = [
        ("Document formats", "PDF · DOCX · TXT · Markdown"),
        ("LLM backends", "LM Studio (local) · OpenAI-compatible APIs"),
        ("Embedding models", "all-MiniLM-L6-v2 (swappable)"),
        ("Graph storage", "NetworkX DiGraph (Neo4j / Neptune roadmap)"),
        ("Evaluation", "RAGAS framework · custom P/R/F1 harness"),
        ("Deployment", "Docker · environment-variable configuration"),
    ]
    row_h = 32
    for i, (name, val) in enumerate(compat):
        ky = CONTENT_TOP - 100 - i * row_h
        c.setFont(_font(FONT_DM_MONO, "Courier"), 9)
        c.setFillColor(GOLD)
        c.drawString(rx, ky, name)
        draw_divider(c, rx, ky - 4, W - rx - MARGIN, a(GHOST, 0.12))
        c.setFont(_font(FONT_SYNE, "Helvetica"), 8.5)
        c.setFillColor(TEXT_MUTED)
        c.drawString(rx, ky - 20, val)

    draw_footer(c, 14, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 15 — Value Proposition
# ─────────────────────────────────────────────────────────────────────────────
def s15(c):
    new_slide(c, 15, GOLD)
    draw_slide_title(c, "Value Proposition")
    draw_subtitle(c, "The core business case for Clearence")

    draw_accent_rule(c, MARGIN, CONTENT_TOP - 86, 80, GOLD, 2)
    draw_card(c, MARGIN, CONTENT_TOP - 72, W - 2 * MARGIN, 50, GOLD, 0.08)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 11)
    c.setFillColor(GHOST)
    c.drawCentredString(W / 2, CONTENT_TOP - 48, "Clearence turns your unstructured documents into a reasoning engine — not just a search index.")
    c.setFont(_font(FONT_SYNE, "Helvetica"), 9.5)
    c.setFillColor(TEXT_MUTED)
    c.drawCentredString(W / 2, CONTENT_TOP - 62, "More accurate, more trustworthy, and fully auditable — without manual knowledge engineering.")

    col_w = (W - 2 * MARGIN - 16) / 2
    card_h = 88
    xs = [MARGIN, MARGIN + col_w + 16]
    ys = [CONTENT_TOP - 100 - card_h, CONTENT_TOP - 100 - 2 * card_h - 10, CONTENT_TOP - 100 - 3 * card_h - 20]
    values = [
        ("Higher Answer Accuracy", "+28% context recall, +15% faithfulness over flat RAG. Your AI finds the right facts.", "check", ACCENT),
        ("Zero Knowledge Engineering", "No ontology experts required. Upload documents — the system builds the graph automatically.", "doc", GOLD),
        ("Compliance-Ready Answers", "Every answer cites exact source, chunk, and confidence. Satisfies audit and legal requirements.", "shield", ICE),
        ("LLM-Agnostic Architecture", "Switch between local and cloud models without rebuilding pipelines.", "cloud", ACCENT),
        ("Reduces Hallucination Risk", "Three validation layers — majority voting, corpus grounding, symbolic reasoning.", "vote", GOLD),
        ("Accelerates Domain Expertise", "Domain expert knowledge in documents becomes a queryable graph in minutes.", "reason", ICE),
    ]
    for i, (title, desc, picto, col) in enumerate(values):
        ci, ri = i % 2, i // 2
        draw_feature_card(c, xs[ci], ys[ri], col_w, card_h, title, desc, col, picto_type=picto)

    draw_footer(c, 15, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 16 — Future Roadmap
# ─────────────────────────────────────────────────────────────────────────────
def s16(c):
    new_slide(c, 16, ACCENT)
    draw_slide_title(c, "Future Roadmap")
    draw_subtitle(c, "Where Clearence is headed")

    phases = [
        ("Now", [
            "7-methodology unified pipeline (extraction → reasoning → OG-RAG)",
            "FastAPI streaming interface with cooperative cancellation",
            "Full provenance on every node, edge, and answer",
            "Docker deployment with LM Studio + OpenAI-compat support",
        ], ACCENT),
        ("Near-term", [
            "FAISS approximate nearest-neighbour for near-linear canonicalization",
            "Async/parallel chunk extraction for faster pipeline throughput",
            "Domain-specific encoder support (BioLM, LegalBERT, FinBERT)",
            "Evaluation at scale: multi-domain benchmarks and larger gold ontologies",
        ], GOLD),
        ("Future", [
            "Production graph database backend (Neo4j / Amazon Neptune)",
            "Multi-domain KB federation with cross-graph query routing",
            "Direct ILP optimal set cover for OG-RAG on dense corpora",
            "Real-time incremental ontology updates from streaming document sources",
        ], ICE),
    ]

    col_w = (W - 2 * MARGIN - 2 * 16) / 3
    col_h = 290
    x_cols = [MARGIN, MARGIN + col_w + 16, MARGIN + 2 * (col_w + 16)]
    col_configs = [
        ("Now", ACCENT, "v0.1.0", phases[0][1]),
        ("Near-term", GOLD, None, phases[1][1]),
        ("Future", ICE, None, phases[2][1]),
    ]

    for (label, color, badge, items_list), x in zip(col_configs, x_cols):
        draw_card(c, x, CONTENT_TOP - 90, col_w, col_h, color, 0.05)
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 14)
        c.setFillColor(GHOST)
        c.drawString(x + 14, CONTENT_TOP - 108, label)
        draw_accent_rule(c, x + 14, CONTENT_TOP - 114, col_w - 28, color)
        if badge:
            draw_tag(c, x + 14, CONTENT_TOP - 132, badge, a(GOLD, 0.20), GOLD, 8)
        start_y = CONTENT_TOP - 148 if badge else CONTENT_TOP - 132
        draw_bullets(c, items_list, x + 14, start_y, size=8.5, spacing=18, max_width=col_w - 28, dot_color=color)

    draw_footer(c, 16, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 17 — Summary
# ─────────────────────────────────────────────────────────────────────────────
def s17(c):
    new_slide(c, 17, GOLD)
    draw_slide_title(c, "Summary")
    draw_subtitle(c, "The Clearence advantage — at a glance")

    col_w = (W - 2 * MARGIN - 16) / 2
    card_h = 88
    xs = [MARGIN, MARGIN + col_w + 16]
    ys = [CONTENT_TOP - 88, CONTENT_TOP - 88 - card_h - 10, CONTENT_TOP - 88 - 2 * (card_h + 10)]
    strengths = [
        ("Fully automated", "From raw document to queryable knowledge graph with no manual ontology work", ACCENT, "doc"),
        ("Multi-layer validation", "Majority voting + corpus grounding + symbolic reasoning eliminates hallucinated facts", GOLD, "vote"),
        ("Hybrid intelligence", "Symbolic graph reasoning + neural embeddings — structure where you need it", ICE, "graph"),
        ("Measurable uplift", "+28% context recall, +15% faithfulness, +55% accurate-fact recall over vanilla RAG", ACCENT, "check"),
        ("Production-ready", "FastAPI · SSE streaming · Docker · full provenance · cooperative cancellation", GOLD, "stream"),
        ("Open & interoperable", "Local or cloud LLM · any document format · embeddable Python SDK · REST API", ICE, "cloud"),
    ]
    for i, (title, desc, col, picto) in enumerate(strengths):
        ci, ri = i % 2, i // 2
        draw_feature_card(c, xs[ci], ys[ri], col_w, card_h, title, desc, col, picto_type=picto)

    # Closing statement card at bottom (y=62, h=46, leaves 34px clearance above footer)
    bar_y = 62
    draw_card(c, MARGIN, bar_y, W - 2 * MARGIN, 46, GOLD, 0.08)
    c.setFont(_font(FONT_SYNE, "Helvetica"), 9.5)
    c.setFillColor(GHOST)
    c.drawCentredString(W / 2, bar_y + 30, "Clearence makes AI trustworthy by grounding it in formal knowledge —")
    c.drawCentredString(W / 2, bar_y + 14, "automatically extracted, rigorously validated, and symbolically reasoned over from your own documents.")

    draw_footer(c, 17, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 18 — Call to Action
# ─────────────────────────────────────────────────────────────────────────────
def s18(c):
    new_slide(c, 18, ACCENT)
    draw_glow_circle(c, W * 0.5, H * 0.5, 300, ACCENT, 0.05)
    draw_glow_circle(c, W * 0.5, H * 0.5, 180, GOLD, 0.04)

    # Centered hero
    c.setFillColor(GHOST)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 36)
    title = "Ready to build smarter AI?"
    tw = c.stringWidth(title, _font(FONT_SYNE, "Helvetica-Bold"), 36)
    c.drawString((W - tw) / 2, H - 130, title)

    c.setFillColor(TEXT_MUTED)
    c.setFont(_font(FONT_SYNE, "Helvetica"), 13)
    sub = "Clearence is open for integration, deployment, and partnership."
    sw2 = c.stringWidth(sub, _font(FONT_SYNE, "Helvetica"), 13)
    c.drawString((W - sw2) / 2, H - 160, sub)

    draw_accent_rule(c, W / 2 - 100, H - 178, 200, GOLD, 2)

    # Three horizontal CTA cards (explicit x positions)
    card_w = (W - 2 * MARGIN - 2 * 16) / 3
    card_h = 180
    y_cards = H / 2 - card_h / 2
    x_cols = [MARGIN, MARGIN + card_w + 16, MARGIN + 2 * (card_w + 16)]
    ctas = [
        ("1", "Deploy It", "DEPLOY", "Docker container. Connect your LLM backend. Drop in documents. Running in under an hour."),
        ("2", "Integrate It", "INTEGRATE", "Python SDK or REST API. Plug Clearence into your existing RAG or Q&A pipeline."),
        ("3", "Evaluate It", "EVALUATE", "Run against your domain documents. Measure the accuracy lift. Compare to your current retrieval."),
    ]
    for (num, title, badge, desc), x in zip(ctas, x_cols):
        draw_card(c, x, y_cards, card_w, card_h, GOLD, 0.08)
        bw = len(badge) * 6 + 16
        draw_tag(c, x + (card_w - bw) / 2, y_cards + card_h - 22, badge, a(GOLD, 0.25), GOLD, 8)
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 36)
        c.setFillColor(GOLD)
        c.drawCentredString(x + card_w / 2, y_cards + card_h - 68, num)
        c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 13)
        c.setFillColor(GHOST)
        c.drawCentredString(x + card_w / 2, y_cards + card_h - 90, title)
        wrap_text(c, desc, x + 16, y_cards + card_h - 108, card_w - 32, 8.5, TEXT_MUTED, 2, max_lines=4)

    # Centered footer pill
    footer_text = "Ontology Graph Research Team · v0.1.0 · March 2026"
    fw = len(footer_text) * 5.5 + 20
    draw_tag(c, (W - fw) / 2, 44, footer_text, a(GHOST, 0.10), TEXT_MUTED, 8)

    draw_footer(c, 18, TOTAL)
    c.showPage()


# ─────────────────────────────────────────────────────────────────────────────
def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(OUTPUT), pagesize=landscape(A4))
    c.setTitle("Clearence — Commercial Presentation")
    c.setAuthor("Ontology Graph Research Team")
    pages = [s01, s02, s03, s04, s05, s06, s07, s08, s09,
             s10, s11, s12, s13, s14, s15, s16, s17, s18]
    for fn in pages:
        fn(c)
    assert len(pages) == 18, "Page count must be 18"
    c.save()
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    build()
