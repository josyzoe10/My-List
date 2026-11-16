"""Tests für Version 2: Stundenplan im Chat, Hausaufgaben-Fristen und Erinnerungen.

"Jetzt" ist Montag, der 16.11.2026 um 10:00 Uhr. Die Namen sind erfunden.
"""

from datetime import date, time

import pytest

import config
from bot import zeitplan

TABELLE = """Tag;Stunde;Fach;Raum;Lehrkraft;E-Mail
Mo;1-2;Deutsch;A1;Frau Beispiel;
Di;3-4;Mathe;112;Herr Muster;muster@schule.example
Di;5-6;Bio;B2;Frau Übel;
Do;8-9;Bio;Lab;Frau Übel;
Fr;3-4;Mathe;112;Herr Muster;
"""


@pytest.fixture
async def schule(bot):
    """Der Bot mit eingetragenem Stundenplan."""
    await bot.schreibe(TABELLE)
    bot.telegram.gesendet.clear()
    return bot


# ----- Stundenplan eintragen und ansehen -----------------------------------

async def test_stundenplan_als_nachricht_eintragen(bot):
    await bot.schreibe("/stundenplan")
    assert "noch kein Stundenplan" in bot.telegram.letzte()["text"]

    await bot.schreibe(TABELLE)
    antwort = bot.telegram.letzte()["text"]
    assert antwort.startswith("✅ Stundenplan gespeichert: 10 Stunden an 4 Tagen.")
    assert "<b>Dienstag</b>\n9:50–11:20 · Mathe · 112 · Herr Muster\n11:50–13:20 · Bio · B2 · Frau Übel" in antwort
    assert bot.db.offene() == []                              # die Tabelle wurde kein To-do


async def test_stundenplan_als_datei_eintragen(bot):
    await bot.schicke_datei("stundenplan.csv", TABELLE)
    assert bot.telegram.letzte()["text"].startswith("✅ Stundenplan gespeichert: 10 Stunden")
    assert len(bot.db.stundenplan()) == 10

    await bot.schicke_datei("foto.png", "egal")
    assert "kann ich nichts anfangen" in bot.telegram.letzte()["text"]


async def test_fehlerhafte_tabelle_aendert_nichts(schule):
    await schule.schreibe("Tag;Stunde;Fach\nMo;1;Kunst\nXx;2;Mathe\n")
    antwort = schule.telegram.letzte()["text"]
    assert "Ich habe nichts geändert" in antwort and "Zeile 3" in antwort
    assert len(schule.db.stundenplan()) == 10


async def test_stundenplan_als_datei_bekommen(schule):
    await schule.schreibe("/stundenplan datei")
    endpunkt, parameter = schule.telegram.gesendet[-1]
    assert endpunkt == "sendDocument"
    [(dateiname, inhalt, _typ)] = parameter["dateien"].values()
    assert dateiname == "stundenplan.csv"
    assert "Di;3-4;Mathe;112;Herr Muster;muster@schule.example" in inhalt.decode("utf-8-sig")


async def test_einzelne_stunde_aendern(schule):
    await schule.schreibe("/stunde Fr 8-9 geschichte 204 Herr Neu")
    antwort = schule.telegram.letzte()["text"]
    assert antwort == (
        "✅ <b>Freitag</b> sieht jetzt so aus:\n"
        "9:50–11:20 · Mathe · 112 · Herr Muster\n"
        "14:05–15:35 · Geschichte · 204 · Herr Neu"
    )

    await schule.schreibe("/stunde Fr 8-9 frei")
    assert "Geschichte" not in schule.telegram.letzte()["text"]
    assert [s.fach for s in schule.db.stundenplan() if s.wochentag == 4] == ["Mathe", "Mathe"]

    await schule.schreibe("/stunde Sa 1 frei")
    assert "nichts mehr eingetragen" in schule.telegram.letzte()["text"]

    await schule.schreibe("/stunde Quatsch")
    assert "So trägst du eine Stunde ein" in schule.telegram.letzte()["text"]


