# Schulbot

Dein persönlicher Assistent in Telegram für To-dos, Hausaufgaben, Termine,
Klausuren und Abgaben. Du schreibst ihm in normaler Sprache, er sortiert es ein
und schickt dir jeden Morgen eine Übersicht.

**Stand: Version 1** (To-dos hinzufügen und Morgennachricht).
Stundenplan, Erinnerungen, Apple-Kalender und Krankmodus folgen in Version 2 bis 4.

## Was er schon kann

- Einträge in normaler Sprache: `Bio-Referat bis Freitag`, `morgen 15 Uhr Zahnarzt`,
  `Mathe-Klausur am 3.12.`, `Mathe S. 45 Nr. 3`
- Er erkennt Datum, Uhrzeit, Fach, Art und Priorität und bestätigt kurz.
  Unter der Bestätigung sind Knöpfe zum Korrigieren (Art, Priorität, Datum, Löschen).
- Morgennachricht jeden Tag um 8:00 Uhr: Überfälliges ganz oben, dann Termine und
  Aufgaben von heute nach Priorität, dann ein Ausblick auf die nächsten 3 Tage.
- Befehle: `/heute`, `/morgen`, `/woche`, `/alle`, `/erledigt`, `/hilfe`
- Nur du kannst ihn benutzen (Whitelist mit deiner Telegram-ID).

Das Erkennen läuft im Moment über feste Regeln, ohne KI und ohne Kosten.

## Einmalig einrichten

Du brauchst etwa 15 Minuten. In den Befehlen unten steht `python`.
Auf **Windows** schreibst du stattdessen `py`, auf dem **Mac** `python3`.

### 1. Python installieren

Lade Python (Version 3.11 oder neuer) von <https://www.python.org/downloads/> und
installiere es. Auf Windows im ersten Fenster das Häkchen bei
**„Add python.exe to PATH“** setzen.

### 2. Code herunterladen

Öffne
<https://github.com/josyzoe10/My-List/archive/refs/heads/claude/personal-school-assistant-bot-w6ow46.zip>,
entpacke die ZIP-Datei und merk dir, wo der Ordner `schulbot` liegt.

### 3. Bot bei Telegram anlegen

1. Such in Telegram nach **@BotFather** (mit blauem Haken) und tippe auf „Start“.
2. Schreib `/newbot`.
3. Gib einen Anzeigenamen ein (z. B. `Mein Schulbot`) und danach einen Benutzernamen,
   der auf `bot` endet (z. B. `mein_schul_bot`).
4. BotFather schickt dir einen **Token**. Das ist das Passwort deines Bots.
   Gib ihn niemandem und schick ihn in keinen Chat.

### 4. Terminal im Ordner `schulbot` öffnen

- **Windows:** Ordner `schulbot` im Explorer öffnen, in die Adresszeile oben klicken,
  `powershell` eintippen und Enter drücken.
- **Mac:** Programm „Terminal“ öffnen, `cd ` (mit Leerzeichen) tippen, den Ordner
  `schulbot` aus dem Finder ins Fenster ziehen und Enter drücken.

### 5. Einrichten und starten

```
python -m pip install -r requirements.txt
python einrichten.py
python main.py
```

- Der erste Befehl lädt die nötigen Bibliotheken.
- `einrichten.py` fragt nach dem Token. Die Frage nach der Telegram-ID
  überspringst du beim ersten Mal mit Enter.
- `main.py` startet den Bot. Schreib ihm jetzt in Telegram irgendetwas.
  Er antwortet mit deiner **Telegram-ID**.

Beende den Bot mit `Strg+C`, starte `python einrichten.py` noch einmal, drück beim
Token Enter und trag die ID ein. Danach wieder `python main.py`. Ab jetzt antwortet
der Bot nur noch dir.

## Ausprobieren

Schreib dem Bot nacheinander:

