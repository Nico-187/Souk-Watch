#!/usr/bin/env python3
"""
Parfumo Souk Watcher
Überwacht neue Angebote und benachrichtigt via Ntfy.
"""

import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────
#  KONFIGURATION  (wird über GitHub Secrets gesetzt)
# ──────────────────────────────────────────────
PARFUMO_USER     = os.environ.get("PARFUMO_USER", "")
PARFUMO_PASS     = os.environ.get("PARFUMO_PASS", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # z.B. "mein-parfumo-watcher-xyz123"

# ──────────────────────────────────────────────
#  FILTER-REGELN  (hier anpassen!)
# ──────────────────────────────────────────────
# ── DEINE SUCH-LISTE ───────────────────────────────────────────────
# Jedes gesuchte Parfum als eigener Eintrag:
#   • "name"      : alle Wörter müssen im Angebots-Text vorkommen (Marke+Parfum).
#   • "max_preis" : Höchstpreis in €. 0 = Preis egal.
#   • "art"       : "flakon" | "abfüllung" | "beides".
#   • "min_fill"  : Mindest-Füllmenge in %. 0 = egal.
#   • "souk_url"  : (optional) direkte Souk-Seite des Parfums → zuverlässiger.
WATCHLIST = [
    {"name": "Pana Dora Oud Republic", "max_preis": 0, "art": "flakon", "min_fill": 95,
     "souk_url": "https://www.parfumo.com/s_souk.php?b=pana-dora&p=oud-republic&img=1"},
    {"name": "Pana Dora Moonlight", "max_preis": 0, "art": "flakon", "min_fill": 95,
     "souk_url": "https://www.parfumo.com/s_souk.php?b=pana-dora&p=moonlight&img=1"},
    {"name": "Attar Collection Khaltat Night", "max_preis": 0, "art": "flakon", "min_fill": 95,
     "souk_url": "https://www.parfumo.com/s_souk.php?b=Attar_Collection&p=Khaltat_Night_Eau_de_Parfum&img=1"},
    {"name": "House of Oud Dates Delight", "max_preis": 0, "art": "flakon", "min_fill": 95,
     "souk_url": "https://www.parfumo.com/s_souk.php?b=The_House_of_Oud&p=Dates_Delight&img=1"},
    {"name": "Ajwaa White Musk", "max_preis": 0, "art": "flakon", "min_fill": 95,
     "souk_url": "https://www.parfumo.com/s_souk.php?b=ajwaa-perfumes&p=white-musk&img=1"},
]

# Preis nicht lesbar → trotzdem melden? (Preis egal, daher True empfohlen)
NOTIFY_IF_PRICE_UNKNOWN = True
# Füllmenge nicht lesbar → trotzdem melden? (True = nichts verpassen, Hinweis "unbekannt")
NOTIFY_IF_FILL_UNKNOWN = True

# Mit True werden ALLE neuen Angebote gemeldet (ignoriert die Watchlist). Normal: False
NOTIFY_ALL_NEW = False

# ──────────────────────────────────────────────
#  DATEIPFADE
# ──────────────────────────────────────────────
DATA_FILE = Path("data/seen_items.json")

# Login-Endpoint (genau der, an den das Browser-Modal postet – ohne CSRF-Token)
LOGIN_URL = "https://www.parfumo.com/board/login.php"
BASE_URL  = "https://www.parfumo.com"


# ──────────────────────────────────────────────
#  HILFSFUNKTIONEN
# ──────────────────────────────────────────────

def load_seen_items() -> set:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_items(items: set):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(list(items), f)


def header_safe(text: str) -> str:
    """
    HTTP-Header dürfen nur Latin-1 enthalten (kein Emoji, keine exotischen Zeichen).
    Umlaute (ä/ö/ü) bleiben erhalten, nicht darstellbares (z.B. 🧴) wird entfernt.
    """
    return text.encode("latin-1", "ignore").decode("latin-1").strip()


def send_ntfy(title: str, message: str, url: str, priority: str = "default"):
    if not NTFY_TOPIC:
        print("[WARN] Ntfy nicht konfiguriert – kein Push (nur Konsole).")
        return
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),       # Body als UTF-8
            headers={
                "Title":    header_safe(title), # Header nur Latin-1
                "Priority": priority,           # urgent, high, default, low, min
                "Click":    url,                # Beim Tippen direkt zum Angebot
            },                                  # (kein Tags-Header → keine Emojis)
            timeout=10,
        )
        r.raise_for_status()
        print("[OK] Ntfy gesendet.")
    except Exception as e:
        print(f"[ERROR] Ntfy Fehler: {e}")


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def login(session: requests.Session) -> bool:
    if not PARFUMO_USER or not PARFUMO_PASS:
        print("[INFO] Kein Login konfiguriert – ohne Login scrapen.")
        return False
    try:
        # 1) Startseite laden → Session-Cookie holen
        session.get(BASE_URL, timeout=15)

        # 2) Direkt an /board/login.php posten (exakt wie das Browser-Modal)
        payload = {
            "username":  PARFUMO_USER,
            "password":  PARFUMO_PASS,
            "autologin": "checked",
            "login":     "Login",
            "redirect":  "",
        }
        r = session.post(LOGIN_URL, data=payload, timeout=15, allow_redirects=True)
        url_low = r.url.lower()
        low     = r.text.lower()

        # 3) Bot-Schutz / Sperre?
        if "access denied" in low or "temporarily blocked" in low:
            print("[WARN] Von Parfumo blockiert (Bot-Schutz). Es wird ohne Login weitergemacht.")
            return False

        # 4) Misserfolg eindeutig: Parfumo leitet bei falschen Daten auf /account/login_error
        if "login_error" in url_low or "invalid username / email or password" in low:
            print("[WARN] Login fehlgeschlagen – Benutzername/E-Mail oder Passwort falsch. "
                  "Es wird ohne Login weitergemacht.")
            return False

        # 5) Erfolg: Fehler landen auf login_error, Erfolg auf der Zielseite (Startseite)
        print("[OK] Login erfolgreich.")
        return True
    except Exception as e:
        print(f"[ERROR] Login Fehler: {e}")
        return False


