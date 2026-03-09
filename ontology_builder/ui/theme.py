"""UI theme: colors and CSS variables. Edit this file (or override via THEME_JSON_PATH) to change the look.

Palette origin: Gold #f8c630 · Void #25171a · Magenta #b81365 · Ghost #f7f7f9 · Ice #b1ddf1

Status system — derived from palette, intentionally avoids conventional green/yellow/red:
  success  → Ice blue    #b1ddf1  calm confirmation, signal clarity (ready / healthy / live)
  info     → Gold        #f8c630  highlight / notable, draws attention without alarm
  warning  → Magenta     #b81365  urgent attention, high-visibility
  error    → Deep fuchsia #7a0040  darker magenta derivative, critical / destructive
  pending  → Slate       #6b7fa8  desaturated ice-blue, neutral / in-progress
  disabled → Muted       #4a3a3e  dark muted, inactive / unavailable

Text highlight philosophy:
  - Gold (#f8c630) is the primary highlight / emphasis color for headings, labels, interactive text
  - Ice blue (#b1ddf1) is reserved exclusively for ready / healthy / success / live states
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_THEME: dict[str, str] = {
    # ── Backgrounds ──────────────────────────────────────────────────────────
    "bg-body":          "#1a0f12",          # deeper void, near-black with warm undertone
    "bg-sidebar":       "#150c0f",          # darkest surface
    "bg-card":          "#221319",          # slightly lifted surface
    "bg-card-hover":    "#2a1820",          # card hover state
    "bg-input":         "#150c0f",          # input fields
    "bg-overlay":       "rgba(26, 15, 18, 0.90)",
    "bg-overlay-95":    "rgba(26, 15, 18, 0.95)",
    "bg-glass":         "rgba(255, 255, 255, 0.03)", # frosted glass panels

    # ── Borders ───────────────────────────────────────────────────────────────
    "border":           "#3a2530",          # default border
    "border-subtle":    "#271a20",          # hairline / divider
    "border-glow":      "rgba(184, 19, 101, 0.35)", # accent glow border

    # ── Text ─────────────────────────────────────────────────────────────────
    "text-primary":     "#f7f7f9",          # ghost white — main body text
    "text-pink":        "#e8609a",          # soft pink for headings / labels
    "text-pink-bright": "#f0287a",          # vivid pink for interactive labels
    "text-gold":        "#f8c630",          # gold — primary highlight / emphasis text
    "text-gold-bright": "#fad54e",          # brighter gold for hover / active
    "text-muted":       "#a08898",          # muted warm grey
    "text-muted-2":     "#7a6270",          # dimmer secondary text
    "text-on-accent":   "#f7f7f9",          # text on magenta backgrounds
    "text-on-gold":     "#25171a",          # text on gold backgrounds (dark)

    # ── Accent primary — Magenta ──────────────────────────────────────────────
    "accent":           "#b81365",
    "accent-bright":    "#d41575",          # slightly lighter for hover
    "accent-dim":       "#8a0e4c",          # darker press / active state
    "accent-05":        "rgba(184, 19, 101, 0.05)",
    "accent-06":        "rgba(184, 19, 101, 0.06)",
    "accent-08":        "rgba(184, 19, 101, 0.08)",
    "accent-1":         "rgba(184, 19, 101, 0.10)",
    "accent-12":        "rgba(184, 19, 101, 0.12)",
    "accent-15":        "rgba(184, 19, 101, 0.15)",
    "accent-18":        "rgba(184, 19, 101, 0.18)",
    "accent-2":         "rgba(184, 19, 101, 0.20)",
    "accent-25":        "rgba(184, 19, 101, 0.25)",
    "accent-3":         "rgba(184, 19, 101, 0.30)",
    "accent-35":        "rgba(184, 19, 101, 0.35)",
    "accent-4":         "rgba(184, 19, 101, 0.40)",
    "accent-5":         "rgba(184, 19, 101, 0.50)",
    "accent-6":         "rgba(184, 19, 101, 0.60)",
    "accent-7":         "rgba(184, 19, 101, 0.70)",

    # ── Accent secondary — Gold (highlights, labels, emphasis) ────────────────
    # Gold is the primary text highlight color. Use for headings, interactive
    # labels, featured items, and general emphasis.
    "accent-secondary":     "#f8c630",       # Gold — primary highlight
    "accent-secondary-on":  "#25171a",       # dark text on gold bg
    "accent-secondary-dim": "#fad54e",       # brighter gold for hover / dark mode legibility
    "accent-secondary-08":  "rgba(248, 198, 48, 0.08)",
    "accent-secondary-1":   "rgba(248, 198, 48, 0.10)",
    "accent-secondary-15":  "rgba(248, 198, 48, 0.15)",
    "accent-secondary-2":   "rgba(248, 198, 48, 0.20)",
    "accent-secondary-28":  "rgba(248, 198, 48, 0.28)",
    "accent-secondary-3":   "rgba(248, 198, 48, 0.30)",
    "accent-secondary-4":   "rgba(248, 198, 48, 0.40)",

    # ── Accent tertiary — Ice blue (reserved: ready / healthy / success only) ──
    # Ice blue must NOT be used for general text highlights or labels.
    # It signals a positive/live/healthy state exclusively.
    "accent-tertiary":      "#b1ddf1",
    "accent-tertiary-dim":  "#7ab8d4",       # deeper ice for pressed state
    "accent-tertiary-2":    "rgba(177, 221, 241, 0.20)",
    "accent-tertiary-15":   "rgba(177, 221, 241, 0.15)",
    "accent-tertiary-1":    "rgba(177, 221, 241, 0.10)",
    "accent-tertiary-08":   "rgba(177, 221, 241, 0.08)",

    # ── STATUS — futuristic, no green / yellow / red ──────────────────────────
    #
    #  success  → Ice blue  — ready / healthy / live / operational
    #  info     → Gold      — highlight / notable / informational
    #  warning  → Magenta   — urgent attention, high-visibility
    #  error    → Fuchsia   — deep magenta derivative, critical / destructive
    #  pending  → Slate     — desaturated ice, neutral / in-progress
    #  disabled → Void mute — inactive / unavailable

    # Success (ice blue) — ready, healthy, live, operational
    "success":          "#b1ddf1",
    "success-on":       "#0d2a38",           # text on success bg
    "success-bg":       "rgba(177, 221, 241, 0.12)",
    "success-border":   "rgba(177, 221, 241, 0.30)",
    "success-glow":     "rgba(177, 221, 241, 0.20)",
    "success-15":       "rgba(177, 221, 241, 0.15)",
    "success-2":        "rgba(177, 221, 241, 0.20)",

    # Info (gold — highlight / notable)
    "info":             "#f8c630",
    "info-on":          "#25171a",           # text on info bg
    "info-bg":          "rgba(248, 198, 48, 0.10)",
    "info-border":      "rgba(248, 198, 48, 0.30)",
    "info-glow":        "rgba(248, 198, 48, 0.18)",

    # Warning (magenta)
    "warning":          "#b81365",
    "warning-on":       "#f7f7f9",
    "warning-bg":       "rgba(184, 19, 101, 0.12)",
    "warning-border":   "rgba(184, 19, 101, 0.35)",
    "warning-glow":     "rgba(184, 19, 101, 0.22)",
    "warning-15":       "rgba(184, 19, 101, 0.15)",

    # Error (deep fuchsia — darker magenta derivative)
    "error":            "#7a0040",
    "error-bright":     "#a8005a",           # lighter variant for text / icons
    "error-on":         "#f7f7f9",
    "error-bg":         "rgba(122, 0, 64, 0.15)",
    "error-border":     "rgba(122, 0, 64, 0.40)",
    "error-glow":       "rgba(122, 0, 64, 0.25)",
    "error-15":         "rgba(122, 0, 64, 0.15)",

    # Pending / in-progress (slate — desaturated ice)
    "pending":          "#6b7fa8",
    "pending-on":       "#f7f7f9",
    "pending-bg":       "rgba(107, 127, 168, 0.12)",
    "pending-border":   "rgba(107, 127, 168, 0.30)",

    # Disabled / unavailable
    "disabled":         "#4a3a3e",
    "disabled-text":    "#6a5660",
    "disabled-bg":      "rgba(74, 58, 62, 0.20)",

    # ── Legacy aliases (kept for backward compat) ─────────────────────────────
    "teal":             "#b1ddf1",           # remapped → ice blue
    "teal-2":           "rgba(177, 221, 241, 0.20)",

    # ── Utility ───────────────────────────────────────────────────────────────
    "white-04":         "rgba(255, 255, 255, 0.04)",
    "white-05":         "rgba(255, 255, 255, 0.05)",
    "white-08":         "rgba(255, 255, 255, 0.08)",
    "black-3":          "rgba(0, 0, 0, 0.30)",
    "black-35":         "rgba(0, 0, 0, 0.35)",
    "black-4":          "rgba(0, 0, 0, 0.40)",
    "black-45":         "rgba(0, 0, 0, 0.45)",
    "black-6":          "rgba(0, 0, 0, 0.60)",

    # ── Glow / FX ─────────────────────────────────────────────────────────────
    "glow-accent":      "0 0 20px rgba(184, 19, 101, 0.40), 0 0 60px rgba(184, 19, 101, 0.15)",
    "glow-gold":        "0 0 16px rgba(248, 198, 48, 0.35), 0 0 48px rgba(248, 198, 48, 0.12)",
    "glow-ice":         "0 0 16px rgba(177, 221, 241, 0.30), 0 0 40px rgba(177, 221, 241, 0.10)",
    "glow-error":       "0 0 16px rgba(122, 0, 64, 0.40), 0 0 48px rgba(122, 0, 64, 0.15)",

    # ── Evaluate tab aliases (job cards, badges, metrics) ─────────────────────
    "bg-card-inner":    "#1c1018",
    "border-card":      "rgba(184, 19, 101, 0.20)",
    "border-input-eval": "rgba(184, 19, 101, 0.25)",
    "pink":             "#b81365",
    "pink-hover":       "rgba(184, 19, 101, 0.08)",
    "cyan":             "#b1ddf1",
    "yellow":           "#f8c630",
    "green":            "#b1ddf1",
    "red":              "#a8005a",
    "blue":             "#6b7fa8",
    "text-value":       "#b1ddf1",
    "text-label":       "#7a6270",
    "accent-expanding": "#f8c630",
    "accent-new":       "#6b7fa8",
    "accent-complete":  "#b1ddf1",
    "accent-failed":    "#a8005a",
    "accent-running":   "#f8c630",
    "accent-attention": "#b81365",
    "badge-bg-expanding":  "rgba(248, 198, 48, 0.15)",
    "badge-bg-new":        "rgba(107, 127, 168, 0.15)",
    "badge-bg-complete":   "rgba(177, 221, 241, 0.15)",
    "badge-bg-failed":     "rgba(168, 0, 90, 0.15)",
    "badge-bg-attention":  "rgba(184, 19, 101, 0.15)",
    "badge-bg-healthy":    "rgba(177, 221, 241, 0.15)",
    "badge-bg-running":    "rgba(248, 198, 48, 0.15)",
    "font-sans":        "'Inter', system-ui, sans-serif",
    "font-mono":        "'JetBrains Mono', 'Fira Code', 'DM Mono', monospace",
    "font-label-size":  "11px",
    "font-label-spacing": "0.08em",
    "radius-app":       "16px",
    "radius-card":      "12px",
    "radius-inner":     "8px",
    "radius-button":    "8px",
    "radius-badge":     "20px",
    "radius-input":     "6px",
    "shadow-card":      "0 2px 12px rgba(0, 0, 0, 0.35)",
    "shadow-modal":     "0 8px 40px rgba(0, 0, 0, 0.60)",
    "transition-fast":  "0.15s ease",
    "transition-med":   "0.25s ease",
    "transition-slow":  "0.4s ease",
}

# Optional: set to a path (e.g. "theme.json") to load overrides from JSON
THEME_JSON_PATH: str | None = None


def get_theme() -> dict[str, str]:
    """Return theme dict (CSS var name -> value). Loads DEFAULT_THEME and optionally overrides from JSON."""
    theme = dict(DEFAULT_THEME)
    if THEME_JSON_PATH:
        path = Path(THEME_JSON_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        if path.exists():
            with open(path, encoding="utf-8") as f:
                overrides: dict[str, Any] = json.load(f)
            for k, v in overrides.items():
                if isinstance(v, str):
                    theme[k] = v
    return theme


def get_css_root_block() -> str:
    """Return a :root { ... } CSS block with all theme variables."""
    theme = get_theme()
    lines = ["    :root {"]
    for name, value in theme.items():
        var_name = f"--{name}" if not name.startswith("--") else name
        lines.append(f"      {var_name}: {value};")
    lines.append("    }")
    return "\n".join(lines)