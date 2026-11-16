# Schulbot

Dein persönlicher Assistent in Telegram für To-dos, Hausaufgaben, Termine,
Klausuren und Abgaben. Du schreibst ihm in normaler Sprache, er sortiert es ein,
kennt deinen Stundenplan und erinnert dich.

**Stand: Version 2** (To-dos, Morgennachricht, Stundenplan, Hausaufgaben, Erinnerungen).
Apple-Kalender, Wochenausblick und Krankmodus folgen in Version 3 und 4.

## Was er kann

- **Einträge in normaler Sprache:** `Bio-Referat bis Freitag`, `morgen 15 Uhr Zahnarzt`,
  `Mathe-Klausur am 3.12.`, `Mathe S. 45 Nr. 3`. Er erkennt Datum, Uhrzeit, Fach, Art und
  Priorität und bestätigt kurz. Unter der Bestätigung sind Knöpfe zum Korrigieren.
- **Stundenplan:** Er weiß, welches Fach du wann, wo und bei wem hast.
  Fragen wie `Was hab ich morgen?` oder `Wer unterrichtet Bio?` beantwortet er direkt.
- **Hausaufgaben:** Ohne Datum setzt er als Frist die nächste Stunde in diesem Fach.
- **Morgennachricht um 8:00 Uhr:** Überfälliges ganz oben, dann Stundenplan, Termine und
  Aufgaben von heute nach Priorität, dann ein Ausblick auf die nächsten 3 Tage.
- **Abendnachricht um 19:00 Uhr:** Hausaufgaben für morgen, offene To-dos, Überfälliges und
  Klausuren oder Abgaben in 3 Tagen. Sie kommt nur, wenn es etwas zu erinnern gibt.
- **Erinnerung vor Terminen:** 1 Stunde vor allem, was Datum und Uhrzeit hat.
- **Nur für dich:** Er antwortet nur deiner Telegram-ID.

Das Erkennen läuft über feste Regeln, ohne KI und ohne Kosten.

## Befehle

| Befehl | Was er macht |
|---|---|
| `/heute`, `/morgen`, `/woche`, `/alle` | Übersichten |
| `/erledigt` | Etwas abhaken |
| `/verschieben` | Einem Eintrag ein neues Datum geben |
| `/loeschen` | Etwas löschen |
| `/stundenplan` | Stundenplan anzeigen |
| `/stundenplan hilfe` | Erklärt, wie du den Stundenplan änderst |
| `/stundenplan datei` | Schickt den Stundenplan als Tabelle (CSV-Datei) |
| `/stunde Mi 3-4 Mathe 112 Frau Beispiel` | Eine Stunde eintragen oder ersetzen |
| `/stunde Mi 3-4 frei` | Eine Stunde löschen |
| `/lehrkraft` | Lehrkräfte und ihre E-Mail-Adressen anzeigen |
| `/lehrkraft Beispiel name@schule.de` | Eine E-Mail-Adresse eintragen |
| `/hilfe` | Kurze Übersicht im Chat |

## Stundenplan eintragen

Schick dem Bot den ganzen Plan als Nachricht. Die erste Zeile muss genau so lauten,
danach kommt eine Zeile pro Block:

```
Tag;Stunde;Fach;Raum;Lehrkraft;E-Mail
Mi;3-4;Mathe;112;Frau Beispiel;beispiel@schule.de
Mi;5-6;Deutsch;N3;Herr Muster;
```

Raum, Lehrkraft und E-Mail dürfen leer bleiben. Ein neuer Plan ersetzt den alten,
E-Mail-Adressen bleiben erhalten. Dieselbe Tabelle kannst du auch als CSV-Datei schicken.
Einzelne Stunden änderst du mit `/stunde`.

Namen und E-Mail-Adressen der Lehrkräfte stehen nur in der Datenbank auf deinem Gerät.
Trag sie nicht in `config.py` ein, denn diese Datei liegt öffentlich auf GitHub.

Fotos kann der Bot ohne KI nicht lesen. Schick ein Foto des Plans an Claude, dann
bekommst du daraus die Tabelle.

## Einmalig einrichten

Du brauchst etwa 15 Minuten. In den Befehlen steht `python`.
Auf **Windows** schreibst du stattdessen `py`, auf dem **Mac** `python3`.

### 1. Python installieren

Lade Python (Version 3.11 oder neuer) von <https://www.python.org/downloads/> und
installiere es. Auf Windows im ersten Fenster das Häkchen bei
**„Add python.exe to PATH“** setzen.

