#!/usr/bin/env python3
"""
Funktionstest (manuell per GitHub Action 'Souk Test-Nachricht').
Schickt für JEDEN Duft der WATCHLIST das NEUESTE Angebot, das alle Kriterien
erfüllt – also je Duft höchstens eine Nachricht. Speichert nichts, ignoriert
das 'seen'-Gedächtnis.

Strenger als der normale Watcher: Angebote ohne lesbaren Preis oder Füllstand
gelten hier NICHT als Treffer. Kommt eine Nachricht an, funktioniert die ganze
Kette (Login → Detailseite → Preis/Füllstand → Filter → Push).
"""
import re
import time
import requests

import scraper as S

MAX_PRUEFEN = 12  # wie viele Angebote je Duft maximal durchgesehen werden


def neuestes_passendes(session, entry: dict):
    """Geht die Angebote eines Dufts von neu nach alt durch und gibt das erste
    zurück, das Art, Füllstand und Preis erfüllt. (None, Notizen) wenn keins."""
    url = entry.get("souk_url")
    if not url:
        return None, ["keine souk_url hinterlegt"]

    listings = S.fetch_listings(session, url)
    print(f"  {len(listings)} Angebote im Souk, prüfe die neuesten {min(MAX_PRUEFEN, len(listings))}:")
    notizen = []

    for item in listings[:MAX_PRUEFEN]:
        item["art"] = S.detect_art_from_text(item["text"])
        item = S.fetch_item_details(session, item)
        time.sleep(1)

        kurz = re.sub(r"\s+", " ", item["text"]).strip()[:60]

        # Art muss stimmen
        want = S._norm_art(entry.get("art", "beides"))
        if want != "beides" and item["art"] and item["art"] != want:
            notizen.append(f"{kurz} → falsche Art ({item['art']})")
            continue

        # Für den Test: Preis, Füllstand und Größe MÜSSEN lesbar sein
        if item.get("price") is None:
            notizen.append(f"{kurz} → Preis nicht lesbar")
            continue
        if item.get("fill_pct") is None:
            notizen.append(f"{kurz} → Füllstand nicht lesbar")
            continue
        if item.get("size_ml") is None:
            notizen.append(f"{kurz} → Flakongröße nicht lesbar")
            continue

        if item["fill_pct"] < entry.get("min_fill", 0):
            notizen.append(f"{kurz} → nur {item['fill_pct']}% voll")
            continue
        min_ml = entry.get("min_ml", 0)
        if min_ml > 0 and item["size_ml"] < min_ml:
            notizen.append(f"{kurz} → nur {item['size_ml']:g} ml")
            continue
        limit = entry.get("max_preis", 0)
        if limit > 0 and item["price"] > limit:
            notizen.append(f"{kurz} → {item['price']:.2f}€ über Limit")
            continue

        return item, notizen

    return None, notizen


def main():
    print("=" * 72)
    print("  SOUK TEST-NACHRICHT – neuestes passendes Angebot je Duft")
    print("=" * 72)

    session = requests.Session()
    session.headers.update(S.HEADERS)
    logged_in = S.login(session)
    print(f"Login: {'OK' if logged_in else 'FEHLGESCHLAGEN'}")
    if not logged_in:
        print("[ABBRUCH] Ohne Login fehlen Preis und Füllstand – der Test wäre wertlos.")
        S.send_ntfy("Souk-Watch Test",
                    "Login bei Parfumo fehlgeschlagen - bitte Secrets pruefen.",
                    "https://www.parfumo.com/Souks", priority="high")
        return

    treffer = []
    for entry in S.WATCHLIST:
        print("\n" + "-" * 72)
        print(f"  {entry['name']}  (max {entry['max_preis']}€ · ab {entry['min_fill']}% · {entry['art']})")
        item, notizen = neuestes_passendes(session, entry)
        for n in notizen:
            print(f"    ⏭  {n}")
        if item:
            _, body = S.build_message(item, entry["name"])
            print(f"    ✅ Treffer: {body}")
            print(f"       {item['url']}")
            treffer.append((entry["name"], item))
        else:
            print("    ✖ Kein passendes Angebot gefunden.")

    print("\n" + "=" * 72)
    print(f"  {len(treffer)} von {len(S.WATCHLIST)} Düften mit passendem Angebot.")
    print("=" * 72)

    if treffer:
        S.notify_matches(treffer)
        print("[FERTIG] Push je Duft verschickt.")
    else:
        S.send_ntfy("Souk-Watch Test",
                    f"Test gelaufen, Login OK - aktuell 0 passende Angebote "
                    f"({len(S.WATCHLIST)} Duefte geprueft).",
                    "https://www.parfumo.com/Souks")
        print("[FERTIG] Keine Treffer – Status-Push verschickt.")


if __name__ == "__main__":
    main()
