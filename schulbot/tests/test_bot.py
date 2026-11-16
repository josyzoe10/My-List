"""Tests für den ganzen Bot: Nachricht rein, Antwort raus.

Statt des echten Telegram wird ein Nachbau benutzt (falsches_telegram.py).
"Jetzt" ist in den Tests Montag, der 16.11.2026 um 10:00 Uhr (siehe conftest.py).
"""

from datetime import date, time

import pytest

import config
from bot import handler, zeitplan
from bot.datenbank import Datenbank
from tests.falsches_telegram import FREMD, ICH, FalschesTelegram, text_update


async def test_eintrag_hinzufuegen_und_bestaetigung(bot):
    await bot.schreibe("Bio-Referat bis Freitag")

    [aufgabe] = bot.db.offene()
    assert (aufgabe.titel, aufgabe.art, aufgabe.fach, aufgabe.faellig_am) == ("Bio-Referat", "abgabe", "Bio", date(2026, 11, 20))
    antwort = bot.telegram.letzte()
    assert antwort["chat_id"] == ICH
    assert antwort["text"].startswith("✅ Gespeichert: <b>Bio-Referat</b>\n📤 Abgabe · Bio · Fr, 20.11. · Priorität hoch")
    assert antwort["parse_mode"] == "HTML"
    assert [k[0] for k in bot.telegram.letzte_knoepfe()] == ["✏️ Art", "⚡ Priorität", "📅 Datum", "🗑 Löschen"]


async def test_fremde_werden_ignoriert(bot):
    await bot.schreibe("Bio-Referat bis Freitag", user_id=FREMD)
    await bot.schreibe("/heute", user_id=FREMD)
    await bot.schreibe("/start", user_id=FREMD)

    assert bot.db.offene() == []
    assert bot.telegram.nachrichten() == []


async def test_fremde_knopfdruecke_werden_ignoriert(bot):
    await bot.schreibe("Zimmer aufräumen")
    [aufgabe] = bot.db.offene()
    await bot.druecke(f"weg:{aufgabe.id}", user_id=FREMD)
    assert len(bot.db.offene()) == 1


async def test_in_gruppen_reagiert_der_bot_nicht(bot):
    await bot.schreibe("Bio-Referat bis Freitag", chat_typ="group")
    assert bot.db.offene() == []


async def test_einrichtungsmodus_nennt_nur_die_id(tmp_path):
    telegram = FalschesTelegram()
    db = Datenbank(str(tmp_path / "test.db"))
    app = handler.baue_app("123:TEST", None, db, request=telegram)
    await app.initialize()
    await app.process_update(text_update(app.bot, "Hallo", user_id=FREMD))
    await app.shutdown()

    assert f"<code>{FREMD}</code>" in telegram.letzte()["text"]
    assert db.offene() == []
    db.schliessen()


async def test_start_stellt_sich_mit_namen_vor(bot):
    await bot.schreibe("/start")
    assert f"ich bin <b>{config.BOT_NAME}</b>" in bot.telegram.letzte()["text"]


async def test_anrede_mit_namen(bot, monkeypatch):
    monkeypatch.setattr(config, "BOT_NAME", "Mia")
    await bot.schreibe("Hey Mia, morgen 15 Uhr Zahnarzt")
    [aufgabe] = bot.db.offene()
    assert (aufgabe.titel, aufgabe.uhrzeit) == ("Zahnarzt", time(15, 0))

    await bot.schreibe("Mia?")
    assert bot.telegram.letzte()["text"].startswith("Ja?")
    assert len(bot.db.offene()) == 1


def test_name_entfernen():
    assert handler.name_entfernen("Hey Mia, Bio-Referat bis Freitag", "Mia") == ("Bio-Referat bis Freitag", True)
    assert handler.name_entfernen("Bio-Referat bis Freitag, Mia", "Mia") == ("Bio-Referat bis Freitag", True)
    assert handler.name_entfernen("[NAME], Zimmer aufräumen", "[NAME]") == ("Zimmer aufräumen", True)
    assert handler.name_entfernen("Miau machen", "Mia") == ("Miau machen", False)
    assert handler.name_entfernen("Zimmer aufräumen", "Mia") == ("Zimmer aufräumen", False)


