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
Öffne `scraper.py` in VS Code und ändere oben die **Such-Liste**. Jedes Parfum ist ein
Eintrag mit eigenem Preislimit, Art und Mindest-Füllmenge:
```python
WATCHLIST = [
    {"name": "Pana Dora Oud Republic", "max_preis": 0, "art": "flakon", "min_fill": 95,
     "souk_url": "https://www.parfumo.com/s_souk.php?b=pana-dora&p=oud-republic&img=1"},
    # beliebig erweitern …
]
```
- **name**: alle Wörter müssen im Angebot vorkommen (Marke + Parfum).
- **max_preis**: Höchstpreis in €. `0` = Preis egal.
- **art**: `"flakon"` · `"abfüllung"` · `"beides"`.
- **min_fill**: Mindest-Füllmenge in % (z. B. `95`). `0` = egal.
- **souk_url** *(optional)*: direkte Souk-Seite des Parfums → der Watcher findet es
  zuverlässiger. Schema: `s_souk.php?b=<marke>&p=<parfum>` (klein, mit Bindestrichen,
  wie in der Parfum-URL `/Parfums/<marke>/<parfum>`).

Treffer = Name **und** Art **und** Füllmenge ≥ min_fill **und** Preis ≤ max_preis.

> **Benachrichtigung:** minimalistisch, ohne Emojis – Titel = Parfum, Text = `Füllmenge · Preis`
> (oder „Preis unbekannt"). Mehrere Treffer eines Laufs kommen als **eine** gebündelte Nachricht.
> Findet ein Lauf **nichts Neues**, kommt eine kurze Status-Nachricht „Check erledigt – keine
> neuen Angebote" (leise, Priorität `low`), damit du weißt, dass der Check lief.

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

**Preis bleibt leer / „Login fehlgeschlagen"?**
Login hat nicht geklappt. Prüfe `PARFUMO_USER` (Benutzername **oder** E-Mail) / `PARFUMO_PASS`.

**Zu viele / zu wenige Nachrichten?**
`WATCHLIST` anpassen: genauere Namen, niedrigere `max_preis`, oder per `art` auf Flakon/Abfüllung einschränken.

**Zeitplan ändern?**
In `.github/workflows/watcher.yml` die `cron`-Zeiten (in UTC; deutsche Zeit = UTC+2 im Sommer).

**Mehr Angebote pro Lauf prüfen?**
Eingeloggt werden die Souk-Seiten für Flakons und Abfüllungen gelesen (je ~16 Angebote) – reicht für 3 Checks/Tag.
