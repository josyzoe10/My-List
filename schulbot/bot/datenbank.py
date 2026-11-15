"""Speichert deine Aufgaben in einer SQLite-Datenbank.

SQLite ist eine Datenbank, die aus einer einzigen Datei besteht (schulbot.db).
Es läuft kein extra Programm dafür. Wenn du die Datei löschst, sind alle
Aufgaben weg. Wenn du sie kopierst, hast du eine Sicherung.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time

# Diese Felder einer Aufgabe dürfen nachträglich geändert werden.
_AENDERBAR = {"titel", "art", "fach", "faellig_am", "uhrzeit", "prioritaet"}


@dataclass
class Aufgabe:
    """Ein Eintrag: To-do, Hausaufgabe, Termin, Klausur/Test oder Abgabe."""

    id: int
    titel: str
    art: str
    fach: str | None
    faellig_am: date | None
    uhrzeit: time | None
    prioritaet: str
    erledigt: bool


def _zu_aufgabe(zeile: sqlite3.Row) -> Aufgabe:
    return Aufgabe(
        id=zeile["id"],
        titel=zeile["titel"],
        art=zeile["art"],
        fach=zeile["fach"],
        faellig_am=date.fromisoformat(zeile["faellig_am"]) if zeile["faellig_am"] else None,
        uhrzeit=time.fromisoformat(zeile["uhrzeit"]) if zeile["uhrzeit"] else None,
        prioritaet=zeile["prioritaet"],
        erledigt=bool(zeile["erledigt"]),
    )


def _zu_text(wert):
    """Datum und Uhrzeit werden als Text gespeichert, z. B. 2026-12-03 und 15:00."""
    if isinstance(wert, date):
        return wert.isoformat()
    if isinstance(wert, time):
        return wert.strftime("%H:%M")
    return wert


class Datenbank:
    def __init__(self, pfad: str):
        self._verbindung = sqlite3.connect(pfad)
        self._verbindung.row_factory = sqlite3.Row
        self._tabellen_anlegen()

    def _tabellen_anlegen(self) -> None:
        with self._verbindung:
            self._verbindung.execute(
                """
                CREATE TABLE IF NOT EXISTS aufgaben (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    titel       TEXT NOT NULL,
                    art         TEXT NOT NULL,
                    fach        TEXT,
                    faellig_am  TEXT,
                    uhrzeit     TEXT,
                    prioritaet  TEXT NOT NULL,
                    erledigt    INTEGER NOT NULL DEFAULT 0,
                    erstellt_am TEXT NOT NULL,
                    erledigt_am TEXT
                )
                """
            )
            # Kleine Merkzettel des Bots, z. B. wann die letzte Morgennachricht kam.
            self._verbindung.execute(
                "CREATE TABLE IF NOT EXISTS einstellungen (name TEXT PRIMARY KEY, wert TEXT)"
            )

    def schliessen(self) -> None:
        self._verbindung.close()

    # ----- Aufgaben -------------------------------------------------------

    def hinzufuegen(
        self,
        titel: str,
        art: str,
        fach: str | None,
        faellig_am: date | None,
        uhrzeit: time | None,
        prioritaet: str,
    ) -> Aufgabe:
        with self._verbindung:
            cursor = self._verbindung.execute(
                "INSERT INTO aufgaben (titel, art, fach, faellig_am, uhrzeit, prioritaet, erstellt_am)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (titel, art, fach, _zu_text(faellig_am), _zu_text(uhrzeit), prioritaet,
                 datetime.now().isoformat(timespec="seconds")),
            )
        return self.hole(cursor.lastrowid)

    def hole(self, aufgaben_id: int) -> Aufgabe | None:
        zeile = self._verbindung.execute("SELECT * FROM aufgaben WHERE id = ?", (aufgaben_id,)).fetchone()
        return _zu_aufgabe(zeile) if zeile else None

    def aendern(self, aufgaben_id: int, **felder) -> None:
        """Ändert einzelne Felder, z. B. aendern(3, prioritaet="hoch")."""
        unbekannt = set(felder) - _AENDERBAR
        if unbekannt:
            raise ValueError(f"Diese Felder kann man nicht ändern: {unbekannt}")
        zuweisungen = ", ".join(f"{name} = ?" for name in felder)
        werte = [_zu_text(wert) for wert in felder.values()]
        with self._verbindung:
            self._verbindung.execute(f"UPDATE aufgaben SET {zuweisungen} WHERE id = ?", (*werte, aufgaben_id))

    def erledigen(self, aufgaben_id: int) -> None:
        with self._verbindung:
            self._verbindung.execute(
                "UPDATE aufgaben SET erledigt = 1, erledigt_am = ? WHERE id = ?",
                (datetime.now().isoformat(timespec="seconds"), aufgaben_id),
            )

    def loeschen(self, aufgaben_id: int) -> None:
        with self._verbindung:
            self._verbindung.execute("DELETE FROM aufgaben WHERE id = ?", (aufgaben_id,))

    def offene(self) -> list[Aufgabe]:
        """Alle Aufgaben, die noch nicht erledigt sind."""
        zeilen = self._verbindung.execute("SELECT * FROM aufgaben WHERE erledigt = 0 ORDER BY id").fetchall()
        return [_zu_aufgabe(zeile) for zeile in zeilen]

    def vergangene_termine_abschliessen(self, heute: date) -> int:
        """Termine und Klausuren von gestern oder früher sind vorbei, nicht überfällig.

        Sie werden deshalb automatisch abgehakt. To-dos, Hausaufgaben und Abgaben
        bleiben offen, bis du sie selbst erledigst.
        """
        with self._verbindung:
            cursor = self._verbindung.execute(
                "UPDATE aufgaben SET erledigt = 1, erledigt_am = ?"
                " WHERE erledigt = 0 AND art IN ('termin', 'klausur') AND faellig_am < ?",
                (datetime.now().isoformat(timespec="seconds"), heute.isoformat()),
            )
        return cursor.rowcount

    # ----- Merkzettel -----------------------------------------------------

    def einstellung(self, name: str) -> str | None:
        zeile = self._verbindung.execute("SELECT wert FROM einstellungen WHERE name = ?", (name,)).fetchone()
        return zeile["wert"] if zeile else None

    def einstellung_setzen(self, name: str, wert: str) -> None:
        with self._verbindung:
            self._verbindung.execute(
                "INSERT INTO einstellungen (name, wert) VALUES (?, ?)"
                " ON CONFLICT(name) DO UPDATE SET wert = excluded.wert",
                (name, wert),
            )
