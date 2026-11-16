"""Gemeinsame Vorbereitung für die Tests: ein fertig gestarteter Bot mit leerer Datenbank."""

from datetime import datetime, time

import pytest

from bot import handler, zeit
from bot.datenbank import Datenbank
from tests.falsches_telegram import ICH, FalschesTelegram, datei_update, knopf_update, text_update

# "Jetzt" ist in den Tests Montag, der 16.11.2026 um 10:00 Uhr.
JETZT = datetime(2026, 11, 16, 10, 0, tzinfo=zeit.ZONE)


@pytest.fixture
async def bot(tmp_path, monkeypatch):
    """Ein fertig gestarteter Bot mit leerer Datenbank."""
    monkeypatch.setattr(zeit, "jetzt", lambda: JETZT)
    telegram = FalschesTelegram()
    db = Datenbank(str(tmp_path / "test.db"))
    app = handler.baue_app("123:TEST", ICH, db, request=telegram)
    await app.initialize()

    class Umgebung:
        pass

    u = Umgebung()
    u.app, u.db, u.telegram = app, db, telegram

    async def schreibe(text, user_id=ICH, chat_typ="private"):
        await app.process_update(text_update(app.bot, text, user_id, chat_typ))

    async def druecke(daten, user_id=ICH):
        await app.process_update(knopf_update(app.bot, daten, user_id))

    async def schicke_datei(dateiname, inhalt):
        telegram.dateiinhalt = inhalt.encode("utf-8")
        await app.process_update(datei_update(app.bot, dateiname))

    def um(stunde, minute=0, tag=JETZT.date()):
        """Stellt die Uhr des Bots auf eine andere Zeit."""
        monkeypatch.setattr(zeit, "jetzt", lambda: datetime.combine(tag, time(stunde, minute), tzinfo=zeit.ZONE))

    u.schreibe, u.druecke, u.schicke_datei, u.um = schreibe, druecke, schicke_datei, um
    yield u
    await app.shutdown()
    db.schliessen()
