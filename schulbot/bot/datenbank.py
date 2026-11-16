"""Speichert deine Aufgaben und deinen Stundenplan in einer SQLite-Datenbank.

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


@dataclass
class Stunde:
    """Eine Schulstunde im Stundenplan, z. B. Mittwoch, 3. Stunde, Mathe."""

    wochentag: int          # 0 = Montag, 4 = Freitag
    stunde: int
    fach: str
    raum: str | None = None
    lehrkraft: str | None = None
    email: str | None = None


@dataclass
class Lehrkraft:
    id: int
    name: str
    email: str | None
    faecher: list[str]


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
            self._verbindung.execute(
                "CREATE TABLE IF NOT EXISTS lehrkraefte ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, email TEXT)"
            )
            self._verbindung.execute(
                "CREATE TABLE IF NOT EXISTS stundenplan ("
                " wochentag INTEGER NOT NULL, stunde INTEGER NOT NULL, fach TEXT NOT NULL, raum TEXT,"
                " lehrkraft_id INTEGER REFERENCES lehrkraefte(id), PRIMARY KEY (wochentag, stunde))"
            )
            # Merkt sich, an welche Termine schon erinnert wurde, damit nichts doppelt kommt.
            self._verbindung.execute(
                "CREATE TABLE IF NOT EXISTS gesendete_erinnerungen ("
                " aufgaben_id INTEGER NOT NULL, art TEXT NOT NULL, PRIMARY KEY (aufgaben_id, art))"
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
            if "faellig_am" in felder or "uhrzeit" in felder:
                # Neuer Zeitpunkt: Der Bot soll wieder daran erinnern dürfen.
                self._verbindung.execute("DELETE FROM gesendete_erinnerungen WHERE aufgaben_id = ?", (aufgaben_id,))

    def erledigen(self, aufgaben_id: int) -> None:
        with self._verbindung:
            self._verbindung.execute(
                "UPDATE aufgaben SET erledigt = 1, erledigt_am = ? WHERE id = ?",
                (datetime.now().isoformat(timespec="seconds"), aufgaben_id),
            )

    def loeschen(self, aufgaben_id: int) -> None:
        with self._verbindung:
            self._verbindung.execute("DELETE FROM aufgaben WHERE id = ?", (aufgaben_id,))
            self._verbindung.execute("DELETE FROM gesendete_erinnerungen WHERE aufgaben_id = ?", (aufgaben_id,))

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

    # ----- Erinnerungen ---------------------------------------------------

    def erinnerung_gesendet(self, aufgaben_id: int, art: str) -> bool:
        zeile = self._verbindung.execute(
            "SELECT 1 FROM gesendete_erinnerungen WHERE aufgaben_id = ? AND art = ?", (aufgaben_id, art)
        ).fetchone()
        return zeile is not None

    def erinnerung_merken(self, aufgaben_id: int, art: str) -> None:
        with self._verbindung:
            self._verbindung.execute(
                "INSERT OR IGNORE INTO gesendete_erinnerungen (aufgaben_id, art) VALUES (?, ?)", (aufgaben_id, art)
            )

    # ----- Stundenplan und Lehrkräfte -------------------------------------

    def stundenplan(self) -> list[Stunde]:
        """Alle Stunden der Woche, sortiert nach Tag und Stunde."""
        zeilen = self._verbindung.execute(
            "SELECT s.wochentag, s.stunde, s.fach, s.raum, l.name AS lehrkraft, l.email"
            " FROM stundenplan s LEFT JOIN lehrkraefte l ON l.id = s.lehrkraft_id"
            " ORDER BY s.wochentag, s.stunde"
        ).fetchall()
        return [Stunde(z["wochentag"], z["stunde"], z["fach"], z["raum"], z["lehrkraft"], z["email"]) for z in zeilen]

    def lehrkraefte(self) -> list[Lehrkraft]:
        """Alle Lehrkräfte mit den Fächern, die sie laut Stundenplan unterrichten."""
        ergebnis = []
        for z in self._verbindung.execute("SELECT id, name, email FROM lehrkraefte ORDER BY name").fetchall():
            faecher = self._verbindung.execute(
                "SELECT DISTINCT fach FROM stundenplan WHERE lehrkraft_id = ? ORDER BY fach", (z["id"],)
            ).fetchall()
            ergebnis.append(Lehrkraft(z["id"], z["name"], z["email"], [f["fach"] for f in faecher]))
        return ergebnis

    def lehrkraft_suchen(self, text: str) -> list[Lehrkraft]:
        """Findet Lehrkräfte, deren Name den Text enthält. "böcker" findet "Frau Böcker"."""
        gesucht = text.strip().casefold()
        alle = self.lehrkraefte()
        genau = [l for l in alle if l.name.casefold() == gesucht]
        return genau or [l for l in alle if gesucht and gesucht in l.name.casefold()]

    def lehrkraft_email_setzen(self, lehrkraft_id: int, email: str | None) -> None:
        with self._verbindung:
            self._verbindung.execute("UPDATE lehrkraefte SET email = ? WHERE id = ?", (email, lehrkraft_id))

    def _lehrkraft_id(self, name: str | None, email: str | None = None) -> int | None:
        """Sucht die Lehrkraft oder legt sie neu an. Muss in einer Transaktion laufen."""
        if not name or not name.strip():
            return None
        treffer = self.lehrkraft_suchen(name)
        if len(treffer) == 1:
            lehrkraft_id = treffer[0].id
        else:
            lehrkraft_id = self._verbindung.execute(
                "INSERT INTO lehrkraefte (name) VALUES (?)", (name.strip(),)
            ).lastrowid
        if email:
            self._verbindung.execute("UPDATE lehrkraefte SET email = ? WHERE id = ?", (email, lehrkraft_id))
        return lehrkraft_id

    def _lehrkraefte_aufraeumen(self) -> None:
        """Entfernt Lehrkräfte, die in keiner Stunde mehr vorkommen und keine E-Mail haben."""
        self._verbindung.execute(
            "DELETE FROM lehrkraefte WHERE email IS NULL"
            " AND id NOT IN (SELECT lehrkraft_id FROM stundenplan WHERE lehrkraft_id IS NOT NULL)"
        )

    def stunde_setzen(self, stunde: Stunde) -> None:
        """Trägt eine Stunde ein. Steht dort schon etwas, wird es ersetzt."""
        with self._verbindung:
            lehrkraft_id = self._lehrkraft_id(stunde.lehrkraft, stunde.email)
            self._verbindung.execute(
                "INSERT OR REPLACE INTO stundenplan (wochentag, stunde, fach, raum, lehrkraft_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (stunde.wochentag, stunde.stunde, stunde.fach, stunde.raum, lehrkraft_id),
            )
            self._lehrkraefte_aufraeumen()

    def stunde_loeschen(self, wochentag: int, stunde: int) -> bool:
        with self._verbindung:
            cursor = self._verbindung.execute(
                "DELETE FROM stundenplan WHERE wochentag = ? AND stunde = ?", (wochentag, stunde)
            )
            self._lehrkraefte_aufraeumen()
        return cursor.rowcount > 0

    def stundenplan_ersetzen(self, stunden: list[Stunde]) -> None:
        """Löscht den alten Stundenplan und trägt den neuen ein. E-Mail-Adressen bleiben erhalten."""
        with self._verbindung:
            self._verbindung.execute("DELETE FROM stundenplan")
            for stunde in stunden:
                lehrkraft_id = self._lehrkraft_id(stunde.lehrkraft, stunde.email)
                self._verbindung.execute(
                    "INSERT OR REPLACE INTO stundenplan (wochentag, stunde, fach, raum, lehrkraft_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (stunde.wochentag, stunde.stunde, stunde.fach, stunde.raum, lehrkraft_id),
                )
            self._lehrkraefte_aufraeumen()

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
