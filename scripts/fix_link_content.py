#!/usr/bin/env python3
"""
Fix useful_links_content.json:
- Strip UMN boilerplate (nav, footer, "Was this page helpful?", etc.)
- Replace useless Salesforce "Loading/CSS Error" placeholder with clear reference
"""

import json
import re
from pathlib import Path

INPUT_FILE = Path("documents/useful_links_content.json")
SALESFORCE_PLACEHOLDER = re.compile(
    r"Salesforce Help\s*\n*\s*Loading\s*×\s*Sorry to interrupt\s*CSS Error\s*Refresh",
    re.IGNORECASE | re.DOTALL,
)

def strip_umn_boilerplate(text: str) -> str:
    """Remove repetitive UMN site boilerplate."""
    # Cut at "Last modified" - everything after is footer
    if "\n\nLast modified\n" in text:
        text = text.split("\n\nLast modified\n")[0]
    if "\n\nWas this page helpful?\n" in text:
        text = text.split("\n\nWas this page helpful?\n")[0]
    # Remove duplicate "Skip to main content" and redundant "How-Tos" header
    text = re.sub(r"Skip to main content\s*\n\s*\n*\s*", "", text)
    text = re.sub(r"How-Tos\s*\n+\s*\n+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fix_record(rec: dict) -> dict:
    """Fix a single record."""
    content = rec.get("content", "")
    url = rec.get("url", "")
    title = rec.get("title", "")

    # Salesforce Help pages that load via JS - replace placeholder with useful reference
    if SALESFORCE_PLACEHOLDER.search(content) or (
        "help.salesforce.com" in url
        and len(content) < 200
        and "Loading" in content
    ):
        rec["content"] = (
            f"Salesforce Help: {title}. "
            f"This documentation page loads content dynamically via JavaScript. "
            f"Visit {url} for the full article."
        )
        rec["content_source"] = "reference"
    # UMN/it.umn.edu pages - strip boilerplate
    elif "it.umn.edu" in url or "umn.edu" in url:
        rec["content"] = strip_umn_boilerplate(content)
        rec["content_source"] = "fetched"
    # Cirrus Insight and others - minimal cleanup
    else:
        rec["content_source"] = "fetched"

    return rec


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        records = json.load(f)

    for rec in records:
        fix_record(rec)

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Fixed {len(records)} records in {INPUT_FILE}")


if __name__ == "__main__":
    main()
