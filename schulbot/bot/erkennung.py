"""Erkennt in einem normalen Satz Datum, Uhrzeit, Fach, Art und Priorität.

Beispiel: "Bio-Referat bis Freitag"
  -> Titel "Bio-Referat", Art Abgabe, Fach Bio, Datum nächster Freitag, Priorität hoch

Das sind feste Regeln, keine KI. Die Regeln kennen nur die Formulierungen, die
hier stehen. Deshalb bestätigt der Bot immer, wie er etwas einsortiert hat,
und du kannst es per Knopf korrigieren.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

ARTEN = ("todo", "hausaufgabe", "termin", "klausur", "abgabe")
PRIORITAETEN = ("hoch", "mittel", "niedrig")


@dataclass
class Erkannt:
    """Das Ergebnis: so hat der Bot einen Satz verstanden."""

    titel: str
    art: str = "todo"
    fach: str | None = None
    datum: date | None = None
    uhrzeit: time | None = None
    prioritaet: str = "mittel"


# ---------------------------------------------------------------------------
# Wörterlisten
# ---------------------------------------------------------------------------

_WOCHENTAGE = {
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
    "freitag": 4, "samstag": 5, "sonnabend": 5, "sonntag": 6,
}
_WOCHENTAGE_KURZ = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}
_MONATE = {
    "januar": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3,
    "mär": 3, "mrz": 3, "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6,
    "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9,
    "sep": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11,
    "dezember": 12, "dez": 12,
}
_ZAHLWOERTER = {
    "einem": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5,
    "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
}

# Wörter, die auf eine bestimmte Art hinweisen
_KLAUSUR_ENDUNGEN = ("klausur", "klausuren", "prüfung", "pruefung", "klassenarbeit", "test", "tests", "lzk")
_KEIN_TEST = {"attest", "protest"}
_ABGABE_ANFAENGE = ("abgabe", "abgeben", "abzugeben", "einreichen", "hochladen")
_ABGABE_ENDUNGEN = (
    "abgabe", "referat", "präsentation", "praesentation", "vortrag", "facharbeit",
    "hausarbeit", "seminararbeit", "aufsatz", "essay", "protokoll", "portfolio",
)
_TERMIN_WOERTER = {
    "termin", "friseur", "training", "treffen", "geburtstag", "fahrstunde",
    "probe", "konzert", "kino", "party", "nachhilfe", "elternabend",
    "sprechstunde", "vorstellungsgespräch",
}
_TERMIN_ENDUNGEN = ("arzt", "ärztin", "termin")
_HAUSAUFGABE_WOERTER = {"ha", "hausaufgabe", "hausaufgaben", "hausi", "arbeitsblatt", "vokabeln", "vokabel"}
# "Mathe lernen für die Klausur" ist keine Klausur, sondern ein To-do.
_VORBEREITEN = {"lernen", "üben", "ueben", "wiederholen", "vorbereiten", "anfangen"}

_WICHTIG = {"wichtig", "dringend", "unbedingt", "asap"}
_UNWICHTIG = {"unwichtig", "irgendwann", "optional", "vielleicht"}

# Ein Fach wird auch in zusammengesetzten Wörtern erkannt ("Matheklausur"),
# aber nur mit diesen Endungen. Sonst würde "Kunststoff" zum Fach Kunst.
_FACH_ENDUNGEN = {
    "klausur", "klausuren", "test", "arbeit", "referat", "ha", "hausaufgabe",
    "hausaufgaben", "buch", "heft", "mappe", "lk", "gk", "kurs", "unterricht",
    "stunde", "lehrer", "lehrerin", "prüfung", "pruefung", "vortrag",
    "präsentation", "protokoll", "aufgabe", "aufgaben", "vokabeln", "abi",
    "profil", "nachhilfe", "lzk",
}

# ---------------------------------------------------------------------------
# Muster (reguläre Ausdrücke)
# ---------------------------------------------------------------------------

_WT = "|".join(_WOCHENTAGE)
_WT_KURZ = "|".join(_WOCHENTAGE_KURZ)
_MON = "|".join(sorted(_MONATE, key=len, reverse=True))

# Wörtchen vor einem Datum, die nicht in den Titel gehören ("bis Freitag")
_VOR = (
    r"(?P<vor>\b(?:bis\s+zum|bis\s+sp(?:ä|ae)testens|bis|am|zum|f(?:ü|ue)r\s+den|"
    r"f(?:ü|ue)r|den|vom|an)\s+)?"
)
# "am Donnerstag, den 3.12."
_WT_VOR = rf"(?P<wt>\b(?:{_WT}|{_WT_KURZ})\.?,?\s+(?:de[nm]\s+)?)?"
# "morgen früh", "Freitagabend"
_TAGESZEIT = r"(?:\s*-?\s*(?:fr(?:ü|ue)h|morgen|vormittag|mittag|nachmittag|abend|nacht))?"
_NAECHSTE = r"(?:n(?:ä|ae)chste|kommende|diese)[nrs]?"

_I = re.IGNORECASE

_DATUM_ZAHL = re.compile(
    _VOR + _WT_VOR + r"(?<![\d.])(?P<tag>\d{1,2})\.\s?(?P<monat>\d{1,2})"
    r"(?:\.(?P<jahr>\d{4}|\d{2})(?!\d)|(?P<punkt>\.))?(?!\d|\.\d)", _I
)
_DATUM_MONAT = re.compile(
    _VOR + _WT_VOR
    + rf"(?<![\d.])(?P<tag>\d{{1,2}})\.?\s*(?P<monat>{_MON})\b\.?(?:\s+(?P<jahr>\d{{4}})\b)?", _I
)
_IN_N = re.compile(
    r"\bin\s+(\d{1,3}|" + "|".join(_ZAHLWOERTER) + r")\s+(tag|woche)(?:e|en|n)?\b", _I
)
_UEBERMORGEN = re.compile(_VOR + r"\b(?:ü|ue)bermorgen" + _TAGESZEIT + r"\b", _I)
_HEUTE = re.compile(_VOR + r"\bheute" + _TAGESZEIT + r"\b", _I)
_NAECHSTE_WOCHE_WT = re.compile(
    _VOR + r"\b(?:n(?:ä|ae)chste|kommende)[nr]?\s+woche\s+(?:am\s+)?"
    + rf"(?P<tagname>{_WT})s?{_TAGESZEIT}\b", _I
)
_WOCHENTAG = re.compile(_VOR + rf"(?:\b{_NAECHSTE}\s+)?\b(?P<tagname>{_WT})s?{_TAGESZEIT}\b", _I)
_WOCHENTAG_KURZ = re.compile(rf"\b(?:bis\s+zum|bis|am|zum)\s+(?P<tagname>{_WT_KURZ})\b\.?", _I)
_MORGEN = re.compile(_VOR + r"\bmorgen" + _TAGESZEIT + r"\b", _I)
_NAECHSTE_WOCHE = re.compile(_VOR + r"\b(?:n(?:ä|ae)chste|kommende)[nr]?\s+woche\b", _I)

# Nach so einem Wort ist "3.2." meist kein Datum, sondern eine Aufgabennummer.
_UEBUNGSWORT = re.compile(
    r"\b(?:nr|aufgaben?|aufg|s|seiten?|kapitel|kap|(?:ü|ue)bung(?:en)?|abschnitt|ab|lektion|unit|teil)\b\.?", _I
)

_ZEIT_SPANNE = re.compile(
    r"\b(?:von\s+|um\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(?:uhr\s*)?(?:-|–|bis)\s*"
    r"\d{1,2}(?:[:.]\d{2})?\s*uhr\b", _I
)
_ZEIT_HHMM_UHR = re.compile(r"\b(?:um\s+|ab\s+)?(\d{1,2})[:.](\d{2})\s*uhr\b", _I)
_ZEIT_HH_UHR = re.compile(r"\b(?:um\s+|ab\s+)?(\d{1,2})\s*uhr\b", _I)
_ZEIT_HHMM = re.compile(r"(?:\bum\s+|\bab\s+)?(?<![\d.:])(\d{1,2}):(\d{2})(?![\d:])", _I)
_ZEIT_UM = re.compile(r"\bum\s+(\d{1,2})\b(?![.:]\d)", _I)
_ZEIT_MUSTER = (_ZEIT_SPANNE, _ZEIT_HHMM_UHR, _ZEIT_HH_UHR, _ZEIT_HHMM, _ZEIT_UM)

_FUELLWOERTER = re.compile(
    r"^(?:bitte\s+|(?:todo|to-do|aufgabe|notiz)\s*:\s*|(?:wichtig|dringend)\s*[:!,]+\s*|"
    r"(?:merk|notier|speicher)e?\s+(?:dir\s+)?(?:bitte\s+)?:?\s*|"
    r"erinnere?\s+mich\s+(?:bitte\s+)?(?:daran\s*,?\s*|an\s+)?|"
    r"ich\s+(?:muss|soll|will|m(?:ö|oe)chte)\s+(?:(?:noch|bitte|unbedingt)\s+)*)",
    _I,
)
_REST_AM_ENDE = re.compile(r"\s+(?:bis|am|um|ab|f(?:ü|ue)r|zum|den|vom|an|von)$", _I)
# "..., wichtig!!" am Ende gehört zur Priorität, nicht in den Titel.
_WICHTIG_AM_ENDE = re.compile(r"[\s,;:\-–]*(?:(?:sehr|ganz)\s+)?(?:wichtig|dringend)?\s*!*$", _I)


# ---------------------------------------------------------------------------
# Uhrzeit
# ---------------------------------------------------------------------------

def _finde_uhrzeit(text: str) -> tuple[time | None, str]:
    """Sucht eine Uhrzeit. Gibt die Uhrzeit und den Text ohne sie zurück."""
    for muster in _ZEIT_MUSTER:
        for treffer in muster.finditer(text):
            stunde = int(treffer.group(1))
            minute = int(treffer.group(2)) if treffer.lastindex and treffer.lastindex >= 2 and treffer.group(2) else 0
            if stunde <= 23 and minute <= 59:
                rest = text[: treffer.start()] + " " + text[treffer.end():]
                return time(stunde, minute), rest
    return None, text


# ---------------------------------------------------------------------------
# Datum
# ---------------------------------------------------------------------------

def _naechster_wochentag(heute: date, wochentag: int) -> date:
    """Der nächste Tag mit diesem Wochentag, frühestens morgen."""
    tage = (wochentag - heute.weekday()) % 7
    return heute + timedelta(days=tage or 7)


def _datum_bauen(tag: int, monat: int, jahr: int | None, heute: date) -> date | None:
    """Baut ein Datum. Ohne Jahr wird das nächste passende Datum genommen."""
    try:
        if jahr is not None:
            return date(jahr + 2000 if jahr < 100 else jahr, monat, tag)
        datum = date(heute.year, monat, tag)
        return datum if datum >= heute else date(heute.year + 1, monat, tag)
    except ValueError:  # so ein Datum gibt es nicht, z. B. 31.2.
        return None


def _finde_datum(text: str, heute: date) -> tuple[date | None, str]:
    """Sucht ein Datum. Gibt das Datum und den Text ohne die Datumsangabe zurück."""

    def ohne(treffer: re.Match) -> str:
        return text[: treffer.start()] + " " + text[treffer.end():]

    # 1) Zahlen: "3.12.", "03.12.2026", "am 3.12"
    for treffer in _DATUM_ZAHL.finditer(text):
        # Sicher ein Datum, wenn "bis", ein Wochentag oder ein Jahr dabeisteht.
        sicher = bool(treffer.group("vor") or treffer.group("wt") or treffer.group("jahr"))
        if not sicher:
            if _UEBUNGSWORT.search(text[: treffer.start("tag")]):
                continue  # z. B. "Nr. 3.2."
            if not treffer.group("punkt") and text[treffer.end():].strip():
                continue  # "3.12" ohne Punkt zählt nur am Satzende
        jahr = treffer.group("jahr")
        datum = _datum_bauen(int(treffer.group("tag")), int(treffer.group("monat")), int(jahr) if jahr else None, heute)
        if datum:
            return datum, ohne(treffer)

    # 2) Monatsname: "3. Dezember"
    for treffer in _DATUM_MONAT.finditer(text):
        jahr = treffer.group("jahr")
        monat = _MONATE[treffer.group("monat").lower()]
        datum = _datum_bauen(int(treffer.group("tag")), monat, int(jahr) if jahr else None, heute)
        if datum:
            return datum, ohne(treffer)

    # 3) "in 3 Tagen", "in zwei Wochen"
    treffer = _IN_N.search(text)
    if treffer:
        anzahl = treffer.group(1).lower()
        zahl = int(anzahl) if anzahl.isdigit() else _ZAHLWOERTER[anzahl]
        tage = zahl * 7 if treffer.group(2).lower() == "woche" else zahl
        return heute + timedelta(days=tage), ohne(treffer)

    # 4) "übermorgen", "heute"
    treffer = _UEBERMORGEN.search(text)
    if treffer:
        return heute + timedelta(days=2), ohne(treffer)
    treffer = _HEUTE.search(text)
    if treffer:
        return heute, ohne(treffer)

    # 5) Wochentage: "nächste Woche Freitag", "bis Freitag", "am Fr"
    treffer = _NAECHSTE_WOCHE_WT.search(text)
    if treffer:
        montag = heute + timedelta(days=7 - heute.weekday())
        return montag + timedelta(days=_WOCHENTAGE[treffer.group("tagname").lower()]), ohne(treffer)
    treffer = _WOCHENTAG.search(text)
    if treffer:
        return _naechster_wochentag(heute, _WOCHENTAGE[treffer.group("tagname").lower()]), ohne(treffer)
    treffer = _WOCHENTAG_KURZ.search(text)
    if treffer:
        return _naechster_wochentag(heute, _WOCHENTAGE_KURZ[treffer.group("tagname").lower()]), ohne(treffer)

    # 6) "morgen" (erst hier, damit "Freitag morgen" der Freitag bleibt)
    treffer = _MORGEN.search(text)
    if treffer:
        return heute + timedelta(days=1), ohne(treffer)

    # 7) "nächste Woche"
    treffer = _NAECHSTE_WOCHE.search(text)
    if treffer:
        return heute + timedelta(days=7), ohne(treffer)

    return None, text


def finde_datum_und_zeit(text: str, heute: date) -> tuple[date | None, time | None]:
    """Liest nur Datum und Uhrzeit aus einem Text, z. B. beim Verschieben."""
    uhrzeit, rest = _finde_uhrzeit(text)
    datum, _ = _finde_datum(rest, heute)
    return datum, uhrzeit


# ---------------------------------------------------------------------------
# Fach, Art, Priorität
# ---------------------------------------------------------------------------

def _woerter(text: str) -> list[str]:
    """Zerlegt den Text in klein geschriebene Wörter. "Bio-Referat" -> bio, referat."""
    return re.findall(r"[a-zäöüß]+", text.lower())


def finde_fach(text: str, faecher: dict[str, list[str]]) -> str | None:
    """Sucht ein Fach aus der Fächerliste im Text."""
    for wort in _woerter(text):
        for fach, schreibweisen in faecher.items():
            for schreibweise in schreibweisen:
                if wort == schreibweise:
                    return fach
                if wort.startswith(schreibweise) and wort[len(schreibweise):] in _FACH_ENDUNGEN:
                    return fach
    return None


def _finde_art(text: str, fach: str | None, hat_uhrzeit: bool, faecher: dict[str, list[str]]) -> str:
    woerter = _woerter(text)
    wortmenge = set(woerter)
    nur_vorbereiten = bool(wortmenge & _VORBEREITEN)

    ist_abgabe = any(w.startswith(_ABGABE_ANFAENGE) or w.endswith(_ABGABE_ENDUNGEN) for w in woerter)
    if ist_abgabe and not nur_vorbereiten:
        return "abgabe"

    ist_klausur = any(w.endswith(_KLAUSUR_ENDUNGEN) and w not in _KEIN_TEST for w in woerter)
    if not ist_klausur and fach:
        # "Mathearbeit" oder "Mathe-Arbeit" ist eine Klassenarbeit
        for schreibweise in faecher.get(fach, []):
            if re.search(rf"\b{re.escape(schreibweise)}[- ]?arbeit\b", text.lower()):
                ist_klausur = True
    if ist_klausur and not nur_vorbereiten:
        return "klausur"

    hat_seitenangabe = bool(re.search(r"\b(?:s\.|seiten?|nr\.?|aufg\.?|aufgaben?|ab)\s*\d", text.lower()))
    if wortmenge & _HAUSAUFGABE_WOERTER or (fach and hat_seitenangabe):
        return "hausaufgabe"

    if hat_uhrzeit or wortmenge & _TERMIN_WOERTER or any(w.endswith(_TERMIN_ENDUNGEN) for w in woerter):
        return "termin"

    if fach and not ist_klausur and not ist_abgabe:
        return "hausaufgabe"
    return "todo"


def schaetze_prioritaet(text: str, art: str, hat_datum: bool) -> str:
    wortmenge = set(_woerter(text))
    if wortmenge & _UNWICHTIG:
        return "niedrig"
    if wortmenge & _WICHTIG or "!!" in text:
        return "hoch"
    if art in ("klausur", "abgabe"):
        return "hoch"
    if art == "todo" and not hat_datum:
        return "niedrig"
    return "mittel"


# ---------------------------------------------------------------------------
# Alles zusammen
# ---------------------------------------------------------------------------

def _titel_aufraeumen(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = text.strip(" ,;:-–")
    text = _FUELLWOERTER.sub("", text)
    text = _WICHTIG_AM_ENDE.sub("", text)
    text = _REST_AM_ENDE.sub("", text)
    text = text.strip(" ,;:-–")
    return text[:1].upper() + text[1:]


def erkenne(text: str, heute: date, faecher: dict[str, list[str]]) -> Erkannt:
    """Versteht einen Satz wie "morgen 15 Uhr Zahnarzt"."""
    uhrzeit, rest = _finde_uhrzeit(text)
    datum, rest = _finde_datum(rest, heute)
    fach = finde_fach(text, faecher)
    art = _finde_art(text, fach, uhrzeit is not None, faecher)
    titel = _titel_aufraeumen(rest) or _titel_aufraeumen(text) or text.strip()
    return Erkannt(
        titel=titel,
        art=art,
        fach=fach,
        datum=datum,
        uhrzeit=uhrzeit,
        prioritaet=schaetze_prioritaet(text, art, datum is not None),
    )
