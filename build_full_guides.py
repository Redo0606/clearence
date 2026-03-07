#!/usr/bin/env python3
"""
Build mobalytics-lol-guides-full.md by combining source content with fetched agent-tools files.
"""
import re
from pathlib import Path

# Same order as fetch_mobalytics_guides.py: 13 TOC + 67 All Guide Links (deduped)
GUIDES = [
    ("LoL Mythic Shop Rotation (Patch 26.5)", "https://mobalytics.gg/lol/guides/mythic-shop-rotation"),
    ("Wave Management Guide", "https://mobalytics.gg/lol/guides/wave-management"),
    ("Warding Guide", "https://mobalytics.gg/lol/guides/warding-guide"),
    ("All Season Changes Guide", "https://mobalytics.gg/lol/guides/all-season-changes-guide"),
    ("Free Champion Rotation", "https://mobalytics.gg/lol/guides/free-champion-rotation"),
    ("How to Climb Fast", "https://mobalytics.gg/lol/guides/how-to-climb-fast-in-season-26"),
    ("Patch Notes Breakdown", "https://mobalytics.gg/lol/guides/patch-notes-breakdown"),
    ("Roaming Guide", "https://mobalytics.gg/lol/guides/everything-you-need-to-know-about-roaming-in-lol"),
    ("Weekly Skin Sale", "https://mobalytics.gg/lol/guides/weekly-skin-sale"),
    ("Best Top Laners S26", "https://mobalytics.gg/lol/guides/best-top-laners-s26"),
    ("Best Junglers S26", "https://mobalytics.gg/lol/guides/best-junglers-s26"),
    ("Best Mid Laners S26", "https://mobalytics.gg/lol/guides/best-mid-laners-s26"),
    ("Best ADCs S26", "https://mobalytics.gg/lol/guides/best-adcs-s26"),
    ("5 Best Duos With Alistar Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-alistar-arena-mode"),
    ("5 Best Duos With Annie Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-annie-arena-mode"),
    ("5 Best Duos With Ez Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-ez-arena-mode"),
    ("5 Best Duos With Heimerdinger Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-heimerdinger-arena-mode"),
    ("5 Best Duos With Kai'Sa Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-kaisa-arena-mode"),
    ("5 Best Duos With Lux Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-lux-arena-mode"),
    ("5 Best Duos With Shaco Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-with-shaco-arena-mode"),
    ("5 Best Duo With Sett Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duo-with-sett-arena-mode"),
    ("5 Best Duos Warwick Arena Mode", "https://mobalytics.gg/lol/guides/5-best-duos-warwick-arena-mode"),
    ("5 Champions With the Most Skins", "https://mobalytics.gg/lol/guides/5-champions-with-the-most-skins"),
    ("5 Least Picked Arena Mode", "https://mobalytics.gg/lol/guides/5-least-picked-arena-mode"),
    ("5 Lowest Health Champions", "https://mobalytics.gg/lol/guides/5-lowest-health-champions"),
    ("5 Most Picked Arena Mode", "https://mobalytics.gg/lol/guides/5-most-picked-arena-mode"),
    ("5 Most Versatile Champs", "https://mobalytics.gg/lol/guides/5-most-versatile-champs"),
    ("5 Removed Abilities", "https://mobalytics.gg/lol/guides/5-removed-abilities"),
    ("ARAM Mayhem Patch Notes", "https://mobalytics.gg/lol/guides/aram-mayhem-patch-notes"),
    ("ARAM Mayhem Tier List", "https://mobalytics.gg/lol/guides/aram-mayhem-tier-list"),
    ("Atakhan Guide", "https://mobalytics.gg/lol/guides/atakhan-guide"),
    ("Best Blind Pick Champions", "https://mobalytics.gg/lol/guides/best-blind-pick-champions"),
    ("Best Bot Duos S26", "https://mobalytics.gg/lol/guides/best-bot-duos-s26"),
    ("Best Champ Reworks", "https://mobalytics.gg/lol/guides/best-champ-reworks"),
    ("Best Supports S26", "https://mobalytics.gg/lol/guides/best-supports-s26"),
    ("Best Synergy With Briar", "https://mobalytics.gg/lol/guides/best-synergy-with-briar"),
    ("Best Synergy With Naafiri", "https://mobalytics.gg/lol/guides/best-synergy-with-naafiri"),
    ("Brawl Best Champs", "https://mobalytics.gg/lol/guides/brawl-best-champs"),
    ("Briar Ability Reveal", "https://mobalytics.gg/lol/guides/briar-ability-reveal"),
    ("Carry as ADC", "https://mobalytics.gg/lol/guides/carry-as-adc"),
    ("Everything About Team Comps and Teamfighting", "https://mobalytics.gg/lol/guides/everything-you-need-to-know-about-team-comps-and-teamfighting"),
    ("Faelights Guide", "https://mobalytics.gg/lol/guides/faelights-guide"),
    ("Fastest Champs", "https://mobalytics.gg/lol/guides/fastest-champs"),
    ("How to Beat Doom Bots", "https://mobalytics.gg/lol/guides/how-to-beat-doom-bots"),
    ("How to Counter Briar", "https://mobalytics.gg/lol/guides/how-to-counter-briar"),
    ("How to Counter Hwei", "https://mobalytics.gg/lol/guides/how-to-counter-hwei"),
    ("How to Counter Zaahen", "https://mobalytics.gg/lol/guides/how-to-counter-zaahen"),
    ("How to Play Briar", "https://mobalytics.gg/lol/guides/how-to-play-briar"),
    ("How to Play Hwei Abilities", "https://mobalytics.gg/lol/guides/how-to-play-hwei-abilities"),
    ("How to Play Zaahen", "https://mobalytics.gg/lol/guides/how-to-play-zaahen"),
    ("How to Split Push", "https://mobalytics.gg/lol/guides/how-to-split-push"),
    ("How to Track LP by Game", "https://mobalytics.gg/lol/guides/how-to-track-lp-by-game"),
    ("Hwei Ability Reveal", "https://mobalytics.gg/lol/guides/hwei-ability-reveal"),
    ("Hwei Counters", "https://mobalytics.gg/lol/guides/hwei-counters"),
    ("Jungle Jayce Guide", "https://mobalytics.gg/lol/guides/jungle-jayce-guide"),
    ("League of Legends Terms", "https://mobalytics.gg/lol/guides/league-of-legends-terms"),
    ("Longest Time Without Skin", "https://mobalytics.gg/lol/guides/longest-time-without-skin"),
    ("Most Legacy Skins", "https://mobalytics.gg/lol/guides/most-legacy-skins"),
    ("New Champion Tracker", "https://mobalytics.gg/lol/guides/new-champion-tracker"),
    ("New LoL Items 2026", "https://mobalytics.gg/lol/guides/new-lol-items-2026"),
    ("New Role Quests", "https://mobalytics.gg/lol/guides/new-role-quests"),
    ("New Skins This Patch", "https://mobalytics.gg/lol/guides/new-skins-this-patch"),
    ("Patch Preview", "https://mobalytics.gg/lol/guides/patch-preview"),
    ("Patch Schedule", "https://mobalytics.gg/lol/guides/patch-schedule"),
    ("Roles", "https://mobalytics.gg/lol/guides/roles"),
    ("S15 Best ADCs", "https://mobalytics.gg/lol/guides/s15-best-adcs"),
    ("S15 Best Junglers", "https://mobalytics.gg/lol/guides/s15-best-junglers"),
    ("S15 Best Mid Laners", "https://mobalytics.gg/lol/guides/s15-best-mid-laners"),
    ("S15 Best Supports", "https://mobalytics.gg/lol/guides/s15-best-supports"),
    ("S15 Best Top Laners", "https://mobalytics.gg/lol/guides/s15-best-top-laners"),
    ("Salvation Cinematic Breakdown", "https://mobalytics.gg/lol/guides/salvation-cinematic-breakdown"),
    ("Shyvana Ability Reveal", "https://mobalytics.gg/lol/guides/shyvana-ability-reveal"),
    ("Summoner Spells", "https://mobalytics.gg/lol/guides/summoner-spells"),
    ("Top 6 Worst Abilities", "https://mobalytics.gg/lol/guides/top-6-worst-abilities"),
    ("Top 10 Rarest Skins", "https://mobalytics.gg/lol/guides/top-10-rarest-skins"),
    ("Upcoming 2026 Skins", "https://mobalytics.gg/lol/guides/upcoming-2026-skins"),
    ("Worst Blind Pick Champions", "https://mobalytics.gg/lol/guides/worst-blind-pick-champions"),
    ("Worst Reworks", "https://mobalytics.gg/lol/guides/worst-reworks"),
    ("Zaahen Abilities Revealed", "https://mobalytics.gg/lol/guides/zaheen-abilites-revealed"),
    ("Yordles", "https://mobalytics.gg/lol/guides/yordles"),
]

