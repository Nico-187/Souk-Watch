#!/usr/bin/env python3
"""
Kontroll-Liste (manuell per GitHub Action 'Souk Kontroll-Liste').
Zeigt eingeloggt die letzten Angebote JEDES Watchlist-Parfums im Souk –
mit Art, Füllmenge und Preis. Verschickt nichts, speichert nichts.
"""
import re
import time
import requests

import scraper as S

LATEST_N = 5  # wie viele der neuesten Angebote je Parfum


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def main():
    session = requests.Session()
    session.headers.update(S.HEADERS)
    logged_in = S.login(session)
    print(f"Login: {'OK' if logged_in else 'FEHLGESCHLAGEN'}")
    if not logged_in:
        print("(ohne Login fehlen Preis & Füllmenge!)")

    for entry in S.WATCHLIST:
        name = entry["name"]
        url = entry.get("souk_url")
        print("\n" + "=" * 72)
        print(f"  {name}")
        print("=" * 72)
        if not url:
            print("  (keine souk_url hinterlegt)")
            continue

        listings = S.fetch_listings(session, url)
        if not listings:
            print("  Aktuell KEINE Angebote im Souk.")
            continue
        print(f"  Angebote gesamt: {len(listings)} — die letzten {min(LATEST_N, len(listings))}:\n")

        for item in listings[:LATEST_N]:
            item["art"] = S.detect_art_from_text(item["text"])
            if logged_in:
                item = S.fetch_item_details(session, item)
                time.sleep(1)
            fill  = item.get("fill_pct")
            price = item.get("price")
            art_s   = {"flakon": "Flakon", "abfüllung": "Abfüllung"}.get(item["art"], "?")
            fill_s  = f"{fill}%" if fill is not None else "unbekannt"
            price_s = f"{price:.2f}€" if price is not None else "unbekannt"
            print(f"  - {clean(item['text'])}")
            print(f"      Art: {art_s} | Füllmenge: {fill_s} | Preis: {price_s}")
            print(f"      {item['url']}")

    print("\n[FERTIG] Kontroll-Liste ausgegeben (nichts gesendet, nichts gespeichert).")


if __name__ == "__main__":
    main()
