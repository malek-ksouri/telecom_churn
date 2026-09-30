"""Captures d'écran du frontend (Playwright + Chrome installé), thèmes clair et sombre.

Prérequis : API (port 8000) et frontend (port 5173) lancés (`npm run dev:all`).
Usage : .venv/Scripts/python frontend/scripts/screenshots.py [chemin] [--out dossier]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=["pilotage/vue-ensemble"])
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "screenshots"))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--full", action="store_true", help="page entière")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for scheme in ("light", "dark"):
            context = browser.new_context(viewport={"width": args.width, "height": args.height},
                                          device_scale_factor=1, color_scheme=scheme,
                                          locale="fr-FR")
            context.add_init_script(
                f"window.localStorage.setItem('churn-color-scheme', '{scheme}');")
            page = context.new_page()
            page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}")
                    if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
            for path in args.paths:
                page.goto(f"{BASE}/{path.lstrip('/')}", wait_until="networkidle")
                page.wait_for_timeout(1400)  # compteurs KPI (< 900 ms) et transitions terminés
                name = path.strip("/").replace("/", "_").replace("?", "_").replace("=", "-")
                target = out / f"{name or 'root'}_{scheme}.png"
                page.screenshot(path=str(target), full_page=args.full)
                print(target)
            context.close()
        browser.close()
    for e in dict.fromkeys(errors):
        print("CONSOLE", e[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