async def test_lehrkraefte_und_email(schule):
    await schule.schreibe("/lehrkraft")
    liste = schule.telegram.letzte()["text"]
    assert "Frau Übel · Bio · keine E-Mail" in liste and "Herr Muster · Mathe · muster@schule.example" in liste

    await schule.schreibe("/lehrkraft übel uebel@schule.example")
    assert schule.telegram.letzte()["text"] == "✅ Frau Übel: uebel@schule.example"
    assert schule.db.lehrkraft_suchen("Übel")[0].email == "uebel@schule.example"

    await schule.schreibe("/lehrkraft Frau x@schule.example")          # passt zu zwei Lehrkräften
    assert "passt zu mehreren" in schule.telegram.letzte()["text"]
    await schule.schreibe("/lehrkraft Niemand x@schule.example")
    assert "kenne ich nicht" in schule.telegram.letzte()["text"]
    await schule.schreibe("/lehrkraft Übel")                           # Adresse vergessen
    assert "fehlt die E-Mail-Adresse" in schule.telegram.letzte()["text"]


# ----- Hausaufgaben --------------------------------------------------------

async def test_hausaufgabe_ohne_datum_ist_zur_naechsten_stunde_faellig(schule):
    await schule.schreibe("Mathe S. 45 Nr. 3")
    [aufgabe] = schule.db.offene()
    assert (aufgabe.art, aufgabe.fach, aufgabe.faellig_am) == ("hausaufgabe", "Mathe", date(2026, 11, 17))
    assert schule.telegram.letzte()["text"].startswith(
        "✅ Gespeichert: <b>Mathe S. 45 Nr. 3</b>\n"
        "📚 Hausaufgabe · Mathe bei Herrn Muster · morgen (Di, 17.11.), nächste Mathe-Stunde · Priorität mittel"
    )


async def test_hausaufgabe_am_tag_der_stunde_ist_erst_naechste_woche_faellig(schule):
    await schule.schreibe("Deutsch Aufgabe 2")                 # heute ist Montag, Deutsch ist montags
    assert schule.db.offene()[0].faellig_am == date(2026, 11, 23)


async def test_hausaufgabe_mit_datum_behaelt_ihr_datum(schule):
    await schule.schreibe("Mathe S. 45 Nr. 3 bis Freitag")
    assert schule.db.offene()[0].faellig_am == date(2026, 11, 20)
    assert "nächste Mathe-Stunde" not in schule.telegram.letzte()["text"]


async def test_hausaufgabe_in_fach_ohne_stundenplan_bleibt_ohne_datum(schule):
    await schule.schreibe("Kunst Aufgabe 1")
    assert schule.db.offene()[0].faellig_am is None


async def test_hausaufgabe_ueberspringt_ferien(schule, monkeypatch):
    monkeypatch.setattr(config, "FERIEN", [("2026-11-17", "2026-11-19")])
    await schule.schreibe("Mathe S. 45 Nr. 3")
    assert schule.db.offene()[0].faellig_am == date(2026, 11, 20)


async def test_art_auf_hausaufgabe_aendern_setzt_die_frist(schule):
    await schule.schreibe("Bio Zellen zeichnen, unwichtig")
    [aufgabe] = schule.db.offene()
    schule.db.aendern(aufgabe.id, art="todo", faellig_am=None)

    await schule.druecke(f"setzeart:{aufgabe.id}:hausaufgabe")
    assert schule.db.hole(aufgabe.id).faellig_am == date(2026, 11, 17)
    assert "nächste Bio-Stunde" in schule.telegram.letzte()["text"]


# ----- Fragen --------------------------------------------------------------

