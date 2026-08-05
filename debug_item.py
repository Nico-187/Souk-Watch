#!/usr/bin/env python3
"""
Diagnose (manuell per GitHub Action 'Souk Angebot analysieren').
Loggt ein und gibt den Rohtext einer Angebotsseite aus – damit sichtbar wird,
welche Felder Parfumo eingeloggt wirklich liefert (Preis, Füllstand,
Flakongröße, Zustand). Verschickt nichts, speichert nichts.

Ohne Argument werden die neuesten Angebote der WATCHLIST analysiert.
"""
import os
import re
import sys
import time
import requests

import scraper as S


def dump(session, url: str):
    r = session.get(url, timeout=20)
    from bs4 import BeautifulSoup
    text = re.sub(r"\s+", " ", BeautifulSoup(r.text, "html.parser").get_text(" ")).strip()

    print(f"\n{'=' * 72}\n  {url}\n  HTTP {r.status_code} · {len(text)} Zeichen Text\n{'=' * 72}")
    print("--- ROHTEXT ---")
    print(text[:2500])
    print("--- WAS DER PARSER DARAUS MACHT ---")
    print("  Preis           :", S.parse_price_field(text))
    print("  parse_fill_level:", S.parse_fill_level(text))
    for label, pattern in [
        ("Prozent-Feld", r"(?<!\w)(\d{1,3})\s*%(?!\w)"),
        ("ml-Verhaeltnis", r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*ml"),
        ("ml vor Label", r"(\d+(?:[.,]\d+)?)\s*ml\s*(?:Bottle size|Flakongr)"),
        ("Zustand", r"(?:Condition|Zustand)[\s:]*([A-Za-zÄÖÜäöü]+)"),
    ]:
        print(f"  {label:16}:", re.findall(pattern, text, re.I)[:5])


def main():
    session = requests.Session()
    session.headers.update(S.HEADERS)
    if not S.login(session):
        print("[ABBRUCH] Login fehlgeschlagen.")
        sys.exit(1)

    urls = [u for u in (os.environ.get("ITEM_URLS", "").split()) if u.startswith("http")]
    if not urls:
        for entry in S.WATCHLIST:
            if entry.get("souk_url"):
                for item in S.fetch_listings(session, entry["souk_url"])[:3]:
                    urls.append(item["url"])

    print(f"[INFO] {len(urls)} Angebote werden analysiert.")
    for u in urls:
        dump(session, u)
        time.sleep(1)


if __name__ == "__main__":
    main()
