"""Robust JSON repair for LLM outputs.

Small models (phi-3-mini, etc.) frequently emit:
  - Markdown code fences  (```json ... ```)
  - JavaScript-style comments  (// ... or /* ... */)
  - Trailing commas before } or ]
  - Single-quoted strings instead of double-quoted
  - Partial/truncated JSON when they hit token limits
  - Extra prose before or after the JSON block
  - Multiple JSON blocks with prose in between (self-correction pattern)
  - Prose injected mid-JSON between key-value pairs

This module tries a progressive series of fixes and returns the first parse
that succeeds.  Only raises json.JSONDecodeError when ALL strategies fail.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual repair transforms
# ---------------------------------------------------------------------------

def _strip_fences(s: str) -> str:
    s = re.sub(r"^```[^\n]*\n?", "", s.strip())
    s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _remove_js_comments(s: str) -> str:
    # Block comments first, then line comments
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r"//[^\n]*", "", s)
    return s


def _fix_trailing_commas(s: str) -> str:
    return re.sub(r",\s*([\]}])", r"\1", s)


def _fix_single_quotes(s: str) -> str:
    """Convert single-quoted JSON keys/values to double-quoted.

    Only converts simple cases (no embedded apostrophes handled here —
    that corner-case is left for the bracket-close fallback).
    """
    # Keys:   'foo':  →  "foo":
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'\s*:", r'"\1":', s)
    # Values: : 'foo'  →  : "foo"
    s = re.sub(r":\s*'([^'\\]*(?:\\.[^'\\]*)*)'", r': "\1"', s)
    return s


def _normalize_json_text(s: str) -> str:
    """Normalize common LLM artifacts before JSON parsing."""
    if not s:
        return s
    # Remove BOM and normalize smart punctuation often emitted by chat models.
    s = s.replace("\ufeff", "")
    s = (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u00a0", " ")
    )
    # Remove control chars that are invalid in JSON (keep whitespace controls).
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return s.strip()


def _extract_json_block(s: str) -> str:
    """Return the first complete JSON object or array found in the string.

    Scans for the outermost matching { } or [ ] pair so leading/trailing
    prose is ignored.
    """
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = s.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(s[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
    return s


def _slice_outer_json_region(s: str) -> str:
    """Slice from first JSON opener to last JSON closer as a fallback."""
    starts = [i for i in (s.find("{"), s.find("[")) if i != -1]
    ends = [i for i in (s.rfind("}"), s.rfind("]")) if i != -1]
    if not starts or not ends:
        return s
    start = min(starts)
    end = max(ends)
    if end <= start:
        return s
    return s[start:end + 1]


def _extract_fenced_blocks(s: str) -> list[str]:
    """Extract all code-fenced blocks from LLM output.

    Handles the common pattern where the model emits an incomplete first block,
    adds prose, then emits a corrected second block.  Returns blocks in
    document order; callers should try the *last* one first.
    """
    blocks: list[str] = []
    for m in re.finditer(r"```(?:json)?\s*\n?(.*?)```", s, flags=re.DOTALL):
        content = m.group(1).strip()
        if content:
            blocks.append(content)
    return blocks


def _extract_last_json_block(s: str) -> str:
    """Return the last complete JSON object or array in the string.

    Small models often self-correct: the first JSON attempt is broken but
    a later one is valid.  Scanning backwards catches that.
    """
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        rindex = s.rfind(end_char)
        if rindex == -1:
            continue
        depth = 0
        in_string = False
        escape_next = False
        for i in range(rindex, -1, -1):
            ch = s[i]
            if escape_next:
                escape_next = False
                continue
            if i > 0 and s[i - 1] == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == end_char:
                depth += 1
            elif ch == start_char:
                depth -= 1
                if depth == 0:
                    return s[i:rindex + 1]
    return s


_JSON_LINE_RE = re.compile(r'^\s*[\[{}\]"0-9\-tfn,:]')


def _strip_non_json_lines(s: str) -> str:
    """Remove lines that don't look like JSON fragments.

    Handles the pattern where the model injects prose lines between
    valid JSON key-value pairs.
    """
    lines = s.splitlines()
    kept = [line for line in lines if not line.strip() or _JSON_LINE_RE.match(line)]
    return "\n".join(kept)


def _slice_from_first_brace_to_end(s: str) -> str:
    """Slice from first { to end of string. Use when LLM output is truncated (no closing brace)."""
    start = s.find("{")
    if start == -1:
        return s
    return s[start:]


def _close_truncated(s: str) -> str:
    """Close any unclosed brackets/braces to recover from truncated output."""
    stack: list[str] = []
    in_string = False
    escape_next = False
    closers = {'{': '}', '[': ']'}

    for ch in s:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(closers[ch])
        elif ch in ('}', ']'):
            if stack and stack[-1] == ch:
                stack.pop()

    # Close open string if dangling
    if in_string:
        s += '"'
    # Add missing closing brackets/braces in reverse order
    s += "".join(reversed(stack))
    return s


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def repair_json(raw: str | list | dict) -> object:
    """Parse JSON from LLM output applying progressive repairs.

    Args:
        raw: Raw LLM response string, or already-parsed list/dict.

    Returns:
        Parsed Python object (dict or list).

    Raises:
        json.JSONDecodeError: When all repair strategies are exhausted.
    """
    if isinstance(raw, (list, dict)):
        return raw
    if not raw or not raw.strip():
        raise json.JSONDecodeError("Empty content", "", 0)

    base = _normalize_json_text(_strip_fences(raw))

    def _try(s: str) -> object | None:
        try:
            return json.loads(_normalize_json_text(s))
        except (json.JSONDecodeError, ValueError):
            return None

    # --- Phase 1: try fenced blocks individually (last first) -----------
    fenced = _extract_fenced_blocks(raw)
    for idx in reversed(range(len(fenced))):
        block = _normalize_json_text(fenced[idx])
        result = _try(block)
        if result is not None:
            logger.debug("[JSONRepair] Repaired with strategy=fenced_block_%d", idx)
            return result
        cleaned = _fix_trailing_commas(_remove_js_comments(block))
        result = _try(cleaned)
        if result is not None:
            logger.debug("[JSONRepair] Repaired with strategy=fenced_block_%d+clean", idx)
            return result
        # Truncated JSON inside fence: close brackets/braces and try again
        closed = _close_truncated(cleaned)
        result = _try(closed)
        if result is not None:
            logger.debug("[JSONRepair] Repaired with strategy=fenced_block_%d+close_truncated", idx)
            return result

    # --- Phase 2: progressive strategies on stripped base ---------------
    last_block = _extract_last_json_block(base)
    stripped = _strip_non_json_lines(base)
    outer_slice = _slice_outer_json_region(base)

    strategies: list[tuple[str, str]] = [
        ("bare",           base),
        ("no_comments",    _remove_js_comments(base)),
        ("no_trailing",    _fix_trailing_commas(base)),
        ("outer_slice",    outer_slice),
        ("outer+fix",      _fix_trailing_commas(_remove_js_comments(outer_slice))),
        ("extract_block",  _extract_json_block(base)),
        ("last_block",     last_block),
        ("last+fix",       _fix_trailing_commas(_remove_js_comments(last_block))),
        ("strip_prose",    stripped),
        ("strip+fix",      _fix_trailing_commas(_remove_js_comments(stripped))),
        ("all_basic",      _fix_trailing_commas(_remove_js_comments(base))),
        ("single_quotes",  _fix_single_quotes(_fix_trailing_commas(_remove_js_comments(base)))),
        ("extract+fix",    _fix_trailing_commas(_extract_json_block(_remove_js_comments(base)))),
        ("extract+quotes", _fix_single_quotes(_fix_trailing_commas(
                               _extract_json_block(_remove_js_comments(base))))),
        ("last+close",     _close_truncated(_fix_trailing_commas(
                               _remove_js_comments(last_block)))),
        ("strip+close",    _close_truncated(_fix_trailing_commas(
                               _remove_js_comments(stripped)))),
        ("close_trunc",    _close_truncated(_fix_trailing_commas(
                               _extract_json_block(_remove_js_comments(base))))),
        # Truncated at end of response: from first { to end, then close brackets
        ("truncated_close", _close_truncated(_fix_trailing_commas(_remove_js_comments(
                               _slice_from_first_brace_to_end(base))))),
    ]

    for name, candidate in strategies:
        result = _try(candidate)
        if result is not None:
            if name != "bare":
                logger.debug("[JSONRepair] Repaired with strategy=%s", name)
            return result

    # All strategies failed — raise with original content preview
    raise json.JSONDecodeError(
        f"All repair strategies failed. Preview: {base[:120]!r}",
        base,
        0,
    )
