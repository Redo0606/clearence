"""Download Syne and DM Mono fonts from Google Fonts for PDF generation.

Run once: python -m presentations.download_fonts
Fonts are saved to presentations/fonts/
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
URLS = {
    "Syne-Variable.ttf": "https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf",
    "DMMono-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/dmmono/DMMono-Regular.ttf",
    "DMMono-Medium.ttf": "https://github.com/google/fonts/raw/main/ofl/dmmono/DMMono-Medium.ttf",
}


def main():
    FONTS_DIR.mkdir(exist_ok=True)
    for name, url in URLS.items():
        path = FONTS_DIR / name
        if path.exists():
            print(f"  {name} already exists")
            continue
        print(f"  Downloading {name}...")
        urllib.request.urlretrieve(url, path)
        print(f"  Saved to {path}")
    print("Done. Fonts ready for slide generation.")


if __name__ == "__main__":
    main()
