"""Einstellungen für deinen Assistenten.

Hier darfst du alles ändern. Nach einer Änderung musst du den Bot neu starten.
Passwörter und Schlüssel gehören NICHT hierher, sondern in die Datei .env.
"""

# Wie heißt dein Assistent? Mit diesem Namen stellt er sich vor,
# und du kannst ihn so ansprechen, z. B. "Hey Mia, Bio-Referat bis Freitag".
BOT_NAME = "[NAME]"

# Deine Zeitzone. Alle Uhrzeiten unten gelten in dieser Zeitzone.
ZEITZONE = "Europe/Berlin"

# Wann kommt die Morgennachricht? (Stunde, Minute)
MORGENNACHRICHT_UHRZEIT = (8, 0)

# Wenn der Bot um 8:00 Uhr nicht lief (z. B. Laptop aus), holt er die
# Morgennachricht beim nächsten Start nach, aber nur bis zu dieser Stunde.
MORGENNACHRICHT_NACHHOLEN_BIS = 12

# Wie viele Tage schaut der Ausblick in der Morgennachricht voraus?
AUSBLICK_TAGE = 3

# In dieser Datei speichert der Bot deine Aufgaben. Sie wird automatisch angelegt.
DATENBANK_DATEI = "schulbot.db"

# Deine Fächer. Links steht der Name, den der Bot anzeigt. Rechts stehen die
# Schreibweisen, an denen er das Fach erkennt (alles klein geschrieben).
# Du kannst Fächer löschen, umbenennen oder neue Zeilen hinzufügen.
FAECHER = {
    "Mathe": ["mathe", "mathematik"],
    "Deutsch": ["deutsch"],
    "Englisch": ["englisch", "english"],
    "Bio": ["bio", "biologie"],
    "Chemie": ["chemie"],
    "Physik": ["physik"],
    "Geschichte": ["geschichte", "geschi"],
    "PGW": ["pgw", "politik", "powi"],
    "Geo": ["geo", "geographie", "geografie", "erdkunde"],
    "Philosophie": ["philosophie", "philo"],
    "Religion": ["religion", "reli"],
    "Informatik": ["informatik", "info"],
    "Französisch": ["französisch", "franzoesisch", "franz"],
    "Spanisch": ["spanisch"],
    "Latein": ["latein"],
    "Kunst": ["kunst"],
    "Musik": ["musik"],
    "Theater": ["theater"],
    "Sport": ["sport"],
    "Seminar": ["seminar"],
}
