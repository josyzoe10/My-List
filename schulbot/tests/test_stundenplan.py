"""Tests für den Stundenplan: Tabelle lesen, Blöcke bilden, nächste Stunde finden.

Die Namen in den Tests sind erfunden.
"""

from datetime import date

import pytest

import config
from bot import stundenplan
from bot.datenbank import Datenbank, Stunde

TABELLE = """Tag;Stunde;Fach;Raum;Lehrkraft;E-Mail
Mo;1-2;Deutsch;A1;Frau Beispiel;
Di;3-4;Mathematik;112;Herr Muster;muster@schule.example
Di;5-6;Bio;B2;Frau Übel;
Do;8-9;Biologie;Lab;Frau Übel;
Fr;3-4;Mathe;112;Herr Muster;
"""
HEUTE = date(2026, 11, 16)  # ein Montag
KEINE_FERIEN: list[tuple[str, str]] = []


@pytest.fixture
def db(tmp_path):
    datenbank = Datenbank(str(tmp_path / "test.db"))
    yield datenbank
    datenbank.schliessen()


def lies(tabelle=TABELLE):
    stunden, fehler = stundenplan.tabelle_lesen(tabelle, config.FAECHER)
    assert fehler == []
    return stunden


@pytest.mark.parametrize(
    "text, nummer",
    [("Mo", 0), ("mo.", 0), ("Montag", 0), ("dienstag", 1), ("Don", 3), ("FR", 4), ("Sonnabend", 5), ("xy", None), ("", None)],
)
def test_wochentag_lesen(text, nummer):
    assert stundenplan.wochentag_lesen(text) == nummer


@pytest.mark.parametrize(
    "text, nummern",
    [("3", [3]), ("3-4", [3, 4]), ("3.-4.", [3, 4]), ("1 bis 4", [1, 2, 3, 4]), ("4-3", None), ("abc", None), ("", None)],
)
def test_stunden_lesen(text, nummern):
    assert stundenplan.stunden_lesen(text) == nummern


def test_tabelle_lesen():
    stunden = lies()
    assert len(stunden) == 10                                   # fünf Doppelstunden
    erste = stunden[0]
    assert (erste.wochentag, erste.stunde, erste.fach, erste.raum, erste.lehrkraft) == (0, 1, "Deutsch", "A1", "Frau Beispiel")
    # "Mathematik" und "Biologie" werden zu den Namen aus der Fächerliste
    assert {s.fach for s in stunden} == {"Deutsch", "Mathe", "Bio"}
    assert stunden[2].email == "muster@schule.example"


def test_tabelle_mit_kommas_und_ohne_kopfzeile():
    stunden = lies("Mi,3-4,Mathe,112\nMi,5,Sport\n")
    assert [(s.wochentag, s.stunde, s.fach, s.raum) for s in stunden] == [(2, 3, "Mathe", "112"), (2, 4, "Mathe", "112"), (2, 5, "Sport", None)]


def test_tabelle_mit_fehlern_nennt_die_zeilen():
    tabelle = "Tag;Stunde;Fach\nMo;1;Deutsch\nXx;1;Mathe\nDi;abc;Mathe\nMi;3;\nDo;1;Bio;;Frau Beispiel;keine-adresse\n"
    stunden, fehler = stundenplan.tabelle_lesen(tabelle, config.FAECHER)
    assert len(stunden) == 1
    assert [f.split(":")[0] for f in fehler] == ["Zeile 3", "Zeile 4", "Zeile 5", "Zeile 6"]


def test_tabelle_erkennen():
    assert stundenplan.sieht_aus_wie_tabelle(TABELLE)
    assert stundenplan.sieht_aus_wie_tabelle("tag, stunde, fach\nMo,1,Mathe")
    assert not stundenplan.sieht_aus_wie_tabelle("Tag der offenen Tür am Freitag")
    assert not stundenplan.sieht_aus_wie_tabelle("")


def test_bloecke_fassen_stunden_zusammen():
    stunden = lies("Mo;1-4;Mathe;112\nMo;5;Mathe;113\nMo;6;Bio;B2\nMo;8;Bio;B2\n")
    bloecke = stundenplan.bloecke(stunden)
    # 1-4 zusammen, 5 hat einen anderen Raum, 6 und 8 liegen nicht direkt hintereinander
    assert [(b.von, b.bis, b.fach) for b in bloecke] == [(1, 4, "Mathe"), (5, 5, "Mathe"), (6, 6, "Bio"), (8, 8, "Bio")]


def test_zeitspanne():
    [block] = stundenplan.bloecke(lies("Mo;1-4;Mathe"))
    assert stundenplan.zeitspanne(block, config.STUNDENZEITEN) == "8:00–11:20"
    assert stundenplan.zeitspanne(block, {}) == "1.–4. Std."


def test_naechste_stunde():
    stunden = lies()
    # Heute ist Montag. Mathe ist Di und Fr, Deutsch nur Mo.
    assert stundenplan.naechste_stunde(stunden, "Mathe", HEUTE, KEINE_FERIEN) == date(2026, 11, 17)
    assert stundenplan.naechste_stunde(stunden, "Mathe", date(2026, 11, 17), KEINE_FERIEN) == date(2026, 11, 20)
    assert stundenplan.naechste_stunde(stunden, "Deutsch", HEUTE, KEINE_FERIEN) == date(2026, 11, 23)   # nicht heute
    assert stundenplan.naechste_stunde(stunden, "Kunst", HEUTE, KEINE_FERIEN) is None