def parse_price(text: str) -> float | None:
    """Extrahiert einen Euro-Preis aus einem String."""
    import re
    match = re.search(r"(\d+[.,]\d+|\d+)\s*€", text.replace("\xa0", " "))
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def parse_fill_level(text: str) -> int | None:
    """
    Versucht den Füllstand aus dem Angebotstext zu lesen.
    Erkennt z.B.: '95%', '90/100ml', '9/10', 'ca. 95%', 'fast voll', 'nahezu voll'
    Gibt einen Prozent-Wert (0–100) zurück oder None wenn nicht erkennbar.
    """
    import re
    text_lower = text.lower()

    # "fast voll" / "nahezu voll" / "overspray" → ~95%
    if any(w in text_lower for w in ["fast voll", "nahezu voll", "fast full", "nearly full", "overspray"]):
        return 95

    # "voll" / "full" (ohne fast/nahezu) → 100%
    if any(w in text_lower for w in ["ungeöffnet", "unbenutzt", "neu ", "new ", "sealed"]):
        return 100

    # Explizite Prozentangabe: "95%" oder "ca. 90%"
    m = re.search(r"(\d{1,3})\s*%", text)
    if m:
        val = int(m.group(1))
        if 0 <= val <= 100:
            return val

    # Bruch mit ml: "90/100ml" → 90%
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*ml", text_lower)
    if m:
        used, total = int(m.group(1)), int(m.group(2))
        if total > 0:
            return round(used / total * 100)

    # Bruch ohne Einheit: "9/10" → 90%
    m = re.search(r"(\d)\s*/\s*(10|8)(?!\d)", text)
    if m:
        num, denom = int(m.group(1)), int(m.group(2))
        return round(num / denom * 100)

    return None


