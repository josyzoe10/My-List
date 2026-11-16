"""Alles, was der Bot von selbst tut: Morgennachricht, Abendnachricht, Erinnerungen.

Einmal pro Minute schaut der Bot auf die Uhr (der "Takt") und prüft, ob etwas
fällig ist. Das klappt auch, wenn der Computer zwischendurch im Ruhezustand war:
Nach dem Aufwachen holt der nächste Takt nach, was gefehlt hat.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

import config
from bot import nachrichten, zeit
from bot.datenbank import Aufgabe, Datenbank

log = logging.getLogger("schulbot")


async def _senden(app: Application, text: str) -> bool:
    """Schickt dir eine Nachricht. Gibt False zurück, wenn das nicht geklappt hat."""
    try:
        await app.bot.send_message(chat_id=app.bot_data["user_id"], text=text)
        return True
    except TelegramError as fehler:
        # Passiert ohne Internet, oder wenn du dem Bot noch nie geschrieben hast.
        log.warning("Nachricht nicht zugestellt (%s). Ich versuche es in einer Minute wieder.", fehler)
        return False


def _plan(db: Datenbank, tag: date) -> list[str]:
    return nachrichten.plan_fuer_tag(db.stundenplan(), tag, config.STUNDENZEITEN, config.FERIEN)


# ---------------------------------------------------------------------------
# Morgens und abends
# ---------------------------------------------------------------------------

async def morgennachricht_senden(app: Application) -> bool:
    """Schickt die Morgennachricht, aber höchstens einmal pro Tag."""
    db: Datenbank = app.bot_data["db"]
    heute = zeit.jetzt().date()
    if db.einstellung("letzte_morgennachricht") == heute.isoformat():
        return False
    db.vergangene_termine_abschliessen(heute)
    text = nachrichten.morgennachricht(db.offene(), heute, config.AUSBLICK_TAGE, _plan(db, heute))
    if not await _senden(app, text):
        return False
    db.einstellung_setzen("letzte_morgennachricht", heute.isoformat())
    return True


async def abendnachricht_senden(app: Application) -> bool:
    """Schickt die Erinnerung am Abend, höchstens einmal pro Tag und nur, wenn es etwas gibt."""
    db: Datenbank = app.bot_data["db"]
    heute = zeit.jetzt().date()
    if db.einstellung("letzte_abendnachricht") == heute.isoformat():
        return False
    db.vergangene_termine_abschliessen(heute)
    text = nachrichten.abendnachricht(
        db.offene(), heute, config.ERINNERUNG_TAGE_VORHER, _plan(db, heute + timedelta(days=1))
    )
    if text is not None and not await _senden(app, text):
        return False
    db.einstellung_setzen("letzte_abendnachricht", heute.isoformat())
    return text is not None


# ---------------------------------------------------------------------------
# Erinnerung vor Terminen mit Uhrzeit
# ---------------------------------------------------------------------------

def minuten_bis_beginn(aufgabe: Aufgabe, jetzt: datetime) -> int | None:
    """Minuten bis zum Beginn, aber nur, wenn jetzt die Zeit zum Erinnern ist. Sonst None."""
    if not (aufgabe.faellig_am and aufgabe.uhrzeit):
        return None
    beginn = datetime.combine(aufgabe.faellig_am, aufgabe.uhrzeit, tzinfo=zeit.ZONE)
    if beginn - timedelta(minutes=config.ERINNERUNG_TERMIN_MINUTEN) <= jetzt < beginn:
        return round((beginn - jetzt).total_seconds() / 60)
    return None


def erinnerung_auslassen_wenn_zu_knapp(db: Datenbank, aufgabe: Aufgabe) -> None:
    """Hast du einen Termin erst kurz vorher eingetragen, erinnert der Bot nicht sofort daran."""
    if minuten_bis_beginn(aufgabe, zeit.jetzt()) is not None:
        db.erinnerung_merken(aufgabe.id, "termin")


async def termine_erinnern(app: Application) -> int:
    """Erinnert an alles mit Datum und Uhrzeit, das bald beginnt. Gibt die Anzahl zurück."""
    db: Datenbank = app.bot_data["db"]
    jetzt = zeit.jetzt()
    anzahl = 0
    for aufgabe in db.offene():
        minuten = minuten_bis_beginn(aufgabe, jetzt)
        if minuten is None or db.erinnerung_gesendet(aufgabe.id, "termin"):
            continue
        if await _senden(app, nachrichten.termin_erinnerung(aufgabe, minuten)):
            db.erinnerung_merken(aufgabe.id, "termin")
            anzahl += 1
    return anzahl


# ---------------------------------------------------------------------------
# Der Takt
# ---------------------------------------------------------------------------

async def takt(app: Application) -> None:
    """Prüft, was gerade fällig ist. Läuft jede Minute und einmal beim Start."""
    uhrzeit = zeit.jetzt().time()
    if time(*config.MORGENNACHRICHT_UHRZEIT) <= uhrzeit and uhrzeit.hour < config.MORGENNACHRICHT_NACHHOLEN_BIS:
        await morgennachricht_senden(app)
    if time(*config.ABENDNACHRICHT_UHRZEIT) <= uhrzeit and uhrzeit.hour < config.ABENDNACHRICHT_NACHHOLEN_BIS:
        await abendnachricht_senden(app)
    await termine_erinnern(app)


async def _takt_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await takt(context.application)


def einrichten(app: Application) -> None:
    """Startet den Takt: ab der nächsten vollen Minute, dann jede Minute."""
    bis_zur_vollen_minute = 60 - zeit.jetzt().second
    app.job_queue.run_repeating(_takt_job, interval=60, first=bis_zur_vollen_minute + 1, name="takt")
