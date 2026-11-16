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

# Wann kommt die Abendnachricht? Sie erinnert an die Hausaufgaben für morgen,
# an offene To-dos und an Klausuren und Abgaben, die bald anstehen.
ABENDNACHRICHT_UHRZEIT = (19, 0)
ABENDNACHRICHT_NACHHOLEN_BIS = 22

# Wie viele Minuten vor einem Termin mit Uhrzeit erinnert der Bot?
ERINNERUNG_TERMIN_MINUTEN = 60

# Wie viele Tage vorher erinnert die Abendnachricht an Klausuren und Abgaben?
ERINNERUNG_TAGE_VORHER = (3, 1)

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
    "Wirtschaft": ["wirtschaft", "wiwi"],
    "Chor": ["chor"],
}

# Beginn und Ende jeder Schulstunde. Stunden, die hier fehlen, zeigt der Bot
# ohne Uhrzeit an.
STUNDENZEITEN = {
    1: ("8:00", "8:45"),
    2: ("8:45", "9:30"),
    3: ("9:50", "10:35"),
    4: ("10:35", "11:20"),
    5: ("11:50", "12:35"),
    6: ("12:35", "13:20"),
    7: ("13:20", "14:05"),
    8: ("14:05", "14:50"),
    9: ("14:50", "15:35"),
}

# Ferien und freie Tage (erster Tag, letzter Tag). An diesen Tagen zeigt der Bot
# keinen Stundenplan, und Hausaufgaben werden nicht auf diese Tage gelegt.
FERIEN = [
    ("2026-12-21", "2027-01-01"),  # Weihnachtsferien
    ("2027-01-29", "2027-01-29"),  # Halbjahrespause
    ("2027-03-01", "2027-03-12"),  # Frühjahrsferien
    ("2027-03-26", "2027-03-29"),  # Karfreitag bis Ostermontag
    ("2027-05-06", "2027-05-14"),  # Himmelfahrt und Maiferien
    ("2027-05-17", "2027-05-17"),  # Pfingstmontag
    ("2027-07-01", "2027-08-11"),  # Sommerferien
]