async def test_gruss_und_dank_werden_keine_eintraege(bot):
    for text in ["Guten Morgen", "Hallo!", "danke", "ok"]:
        await bot.schreibe(text)
    assert bot.db.offene() == []
    assert len(bot.telegram.nachrichten()) == 4


async def test_fragen_werden_beantwortet_statt_gespeichert(bot):
    await bot.schreibe("morgen 15 Uhr Zahnarzt")
    await bot.schreibe("Was steht morgen an?")
    assert "📆 <b>Morgen, Dienstag, 17.11.</b>" in bot.telegram.letzte()["text"]
    assert "🕒 15:00 Zahnarzt" in bot.telegram.letzte()["text"]

    await bot.schreibe("Wie wird das Wetter?")
    assert "kann ich (noch) nicht beantworten" in bot.telegram.letzte()["text"]
    assert len(bot.db.offene()) == 1


async def test_befehle_heute_morgen_woche_alle(bot):
    await bot.schreibe("Vokabeln lernen heute")
    await bot.schreibe("morgen 15 Uhr Zahnarzt")
    await bot.schreibe("Mathe-Klausur am 3.12.")

    await bot.schreibe("/heute")
    heute = bot.telegram.letzte()["text"]
    assert heute.startswith("📆 <b>Heute, Montag, 16.11.</b>")
    assert "🟡 Vokabeln lernen" in heute and "Morgen: 🕒 15:00 Zahnarzt" in heute and "Klausur" not in heute

    await bot.schreibe("/morgen")
    assert "🕒 15:00 Zahnarzt" in bot.telegram.letzte()["text"]

    await bot.schreibe("/woche")
    assert "Zahnarzt" in bot.telegram.letzte()["text"] and "Klausur" not in bot.telegram.letzte()["text"]

    await bot.schreibe("/alle")
    assert "✍️ Mathe-Klausur" in bot.telegram.letzte()["text"]


async def test_unbekannter_befehl(bot):
    await bot.schreibe("/quatsch")
    assert "kenne ich (noch) nicht" in bot.telegram.letzte()["text"]
    assert bot.db.offene() == []


async def test_korrigieren_per_knopf(bot):
    await bot.schreibe("Bio Buch kaufen")
    [aufgabe] = bot.db.offene()
    assert aufgabe.art == "hausaufgabe"     # falsch geraten, also korrigieren

    await bot.druecke(f"art:{aufgabe.id}")
    assert ("☑️ To-do", f"setzeart:{aufgabe.id}:todo") in bot.telegram.letzte_knoepfe()
    await bot.druecke(f"setzeart:{aufgabe.id}:todo")
    assert bot.db.hole(aufgabe.id).art == "todo"
    assert bot.telegram.letzte()["text"].startswith("✅ Geändert: <b>Bio Buch kaufen</b>\n☑️ To-do")

    await bot.druecke(f"prio:{aufgabe.id}")
    await bot.druecke(f"setzeprio:{aufgabe.id}:niedrig")
    assert bot.db.hole(aufgabe.id).prioritaet == "niedrig"

    await bot.druecke(f"weg:{aufgabe.id}")
    assert bot.db.offene() == []
    assert "Gelöscht" in bot.telegram.letzte()["text"]

    # Ein Knopf unter einer alten Nachricht für einen gelöschten Eintrag
    await bot.druecke(f"prio:{aufgabe.id}")
    assert "gibt es nicht mehr" in bot.telegram.letzte()["text"]


async def test_datum_aendern(bot):
    await bot.schreibe("Zahnarzt morgen 15 Uhr")
    [aufgabe] = bot.db.offene()

    await bot.druecke(f"datum:{aufgabe.id}")
    assert "Auf wann soll ich <b>Zahnarzt</b> legen?" in bot.telegram.letzte()["text"]

    await bot.schreibe("blabla")                       # nicht verstanden: nichts ändert sich
    assert "nicht verstanden" in bot.telegram.letzte()["text"]
    assert bot.db.hole(aufgabe.id).faellig_am == date(2026, 11, 17)

    await bot.schreibe("Freitag")                      # neues Datum, Uhrzeit bleibt
    geaendert = bot.db.hole(aufgabe.id)
    assert (geaendert.faellig_am, geaendert.uhrzeit) == (date(2026, 11, 20), time(15, 0))
    assert len(bot.db.offene()) == 1                   # "Freitag" wurde kein neuer Eintrag

    await bot.schreibe("Zimmer aufräumen")             # danach wieder normales Verhalten
    assert len(bot.db.offene()) == 2


