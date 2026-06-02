#!/usr/bin/env python3
"""
Einmaliger Live-Check (manuell per GitHub Action 'Souk jetzt prüfen').
Loggt ein, prüft ALLE aktuell online stehenden Angebote gegen die WATCHLIST
(ohne das 'seen'-Gedächtnis), gibt einen Textbericht aus und schickt das
Ergebnis als Push aufs iPhone. Speichert nichts.
"""
import time
import requests
from bs4 import BeautifulSoup

import scraper as S


def collect_sources(logged_in: bool):
    if logged_in:
        sources = [
            ("https://www.parfumo.com/Souks/Offers/Perfumes", "Flakons"),
            ("https://www.parfumo.com/Souks/Offers/Samples",  "Proben"),
        ]
    else:
        sources = [("https://www.parfumo.com/Souks", "Flakons & Proben")]
    sources += [(e["souk_url"], "") for e in S.WATCHLIST if e.get("souk_url")]
    return sources


def main():
    print("=" * 70)
    print("  SOUK JETZT PRÜFEN – aktueller Stand deiner Watchlist")
    print("=" * 70)

    session = requests.Session()
    session.headers.update(S.HEADERS)
    logged_in = S.login(session)

    matches = []
    checked = 0
    seen = set()

    for url, category in collect_sources(logged_in):
        print(f"  → Lade {category or 'Watchlist-Suche'}: {url}")
        listings = S.fetch_listings(session, url)
        print(f"     {len(listings)} Angebote gefunden.")
        for item in listings:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            checked += 1
            item["art"] = S.category_art(category) or S.detect_art_from_text(item["text"])
            if logged_in:
                item = S.fetch_item_details(session, item)
                time.sleep(1)
            ok, reason = S.matches_filter(item)
            if ok:
                matches.append((item, reason, category))

    # ── Textbericht ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"  Login: {'✅ OK' if logged_in else '❌ FEHLGESCHLAGEN'}")
    print(f"  Geprüfte Angebote: {checked}")
    print(f"  Treffer aus deiner Watchlist: {len(matches)}")
    for item, reason, _ in matches:
        price = f"{item['price']:.2f}€" if item.get("price") is not None else "Preis unbekannt"
        print(f"   • {item['text']}  |  {price}  |  {reason}")
        print(f"     {item['url']}")
    print("=" * 70)

    # ── Push aufs Handy ───────────────────────────────────────────
    if matches:
        for item, reason, category in matches:
            label = category or {"flakon": "Flakon", "abfüllung": "Abfüllung"}.get(item["art"], "Souk")
            title, body = S.build_message(item, reason, label)
            prio = "high" if "⭐" in reason else "default"
            S.send_ntfy(title, body + f"\n{item['url']}", item["url"], prio)
    else:
        status = ("✅ Watcher läuft & Login klappt.\n"
                  if logged_in else "⚠️ Login fehlgeschlagen.\n")
        S.send_ntfy(
            "Souk-Watch: Status-Check",
            status + f"Aktuell 0 passende Angebote aus deiner Liste online ({checked} geprüft).",
            "https://www.parfumo.com/Souks", "default",
        )
    print("[FERTIG] Push verschickt.")


if __name__ == "__main__":
    main()