def test_naechste_stunde_ueberspringt_ferien():
    stunden = lies()
    ferien = [("2026-11-17", "2026-11-20")]
    assert stundenplan.naechste_stunde(stunden, "Mathe", HEUTE, ferien) == date(2026, 11, 24)
    assert stundenplan.stunden_am(stunden, date(2026, 11, 17), ferien) == []
    assert len(stundenplan.stunden_am(stunden, date(2026, 11, 24), ferien)) == 4


def test_ferien_in_der_config_sind_gueltige_zeitraeume():
    for von, bis in config.FERIEN:
        assert date.fromisoformat(von) <= date.fromisoformat(bis)


def test_tabelle_schreiben_und_wieder_lesen(db):
    db.stundenplan_ersetzen(lies())
    geschrieben = stundenplan.tabelle_schreiben(db.stundenplan())
    assert geschrieben.splitlines()[0] == "Tag;Stunde;Fach;Raum;Lehrkraft;E-Mail"
    assert "Di;3-4;Mathe;112;Herr Muster;muster@schule.example" in geschrieben.splitlines()
    assert "Fr;3-4;Mathe;112;Herr Muster;muster@schule.example" in geschrieben.splitlines()   # E-Mail in jeder Zeile
    assert lies(geschrieben) == db.stundenplan()


# ----- Datenbank ----------------------------------------------------------

def test_stundenplan_speichern_und_lehrkraefte(db):
    db.stundenplan_ersetzen(lies())
    assert len(db.stundenplan()) == 10
    lehrkraefte = {l.name: l for l in db.lehrkraefte()}
    assert set(lehrkraefte) == {"Frau Beispiel", "Herr Muster", "Frau Übel"}
    assert lehrkraefte["Herr Muster"].email == "muster@schule.example"
    assert lehrkraefte["Frau Übel"].faecher == ["Bio"]


def test_lehrkraft_suchen_auch_mit_umlauten(db):
    db.stundenplan_ersetzen(lies())
    assert [l.name for l in db.lehrkraft_suchen("übel")] == ["Frau Übel"]
    assert [l.name for l in db.lehrkraft_suchen("MUSTER")] == ["Herr Muster"]
    assert len(db.lehrkraft_suchen("Frau")) == 2
    assert db.lehrkraft_suchen("Niemand") == []


def test_neuer_stundenplan_behaelt_email_adressen(db):
    db.stundenplan_ersetzen(lies())
    [uebel] = db.lehrkraft_suchen("Übel")
    db.lehrkraft_email_setzen(uebel.id, "uebel@schule.example")

    db.stundenplan_ersetzen(lies("Mo;1;Bio;B2;Frau Übel\nMo;2;Kunst;K1;Herr Neu\n"))
    lehrkraefte = {l.name: l.email for l in db.lehrkraefte()}
    # Frau Übel behält ihre Adresse, Herr Muster bleibt wegen seiner Adresse gespeichert,
    # Frau Beispiel (ohne Adresse, ohne Stunde) wird entfernt.
    assert lehrkraefte == {"Frau Übel": "uebel@schule.example", "Herr Muster": "muster@schule.example", "Herr Neu": None}


def test_einzelne_stunde_setzen_und_loeschen(db):
    db.stundenplan_ersetzen(lies())
    db.stunde_setzen(Stunde(4, 8, "Geschichte", "204", "Muster"))        # "Muster" findet "Herr Muster"
    freitag = [s for s in db.stundenplan() if s.wochentag == 4]
    assert (freitag[-1].fach, freitag[-1].lehrkraft) == ("Geschichte", "Herr Muster")

    db.stunde_setzen(Stunde(4, 8, "Kunst", None, None))                  # ersetzt die Stunde
    assert [s.fach for s in db.stundenplan() if (s.wochentag, s.stunde) == (4, 8)] == ["Kunst"]

    assert db.stunde_loeschen(4, 8) is True
    assert db.stunde_loeschen(4, 8) is False


def test_alte_datenbank_von_version_1_funktioniert_weiter(tmp_path):
    """Eine Datenbank ohne die neuen Tabellen bekommt sie beim Öffnen dazu."""
    import sqlite3

    pfad = str(tmp_path / "alt.db")
    alt = sqlite3.connect(pfad)
    alt.execute(
        "CREATE TABLE aufgaben (id INTEGER PRIMARY KEY AUTOINCREMENT, titel TEXT NOT NULL, art TEXT NOT NULL,"
        " fach TEXT, faellig_am TEXT, uhrzeit TEXT, prioritaet TEXT NOT NULL, erledigt INTEGER NOT NULL DEFAULT 0,"
        " erstellt_am TEXT NOT NULL, erledigt_am TEXT)"
    )
    alt.execute("CREATE TABLE einstellungen (name TEXT PRIMARY KEY, wert TEXT)")
    alt.execute(
        "INSERT INTO aufgaben (titel, art, prioritaet, erstellt_am) VALUES ('Zahnarzt', 'termin', 'mittel', '2026-11-16T17:43:00')"
    )
    alt.commit()
    alt.close()

    db = Datenbank(pfad)
    assert [a.titel for a in db.offene()] == ["Zahnarzt"]
    assert db.stundenplan() == []
    db.stundenplan_ersetzen(lies())
    assert len(db.stundenplan()) == 10
    db.schliessen()