| Du schreibst | Das sollte passieren |
|---|---|
| `/start` | Er stellt sich vor und zeigt die Befehle. |
| `Bio-Referat bis Freitag` | Abgabe, Fach Bio, nächster Freitag, Priorität hoch. |
| `morgen 15 Uhr Zahnarzt` | Termin, morgen um 15:00. |
| `Mathe S. 45 Nr. 3` | Hausaufgabe, Fach Mathe, kein Datum. |
| Knopf „Datum“, dann `Freitag` | Die Hausaufgabe bekommt den Freitag als Datum. |
| `/heute` | Die Übersicht, die auch morgens kommt. |
| `/alle` | Alles Offene. |
| `/erledigt` | Liste mit Knöpfen zum Abhaken. |

Die Morgennachricht kommt um 8:00 Uhr, solange der Bot läuft. War er um 8:00 Uhr
aus, holt er sie nach, wenn du ihn vor 12:00 Uhr startest. Zum Testen kannst du in
`config.py` bei `MORGENNACHRICHT_UHRZEIT` eine Uhrzeit in zwei Minuten eintragen
und den Bot neu starten.

Solange es kein Hosting gibt, läuft der Bot nur, während das Terminalfenster offen
und dein Laptop an ist.

## Ändern

Fast alles, was du anpassen willst, steht in **`config.py`**:

- `BOT_NAME`: der Name deines Assistenten
- `MORGENNACHRICHT_UHRZEIT`: wann die Morgennachricht kommt
- `AUSBLICK_TAGE`: wie weit der Ausblick reicht
- `FAECHER`: deine Fächer und ihre Schreibweisen

Nach jeder Änderung den Bot mit `Strg+C` beenden und mit `python main.py` neu starten.

Token oder Telegram-ID änderst du mit `python einrichten.py`. Sie stehen in der Datei
`.env`, die nie zu GitHub hochgeladen wird.

## Neue Version holen

Lade die ZIP-Datei neu herunter und entpacke sie. Kopiere dann aus dem alten Ordner
`schulbot` zwei Dateien in den neuen: **`.env`** (deine Geheimnisse) und
**`schulbot.db`** (deine Einträge). Falls du `config.py` geändert hast, übernimm
deine Änderungen dort von Hand.

Wie der Bot dauerhaft im Internet läuft und wie du ihn dort aktualisierst, kommt in
diese Anleitung, sobald das Hosting eingerichtet ist.

## Die Dateien

| Datei | Aufgabe |
|---|---|
| `main.py` | Startet den Bot. |
| `einrichten.py` | Legt die Datei `.env` an. |
| `config.py` | Deine Einstellungen. |
| `bot/erkennung.py` | Versteht Sätze: Datum, Uhrzeit, Fach, Art, Priorität. |
| `bot/datenbank.py` | Speichert alles in der Datei `schulbot.db`. |
| `bot/nachrichten.py` | Baut die Texte, z. B. die Morgennachricht. |
| `bot/handler.py` | Der Telegram-Teil: Befehle, Knöpfe, Zeitplan. |
| `tests/` | Automatische Tests. |

## Tests

```
python -m pip install -r requirements-dev.txt
python -m pytest
```

Die Tests brauchen weder Internet noch Token. Sie benutzen einen Nachbau von Telegram.

## Wenn etwas nicht klappt

- **„Es fehlt der Bot-Token“**: erst `python einrichten.py` starten.
- **„Telegram kennt diesen Token nicht“**: Token in BotFather mit `/token` neu
  anzeigen lassen und mit `python einrichten.py` eintragen.
- **Der Bot antwortet nicht**: Läuft `python main.py` noch? Stimmt die Telegram-ID?
- **`pip` meldet „externally-managed-environment“**: Dann einmal
  `python -m venv .venv` ausführen und danach statt `python` immer
  `.venv/bin/python` (Mac) oder `.venv\Scripts\python` (Windows) schreiben.
