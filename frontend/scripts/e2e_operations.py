"""Tests de bout en bout de la page Clients à risque et de la fiche client (Playwright).

Prérequis : API (8000) et frontend en développement (5173). Usage :
    .venv/Scripts/python frontend/scripts/e2e_operations.py
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:5173/operations/clients"
OUT = Path(__file__).resolve().parents[1] / "screenshots"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'OK' if ok else 'ÉCHEC'}] {name}" + (f" — {detail}" if detail else ""))


def qs(page: Page) -> dict[str, list[str]]:
    return parse_qs(urlparse(page.url).query)


def row_ids(page: Page) -> list[str]:
    return page.locator("[role=row][row-id]").evaluate_all(
        "rows => rows.sort((a, b) => a.getAttribute('row-index') - b.getAttribute('row-index'))"
        ".map(r => r.getAttribute('row-id'))"
        ".filter((id, i, all) => all.indexOf(id) === i)")  # animation : lignes sortantes gardées un instant


def wait_rows(page: Page) -> None:
    page.wait_for_selector("[role=row][row-id]", timeout=20_000)
    page.wait_for_timeout(1500)  # fin de l'animation de remplacement des lignes


def table(page: Page) -> None:
    page.goto(BASE, wait_until="networkidle")
    wait_rows(page)
    ids = row_ids(page)
    check("table : 25 lignes, triées par risque", len(ids) == 25, f"{len(ids)} lignes")
    title = page.locator("h1").inner_text()
    check("titre : clients dans la base + équivalent portefeuille",
          "clients à fidéliser" in title and "Équivalent portefeuille" in page.locator("h1 ~ p").first.inner_text(), title)

    # Tri par facture (clic sur l'en-tête, deux fois : décroissant).
    header = page.locator('.ag-header-cell[col-id="monthly_bill"] .ag-header-cell-label')
    header.click(); page.wait_for_timeout(1500); header.click()
    wait_rows(page)
    check("tri par facture -> URL", qs(page).get("sort") == ["monthly_bill"], str(qs(page)))
    bills = page.locator('[role=row][row-id] [col-id="monthly_bill"]').all_inner_texts()
    values = [float(b.replace(" ", "").replace(" ", "").replace("$", "").replace(",", ".")) for b in bills if b.strip() not in ("", "—")]
    check("tri par facture -> ordre décroissant", values == sorted(values, reverse=True) and len(values) > 5, str(values[:3]))

    # Recherche par identifiant.
    page.get_by_label("Rechercher un client par identifiant").fill("10729")
    page.wait_for_timeout(600)
    wait_rows(page)
    ids = row_ids(page)
    check("recherche « 10729 »", bool(ids) and all("10729" in i for i in ids), f"{len(ids)} résultats")
    page.get_by_label("Rechercher un client par identifiant").fill("")
    wait_rows(page)

    # Filtre action (menu de la barre d'outils).
    page.get_by_role("button", name="Action", exact=True).click()
    page.wait_for_timeout(400)
    # Position vérifiée immobile (8 mesures) : le contrôle de stabilité de Playwright bute sur le
    # recalcul de taille de la zone défilante de la liste ; clic forcé sur l'option seulement.
    page.get_by_text("Offre de réengagement", exact=True).last.click(force=True)
    page.keyboard.press("Escape")
    wait_rows(page)
    actions = set(page.locator('[role=row][row-id] [col-id="action"]').all_inner_texts())
    check("filtre action", actions == {"Offre de réengagement"}, str(actions))

    # Export CSV : même sélection que la table.
    href = page.get_by_role("link", name="Exporter CSV").get_attribute("href") or ""
    body = urllib.request.urlopen("http://localhost:5173" + href).read().decode("utf-8").lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(body), delimiter=";"))
    total_text = page.get_by_text("clients dans la base", exact=False).last.inner_text()
    total = int("".join(ch for ch in total_text if ch.isdigit()))
    check("export CSV = sélection filtrée", len(rows) == total and {r["action_suggeree"] for r in rows} == {"Offre de réengagement"},
          f"{len(rows)} lignes exportées, {total} dans la table")

    # Voir les inactifs.
    page.goto(BASE, wait_until="networkidle")
    wait_rows(page)
    page.get_by_role("button", name="Voir les inactifs").click()
    page.wait_for_timeout(1400)
    levels = set(page.locator('[role=row][row-id] [col-id="risk_level"]').all_inner_texts())
    check("« Voir les inactifs » -> uniquement des inactifs", levels == {"Inactif"} and "inactifs" in page.locator("h1").inner_text(), str(levels))
    page.get_by_role("button", name="Revenir aux clients actifs").click()
    page.wait_for_timeout(1200)


def drawer(page: Page) -> None:
    page.goto(BASE, wait_until="networkidle")
    wait_rows(page)
    ids = row_ids(page)
    page.locator(f'.ag-row[row-id="{ids[0]}"] [col-id="top_reason"]').click()
    page.wait_for_timeout(1500)
    check("clic sur une ligne -> fiche ouverte, URL mise à jour", qs(page).get("client") == [ids[0]] and page.get_by_role("dialog").get_by_text("Action suggérée").is_visible(), str(qs(page).get("client")))
    check("fiche : 3 raisons et cascade", page.locator("text=Du score moyen au score du client").is_visible()
          and page.locator("[aria-label^='Cascade SHAP']").count() == 1)
    page.get_by_label("Client suivant").click()
    page.wait_for_timeout(1000)
    check("suivant -> 2e client de la liste", qs(page).get("client") == [ids[1]], str(qs(page).get("client")))
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(1000)
    check("flèche ← -> client précédent", qs(page).get("client") == [ids[0]], str(qs(page).get("client")))
    page.keyboard.press("Escape")
    page.wait_for_timeout(700)
    check("Échap -> fiche fermée, URL nettoyée", "client" not in qs(page))

    # Suivant depuis le dernier client de la page -> page 2, premier client.
    page.locator(f'.ag-row[row-id="{ids[-1]}"] [col-id="top_reason"]').click()
    page.wait_for_timeout(1300)
    page.get_by_label("Client suivant").click()
    page.wait_for_timeout(2500)
    page2 = row_ids(page)
    check("suivant en fin de page -> page 2", qs(page).get("page") == ["2"] and qs(page).get("client") == [page2[0]] if page2 else False,
          f"page={qs(page).get('page')} client={qs(page).get('client')}")
    page.screenshot(path=str(OUT / "fiche_navigation_light.png"))
    page.keyboard.press("Escape")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="fr-FR", accept_downloads=True)
        context.add_init_script("localStorage.setItem('churn-color-scheme','light')")
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        table(page)
        drawer(page)
        check("aucune erreur JavaScript", not errors, "; ".join(errors)[:300])
        browser.close()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} vérifications réussies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
