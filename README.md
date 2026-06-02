# 🧴 Parfumo Souk Watcher

Überwacht den Parfumo Souk automatisch 3× täglich und schickt dir Push-Nachrichten aufs iPhone (via Ntfy) bei passenden Angeboten.

**Kosten: 0 €** – läuft komplett auf GitHub Actions.

Filter: Marke/Parfum-Name • Höchstpreis • Mindest-Füllstand.

---

## 📁 Diese Dateien

```
parfumo-watcher/
├── scraper.py              ← Das Hauptprogramm (hier Filter anpassen)
├── requirements.txt        ← Python-Pakete
├── README.md               ← Diese Anleitung
├── .gitignore
├── data/
│   └── seen_items.json     ← "Gedächtnis" (bekannte Angebote)
└── .github/workflows/
    └── watcher.yml         ← Zeitplan für GitHub Actions
```

---

# TEIL A — Lokal auf dem Mac ausprobieren (VS Code)

### 1. Python prüfen / installieren
Öffne in VS Code das Terminal (**Menü: Terminal → New Terminal**) und tippe:
```bash
python3 --version
```
Kommt eine Version (z.B. `Python 3.12.x`) → gut. Falls nicht:
```bash
brew install python
```
(Falls `brew` fehlt: [brew.sh](https://brew.sh) → Installationsbefehl kopieren.)

### 2. Projekt in VS Code öffnen
**Menü: File → Open Folder…** → den Ordner `parfumo-watcher` auswählen.

### 3. Pakete installieren
Im VS-Code-Terminal (stelle sicher dass du im Projektordner bist):
```bash
pip3 install -r requirements.txt
```

### 4. Zugangsdaten setzen + Probelauf
Im selben Terminal (ersetze E-Mail & Passwort):
```bash
export PARFUMO_USER="deine@email.de"
export PARFUMO_PASS="deinPasswort"
python3 scraper.py
```
→ Im Terminal siehst du den Login-Status und für jedes Angebot, ob es ein Treffer ist (`✅ Match` / `⏭ Kein Match`).

> 💡 **Tipp für den ersten Lauf:** Setze `NTFY_TOPIC` noch **nicht**. Dann wird **kein** Push verschickt (es kommt nur ein Hinweis „Ntfy nicht konfiguriert"), und du kannst in Ruhe prüfen, ob Login, Preise und Treffer stimmen. Beim ersten Lauf werden alle aktuellen Angebote in `data/seen_items.json` als „bekannt" gespeichert.

> ⚠️ Die `export`-Zeilen gelten nur für das aktuelle Terminal-Fenster. Schließt du es, musst du sie erneut eingeben.

### 5. Filter anpassen
Öffne `scraper.py` in VS Code und ändere oben den Block **FILTER-REGELN**:
```python
WATCH_KEYWORDS = [
    "Creed",
    "Amouage",
    "Xerjoff",
    # beliebig erweitern: "Aventus", "Layton", ...
]

PRICE_LIMIT = 80.0        # Höchstpreis in € (0 = aus)
MIN_FILL_PERCENT = 90     # Mindest-Füllstand in % (0 = aus)
NOTIFY_ALL_NEW = False    # True = ALLE neuen Angebote melden
```

---

# TEIL B — Ntfy (Push aufs iPhone)

### 6. App installieren
[**ntfy im App Store**](https://apps.apple.com/app/ntfy/id1625396347)

### 7. Topic abonnieren
App öffnen → **+** → einen **einzigartigen** Namen wählen (wie ein geheimes Passwort, da jeder mit dem Namen mitlesen könnte), z.B.:
```
parfumo-max-7x9k2q
```
Diesen Namen brauchst du gleich als `NTFY_TOPIC`.

### 8. Push lokal testen (optional)
```bash
export NTFY_TOPIC="parfumo-max-7x9k2q"
python3 scraper.py
```
→ Bei einem Treffer sollte sofort eine Benachrichtigung aufs iPhone kommen.

---

# TEIL C — GitHub (läuft automatisch, kostenlos)

### 9. GitHub-Account
Falls nötig: [github.com](https://github.com) → kostenlos registrieren.

### 10. Repository anlegen
- Oben rechts **+** → **New repository**
- Name: `parfumo-watcher`
- Sichtbarkeit: **Private** ✅ (wichtig!)
- **Create repository**

### 11. Dateien hochladen
**Einfachster Weg (ohne Git-Kenntnisse):**
Auf der Repo-Seite → **uploading an existing file** → alle Dateien reinziehen.
> Wichtig: Die Ordnerstruktur muss erhalten bleiben (`.github/workflows/watcher.yml` und `data/seen_items.json`).

**Oder per Terminal (in VS Code):**
```bash
git init
git add .
git commit -m "Erste Version"
git branch -M main
git remote add origin https://github.com/DEIN-NAME/parfumo-watcher.git
git push -u origin main
```

### 12. Secrets hinterlegen
Im Repository: **Settings → Secrets and variables → Actions → New repository secret**

Lege diese **drei** Secrets an:

| Name | Wert |
|------|------|
| `PARFUMO_USER` | deine Parfumo-E-Mail |
| `PARFUMO_PASS` | dein Parfumo-Passwort |
| `NTFY_TOPIC` | dein Ntfy-Topic-Name |

### 13. Aktivieren & testen
- Reiter **Actions** → falls gefragt, Workflows aktivieren
- Links **Parfumo Souk Watcher** → **Run workflow** → grüner Button
- Nach ~1 Min sollte der Lauf grün sein. Beim ersten Mal werden alle aktuellen Angebote als "bekannt" gespeichert; ab dann nur noch wirklich neue.

**Fertig!** 🎉 Läuft automatisch um **8:00, 14:00 und 20:00 Uhr** (deutsche Zeit).

---

## 🔧 Häufige Fragen

**Preis/Füllstand bleibt leer (`—`)?**
Login hat nicht geklappt. Prüfe `PARFUMO_USER` / `PARFUMO_PASS`.

**Zu viele / zu wenige Nachrichten?**
`WATCH_KEYWORDS` verfeinern, `PRICE_LIMIT` / `MIN_FILL_PERCENT` anpassen.

**Zeitplan ändern?**
In `.github/workflows/watcher.yml` die `cron`-Zeiten (in UTC; deutsche Zeit = UTC+2 im Sommer).

**Mehr Angebote pro Lauf prüfen?**
Aktuell wird die erste Übersichtsseite (16 Angebote) gelesen – reicht für 3 Checks/Tag.