async def test_was_hab_ich_morgen(schule):
    await schule.schreibe("morgen 16 Uhr Zahnarzt")
    await schule.schreibe("Was hab ich morgen?")
    assert schule.telegram.letzte()["text"] == (
        "📆 <b>Morgen, Dienstag, 17.11.</b>\n\n"
        "🏫 <b>Stundenplan</b>\n"
        "9:50–11:20 · Mathe · 112\n"
        "11:50–13:20 · Bio · B2\n\n"
        "📋 <b>Einträge</b>\n"
        "🕒 16:00 Zahnarzt"
    )
    await schule.schreibe("/morgen")
    assert "9:50–11:20 · Mathe · 112" in schule.telegram.letzte()["text"]


async def test_was_hab_ich_am_donnerstag(schule):
    await schule.schreibe("Was hab ich am Donnerstag?")
    antwort = schule.telegram.letzte()["text"]
    assert "Donnerstag, 19.11." in antwort and "14:05–15:35 · Bio · Lab" in antwort
    assert "Sonst ist nichts eingetragen" in antwort


async def test_wer_unterrichtet_bio(schule):
    await schule.schreibe("Bio-Test am Donnerstag")
    await schule.schreibe("Wer unterrichtet Bio?")
    assert schule.telegram.letzte()["text"] == (
        "<b>Bio</b> bei Frau Übel\n"
        "Di 11:50–13:20 · B2\n"
        "Do 14:05–15:35 · Lab\n"
        "Nächste Stunde: morgen (Di, 17.11.)\n\n"
        "<b>Offen in diesem Fach</b>\n"
        "✍️ Bio-Test (Do, 19.11.)"
    )


async def test_fragen_zu_faechern(schule):
    await schule.schreibe("Wann hab ich Mathe?")
    antwort = schule.telegram.letzte()["text"]
    assert antwort.startswith("<b>Mathe</b> bei Herrn Muster\n")
    assert "Di 9:50–11:20 · 112" in antwort and "📧 Herr Muster: muster@schule.example" in antwort

    await schule.schreibe("Wer unterrichtet Kunst?")
    assert "Kunst steht nicht in deinem Stundenplan" in schule.telegram.letzte()["text"]
    assert schule.db.offene() == []


async def test_heute_und_morgennachricht_zeigen_den_stundenplan(schule):
    await schule.schreibe("/heute")
    assert "🏫 <b>Stundenplan</b>\n8:00–9:30 · Deutsch · A1\n\nSonst ist für heute nichts eingetragen." in schule.telegram.letzte()["text"]

    await zeitplan.morgennachricht_senden(schule.app)
    text = schule.telegram.letzte()["text"]
    assert text.startswith("☀️ <b>Guten Morgen!</b> Heute ist Montag, 16.11.\n\n🏫 <b>Stundenplan</b>\n8:00–9:30 · Deutsch · A1")


async def test_in_den_ferien_kein_stundenplan(schule, monkeypatch):
    monkeypatch.setattr(config, "FERIEN", [("2026-11-16", "2026-11-16")])
    await schule.schreibe("/heute")
    assert "Stundenplan" not in schule.telegram.letzte()["text"]


# ----- Abendnachricht ------------------------------------------------------

