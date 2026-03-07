"""Slide theme for Clearence PDF presentations.

Matches ontology_builder.ui website: Syne + DM Mono fonts, same colors,
radial gradient background, card/tag styling from base.css and components.css.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.pagesizes import landscape, A4

# Add project root for theme import
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from ontology_builder.ui.theme import get_theme

_T = get_theme()

# Design tokens from website (base.css, components.css)
CARD_RADIUS = 14
TAG_RADIUS = 999  # pill
MARGIN = 56
BG_BODY = "#1a0f12"
BG_CARD = "#221319"
BORDER_COLOR = "#3a2530"

# Font names (fallback to Helvetica/Courier if custom fonts not loaded)
FONT_SYNE = "Syne"
FONT_DM_MONO = "DMMono"
_USE_CUSTOM_FONTS = False


def _register_fonts():
    """Register Syne and DM Mono from presentations/fonts/ if available."""
    global _USE_CUSTOM_FONTS
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        fonts_dir = Path(__file__).resolve().parent / "fonts"
        if (fonts_dir / "Syne-Variable.ttf").exists():
            pdfmetrics.registerFont(TTFont("Syne", str(fonts_dir / "Syne-Variable.ttf")))
        if (fonts_dir / "DMMono-Regular.ttf").exists():
            pdfmetrics.registerFont(TTFont("DMMono", str(fonts_dir / "DMMono-Regular.ttf")))
        if (fonts_dir / "DMMono-Medium.ttf").exists():
            pdfmetrics.registerFont(TTFont("DMMono-Medium", str(fonts_dir / "DMMono-Medium.ttf")))
        _USE_CUSTOM_FONTS = True
    except Exception:
        pass


_register_fonts()


def _font(name: str, fallback: str) -> str:
    return name if _USE_CUSTOM_FONTS else fallback


def _hex(c: str) -> HexColor:
    if c.startswith("#"):
        return HexColor(c)
    if c.startswith("rgba("):
        inner = c[5:-1]
        parts = [p.strip() for p in inner.split(",")]
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return Color(r / 255, g / 255, b / 255, alpha=a)
    return HexColor("#000000")


# Page dimensions
_W, _H = landscape(A4)
W = _W
H = _H

# Content area: main content must start below this (avoids overlap with title/subtitle)
CONTENT_TOP = H - 100
# Footer zone: no content below this (footer at y=28)
CONTENT_BOTTOM = 68

# Colors from UI theme
ACCENT = _hex(_T["accent"])
ACCENT_BRIGHT = _hex(_T["accent-bright"])
GOLD = _hex(_T["accent-secondary"])
GOLD_DIM = _hex("#c9a01f")
ICE = _hex(_T["accent-tertiary"])
GHOST = _hex(_T["text-primary"])
VOID = _hex(_T["bg-body"])
TEXT_PINK = _hex(_T["text-pink"])
TEXT_MUTED = _hex(_T["text-muted"])
TEXT_MUTED2 = _hex(_T["text-muted-2"])
PENDING = _hex(_T["pending"])
BORDER = _hex(_T["border"])
ERROR = _hex(_T["error"])


def a(color: Color, alpha: float) -> Color:
    return Color(color.red, color.green, color.blue, alpha=alpha)


# ── Drawing helpers (website-matched) ─────────────────────────────────────────

def draw_bg(c):
    """Background: website style — base + radial glows (magenta top-left, ice bottom-right)."""
    c.setFillColor(HexColor(BG_BODY))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    # Magenta glow top-left (rgba(184,19,101,0.08) → transparent)
    c.radialGradient(W * 0.1, H, W * 0.7, [HexColor("#2a1820"), HexColor(BG_BODY)], positions=[0, 1])
    c.circle(W * 0.1, H, W * 0.7, fill=1, stroke=0)
    # Ice glow bottom-right (rgba(177,221,241,0.05) → transparent)
    c.radialGradient(W * 0.9, 0, W * 0.55, [HexColor("#1c1216"), HexColor(BG_BODY)], positions=[0, 1])
    c.circle(W * 0.9, 0, W * 0.55, fill=1, stroke=0)


def draw_top_bar(c, color, height=6):
    """Top bar — gold accent at top of page. Must be called after draw_bg so it paints over background."""
    c.setFillColor(color)
    c.rect(0, H - height, W, height, fill=1, stroke=0)


def draw_footer(c, n: int, total: int):
    """Footer — DM Mono, muted."""
    c.setFillColor(a(GHOST, 0.35))
    c.setFont(_font(FONT_DM_MONO, "Courier"), 9)
    c.drawRightString(W - MARGIN, 28, f"{n} / {total}")


def draw_glow_circle(c, cx, cy, r, color, alpha=0.06):
    c.setFillColor(a(color, alpha))
    c.circle(cx, cy, r, fill=1, stroke=0)


def draw_tag(c, x, y, text, bg_color=None, text_color=None, font_size=11):
    """Tag — website .tag: pill, 11px, DM Mono, letter-spacing 0.06em."""
    if bg_color is None:
        bg_color = a(ACCENT, 0.18)
    if text_color is None:
        text_color = ACCENT_BRIGHT
    c.setFont(_font(FONT_DM_MONO, "Courier"), font_size)
    tw = c.stringWidth(text, _font(FONT_DM_MONO, "Courier"), font_size)
    pad_x, pad_y = 12, 8
    th = font_size + pad_y
    w = tw + pad_x * 2
    c.setFillColor(bg_color)
    c.roundRect(x, y - th, w, th, min(TAG_RADIUS, th / 2), fill=1, stroke=0)
    c.setFillColor(text_color)
    c.drawString(x + pad_x, y - font_size - pad_y / 2, text)


def draw_accent_rule(c, x, y=None, width=None, color=None, thickness=2):
    """Accent rule — section-label style."""
    if y is None:
        y = H - 100
    if width is None:
        width = 80
    if color is None:
        color = GOLD
    c.setStrokeColor(color)
    c.setLineWidth(thickness)
    c.setLineCap(2)
    c.line(x, y, x + width, y)
    c.setLineWidth(1)
    c.setLineCap(0)


def draw_divider(c, x, y, width, color):
    c.setStrokeColor(color)
    c.setLineWidth(0.5)
    c.line(x, y, x + width, y)
    c.setLineWidth(1)


def draw_vertical_divider(c, x, y_top, height, color):
    """Vertical line — for two-column layouts."""
    c.setStrokeColor(color)
    c.setLineWidth(0.5)
    c.line(x, y_top - height, x, y_top)
    c.setLineWidth(1)


def draw_metric(c, x, y, w, h, val, lbl, fill_color, accent_color=None, sub=None, val_size=18):
    """Metric card — website .status-card: 14px radius, bg-card, border. Optional sub for delta text."""
    if accent_color is None:
        accent_color = fill_color
    c.setFillColor(HexColor(BG_CARD))
    c.roundRect(x, y, w, h, CARD_RADIUS, fill=1, stroke=0)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, CARD_RADIUS, fill=0, stroke=1)
    c.setFillColor(accent_color)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), val_size)
    vw = c.stringWidth(val, _font(FONT_SYNE, "Helvetica-Bold"), val_size)
    c.drawString(x + (w - vw) / 2, y + h - 38, val)
    c.setFillColor(TEXT_MUTED)
    c.setFont(_font(FONT_DM_MONO, "Courier"), 7.5)
    words = lbl.split()
    lines, cur = [], []
    for wd in words:
        test = " ".join(cur + [wd])
        if c.stringWidth(test, _font(FONT_DM_MONO, "Courier"), 7.5) <= w - 8:
            cur.append(wd)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [wd]
    if cur:
        lines.append(" ".join(cur))
    for i, ln in enumerate(lines[:2]):
        lw = c.stringWidth(ln, _font(FONT_DM_MONO, "Courier"), 7.5)
        c.drawString(x + (w - lw) / 2, y + h - 52 - i * 11, ln)
    if sub:
        c.setFillColor(TEXT_MUTED2)
        c.setFont(_font(FONT_DM_MONO, "Courier"), 7.5)
        sw = c.stringWidth(sub, _font(FONT_DM_MONO, "Courier"), 7.5)
        c.drawString(x + (w - sw) / 2, y + 16, sub)


def draw_slide_title(c, title):
    """Slide title — Syne 26px bold, text-primary. Always at y = H - 52."""
    c.setFillColor(GHOST)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 26)
    c.drawString(MARGIN, H - 52, title)


def draw_subtitle(c, subtitle):
    """Subtitle — DM Mono 11px, text-muted. Always at y = H - 74."""
    c.setFillColor(a(TEXT_MUTED, 0.9))
    c.setFont(_font(FONT_DM_MONO, "Courier"), 11)
    c.drawString(MARGIN, H - 74, subtitle)


def _wrap_lines(c, text, font, size, max_width):
    words = text.split()
    lines, cur = [], []
    for wd in words:
        test = " ".join(cur + [wd])
        if c.stringWidth(test, font, size) <= max_width:
            cur.append(wd)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [wd]
    if cur:
        lines.append(" ".join(cur))
    return lines


def draw_bullets(c, items, x, y, size=9, spacing=20, max_width=None, dot_color=None):
    """Bullets — Syne body, accent dots."""
    if dot_color is None:
        dot_color = ACCENT_BRIGHT
    if max_width is None:
        max_width = W - 2 * MARGIN
    cy = y
    line_height = size + 5
    font = _font(FONT_SYNE, "Helvetica")
    for item in items:
        c.setFillColor(dot_color)
        c.circle(x + 5, cy - size / 2, 3, fill=1, stroke=0)
        c.setFillColor(a(TEXT_MUTED, 0.95))
        c.setFont(font, size)
        lines = _wrap_lines(c, item, font, size, max_width - 18)
        for i, ln in enumerate(lines):
            c.drawString(x + 16, cy - size - i * line_height, ln)
        cy -= len(lines) * line_height + spacing


def draw_card(c, x, y, w, h, color, alpha=0.08, radius=None, border_override=None):
    """Card — website .card: tinted bg, border, 14px radius."""
    if radius is None:
        radius = CARD_RADIUS
    c.setFillColor(a(color, alpha))
    c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
    c.setStrokeColor(border_override if border_override is not None else BORDER)
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, radius, fill=0, stroke=1)


def draw_left_accent_bar(c, x, y, h, color, width=4):
    c.setFillColor(color)
    c.roundRect(x, y, width, h, 2, fill=1, stroke=0)


def draw_arrow(c, x, y, color):
    """Right-pointing arrow between pipeline steps."""
    c.setFillColor(color)
    path = c.beginPath()
    path.moveTo(x, y + 4)
    path.lineTo(x + 10, y)
    path.lineTo(x, y - 4)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


# Pro palette: 3 colors only (ACCENT, GOLD, ICE)
PRO_COLORS = [None, None, None]  # filled at runtime


def _pro_color(index: int):
    """Rotate through ACCENT, GOLD, ICE for professional look."""
    return [ACCENT, GOLD, ICE][index % 3]


def draw_picto(c, x, y, size, ptype: str, color):
    """Draw simple picto icon. Types: doc, vote, shield, graph, link, stream, cloud, reason, check."""
    s = size / 2
    c.setFillColor(color)
    c.setStrokeColor(color)
    if ptype == "doc":
        c.roundRect(x - s * 0.7, y - s, s * 1.4, s * 1.4, 3, fill=0, stroke=1)
        c.setLineWidth(1)
        c.line(x - s * 0.4, y - s * 0.3, x + s * 0.4, y - s * 0.3)
        c.line(x - s * 0.4, y, x + s * 0.4, y)
    elif ptype == "vote":
        c.circle(x, y, s * 0.5, fill=0, stroke=1)
        c.circle(x - s * 0.35, y - s * 0.1, s * 0.25, fill=0, stroke=1)
        c.circle(x + s * 0.35, y - s * 0.1, s * 0.25, fill=0, stroke=1)
    elif ptype == "shield":
        path = c.beginPath()
        path.moveTo(x, y + s)
        path.lineTo(x + s, y)
        path.lineTo(x + s * 0.5, y - s)
        path.lineTo(x - s * 0.5, y - s)
        path.lineTo(x - s, y)
        path.close()
        c.drawPath(path, fill=0, stroke=1)
    elif ptype == "graph":
        c.circle(x - s * 0.5, y + s * 0.3, s * 0.35, fill=1, stroke=0)
        c.circle(x + s * 0.5, y + s * 0.3, s * 0.35, fill=1, stroke=0)
        c.circle(x, y - s * 0.5, s * 0.35, fill=1, stroke=0)
        c.setLineWidth(1.5)
        c.line(x - s * 0.5, y + s * 0.3, x, y - s * 0.5)
        c.line(x + s * 0.5, y + s * 0.3, x, y - s * 0.5)
    elif ptype == "link":
        c.circle(x - s * 0.4, y, s * 0.35, fill=0, stroke=1)
        c.circle(x + s * 0.4, y, s * 0.35, fill=0, stroke=1)
        c.setLineWidth(1)
        c.line(x - s * 0.05, y, x + s * 0.05, y)
    elif ptype == "stream":
        for i in range(3):
            c.setLineWidth(1.5)
            c.line(x - s, y + s * 0.5 - i * s * 0.4, x + s, y + s * 0.5 - i * s * 0.4)
    elif ptype == "cloud":
        c.circle(x - s * 0.4, y, s * 0.5, fill=0, stroke=1)
        c.circle(x + s * 0.4, y, s * 0.5, fill=0, stroke=1)
    elif ptype == "reason":
        c.circle(x, y, s * 0.6, fill=0, stroke=1)
        c.setFont(_font(FONT_DM_MONO, "Courier"), size * 0.8)
        c.drawCentredString(x, y - size * 0.25, "∀")
    elif ptype == "check":
        c.circle(x, y, s * 0.6, fill=0, stroke=1)
        path = c.beginPath()
        path.moveTo(x - s * 0.3, y)
        path.lineTo(x - s * 0.05, y + s * 0.35)
        path.lineTo(x + s * 0.4, y - s * 0.25)
        c.drawPath(path, fill=0, stroke=1)
    else:
        c.circle(x, y, s * 0.5, fill=1, stroke=0)
    c.setLineWidth(1)


def draw_feature_card(c, x, y, w, h, title, desc, color, picto_type="doc"):
    """Feature card with picto, title, desc — pro 3-color palette, frontend-style highlight."""
    draw_card(c, x, y, w, h, color, 0.06)
    draw_left_accent_bar(c, x, y, h, color, 4)
    # Picto (status-badge style)
    px, py = x + 24, y + h - 22
    draw_picto(c, px, py, 14, picto_type, color)
    # Title (GHOST for slide 1 pattern — accent bar provides color)
    c.setFillColor(GHOST)
    c.setFont(_font(FONT_SYNE, "Helvetica-Bold"), 9.5)
    c.drawString(x + 44, y + h - 20, title)
    # Desc — clamp to card bounds
    font_size, line_spacing = 8, 2
    max_lines = max(1, int((h - 40) / (font_size + line_spacing)))
    c.setFillColor(TEXT_MUTED)
    c.setFont(_font(FONT_SYNE, "Helvetica"), font_size)
    wrap_text(c, desc, x + 44, y + h - 36, w - 52, font_size, TEXT_MUTED, line_spacing, max_lines)


def wrap_text(c, text, x, y, max_width, font_size, color, line_spacing=2, max_lines=None):
    """Render text top-down. y is baseline of first line; subsequent lines go downward."""
    c.setFillColor(color)
    c.setFont(_font(FONT_SYNE, "Helvetica"), font_size)
    words = text.split()
    lines, cur = [], []
    for wd in words:
        test = " ".join(cur + [wd])
        if c.stringWidth(test, _font(FONT_SYNE, "Helvetica"), font_size) <= max_width:
            cur.append(wd)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [wd]
    if cur:
        lines.append(" ".join(cur))
    if max_lines is not None:
        truncated = len(lines) > max_lines
        lines = lines[:max_lines]
        if truncated and lines:
            lines[-1] = lines[-1].rstrip() + "…"
    line_h = font_size + line_spacing
    for i, ln in enumerate(lines):
        c.drawString(x, y - i * line_h, ln)


__all__ = [
    "W", "H", "MARGIN", "CONTENT_TOP", "CONTENT_BOTTOM", "CARD_RADIUS", "landscape", "A4",
    "ACCENT", "ACCENT_BRIGHT", "GOLD", "GOLD_DIM", "ICE", "GHOST", "VOID",
    "TEXT_PINK", "TEXT_MUTED", "TEXT_MUTED2", "PENDING", "BORDER", "ERROR",
    "a", "FONT_SYNE", "FONT_DM_MONO", "_font", "_pro_color",
    "draw_bg", "draw_top_bar", "draw_footer", "draw_glow_circle", "draw_tag",
    "draw_accent_rule", "draw_divider", "draw_vertical_divider", "draw_arrow", "draw_metric", "draw_slide_title",
    "draw_subtitle", "draw_bullets", "draw_card", "draw_left_accent_bar",
    "draw_picto", "draw_feature_card", "wrap_text",
]