### 2. Code herunterladen

Falls du den Ordner `schulbot` noch nicht auf deinem Computer hast: Öffne
<https://github.com/josyzoe10/My-List/archive/refs/heads/claude/personal-school-assistant-bot-w6ow46.zip>
und entpacke die ZIP-Datei. Merk dir, wo der Ordner `schulbot` liegt.

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

Beende den Bot mit `Strg+C` (Mac: `Control+C`), starte `python einrichten.py` noch
einmal, drück beim Token Enter und trag die ID ein. Danach wieder `python main.py`.
Ab jetzt antwortet der Bot nur noch dir.

## Starten und beenden

- **Starten:** Terminal im Ordner `schulbot` öffnen (Schritt 4) und `python main.py` eingeben.
- **Beenden:** `Strg+C` im Terminal (Mac: `Control+C`).

Solange es kein Hosting gibt, läuft der Bot nur, während das Terminalfenster offen
und dein Computer an ist. War der Computer im Ruhezustand, holt der Bot nach dem
Aufwachen nach, was fällig war: die Morgennachricht bis 12:00 Uhr, die Abendnachricht
bis 22:00 Uhr.

## Neue Version holen

```
python aktualisieren.py
python main.py
```

Beende den Bot vorher mit `Strg+C`. Das Programm lädt den neuesten Stand von GitHub
und ersetzt die Programmdateien. Deine Geheimnisse (`.env`) und deine Einträge
(`schulbot.db`) bleiben unverändert. Hattest du `config.py` selbst geändert, liegt
deine alte Fassung danach in `config_alt.py`.

Wie der Bot dauerhaft im Internet läuft und wie du ihn dort aktualisierst, kommt in
diese Anleitung, sobald das Hosting eingerichtet ist.

## Ändern

Fast alles, was du anpassen willst, steht in **`config.py`**:

- `BOT_NAME`: der Name deines Assistenten
- `MORGENNACHRICHT_UHRZEIT`, `ABENDNACHRICHT_UHRZEIT`: wann die Nachrichten kommen
- `ERINNERUNG_TERMIN_MINUTEN`: wie lange vor einem Termin er erinnert
- `ERINNERUNG_TAGE_VORHER`: wie viele Tage vorher er an Klausuren und Abgaben erinnert
- `AUSBLICK_TAGE`: wie weit der Ausblick der Morgennachricht reicht
- `FAECHER`: deine Fächer und ihre Schreibweisen
- `STUNDENZEITEN`: Beginn und Ende jeder Schulstunde
- `FERIEN`: Ferien und freie Tage (dann gibt es keinen Stundenplan und keine Fristen)

Nach jeder Änderung den Bot beenden und neu starten. Am besten sagst du Claude, was
du ändern willst. Dann steht es auch auf GitHub und geht beim nächsten Update nicht verloren.

Token oder Telegram-ID änderst du mit `python einrichten.py`. Sie stehen in der Datei
`.env`, die nie zu GitHub hochgeladen wird.

## Die Dateien

| Datei | Aufgabe |
|---|---|
| `main.py` | Startet den Bot. |
| `einrichten.py` | Legt die Datei `.env` an. |
| `aktualisieren.py` | Holt die neueste Version von GitHub. |
| `config.py` | Deine Einstellungen. |
| `bot/erkennung.py` | Versteht Sätze: Datum, Uhrzeit, Fach, Art, Priorität. |
| `bot/stundenplan.py` | Rechnet mit dem Stundenplan und liest Tabellen. |
| `bot/datenbank.py` | Speichert alles in der Datei `schulbot.db`. |
| `bot/nachrichten.py` | Baut die Texte, z. B. die Morgennachricht. |
| `bot/zeitplan.py` | Morgennachricht, Abendnachricht und Erinnerungen. |
| `bot/handler.py` | Der Telegram-Teil: Befehle, Nachrichten, Knöpfe. |
| `bot/zeit.py` | Die aktuelle Zeit in deiner Zeitzone. |
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
- **Eine Hausaufgabe bekommt kein Datum**: Das Fach steht nicht im Stundenplan
  (`/stundenplan`), oder der Bot hat das Fach im Satz nicht erkannt.
- **`pip` meldet „externally-managed-environment“**: Dann einmal
  `python -m venv .venv` ausführen und danach statt `python` immer
  `.venv/bin/python` (Mac) oder `.venv\Scripts\python` (Windows) schreiben.
