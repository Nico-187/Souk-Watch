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
# Suchbegriffe: Trifft zu wenn Parfum-Name ODER Marke den Begriff enthält (Groß-/Kleinschreibung egal)
WATCH_KEYWORDS = [
    "Creed",
    "Amouage",
    "Xerjoff",
    # weitere Marken oder Parfumnamen einfach hinzufügen:
    # "Aventus",
    # "Reflection Man",
]

# Preislimit in Euro: Nur Angebote UNTER diesem Preis werden gemeldet (0 = deaktiviert)
PRICE_LIMIT = 80.0

# Mindeststfüllstand in Prozent: Nur Angebote mit >= diesem Wert (0 = deaktiviert)
# Erkennt Angaben wie "95%", "90/100ml", "ca. 9/10", "fast voll" etc.
MIN_FILL_PERCENT = 90

# Sende ALLE neuen Angebote (auch ohne Filter-Match)?
NOTIFY_ALL_NEW = False

# ──────────────────────────────────────────────
#  DATEIPFADE
# ──────────────────────────────────────────────
DATA_FILE = Path("data/seen_items.json")

# ──────────────────────────────────────────────
#  SOUK URLs
# ──────────────────────────────────────────────
SOUK_URLS = [
    # Öffentliche Übersichtsseite (funktioniert ohne Login)
    ("https://www.parfumo.com/Souks", "Flakons & Proben"),
    # Mit Login auch spezifischere Seiten:
    ("https://www.parfumo.com/Souks/Offers/Perfumes", "Flakons"),
    ("https://www.parfumo.com/Souks/Offers/Samples",  "Proben"),
]

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
            data=message.encode("utf-8"),       # Body darf UTF-8 (Emoji ok)
            headers={
                "Title":    header_safe(title), # Header nur Latin-1 (kein Emoji)
                "Priority": priority,           # urgent, high, default, low, min
                "Tags":     "perfume",
                "Click":    url,                # Beim Tippen direkt zum Angebot
            },
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


def matches_filter(item: dict) -> tuple[bool, str]:
    """
    Prüft ob ein Angebot den Filtern entspricht.
    Gibt (match, grund) zurück.
    """
    text_lower = item["text"].lower()
    price      = item.get("price")
    reasons    = []

    # Keyword-Match?
    keyword_match = any(kw.lower() in text_lower for kw in WATCH_KEYWORDS)
    if keyword_match:
        matched_kw = [kw for kw in WATCH_KEYWORDS if kw.lower() in text_lower]
        reasons.append(f"🔍 Keyword: {', '.join(matched_kw)}")

    # Preis-Match?
    price_match = False
    if PRICE_LIMIT > 0 and price is not None and price < PRICE_LIMIT:
        price_match = True
        reasons.append(f"💶 Preis: {price:.2f}€ (unter {PRICE_LIMIT:.0f}€)")

    # Füllstand-Filter
    # Füllstand: strukturiertes Feld (von Detailseite) hat Vorrang vor Freitext
    fill_pct = item.get("fill_pct")  # gesetzt von fetch_item_details (strukturiert)
    if fill_pct is None:
        # Fallback: Freitext aus Titel/Beschreibung (z.B. wenn kein Login)
        fill_pct = parse_fill_level(item["text"])
    fill_source = item.get("fill_source", "text")

    fill_match = False
    if MIN_FILL_PERCENT > 0:
        if fill_pct is not None and fill_pct >= MIN_FILL_PERCENT:
            fill_match = True
            src_label = "Parfumo-Feld" if fill_source == "structured" else "Freitext"
            reasons.append(f"🫙 Füllstand: {fill_pct}% (≥{MIN_FILL_PERCENT}%, via {src_label})")
        elif fill_pct is None:
            # Füllstand unbekannt → trotzdem durchlassen wenn anderer Filter greift
            pass
        else:
            # Zu wenig gefüllt → blockieren, auch wenn Keyword/Preis passt
            return False, f"⛔ Füllstand zu niedrig: {fill_pct}% (min. {MIN_FILL_PERCENT}%)"

    # TOP-TREFFER: Keyword + Preis + Füllstand
    if sum([keyword_match, price_match, fill_match]) >= 2:
        reasons = ["⭐ TOP-TREFFER"] + reasons

    match = keyword_match or price_match or fill_match or NOTIFY_ALL_NEW
    return match, " | ".join(reasons)


def build_message(item: dict, reason: str, category: str) -> tuple[str, str]:
    price_str = f"{item['price']:.2f}€" if item.get("price") else "Preis unbekannt (Login)"
    title = item["text"][:80]                       # Titel: nur Latin-1-sicherer Text
    body  = f"🧴 [{category}] {price_str}\n{reason}" # Body darf UTF-8 → Emoji hier
    return title, body


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Parfumo Souk Watcher startet…")

    seen_items = load_seen_items()
    session    = requests.Session()
    session.headers.update(HEADERS)
    logged_in  = login(session)

    new_count = 0

    for url, category in SOUK_URLS:
        # Mit Login: spezifischere Seiten bevorzugen; ohne Login: nur öffentliche Seite
        if not logged_in and url != "https://www.parfumo.com/Souks":
            continue
        if logged_in and url == "https://www.parfumo.com/Souks":
            continue  # Mit Login die spezifischen Seiten nutzen

        print(f"  → Lade {category}: {url}")
        listings = fetch_listings(session, url)
        print(f"     {len(listings)} Angebote gefunden.")

        for item in listings:
            if item["id"] in seen_items:
                continue  # Bereits bekannt

            seen_items.add(item["id"])
            new_count += 1

            # Details laden (Preis) – nur wenn Login vorhanden
            if logged_in:
                item = fetch_item_details(session, item)
                time.sleep(1)  # Höflichkeit gegenüber dem Server

            match, reason = matches_filter(item)
            if match:
                title, body = build_message(item, reason, category)
                # Top-Treffer = hohe Priorität
                priority = "high" if "TOP-TREFFER" in reason else "default"
                print(f"  ✅ Match: {item['text']} | {reason}")
                send_ntfy(title, body, item["url"], priority)
            else:
                print(f"  ⏭  Kein Match: {item['text'][:60]}")

    save_seen_items(seen_items)
    print(f"[DONE] {new_count} neue Angebote verarbeitet. Gesamt bekannt: {len(seen_items)}")


if __name__ == "__main__":
    main()