def fetch_listings(session: requests.Session, url: str) -> list[dict]:
    """Lädt eine Souk-Seite und gibt eine Liste von Angeboten zurück."""
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Seite nicht ladbar: {url} – {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    listings = []

    # Angebote sind Links mit /Users/.../Souk/Item/...
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Souk/Item/" not in href:
            continue
        if not href.startswith("http"):
            href = BASE_URL + href

        # Item-ID aus URL
        item_id = href.split("/Souk/Item/")[-1].split("?")[0]

        # Text des Links für Name + Marke
        text = a.get_text(" ", strip=True)
        if not text or len(text) < 3:
            continue

        listings.append({
            "id":   item_id,
            "url":  href,
            "text": text,
        })

    # Deduplizieren nach ID
    seen_ids = set()
    unique = []
    for item in listings:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique.append(item)

    return unique


def fetch_item_details(session: requests.Session, item: dict) -> dict:
    """
    Lädt die Detailseite eines Angebots.
    Liest Preis UND den strukturierten Füllstand direkt aus den Parfumo-Feldern.
    Parfumo zeigt den Füllstand immer als eigenes Feld (z.B. "100%" + "4 / 4 ml").
    """
    try:
        r = session.get(item["url"], timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        full_text = soup.get_text(" ")

        # ── Preis ──────────────────────────────────────────────────────
        item["price"] = parse_price(full_text)

        # ── Füllstand aus strukturiertem Feld ──────────────────────────
        # Parfumo zeigt immer "XX%" als eigene Zeile + "X / Y ml" darunter.
        # Wir suchen zuerst das strukturierte Prozent-Feld, dann ml-Verhältnis.
        import re

        # Methode 1: Explizites Prozent-Feld (z.B. "100%" allein in einer Zeile)
        # Im gerenderten Text erscheint es als isolierter Wert wie "\n100%\n"
        fill_from_field = None
        pct_matches = re.findall(r"(?<!\w)(\d{1,3})\s*%(?!\w)", full_text)
        for pct in pct_matches:
            val = int(pct)
            if 0 <= val <= 100:
                fill_from_field = val
                break  # Erstes sinnvolles Ergebnis nehmen

        # Methode 2: ml-Verhältnis (z.B. "4 / 4 ml" oder "90 / 100 ml")
        fill_from_ml = None
        ml_match = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*ml", full_text)
        if ml_match:
            current = float(ml_match.group(1).replace(",", "."))
            total   = float(ml_match.group(2).replace(",", "."))
            if total > 0:
                fill_from_ml = round(current / total * 100)

        # Strukturiertes Feld hat Vorrang vor Freitext-Erkennung
        item["fill_pct"] = fill_from_field if fill_from_field is not None else fill_from_ml
        item["fill_source"] = "structured" if fill_from_field or fill_from_ml else "none"

    except Exception as e:
        print(f"[WARN] Details für {item['id']} nicht ladbar: {e}")
        item["price"]       = None
        item["fill_pct"]    = None
        item["fill_source"] = "none"
    return item


def _name_matches(name: str, text_lower: str) -> bool:
    """Alle Wörter aus 'name' müssen im Angebots-Text vorkommen (Reihenfolge egal)."""
    return all(tok in text_lower for tok in name.lower().split())


def _norm_art(s: str) -> str:
    """Normalisiert eine Art-Angabe auf 'flakon' | 'abfüllung' | 'beides'."""
    s = (s or "").lower().strip()
    if s in ("flakon", "flakons", "bottle", "voll"):
        return "flakon"
    if s in ("abfüllung", "abfuellung", "abfüllungen", "probe", "proben", "decant", "sample", "samples"):
        return "abfüllung"
    return "beides"


def category_art(category: str) -> str:
    """Leitet aus der Souk-Kategorie die Art ab ('' = gemischt/unbekannt)."""
    c = (category or "").lower()
    has_flakon = "flakon" in c
    has_probe  = "probe" in c or "abf" in c
    if has_flakon and not has_probe:
        return "flakon"
    if has_probe and not has_flakon:
        return "abfüllung"
    return ""  # z.B. öffentliche Mischseite → Art unbekannt


def detect_art_from_text(text: str) -> str:
    """Erkennt die Art am Angebots-Text (Souk zeigt 'Bottle' bzw. 'Sample/Split')."""
    t = (text or "").lower()
    if any(w in t for w in ["sample", "split", "decant", "probe", "abfüll", "abfuell"]):
        return "abfüllung"
    if any(w in t for w in ["bottle", "flakon"]):
        return "flakon"
    return ""


def _entry_check(item: dict, entry: dict) -> tuple[str | None, str]:
    """
    Prüft Art, Füllmenge und Preis eines Angebots gegen EINEN Watchlist-Eintrag
    (ohne Namensprüfung – die macht der Aufrufer bzw. entfällt bei souk_url-Seiten).
    Gibt (treffer_name | None, log_grund) zurück.
    """
    # Art
    want_art = _norm_art(entry.get("art", "beides"))
    have_art = item.get("art", "")
    if want_art != "beides" and have_art and want_art != have_art:
        return None, ""

    # Füllmenge
    fill_pct = item.get("fill_pct")
    if fill_pct is None:
        fill_pct = parse_fill_level(item["text"])
    min_fill = entry.get("min_fill", 0)
    if min_fill > 0:
        if fill_pct is None:
            if not NOTIFY_IF_FILL_UNKNOWN:
                return None, ""
        elif fill_pct < min_fill:
            return None, ""  # zu wenig voll

    # Preis
    price = item.get("price")
    limit = entry.get("max_preis", 0)
    if limit > 0 and price is not None and price > limit:
        return None, ""
    if price is None and limit > 0 and not NOTIFY_IF_PRICE_UNKNOWN:
        return None, ""

    fill_str  = f"{fill_pct}%" if fill_pct is not None else "Füllmenge unbekannt"
    price_str = f"{price:.2f}€" if price is not None else "Preis unbekannt"
    return entry["name"], f"{entry['name']} · {fill_str} · {price_str}"


def matches_filter(item: dict) -> tuple[str | None, str]:
    """Prüft ein Angebot gegen die GESAMTE Watchlist (Name muss passen)."""
    if NOTIFY_ALL_NEW:
        return _entry_check(item, {"name": "Neues Angebot", "art": "beides"})
    text_lower = item["text"].lower()
    for entry in WATCHLIST:
        if not _name_matches(entry["name"], text_lower):
            continue
        name, reason = _entry_check(item, entry)
        if name:
            return name, reason
    return None, ""


def build_message(item: dict, name: str) -> tuple[str, str]:
    """Minimalistische ntfy-Nachricht: Parfum · Füllmenge · Preis – keine Emojis."""
    fill      = item.get("fill_pct")
    fill_str  = f"{fill}% voll" if fill is not None else "Füllmenge unbekannt"
    price     = item.get("price")
    price_str = f"{price:.2f} €".replace(".", ",") if price is not None else "Preis unbekannt"
    return name, f"{fill_str} · {price_str}"


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Parfumo Souk Watcher startet…")

    # Seed-Modus: aktuelle Angebote nur als "bekannt" markieren, NICHT melden
    seed_mode = os.environ.get("SEED", "").lower() in ("1", "true", "yes", "on")
    if seed_mode:
        print("[SEED] Seed-Modus aktiv – aktuelle Angebote werden NICHT gemeldet, nur gemerkt.")

    seen_items = load_seen_items()
    session    = requests.Session()
    session.headers.update(HEADERS)
    logged_in  = login(session)

    new_count = 0

    # Quellen: eingeloggt die Offers-Seiten, sonst die öffentliche Übersicht …
    # entry=None → gegen die ganze Watchlist (Name muss passen);
    # entry gesetzt → gezielte Souk-Seite eines Parfums (Name schon klar).
    if logged_in:
        sources = [
            ("https://www.parfumo.com/Souks/Offers/Perfumes", "Flakons", None),
            ("https://www.parfumo.com/Souks/Offers/Samples",  "Proben",  None),
        ]
    else:
        sources = [("https://www.parfumo.com/Souks", "Flakons & Proben", None)]
    sources += [(e["souk_url"], "", e) for e in WATCHLIST if e.get("souk_url")]

    matches = []  # (name, item) – am Ende gesammelt verschicken

    for url, category, entry in sources:
        label = category or (entry["name"] if entry else "Watchlist-Suche")
        print(f"  → Lade {label}: {url}")
        listings = fetch_listings(session, url)
        print(f"     {len(listings)} Angebote gefunden.")

        for item in listings:
            if item["id"] in seen_items:
                continue  # Bereits bekannt

            seen_items.add(item["id"])
            new_count += 1

            # Art (Flakon/Abfüllung): aus Kategorie, sonst aus dem Angebots-Text
            item["art"] = category_art(category) or detect_art_from_text(item["text"])

            # Details laden (Preis/Füllmenge) – nur wenn Login vorhanden
            if logged_in:
                item = fetch_item_details(session, item)
                time.sleep(1)  # Höflichkeit gegenüber dem Server

            # souk_url-Quelle: direkt gegen ihren Eintrag prüfen, sonst ganze Watchlist
            if entry is not None:
                name, reason = _entry_check(item, entry)
            else:
                name, reason = matches_filter(item)

            if name:
                print(f"  ✅ Match: {reason}")
                matches.append((name, item))
            else:
                print(f"  ⏭  Kein Match: {item['text'][:60]}")

    if seed_mode:
        print(f"[SEED] {len(matches)} aktuelle Treffer als bekannt markiert – KEINE Nachricht verschickt.")
    elif matches:
        notify_matches(matches)
    else:
        # Lebenszeichen: Lauf hat stattgefunden, aber nichts Neues gefunden
        send_ntfy("Souk-Check",
                  "Check erledigt – keine neuen Angebote.",
                  "https://www.parfumo.com/Souks", priority="low")
        print("[INFO] Keine neuen Treffer – Status-Nachricht verschickt.")
    save_seen_items(seen_items)
    print(f"[DONE] {new_count} neue Angebote verarbeitet, "
          f"{len(matches)} Treffer. Gesamt bekannt: {len(seen_items)}")


def notify_matches(matches: list):
    """Verschickt Treffer: einzeln (1) oder als eine gebündelte Nachricht (mehrere)."""
    if not matches:
        return
    if len(matches) == 1:
        name, item = matches[0]
        title, body = build_message(item, name)
        send_ntfy(title, body, item["url"])
        return
    # Mehrere Treffer in einem Lauf → eine kompakte Nachricht (kein Push-Flut)
    lines = []
    for name, item in matches:
        _, body = build_message(item, name)
        lines.append(f"{name} – {body}")
    send_ntfy(f"Souk: {len(matches)} Treffer",
              "\n".join(lines[:20]),
              "https://www.parfumo.com/Souks")


if __name__ == "__main__":
    main()
