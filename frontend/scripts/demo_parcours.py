"""Parcours de démonstration de 3 minutes, joué de bout en bout (Playwright + Chrome installé).

vue d'ensemble -> drill-down « fin d'engagement » -> simulateur (10 %, 20 %, 12 mois) ->
clients à risque -> fiche d'un client High -> « Expliquer » -> « Rédiger une offre » ->
question à l'assistant.

Une capture par étape (clair et sombre) dans frontend/screenshots/demo/. Le fournisseur de
l'assistant est celui de l'API (mode démonstration si LLM_PROVIDER=demo ou sans clé).

Usage (API et frontend lancés) : .venv/Scripts/python frontend/scripts/demo_parcours.py [--theme light|dark|both]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[1] / "screenshots" / "demo"
HIGH_CUSTOMER = "1072931"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'OK' if ok else 'ÉCHEC'}] {name}" + (f" — {detail}" if detail else ""))


def shot(page: Page, scheme: str, index: int, name: str) -> None:
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{index:02d}_{name}_{scheme}.png"))


def bar_click(page: Page, aria: str, category: str) -> None:
    """Clic sur la barre d'une modalité dans un graphique ECharts (coordonnées calculées)."""
    container = page.locator(f'[role=img][aria-label*="{aria}"]').first
    container.scroll_into_view_if_needed()
    box = container.bounding_box()
    assert box is not None
    xy = container.evaluate(
        "(el, cat) => { const c = window.__echarts.getInstanceByDom(el.querySelector('div'));"
        " const o = c.getOption(); const i = o.yAxis[0].data.indexOf(cat);"
        " return c.convertToPixel({seriesIndex: 0}, [o.series[0].data[i].value / 2, i]); }", category)
    page.mouse.click(box["x"] + xy[0], box["y"] + xy[1])


