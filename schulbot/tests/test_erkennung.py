"""Tests für die Satz-Erkennung. "Heute" ist in allen Tests Montag, der 16.11.2026."""

from datetime import date, time

import pytest

import config
from bot.erkennung import erkenne, finde_datum_und_zeit

HEUTE = date(2026, 11, 16)  # ein Montag


def verstehe(satz: str):
    return erkenne(satz, HEUTE, config.FAECHER)


# Die vier Beispiele aus der Aufgabenstellung
def test_referat_bis_freitag():
    e = verstehe("Bio-Referat bis Freitag")
    assert (e.titel, e.art, e.fach, e.datum, e.prioritaet) == ("Bio-Referat", "abgabe", "Bio", date(2026, 11, 20), "hoch")


def test_zahnarzt_morgen_15_uhr():
    e = verstehe("morgen 15 Uhr Zahnarzt")
    assert (e.titel, e.art, e.datum, e.uhrzeit) == ("Zahnarzt", "termin", date(2026, 11, 17), time(15, 0))


def test_klausur_mit_datum():
    e = verstehe("Mathe-Klausur am 3.12.")
    assert (e.titel, e.art, e.fach, e.datum, e.prioritaet) == ("Mathe-Klausur", "klausur", "Mathe", date(2026, 12, 3), "hoch")


def test_hausaufgabe_ohne_datum():
    e = verstehe("Mathe S. 45 Nr. 3")
    assert (e.titel, e.art, e.fach, e.datum) == ("Mathe S. 45 Nr. 3", "hausaufgabe", "Mathe", None)


@pytest.mark.parametrize(
    "satz, datum",
    [
        ("Aufsatz heute", date(2026, 11, 16)),
        ("Aufsatz übermorgen", date(2026, 11, 18)),
        ("Aufsatz bis Mi", date(2026, 11, 18)),
        ("Aufsatz am Montag", date(2026, 11, 23)),           # heute ist Montag -> nächster Montag
        ("Aufsatz nächste Woche Freitag", date(2026, 11, 27)),
        ("Aufsatz in 2 Wochen", date(2026, 11, 30)),
        ("Aufsatz in drei Tagen", date(2026, 11, 19)),
        ("Aufsatz bis zum 24. November", date(2026, 11, 24)),
        ("Aufsatz am 12.1.", date(2027, 1, 12)),             # schon vorbei in diesem Jahr -> nächstes Jahr
        ("Aufsatz 3.12.2026", date(2026, 12, 3)),
        ("Aufsatz am Donnerstag, den 3.12.", date(2026, 12, 3)),
        ("Aufsatz 3.12", date(2026, 12, 3)),
        ("Freitag morgen Aufsatz", date(2026, 11, 20)),      # "morgen" heißt hier "am Morgen"
        ("Aufsatz nächste Woche", date(2026, 11, 23)),
        ("Aufsatz", None),
        ("Aufsatz 31.2.", None),                             # dieses Datum gibt es nicht
    ],
)
def test_datum(satz, datum):
    assert verstehe(satz).datum == datum


@pytest.mark.parametrize(
    "satz",
    ["Mathe Aufgabe 3.2.", "Physik Nr. 3.2 und 3.4.", "Buch S. 3.12. lesen", "AB 3.2 bearbeiten"],
)
def test_aufgabennummern_sind_kein_datum(satz):
    assert verstehe(satz).datum is None


@pytest.mark.parametrize(
    "satz, uhrzeit",
    [
        ("Zahnarzt 15 Uhr", time(15, 0)),
        ("Zahnarzt 15:30", time(15, 30)),
        ("Zahnarzt um 15.30 Uhr", time(15, 30)),
        ("Zahnarzt um 7", time(7, 0)),
        ("Training 18-19:30 Uhr", time(18, 0)),
        ("Zahnarzt", None),
        ("Buch S. 12-15 lesen", None),
    ],
)
def test_uhrzeit(satz, uhrzeit):
    assert verstehe(satz).uhrzeit == uhrzeit


def test_datum_und_uhrzeit_zusammen():
    e = verstehe("Zahnarzt am 3.12. um 15.30 Uhr")
    assert (e.titel, e.datum, e.uhrzeit) == ("Zahnarzt", date(2026, 12, 3), time(15, 30))


@pytest.mark.parametrize(
    "satz, art",
    [
        ("Zimmer aufräumen", "todo"),
        ("Vokabeltest Englisch am Freitag", "klausur"),
        ("Mathearbeit Montag", "klausur"),
        ("Attest abgeben bis übermorgen", "abgabe"),          # "Attest" ist kein Test
        ("Abgabe Seminararbeit 3.12.2026", "abgabe"),
        ("Chemie Protokoll bis Freitag", "abgabe"),
        ("Hausaufgabe Mathe S.45 Nr.3", "hausaufgabe"),
        ("Englisch Vokabeln Unit 3", "hausaufgabe"),
        ("heute Abend Kino mit Lena", "termin"),
        ("Nachhilfe Mathe morgen um 16 Uhr", "termin"),
        ("Mathe lernen für die Klausur am Donnerstag", "todo"),  # lernen ist ein To-do
        ("Kunststoff sortieren", "todo"),                        # kein Fach Kunst
    ],
)
def test_art(satz, art):
    assert verstehe(satz).art == art


@pytest.mark.parametrize(
    "satz, prioritaet",
    [
        ("Mathe-Klausur am 3.12.", "hoch"),
        ("Bio-Referat bis Freitag", "hoch"),
        ("Mathe S. 45 Nr. 3", "mittel"),
        ("Geschenk kaufen bis Freitag", "mittel"),
        ("Zimmer aufräumen", "niedrig"),
        ("Geschenk für Oma kaufen, wichtig!!", "hoch"),
        ("irgendwann Schrank ausmisten", "niedrig"),
    ],
)
def test_prioritaet(satz, prioritaet):
    assert verstehe(satz).prioritaet == prioritaet


@pytest.mark.parametrize(
    "satz, titel",
    [
        ("ich muss noch Mathe lernen", "Mathe lernen"),
        ("erinner mich an Müll rausbringen", "Müll rausbringen"),
        ("Geschenk für Oma kaufen, wichtig!!", "Geschenk für Oma kaufen"),
        ("Dringend: Formular unterschreiben", "Formular unterschreiben"),
        ("morgen", "Morgen"),                                    # nur ein Datum: der Satz bleibt der Titel
    ],
)
def test_titel(satz, titel):
    assert verstehe(satz).titel == titel


def test_nur_datum_und_zeit_lesen():
    assert finde_datum_und_zeit("Freitag", HEUTE) == (date(2026, 11, 20), None)
    assert finde_datum_und_zeit("morgen 15 Uhr", HEUTE) == (date(2026, 11, 17), time(15, 0))
    assert finde_datum_und_zeit("keine Ahnung", HEUTE) == (None, None)