async def test_datum_aendern_abbrechen_und_entfernen(bot):
    await bot.schreibe("Zahnarzt morgen 15 Uhr")
    [aufgabe] = bot.db.offene()

    await bot.druecke(f"datum:{aufgabe.id}")
    await bot.schreibe("abbrechen")
    assert bot.db.hole(aufgabe.id).faellig_am == date(2026, 11, 17)

    await bot.druecke(f"datum:{aufgabe.id}")
    await bot.schreibe("kein Datum")
    assert (bot.db.hole(aufgabe.id).faellig_am, bot.db.hole(aufgabe.id).uhrzeit) == (None, None)


async def test_erledigt(bot):
    await bot.schreibe("/erledigt")
    assert "nichts offen" in bot.telegram.letzte()["text"]

    await bot.schreibe("Zimmer aufräumen")
    await bot.schreibe("Bio-Referat bis Freitag")
    await bot.schreibe("/erledigt")
    knoepfe = bot.telegram.letzte_knoepfe()
    assert [k[0] for k in knoepfe] == ["Bio-Referat · Fr, 20.11.", "Zimmer aufräumen"]   # mit Datum zuerst

    await bot.druecke(knoepfe[0][1])
    assert [a.titel for a in bot.db.offene()] == ["Zimmer aufräumen"]
    assert "✅ Erledigt: <b>Bio-Referat</b>" in bot.telegram.letzte()["text"]

    await bot.druecke(bot.telegram.letzte_knoepfe()[0][1])
    assert bot.db.offene() == []
    assert "alles erledigt" in bot.telegram.letzte()["text"]


# ----- Morgennachricht ----------------------------------------------------

async def test_morgennachricht_kommt_nur_einmal_pro_tag(bot):
    await bot.schreibe("Vokabeln lernen heute")
    vorher = len(bot.telegram.nachrichten())

    assert await zeitplan.morgennachricht_senden(bot.app) is True
    assert bot.telegram.letzte()["text"].startswith("☀️ <b>Guten Morgen!</b> Heute ist Montag, 16.11.")
    assert bot.telegram.letzte()["chat_id"] == ICH

    assert await zeitplan.morgennachricht_senden(bot.app) is False     # zweiter Versuch am selben Tag
    assert len(bot.telegram.nachrichten()) == vorher + 1


async def test_morgennachricht_wird_nach_spaetem_start_nachgeholt(bot, monkeypatch):
    await handler._nach_dem_start(bot.app)                # Start um 10:00 Uhr: nachholen
    assert "Guten Morgen" in bot.telegram.letzte()["text"]
    assert ("setMyCommands" in [endpunkt for endpunkt, _ in bot.telegram.gesendet])


@pytest.mark.parametrize("uhrzeit", [time(7, 30), time(12, 0), time(18, 0)])
async def test_kein_nachholen_vor_8_oder_ab_12_uhr(bot, monkeypatch, uhrzeit):
    bot.um(uhrzeit.hour, uhrzeit.minute)
    await handler._nach_dem_start(bot.app)
    assert bot.telegram.nachrichten() == []


async def test_morgennachricht_wenn_bot_noch_nie_gestartet_wurde(bot):
    bot.telegram.blockiert = True
    assert await zeitplan.morgennachricht_senden(bot.app) is False     # kein Absturz
    bot.telegram.blockiert = False
    assert await zeitplan.morgennachricht_senden(bot.app) is True      # und später klappt es noch


async def test_der_takt_laeuft_jede_minute(bot):
    [job] = bot.app.job_queue.jobs()
    assert job.name == "takt"
    assert job.job.trigger.interval.total_seconds() == 60


async def test_takt_schickt_die_morgennachricht_auch_nach_dem_ruhezustand(bot):
    bot.um(7, 59)
    await zeitplan.takt(bot.app)
    assert bot.telegram.nachrichten() == []

    bot.um(9, 30)                                         # Computer war um 8:00 im Ruhezustand
    await zeitplan.takt(bot.app)
    await zeitplan.takt(bot.app)                          # der nächste Takt schickt sie nicht nochmal
    assert len(bot.telegram.nachrichten()) == 1
    assert "Guten Morgen" in bot.telegram.letzte()["text"]