AGENT_TOOLS = Path.home() / ".cursor/projects/Users-redasarehane-Documents-CODE-clearance-clearence/agent-tools"
SOURCE_MD = Path(__file__).parent / "mobalytics-lol-guides.md"
OUT_PATH = Path(__file__).parent / "mobalytics-lol-guides-full.md"

# Map URL path (from mobalytics.gg/lol/guides/XXX) to agent-tools file
URL_TO_FILE = {
    "how-to-split-push": "9d449511-69fb-444b-98d5-0093ddfcbbbf.txt",
    "everything-you-need-to-know-about-team-comps-and-teamfighting": "602c9d65-72b9-4cfe-a7b2-b7b569aa7c89.txt",
    "league-of-legends-terms": "a7d14e6b-fed7-40b7-b950-23cf5b523f36.txt",
    "roles": "69442740-6ad1-4ccb-8a42-fffe6493e064.txt",
    "wave-management": "f719763a-874f-4241-bcc8-57f0ccb9911a.txt",
    "warding-guide": "e6f3ff1a-6367-4d7a-a663-df91fac83fed.txt",
    "everything-you-need-to-know-about-roaming-in-lol": "a11ddaa4-d0d9-466a-a40d-3caf8b56dcbf.txt",
}


def slugify(title: str) -> str:
    """Create anchor-friendly slug from title."""
    s = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[-\s]+", "-", s).strip("-")