async def test_abendnachricht(schule):
    await schule.schreibe("Mathe S. 45 Nr. 3")                        # fällig morgen (nächste Mathe-Stunde)
    await schule.schreibe("Vokabeln lernen heute")                    # heute noch offen
    await schule.schreibe("morgen 16 Uhr Zahnarzt")
    await schule.schreibe("Bio-Referat bis Donnerstag")               # in 3 Tagen
    await schule.schreibe("Zimmer aufräumen")                         # ohne Datum
    schule.db.hinzufuegen("Altes Arbeitsblatt", "hausaufgabe", "Bio", date(2026, 11, 13), None, "mittel")

    schule.um(19, 0)
    await zeitplan.takt(schule.app)
    assert schule.telegram.letzte()["text"] == (
        "🌙 <b>Für morgen, Dienstag, 17.11.</b>\n\n"
        "⚠️ <b>ÜBERFÄLLIG</b>\n"
        "🟡 Altes Arbeitsblatt · Hausaufgabe (seit Fr, 13.11.)\n\n"
        "⏳ <b>Heute noch offen</b>\n"
        "🟡 Vokabeln lernen · Hausaufgabe\n\n"
        "📚 <b>Hausaufgaben für morgen</b>\n"
        "🟡 Mathe S. 45 Nr. 3 · Hausaufgabe\n\n"
        "📋 <b>Außerdem morgen</b>\n"
        "🕒 16:00 Zahnarzt\n\n"
        "📣 <b>Bald</b>\n"
        "In 3 Tagen (Do, 19.11.): 🔴 Bio-Referat · Abgabe\n\n"
        "📌 <b>Offene To-dos ohne Datum</b>\n"
        "🟢 Zimmer aufräumen\n\n"
        "🏫 <b>Stundenplan morgen</b>\n"
        "9:50–11:20 · Mathe · 112\n"
        "11:50–13:20 · Bio · B2"
    )

    anzahl = len(schule.telegram.nachrichten())
    await zeitplan.takt(schule.app)                                   # eine Minute später: nicht nochmal
    assert len(schule.telegram.nachrichten()) == anzahl


async def test_abendnachricht_kommt_nicht_ohne_anlass_und_nicht_zur_falschen_zeit(schule):
    schule.um(19, 30)
    await zeitplan.takt(schule.app)                                   # nichts offen: keine Nachricht
    assert schule.telegram.nachrichten() == []

    await schule.schreibe("Zimmer aufräumen")
    schule.telegram.gesendet.clear()
    for stunde in (18, 22, 23):
        schule.um(stunde, 0, tag=date(2026, 11, 17))
        await zeitplan.takt(schule.app)
    assert schule.telegram.nachrichten() == []

    schule.um(21, 59, tag=date(2026, 11, 17))                         # später Start: wird nachgeholt
    await zeitplan.takt(schule.app)
    assert "Zimmer aufräumen" in schule.telegram.letzte()["text"]


async def test_ueberfaelliges_kommt_jeden_tag_bis_es_erledigt_ist(schule):
    schule.db.hinzufuegen("Altes Arbeitsblatt", "hausaufgabe", "Bio", date(2026, 11, 13), None, "mittel")
    for tag in (date(2026, 11, 16), date(2026, 11, 17)):
        schule.um(8, 0, tag=tag)
        await zeitplan.takt(schule.app)
        assert "ÜBERFÄLLIG" in schule.telegram.letzte()["text"]
        schule.um(19, 0, tag=tag)
        await zeitplan.takt(schule.app)
        assert "ÜBERFÄLLIG" in schule.telegram.letzte()["text"]
    assert len(schule.telegram.nachrichten()) == 4

    schule.db.erledigen(schule.db.offene()[0].id)
    schule.um(8, 0, tag=date(2026, 11, 18))
    await zeitplan.takt(schule.app)
    assert "ÜBERFÄLLIG" not in schule.telegram.letzte()["text"]


# ----- Erinnerung vor Terminen ---------------------------------------------

async def test_erinnerung_eine_stunde_vor_dem_termin(bot):
    await bot.schreibe("heute 15 Uhr Zahnarzt")
    bot.telegram.gesendet.clear()

    bot.um(13, 59)
    await zeitplan.takt(bot.app)
    assert bot.telegram.nachrichten() == []                           # noch zu früh

    bot.um(14, 0)
    await zeitplan.takt(bot.app)
    assert bot.telegram.letzte()["text"] == "⏰ <b>Zahnarzt</b> um 15:00 Uhr (in 1 Stunde)"

    bot.um(14, 1)
    await zeitplan.takt(bot.app)
    assert len(bot.telegram.nachrichten()) == 1                       # nur einmal


