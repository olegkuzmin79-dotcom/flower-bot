"""Download bouquet photos into assets/. Run: py scripts/download_assets.py"""
from __future__ import annotations

import urllib.request
from pathlib import Path

URLS: dict[int, str] = {
    1: "https://images.unsplash.com/photo-1518895949257-762f943ed210?w=800&q=80",
    2: "https://images.unsplash.com/photo-1561181286-d3fee7d5d906?w=800&q=80",
    3: "https://images.unsplash.com/photo-1490759846234-55849e5564ed?w=800&q=80",
    4: "https://images.unsplash.com/photo-1526047932273-341f2a7631f9?w=800&q=80",
    5: "https://images.unsplash.com/photo-1582794543139-8ac9cb0f7b39?w=800&q=80",
    6: "https://images.unsplash.com/photo-1591886960571-74d2a293f9e4?w=800&q=80",
    7: "https://images.unsplash.com/photo-1462275646964-a0e3386b89d7?w=800&q=80",
    8: "https://images.unsplash.com/photo-1498931299452-fcde1eafca84?w=800&q=80",
    9: "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&q=80",
}


def main() -> None:
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for bouquet_id, url in URLS.items():
        out = assets / f"bouquet_{bouquet_id}.jpg"
        print(f"Downloading {out.name}...")
        urllib.request.urlretrieve(url, out)
        print(f"  -> {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