def parcours(page: Page, scheme: str) -> None:
    timings: list[tuple[str, float]] = []
    t0 = time.perf_counter()

    def step(label: str) -> None:
        timings.append((label, time.perf_counter() - t0))

    print(f"Parcours en thème {scheme}")
    # 1. Vue d'ensemble.
    page.goto(f"{BASE}/pilotage/vue-ensemble", wait_until="networkidle")
    page.wait_for_timeout(1500)
    h1 = page.locator("h1").inner_text()
    check("1. vue d'ensemble : 2 002 départs, 116 162 $", "2 002" in h1 and "116 162" in h1, h1)
    summary = page.locator("text=Ce qu'il faut retenir").count() > 0 and page.locator("li", has_text="départs attendus").count() > 0
    check("1. « Ce qu'il faut retenir » chargé", summary)
    shot(page, scheme, 1, "vue-ensemble")
    step("vue d'ensemble")

    # 2. Drill-down sur la fin d'engagement.
    page.get_by_role("link", name="Segments et facteurs").click()
    page.wait_for_timeout(1500)
    bar_click(page, "Risque mensuel moyen par tranche d'ancienneté", "11-12 mois (fin d'engagement)")
    page.wait_for_timeout(1500)
    check("2. drill-down -> filtre fin d'engagement", "tenure_band=11-12" in page.url, page.locator("h1").inner_text())
    shot(page, scheme, 2, "drilldown-fin-engagement")
    step("drill-down")

    # 3. Simulateur sur tout le portefeuille (filtre retiré) : 10 %, 20 %, 12 mois (réglages par défaut).
    page.get_by_role("button", name="Retirer le filtre Ancienneté : 11-12 mois (fin d'engagement)").click()
    page.wait_for_function("() => !location.search.includes('tenure_band')", timeout=10_000)
    # Le lien de la barre latérale porte les filtres : attendre son nouveau rendu (sans le filtre).
    page.wait_for_function(
        "() => [...document.querySelectorAll('nav a')].every(a => !a.href.includes('tenure_band'))", timeout=10_000)
    page.get_by_role("link", name="Simulateur").click()
    page.wait_for_timeout(1800)
    h1 = page.locator("h1").inner_text()
    check("3. simulateur : 10 %, 511 churners, 2,6 fois le hasard", "cibler 10" in h1 and "511 churners" in h1, h1)
    desc = page.locator("h1 ~ p").first.inner_text()
    check("3. hypothèses 20 % et 12 mois", "20 %" in desc and "12 mois" in desc, desc)
    shot(page, scheme, 3, "simulateur")
    step("simulateur")

    # 4. Clients à risque.
    page.get_by_role("link", name="Clients à risque").click()
    page.wait_for_selector("[role=row][row-id]", timeout=20_000)
    page.wait_for_timeout(1200)
    check("4. liste des clients à fidéliser", "clients à fidéliser" in page.locator("h1").inner_text(), page.locator("h1").inner_text())
    shot(page, scheme, 4, "clients-a-risque")
    step("clients à risque")

    # 5. Fiche d'un client High (recherche puis clic sur la ligne).
    page.get_by_label("Rechercher un client par identifiant").fill(HIGH_CUSTOMER)
    page.wait_for_timeout(1500)
    page.locator(f'[role=row][row-id="{HIGH_CUSTOMER}"] [col-id="top_reason"]').click()
    page.wait_for_timeout(2000)
    dialog = page.get_by_role("dialog")
    check("5. fiche High ouverte", "Risque élevé" in dialog.inner_text() and f"client={HIGH_CUSTOMER}" in page.url)
    shot(page, scheme, 5, "fiche-high")
    step("fiche client")

    # 6. Expliquer.
    dialog.get_by_role("button", name="Expliquer").click()
    page.wait_for_selector("text=Explication pour le conseiller", timeout=20_000)
    text = dialog.locator("text=Explication pour le conseiller").locator("xpath=ancestor::div[contains(@class,'Paper')][1]").inner_text()
    check("6. « Expliquer » : explication selon le modèle", "selon le modèle" in text.lower(), text[:90].replace("\n", " "))
    dialog.locator("text=Explication pour le conseiller").scroll_into_view_if_needed()
    shot(page, scheme, 6, "fiche-expliquer")
    step("expliquer")

    # 7. Rédiger une offre.
    dialog.get_by_role("button", name="Rédiger une offre").click()
    page.wait_for_selector("text=Messages de rétention", timeout=20_000)
    sms = dialog.locator("text=/\\d+ \\/ 300 caractères/").inner_text()
    check("7. « Rédiger une offre » : SMS ≤ 300 caractères + email", int(sms.split("/")[0]) <= 300 and dialog.locator("text=Email ·").count() == 1, sms)
    dialog.locator("text=Messages de rétention").scroll_into_view_if_needed()
    shot(page, scheme, 7, "fiche-offre")
    step("rédiger une offre")

    # 8. Question à l'assistant (panneau latéral, depuis la page courante).
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)
    page.get_by_role("button", name="Ouvrir l'assistant").click()
    page.wait_for_timeout(700)
    page.get_by_text("Si je contacte 10 % des clients avec un taux de succès de 20 % ?").click()
    # Réponse terminée : le badge du fournisseur s'affiche sous la réponse.
    page.get_by_role("dialog").get_by_text("Mode démonstration", exact=True).or_(
        page.get_by_role("dialog").get_by_text("Gemini", exact=True)).last.wait_for(timeout=60_000)
    answer = page.get_by_role("dialog").locator("[class*=markdown]").last.inner_text()
    check("8. assistant : simulation, hypothèse annoncée", "511" in answer and "ypothèse" in answer, answer[:110].replace("\n", " "))
    shot(page, scheme, 8, "assistant")
    step("assistant")

    total = timings[-1][1]
    print("  durée automatisée par étape :", ", ".join(f"{label} {t:.1f} s" for label, t in timings), f"(total {total:.0f} s)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    schemes = ["light", "dark"] if args.theme == "both" else [args.theme]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        errors: list[str] = []
        for scheme in schemes:
            context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="fr-FR")
            context.add_init_script(f"localStorage.setItem('churn-color-scheme','{scheme}')")
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            parcours(page, scheme)
            context.close()
        browser.close()
    check("aucune erreur JavaScript", not errors, "; ".join(errors)[:300])
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} vérifications réussies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