def strip_boilerplate(text: str) -> str:
    """Remove nav links, LoL Guide, Share, and similar boilerplate from fetched content."""
    lines = text.split("\n")
    out = []
    found_title = False
    skip_meta = 0  # Skip next N lines after title (Guides, By Mobalytics, Updated, date, Share)

    for line in lines:
        stripped = line.strip()
        # Skip single-line nav links [X](url)
        if re.match(r"^\[[\w\s]+\]\(https://[^)]+\)\s*$", stripped) and " " not in stripped[1:stripped.find("]")]:
            continue
        if stripped in ("Use your favourite features in-game with our Desktop App", "LoL Guide", "Share"):
            continue
        if stripped == "Guides" and found_title:
            continue
        if re.match(r"^By \[Mobalytics\].*$", stripped):
            continue
        if re.match(r"^Updated on .*$", stripped):
            continue
        if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d+, \d{4}$", stripped):
            continue
        if "Back to top" in stripped and re.search(r"\[1\. .*\]", stripped):
            continue

        if stripped.startswith("# ") and not found_title:
            found_title = True
            out.append(line)
            continue
        if found_title:
            out.append(line)

    result = "\n".join(out)
    result = re.sub(r"\n{4,}", "\n\n\n", result)
    return result.strip()


def get_fetched_content(url: str) -> str | None:
    """Get stripped content from agent-tools if available."""
    path_part = url.rstrip("/").split("/guides/")[-1]
    fname = URL_TO_FILE.get(path_part)
    if not fname:
        return None
    fpath = AGENT_TOOLS / fname
    if not fpath.exists():
        return None
    try:
        content = fpath.read_text(encoding="utf-8")
        return strip_boilerplate(content)
    except Exception:
        return None


def load_summaries() -> dict[int, str]:
    """Extract guide summaries from mobalytics-lol-guides.md for guides 1-13."""
    text = SOURCE_MD.read_text(encoding="utf-8")
    summaries = {}
    # Split by ### N. pattern; capturing group yields [before, num1, block1, num2, block2, ...]
    blocks = re.split(r"\n### (\d+)\. ", text)
    for i in range(1, len(blocks) - 1, 2):
        num = int(blocks[i])
        block = blocks[i + 1]
        if 1 <= num <= 13:
            # block = "Title\n\n**Category:**...\n\ncontent..."
            match = re.match(r"^([^\n]+)\n\n(.*?)(?=\n\n---|\n## |\Z)", block, re.DOTALL)
            if match:
                content = match.group(2)
                content = re.sub(r"\*\*Source:\*\* \[[^\]]*\]\([^)]+\)\n\n?", "", content)
                summaries[num] = content.strip()
    return summaries


def main():
    summaries = load_summaries()

    parts = [
        "# Mobalytics League of Legends Guides – Complete Collection (80 Guides)",
        "",
        "> Source: [Mobalytics LoL Guides](https://mobalytics.gg/lol/guides)",
        "> Last updated: March 6, 2026",
        "",
        "---",
        "",
        "## Table of Contents",
        "",
        "| # | Guide | URL |",
        "|---|-------|-----|",
    ]

    for i, (name, url) in enumerate(GUIDES, 1):
        slug = slugify(name)
        parts.append(f"| {i} | [{name}](#{i}-{slug}) | {url} |")

    parts.extend(["", "---", ""])

    for i, (name, url) in enumerate(GUIDES, 1):
        slug = slugify(name)
        content = get_fetched_content(url)

        if not content and i <= 13 and i in summaries:
            content = summaries[i]

        parts.append(f"## {i}. {name}")
        parts.append("")
        parts.append(f"**Source:** {url}")
        parts.append("")

        if content:
            parts.append(content)
        else:
            parts.append("Full content available at: [" + url + "](" + url + ")")

        parts.extend(["", "---", ""])

    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Total guides: {len(GUIDES)}")


if __name__ == "__main__":
    main()
