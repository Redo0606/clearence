#!/usr/bin/env python3
"""
Transform useful_links_content.json into a markdown guide with title, url, description, content.
"""

import json
from pathlib import Path

INPUT = Path("documents/useful_links_content.json")
OUTPUT = Path("documents/useful_links_content.md")


def get_description(content: str) -> str:
    """Extract first meaningful paragraph as description."""
    if not content:
        return "(No description)"
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    for p in paragraphs:
        if "| IT@UMN" in p or (p.startswith("Enterprise CRM:") and len(p) < 80):
            continue
        if len(p) > 30:
            return p[:250].rsplit(" ", 1)[0] + "..." if len(p) > 250 else p
    return paragraphs[0][:250] if paragraphs else "(No description)"


def main():
    with open(INPUT, encoding="utf-8") as f:
        records = json.load(f)

    lines = ["# Enterprise CRM Self-Help Guide", ""]
    for rec in records:
        title = rec.get("title", "Untitled")
        url = rec.get("url", "")
        content = rec.get("content", "")
        desc = get_description(content)
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"**URL:** {url}")
        lines.append("")
        lines.append(f"**Description:** {desc}")
        lines.append("")
        lines.append("**Content:**")
        lines.append("")
        lines.append(content if content else "(Content not available)")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
