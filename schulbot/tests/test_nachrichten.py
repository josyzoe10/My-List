"""Tests für Datenbank und Nachrichtentexte."""

from datetime import date, time

import pytest

from bot import nachrichten
from bot.datenbank import Datenbank

HEUTE = date(2026, 11, 16)  # ein Montag


@pytest.fixture
def db(tmp_path):
    datenbank = Datenbank(str(tmp_path / "test.db"))
    yield datenbank
    datenbank.schliessen()


def test_speichern_aendern_erledigen_loeschen(db):
    a = db.hinzufuegen("Bio-Referat", "abgabe", "Bio", date(2026, 11, 20), None, "hoch")
    assert db.hole(a.id).faellig_am == date(2026, 11, 20)

    db.aendern(a.id, prioritaet="niedrig", uhrzeit=time(9, 30))
    assert (db.hole(a.id).prioritaet, db.hole(a.id).uhrzeit) == ("niedrig", time(9, 30))

    db.erledigen(a.id)
    assert db.offene() == []

    db.loeschen(a.id)
    assert db.hole(a.id) is None


def test_daten_bleiben_nach_neustart_erhalten(tmp_path):
    pfad = str(tmp_path / "test.db")
    erste = Datenbank(pfad)
    erste.hinzufuegen("Zimmer aufräumen", "todo", None, None, None, "niedrig")
    erste.einstellung_setzen("letzte_morgennachricht", "2026-11-16")
    erste.schliessen()

    zweite = Datenbank(pfad)
    assert [a.titel for a in zweite.offene()] == ["Zimmer aufräumen"]
    assert zweite.einstellung("letzte_morgennachricht") == "2026-11-16"


def test_vergangene_termine_werden_abgehakt_aufgaben_nicht(db):
    db.hinzufuegen("Zahnarzt", "termin", None, date(2026, 11, 13), time(15, 0), "mittel")
    db.hinzufuegen("Mathe-Klausur", "klausur", "Mathe", date(2026, 11, 12), None, "hoch")
    db.hinzufuegen("Mathe S. 45", "hausaufgabe", "Mathe", date(2026, 11, 13), None, "mittel")
    db.hinzufuegen("Kino", "termin", None, HEUTE, None, "mittel")

    assert db.vergangene_termine_abschliessen(HEUTE) == 2
    assert [a.titel for a in db.offene()] == ["Mathe S. 45", "Kino"]


def test_unbekanntes_feld_wird_abgelehnt(db):
    a = db.hinzufuegen("Test", "todo", None, None, None, "mittel")
    with pytest.raises(ValueError):
        db.aendern(a.id, erledigt=1)


def test_morgennachricht(db):
    db.hinzufuegen("Mathe S. 45 Nr. 3", "hausaufgabe", "Mathe", date(2026, 11, 13), None, "mittel")  # überfällig
    db.hinzufuegen("Vokabeln lernen", "todo", None, HEUTE, None, "niedrig")
    db.hinzufuegen("Bio-Referat", "abgabe", "Bio", HEUTE, None, "hoch")
    db.hinzufuegen("Geschenk kaufen", "todo", None, HEUTE, None, "mittel")
    db.hinzufuegen("Zahnarzt", "termin", None, HEUTE, time(15, 0), "mittel")
    db.hinzufuegen("Friseur", "termin", None, HEUTE, time(9, 30), "mittel")
    db.hinzufuegen("Zimmer aufräumen", "todo", None, None, None, "niedrig")
    db.hinzufuegen("Mathe-Klausur", "klausur", "Mathe", date(2026, 11, 18), None, "hoch")   # in 2 Tagen
    db.hinzufuegen("Weit weg", "todo", None, date(2026, 12, 20), None, "mittel")            # nicht im Ausblick

    text = nachrichten.morgennachricht(db.offene(), HEUTE, ausblick_tage=3)
    zeilen = text.split("\n")

    assert zeilen[0] == "☀️ <b>Guten Morgen!</b> Heute ist Montag, 16.11."
    # Überfälliges steht ganz oben und ist deutlich markiert
    assert zeilen[2] == "⚠️ <b>ÜBERFÄLLIG</b>"
    assert zeilen[3] == "🟡 Mathe S. 45 Nr. 3 · Hausaufgabe (seit Fr, 13.11.)"
    # Termine nach Uhrzeit
    assert zeilen.index("🕒 09:30 Friseur") < zeilen.index("🕒 15:00 Zahnarzt")
    # Aufgaben nach Priorität: hoch, mittel, niedrig
    assert zeilen.index("🔴 Bio-Referat · Abgabe") < zeilen.index("🟡 Geschenk kaufen") < zeilen.index("🟢 Vokabeln lernen")
    # Ausblick auf die nächsten Tage
    assert "Mi, 18.11.: ✍️ Mathe-Klausur" in zeilen
    assert "Weit weg" not in text
    assert "🟢 Zimmer aufräumen" in zeilen


def test_leerer_tag(db):
    text = nachrichten.morgennachricht(db.offene(), HEUTE, ausblick_tage=3)
    assert "Für heute ist nichts eingetragen" in text
    assert "ÜBERFÄLLIG" not in text


def test_sonderzeichen_im_titel_machen_nichts_kaputt(db):
    a = db.hinzufuegen("Mathe <3 & mehr", "todo", None, HEUTE, None, "mittel")
    assert "Mathe &lt;3 &amp; mehr" in nachrichten.zeile(a)
    assert "Mathe &lt;3 &amp; mehr" in nachrichten.bestaetigung(a, HEUTE)


def test_bestaetigung(db):
    a = db.hinzufuegen("Zahnarzt", "termin", None, date(2026, 11, 17), time(15, 0), "mittel")
    assert nachrichten.bestaetigung(a, HEUTE) == (
        "✅ Gespeichert: <b>Zahnarzt</b>\n📅 Termin · morgen (Di, 17.11.) um 15:00 · Priorität mittel"
    )
    b = db.hinzufuegen("Abgabe", "abgabe", "Deutsch", date(2027, 1, 12), None, "hoch")
    assert "Di, 12.1.2027" in nachrichten.bestaetigung(b, HEUTE)   # anderes Jahr wird dazugeschrieben


def test_wochenliste_und_alle(db):
    db.hinzufuegen("Kino", "termin", None, date(2026, 11, 17), time(20, 0), "mittel")
    db.hinzufuegen("Bio-Referat", "abgabe", "Bio", date(2026, 11, 20), None, "hoch")
    db.hinzufuegen("In zwei Wochen", "todo", None, date(2026, 11, 30), None, "mittel")

    woche = nachrichten.wochen_liste(db.offene(), HEUTE)
    assert "<b>Morgen</b>\n🕒 20:00 Kino" in woche
    assert "<b>Freitag, 20.11.</b>\n🔴 Bio-Referat · Abgabe" in woche
    assert "In zwei Wochen" not in woche

    alles = nachrichten.alle_liste(db.offene(), HEUTE)
    assert "In zwei Wochen" in alles and "(3)" in alles
