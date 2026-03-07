#!/usr/bin/env python3
"""
Fetch all Mobalytics LoL guides and combine into one Markdown file.
"""
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# All guide URLs from mobalytics-lol-guides.md (TOC + All Guide Links)
GUIDES = [
    # From TOC (13)
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
    # From All Guide Links (67 - deduped)
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def slugify(title: str) -> str:
    """Create anchor-friendly slug from title."""
    s = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[-\s]+", "-", s).strip("-")


def extract_content(html: str, url: str) -> str:
    """Extract main article content from Mobalytics page HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Try common article containers
    article = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_=re.compile(r"article|content|post|guide", re.I))
        or soup.find("div", {"data-testid": "article"})
    )
    if not article:
        # Fallback: look for content in body
        article = soup.body

    if not article:
        return "[Content could not be extracted - page may use client-side rendering]"

    # Convert to markdown-like text
    lines = []
    for elem in article.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "strong", "em", "a"]):
        if elem.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(elem.name[1])
            prefix = "#" * level + " "
            text = elem.get_text(strip=True)
            if text:
                lines.append(f"\n{prefix}{text}\n")
        elif elem.name == "p" and elem.parent and elem.parent.name != "li":
            text = elem.get_text(strip=True)
            if text:
                lines.append(f"\n{text}\n")
        elif elem.name == "li" and elem.parent and elem.parent.name in ("ul", "ol"):
            # Only process direct li children to avoid duplicates
            if elem.parent and elem.parent.name in ("ul", "ol"):
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")

    # Fallback: get all text if structure parsing failed
    if len(lines) < 3:
        text = article.get_text(separator="\n", strip=True)
        # Clean up excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    return "\n".join(lines).strip()


def fetch_guide(name: str, url: str) -> tuple[str, str]:
    """Fetch a single guide and return (name, content)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        content = extract_content(r.text, url)
        return (name, content)
    except Exception as e:
        return (name, f"[Failed to fetch: {e}]")


def main():
    out_path = Path(__file__).parent / "mobalytics-lol-guides-full.md"
    parts = [
        "# Mobalytics League of Legends Guides – Complete Collection",
        "",
        "> Source: [Mobalytics LoL Guides](https://mobalytics.gg/lol/guides)",
        "> Last updated: March 6, 2026",
        "",
        "---",
        "",
        "## Table of Contents",
        "",
    ]

    # Build TOC
    for i, (name, url) in enumerate(GUIDES, 1):
        slug = slugify(name)
        parts.append(f"| {i} | [{name}](#{slug}) | {url} |")
    parts.append("")
    parts.append("---")
    parts.append("")

    # Fetch and add each guide
    seen_urls = set()
    for i, (name, url) in enumerate(GUIDES, 1):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        print(f"[{i}/{len(GUIDES)}] Fetching: {name}")
        _, content = fetch_guide(name, url)
        slug = slugify(name)
        parts.append(f"## {i}. {name}")
        parts.append("")
        parts.append(f"**Source:** {url}")
        parts.append("")
        parts.append(content)
        parts.append("")
        parts.append("---")
        parts.append("")
        time.sleep(0.5)  # Be nice to the server

    out_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"\nWrote {len(GUIDES)} guides to {out_path}")


if __name__ == "__main__":
    main()
