"""Tests de bout en bout des pages Pilotage (Playwright + Chrome installé).

1. Drill-down : clic sur une barre (ancienneté), une case de la heatmap et une carte de profil
   -> filtres dans l'URL, puces, toute la page (et la vue d'ensemble) recalculée ; Retour.
2. Simulateur : curseurs au clavier (capacité, taux de succès, horizon), coût saisi ->
   conclusion, cartes et graphique du solde mis à jour.

Prérequis : API (8000) et frontend en développement (5173). Usage :
    .venv/Scripts/python frontend/scripts/e2e_pilotage.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote_plus

from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[1] / "screenshots"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'OK' if ok else 'ÉCHEC'}] {name}" + (f" — {detail}" if detail else ""))


def chart_click(page: Page, aria_contains: str, finder: str) -> None:
    """Clique sur un élément d'un graphique ECharts : `finder` est une expression JS qui reçoit
    l'instance `chart` et renvoie [x, y] en pixels (relatifs au graphique)."""
    container = page.locator(f"[role=img][aria-label*=\"{aria_contains}\"]").first
    container.scroll_into_view_if_needed()
    box = container.bounding_box()
    assert box is not None
    xy = container.evaluate(
        f"(el) => {{ const chart = window.__echarts.getInstanceByDom(el.querySelector('div')); "
        f"return ({finder}); }}")
    page.mouse.click(box["x"] + xy[0], box["y"] + xy[1])


def url_filters(page: Page) -> str:
    return unquote_plus(page.url.split("?", 1)[1]) if "?" in page.url else ""


def drill_down(page: Page) -> None:
    page.goto(f"{BASE}/pilotage/segments", wait_until="networkidle")
    page.wait_for_timeout(1200)
    title0 = page.locator("h1").inner_text()
    page.goto(f"{BASE}/pilotage/vue-ensemble", wait_until="networkidle")
    page.wait_for_timeout(1300)
    overview0 = page.locator("h1").inner_text()
    page.go_back(wait_until="networkidle")
    page.wait_for_timeout(1000)

    # 1. Clic sur la barre « 11-12 mois (fin d'engagement) » (catégorie d'indice 1).
    chart_click(page, "Risque mensuel moyen par tranche d'ancienneté",
                "chart.convertToPixel({seriesIndex: 0}, [chart.getOption().series[0].data[1].value / 2, 1])")
    page.wait_for_timeout(1200)
    f1 = url_filters(page)
    check("clic sur une barre -> filtre dans l'URL", "tenure_band=11-12 mois (fin d'engagement)" in f1, f1)
    check("puce du filtre affichée", page.get_by_text("11-12 mois (fin d'engagement)").first.is_visible())
    title1 = page.locator("h1").inner_text()
    check("titre de la page recalculé", title1 != title0, f"{title0!r} -> {title1!r}")
    drivers_title = page.locator("h3", has_text="leviers actionnables").inner_text()
    check("facteurs recalculés sur le périmètre", "fin d'engagement" in drivers_title.lower(), drivers_title)

    # 2. Clic sur une case de la heatmap (terminal 10-12 mois, ancienneté 11-12 mois).
    chart_click(page, "Carte de chaleur",
                "chart.convertToPixel({seriesIndex: 0}, [chart.getOption().xAxis[0].data.indexOf("
                "\"11-12 mois (fin d'engagement)\"), chart.getOption().yAxis[0].data.indexOf(\"10-12 mois\")])")
    page.wait_for_timeout(1200)
    f2 = url_filters(page)
    check("clic sur une case -> deux filtres", "handset_age_band=10-12 mois" in f2 and "tenure_band=11-12" in f2, f2)

    # 3. Clic sur la carte de profil la plus risquée.
    first_card = page.locator("button[aria-pressed]").first
    name = first_card.locator("p").first.inner_text()
    first_card.click()
    page.wait_for_timeout(1200)
    f3 = url_filters(page)
    check("clic sur un profil -> filtre segment", f"cluster={name}" in f3, f3)
    OUT.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT / "drilldown_segments_light.png"), full_page=False)

    # 4. La vue d'ensemble reprend les filtres (navigation) et se recalcule.
    page.get_by_role("link", name="Vue d'ensemble").click()
    page.wait_for_timeout(1500)
    f4 = url_filters(page)
    overview1 = page.locator("h1").inner_text()
    check("vue d'ensemble : filtres conservés", f4 == f3, f4)
    check("vue d'ensemble : KPI recalculés", overview1 != overview0, f"{overview0!r} -> {overview1!r}")
    page.screenshot(path=str(OUT / "drilldown_vue-ensemble_light.png"), full_page=False)

    # 5. Retour navigateur : on revient à la page Segments avec les mêmes filtres, puis on
    #    défait le dernier filtre (profil).
    page.go_back(); page.wait_for_timeout(800)
    page.go_back(); page.wait_for_timeout(1000)
    check("Retour : dernier filtre retiré", "cluster=" not in url_filters(page), url_filters(page))


def simulator(page: Page) -> None:
    page.goto(f"{BASE}/pilotage/simulateur", wait_until="networkidle")
    page.wait_for_timeout(1300)
    h1 = page.locator("h1")
    check("simulateur : conclusion initiale (10 %)", "cibler 10" in h1.inner_text() and "511 churners" in h1.inner_text(), h1.inner_text())

    # Capacité : 10 -> 20 % au clavier.
    cap = page.get_by_role("slider", name="Capacité de contact")
    cap.focus()
    for _ in range(10):
        page.keyboard.press("ArrowRight")
    page.wait_for_timeout(1300)
    text = h1.inner_text()
    check("curseur capacité -> 20 % et churners recalculés", "cibler 20" in text and "831 churners" in text, text)

    # Taux de succès : 20 -> 0 %.
    succ = page.get_by_role("slider", name="Taux de succès de l'offre")
    succ.focus()
    page.keyboard.press("Home")
    page.wait_for_timeout(1300)
    desc = page.locator("h1 + p, h1 ~ p").first.inner_text()
    check("taux de succès 0 % -> aucun départ évité", "aucun départ n'est évité" in desc, desc)
    evites = page.locator(".mantine-Paper-root", has_text="Départs évités").last.inner_text()
    check("carte « Départs évités » = 0", re.search(r"\n0\n", evites) is not None, evites.replace("\n", " | "))

    # Remise à 20 %, horizon 24 mois, coût 5 $.
    succ.focus()
    for _ in range(20):
        page.keyboard.press("ArrowRight")
    hor = page.get_by_role("slider", name="Horizon de revenu")
    hor.focus()
    page.keyboard.press("End")
    page.get_by_label("Saisir un coût par contact").check()
    cost = page.get_by_label("Coût par contact", exact=True)
    cost.fill("5")
    page.wait_for_timeout(1500)
    desc = page.locator("h1 ~ p").first.inner_text()
    check("horizon 24 mois et coût -> solde calculé", "24 mois" in desc and "solde" in desc, desc)
    balance = page.locator("[role=img][aria-label*=\"Solde de la campagne\"]")
    check("graphique du solde affiché avec un coût", balance.count() == 1)
    page.screenshot(path=str(OUT / "simulateur_cout_light.png"), full_page=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="fr-FR")
        context.add_init_script("localStorage.setItem('churn-color-scheme','light')")
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        drill_down(page)
        simulator(page)
        check("aucune erreur JavaScript", not errors, "; ".join(errors)[:300])
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} vérifications réussies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
