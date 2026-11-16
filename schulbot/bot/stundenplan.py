"""Rechnet mit dem Stundenplan: Stunden zusammenfassen, nächste Stunde finden,
Tabellen lesen und schreiben. Hier wird nichts gespeichert und nichts verschickt.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, timedelta

from bot.datenbank import Stunde

TAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
TAGE_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
KOPFZEILE = ["Tag", "Stunde", "Fach", "Raum", "Lehrkraft", "E-Mail"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Block:
    """Mehrere Stunden hintereinander im selben Fach, z. B. Mathe in der 3. und 4. Stunde."""

    wochentag: int
    von: int
    bis: int
    fach: str
    raum: str | None
    lehrkraft: str | None


# ---------------------------------------------------------------------------
# Eingaben lesen
# ---------------------------------------------------------------------------

def wochentag_lesen(text: str) -> int | None:
    """ "Mo", "mo.", "Montag" oder "mont" -> 0 """
    klein = text.strip().lower().rstrip(".,:")
    if klein == "sonnabend":
        return 5
    for nummer, (lang, kurz) in enumerate(zip(TAGE, TAGE_KURZ)):
        if klein == kurz.lower() or klein == lang.lower() or (len(klein) >= 3 and lang.lower().startswith(klein)):
            return nummer
    return None


def stunden_lesen(text: str) -> list[int] | None:
    """ "3" -> [3],  "3-4" oder "3.-4." -> [3, 4] """
    treffer = re.fullmatch(r"\s*(\d{1,2})\.?\s*(?:(?:-|–|bis)\s*(\d{1,2})\.?)?\s*", text)
    if not treffer:
        return None
    von = int(treffer.group(1))
    bis = int(treffer.group(2) or von)
    if not 0 <= von <= bis <= 20:
        return None
    return list(range(von, bis + 1))


def ist_email(text: str) -> bool:
    return bool(_EMAIL.match(text))


def fach_name(text: str, faecher: dict[str, list[str]]) -> str:
    """Macht aus "Mathematik" oder "mathe" den Namen aus der Fächerliste ("Mathe")."""
    klein = text.strip().casefold()
    for fach, schreibweisen in faecher.items():
        if klein == fach.casefold() or klein in schreibweisen:
            return fach
    return text.strip()


def alle_faecher(stunden: list[Stunde], faecher: dict[str, list[str]]) -> dict[str, list[str]]:
    """Die Fächerliste aus config.py, ergänzt um Fächer, die nur im Stundenplan stehen."""
    ergebnis = dict(faecher)
    for stunde in stunden:
        if stunde.fach not in ergebnis:
            ergebnis[stunde.fach] = [stunde.fach.lower()]
    return ergebnis


# ---------------------------------------------------------------------------
# Auskünfte
# ---------------------------------------------------------------------------

def bloecke(stunden: list[Stunde]) -> list[Block]:
    """Fasst aufeinanderfolgende Stunden im selben Fach zusammen."""
    ergebnis: list[Block] = []
    for s in sorted(stunden, key=lambda s: (s.wochentag, s.stunde)):
        letzter = ergebnis[-1] if ergebnis else None
        if (
            letzter
            and letzter.wochentag == s.wochentag
            and letzter.bis + 1 == s.stunde
            and (letzter.fach, letzter.raum, letzter.lehrkraft) == (s.fach, s.raum, s.lehrkraft)
        ):
            letzter.bis = s.stunde
        else:
            ergebnis.append(Block(s.wochentag, s.stunde, s.stunde, s.fach, s.raum, s.lehrkraft))
    return ergebnis


def zeitspanne(block: Block, stundenzeiten: dict[int, tuple[str, str]]) -> str:
    """ "9:50–11:20", oder "10.–11. Std.", wenn keine Uhrzeiten hinterlegt sind."""
    beginn = stundenzeiten.get(block.von)
    ende = stundenzeiten.get(block.bis)
    if beginn and ende:
        return f"{beginn[0]}–{ende[1]}"
    return f"{block.von}. Std." if block.von == block.bis else f"{block.von}.–{block.bis}. Std."


def ist_frei(tag: date, ferien: list[tuple[str, str]]) -> bool:
    """Liegt der Tag in den Ferien oder ist er ein freier Tag?"""
    return any(date.fromisoformat(von) <= tag <= date.fromisoformat(bis) for von, bis in ferien)


def stunden_am(stunden: list[Stunde], tag: date, ferien: list[tuple[str, str]]) -> list[Stunde]:
    """Die Stunden an einem bestimmten Datum. In den Ferien: keine."""
    if ist_frei(tag, ferien):
        return []
    return [s for s in stunden if s.wochentag == tag.weekday()]


def naechste_stunde(stunden: list[Stunde], fach: str, nach: date, ferien: list[tuple[str, str]]) -> date | None:
    """Das Datum der nächsten Stunde in diesem Fach, frühestens am Tag nach `nach`."""
    if not any(s.fach == fach for s in stunden):
        return None
    for abstand in range(1, 120):
        tag = nach + timedelta(days=abstand)
        if any(s.fach == fach for s in stunden_am(stunden, tag, ferien)):
            return tag
    return None


def lehrkraft_fuer(stunden: list[Stunde], fach: str) -> Stunde | None:
    """Die erste Stunde dieses Fachs, in der eine Lehrkraft eingetragen ist."""
    for stunde in stunden:
        if stunde.fach == fach and stunde.lehrkraft:
            return stunde
    return None


# ---------------------------------------------------------------------------
# Tabelle (CSV) lesen und schreiben
# ---------------------------------------------------------------------------

def sieht_aus_wie_tabelle(text: str) -> bool:
    """Beginnt der Text mit der Kopfzeile "Tag;Stunde;..."?"""
    zeilen = text.strip().splitlines()
    return bool(zeilen) and bool(re.match(r"\s*(?:wochen)?tag\s*[;,\t]\s*stunde", zeilen[0], re.IGNORECASE))


def tabelle_lesen(text: str, faecher: dict[str, list[str]]) -> tuple[list[Stunde], list[str]]:
    """Liest einen Stundenplan als Tabelle.

    Jede Zeile: Tag; Stunde; Fach; Raum; Lehrkraft; E-Mail  (die letzten drei dürfen fehlen)
    Beispiel:   Mi; 3-4; Mathe; 112; Frau Beispiel; beispiel@schule.de

    Gibt die gelesenen Stunden und eine Liste mit Fehlermeldungen zurück.
    """
    text = text.lstrip("﻿")
    zeilen = [z for z in text.splitlines() if z.strip()]
    if not zeilen:
        return [], ["Die Tabelle ist leer."]
    trenner = max(";", ",", "\t", key=zeilen[0].count)

    eintraege: dict[tuple[int, int], Stunde] = {}
    fehler: list[str] = []
    for nummer, zellen in enumerate(csv.reader(io.StringIO(text), delimiter=trenner), start=1):
        zellen = [zelle.strip() for zelle in zellen]
        if not any(zellen) or zellen[0].lower() in ("tag", "wochentag"):
            continue
        zellen += [""] * (6 - len(zellen))
        tag_text, stunden_text, fach, raum, lehrkraft, email = zellen[:6]

        tag = wochentag_lesen(tag_text)
        nummern = stunden_lesen(stunden_text)
        if tag is None:
            fehler.append(f"Zeile {nummer}: Den Tag „{tag_text}“ kenne ich nicht (z. B. Mo oder Montag).")
        elif nummern is None:
            fehler.append(f"Zeile {nummer}: Die Stunde „{stunden_text}“ verstehe ich nicht (z. B. 3 oder 3-4).")
        elif not fach:
            fehler.append(f"Zeile {nummer}: Das Fach fehlt.")
        elif email and not ist_email(email):
            fehler.append(f"Zeile {nummer}: „{email}“ ist keine E-Mail-Adresse.")
        else:
            for n in nummern:
                eintraege[(tag, n)] = Stunde(tag, n, fach_name(fach, faecher), raum or None, lehrkraft or None, email or None)

    return [eintraege[schluessel] for schluessel in sorted(eintraege)], fehler


def tabelle_schreiben(stunden: list[Stunde]) -> str:
    """Schreibt den Stundenplan als Tabelle, eine Zeile pro Block."""
    emails = {s.lehrkraft: s.email for s in stunden if s.lehrkraft and s.email}
    ausgabe = io.StringIO()
    schreiber = csv.writer(ausgabe, delimiter=";", lineterminator="\n")
    schreiber.writerow(KOPFZEILE)
    for block in bloecke(stunden):
        stunde = str(block.von) if block.von == block.bis else f"{block.von}-{block.bis}"
        schreiber.writerow([
            TAGE_KURZ[block.wochentag], stunde, block.fach, block.raum or "",
            block.lehrkraft or "", emails.get(block.lehrkraft, ""),
        ])
    return ausgabe.getvalue()