async def test_erinnerung_nach_ruhezustand_kommt_spaeter_aber_nicht_nach_beginn(bot):
    await bot.schreibe("heute 15 Uhr Zahnarzt")
    await bot.schreibe("heute 12 Uhr Friseur")
    bot.telegram.gesendet.clear()

    bot.um(14, 40)                                                    # Computer war bis 14:40 im Ruhezustand
    await zeitplan.takt(bot.app)
    assert [n["text"] for n in bot.telegram.nachrichten()] == ["⏰ <b>Zahnarzt</b> um 15:00 Uhr (in 20 Minuten)"]


async def test_keine_erinnerung_direkt_nach_dem_eintragen(bot):
    bot.um(14, 30)
    await bot.schreibe("heute 15 Uhr Zahnarzt")                       # nur 30 Minuten vorher eingetragen
    bot.telegram.gesendet.clear()
    await zeitplan.takt(bot.app)
    assert bot.telegram.nachrichten() == []


async def test_nach_dem_verschieben_wird_neu_erinnert(bot):
    await bot.schreibe("heute 15 Uhr Zahnarzt")
    [aufgabe] = bot.db.offene()
    bot.um(14, 0)
    await zeitplan.takt(bot.app)

    await bot.druecke(f"datum:{aufgabe.id}")
    await bot.schreibe("morgen 17 Uhr")
    assert (bot.db.hole(aufgabe.id).faellig_am, bot.db.hole(aufgabe.id).uhrzeit) == (date(2026, 11, 17), time(17, 0))
    bot.telegram.gesendet.clear()

    bot.um(16, 20, tag=date(2026, 11, 17))
    await zeitplan.takt(bot.app)
    assert bot.telegram.letzte()["text"] == "⏰ <b>Zahnarzt</b> um 17:00 Uhr (in 40 Minuten)"


async def test_erledigte_termine_werden_nicht_erinnert(bot):
    await bot.schreibe("heute 15 Uhr Zahnarzt")
    bot.db.erledigen(bot.db.offene()[0].id)
    bot.telegram.gesendet.clear()
    bot.um(14, 0)
    await zeitplan.takt(bot.app)
    assert bot.telegram.nachrichten() == []


# ----- Verschieben und Löschen ---------------------------------------------

async def test_verschieben(bot):
    await bot.schreibe("Bio-Referat bis Freitag")
    await bot.schreibe("/verschieben")
    [(beschriftung, daten)] = bot.telegram.letzte_knoepfe()
    assert beschriftung == "Bio-Referat · Fr, 20.11."

    await bot.druecke(daten)
    await bot.schreibe("nächste Woche Montag")
    assert bot.db.offene()[0].faellig_am == date(2026, 11, 23)
    assert bot.telegram.letzte()["text"].startswith("📅 Geändert: <b>Bio-Referat</b>")


async def test_loeschen(bot):
    await bot.schreibe("/loeschen")
    assert "nichts offen" in bot.telegram.letzte()["text"]

    await bot.schreibe("Zimmer aufräumen")
    await bot.schreibe("Müll rausbringen")
    await bot.schreibe("/loeschen")
    await bot.druecke(bot.telegram.letzte_knoepfe()[0][1])
    assert [a.titel for a in bot.db.offene()] == ["Müll rausbringen"]
    assert "Gelöscht" in bot.telegram.letzte()["text"] and len(bot.telegram.letzte_knoepfe()) == 1

    await bot.druecke(bot.telegram.letzte_knoepfe()[0][1])
    assert bot.db.offene() == []
    assert "nichts mehr offen" in bot.telegram.letzte()["text"]


async def test_sehr_lange_listen_werden_aufgeteilt(bot):
    for nummer in range(150):
        bot.db.hinzufuegen(f"Aufgabe Nummer {nummer} mit einem ziemlich langen Titel", "todo", None, None, None, "mittel")
    await bot.schreibe("/alle")
    teile = [n["text"] for n in bot.telegram.nachrichten()]
    assert len(teile) > 1 and all(len(t) <= 4096 for t in teile)
    assert "Aufgabe Nummer 149" in teile[-1]
