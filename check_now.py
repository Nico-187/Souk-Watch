#!/usr/bin/env python3
"""
Einmaliger Live-Check (manuell per GitHub Action 'Souk jetzt prüfen').
Loggt ein, prüft ALLE aktuell online stehenden Angebote gegen die WATCHLIST
(ohne das 'seen'-Gedächtnis), gibt einen Textbericht aus und schickt das
Ergebnis als Push aufs iPhone. Speichert nichts.
"""
import time
import requests

import scraper as S


def collect_sources(logged_in: bool):
    # entry=None → gegen die ganze Watchlist; entry gesetzt → gezielte Souk-Seite
    if logged_in:
        sources = [
            ("https://www.parfumo.com/Souks/Offers/Perfumes", "Flakons", None),
            ("https://www.parfumo.com/Souks/Offers/Samples",  "Proben",  None),
        ]
    else:
        sources = [("https://www.parfumo.com/Souks", "Flakons & Proben", None)]
    sources += [(e["souk_url"], "", e) for e in S.WATCHLIST if e.get("souk_url")]
    return sources


def main():
    print("=" * 70)
    print("  SOUK JETZT PRÜFEN – aktueller Stand deiner Watchlist")
    print("=" * 70)

    session = requests.Session()
    session.headers.update(S.HEADERS)
    logged_in = S.login(session)

    matches = []   # (name, item)
    checked = 0
    seen = set()

    for url, category, entry in collect_sources(logged_in):
        label = category or (entry["name"] if entry else "Watchlist-Suche")
        print(f"  → Lade {label}: {url}")
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
            if entry is not None:
                name, reason = S._entry_check(item, entry)
            else:
                name, reason = S.matches_filter(item)
            if name:
                matches.append((name, item))

    # ── Textbericht ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"  Login: {'OK' if logged_in else 'FEHLGESCHLAGEN'}")
    print(f"  Geprüfte Angebote: {checked}")
    print(f"  Treffer aus deiner Watchlist: {len(matches)}")
    for name, item in matches:
        _, body = S.build_message(item, name)
        print(f"   - {name} | {body} | {item['url']}")
    print("=" * 70)

    # ── Push aufs Handy (minimalistisch, ohne Emojis) ─────────────
    if matches:
        S.notify_matches(matches)   # einzeln (1) oder gebündelt (mehrere)
    else:
        status = "Watcher laeuft, Login OK." if logged_in else "Login fehlgeschlagen."
        S.send_ntfy(
            "Souk-Watch Status",
            f"{status} Aktuell 0 passende Angebote ({checked} geprueft).",
            "https://www.parfumo.com/Souks",
        )
    print("[FERTIG] Push verschickt.")


if __name__ == "__main__":
    main()
