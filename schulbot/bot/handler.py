"""Der Telegram-Teil: reagiert auf deine Nachrichten, Befehle und Knöpfe.

Ablauf: Telegram schickt jede Nachricht an dieses Programm. Je nach Inhalt
ruft die Bibliothek eine der Funktionen hier unten auf ("Handler").
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

import config
from bot import nachrichten
from bot.datenbank import Aufgabe, Datenbank
from bot.erkennung import ARTEN, PRIORITAETEN, erkenne, finde_datum_und_zeit

log = logging.getLogger("schulbot")
ZONE = ZoneInfo(config.ZEITZONE)

_GRUSS = re.compile(
    r"^(?:hi|hallo|hey|moin|servus|na|guten\s+(?:morgen|tag|abend)|gute\s+nacht)[\s!.,]*$", re.IGNORECASE
)
_DANK = re.compile(
    r"^(?:danke(?:sch(?:ö|oe)n)?|dank\s+dir|thx|merci|super|ok|okay|top|cool|alles\s+klar|passt)[\s!.,]*$",
    re.IGNORECASE,
)
_FRAGEWORT = re.compile(r"^(?:was|wann|wer|wie|wo|welche[rs]?|zeige?|liste)\b", re.IGNORECASE)


def jetzt() -> datetime:
    """Die aktuelle Zeit in deiner Zeitzone."""
    return datetime.now(ZONE)


def _db(context: ContextTypes.DEFAULT_TYPE) -> Datenbank:
    return context.bot_data["db"]


def _offene(context: ContextTypes.DEFAULT_TYPE) -> list[Aufgabe]:
    """Alle offenen Aufgaben. Vergangene Termine werden vorher abgehakt."""
    db = _db(context)
    db.vergangene_termine_abschliessen(jetzt().date())
    return db.offene()


# ---------------------------------------------------------------------------
# Dein Name für den Bot
# ---------------------------------------------------------------------------

def name_entfernen(text: str, name: str) -> tuple[str, bool]:
    """Entfernt die Anrede, z. B. "Hey Mia, Bio-Referat bis Freitag".

    Gibt den Text ohne Anrede zurück und ob der Bot angesprochen wurde.
    """
    n = re.escape(name)
    vorne = re.compile(rf"^\s*(?:(?:hey|hi|hallo|ok|okay)[\s,]+)?{n}(?!\w)[\s,:!?.\-–]*", re.IGNORECASE)
    hinten = re.compile(rf"[\s,]+{n}[\s!.?]*$", re.IGNORECASE)
    ohne, treffer_vorne = vorne.subn("", text, count=1)
    ohne, treffer_hinten = hinten.subn("", ohne, count=1)
    return ohne.strip(), bool(treffer_vorne or treffer_hinten)


# ---------------------------------------------------------------------------
# Knöpfe
# ---------------------------------------------------------------------------

def _knoepfe_aufgabe(aufgaben_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Art", callback_data=f"art:{aufgaben_id}"),
            InlineKeyboardButton("⚡ Priorität", callback_data=f"prio:{aufgaben_id}"),
        ],
        [
            InlineKeyboardButton("📅 Datum", callback_data=f"datum:{aufgaben_id}"),
            InlineKeyboardButton("🗑 Löschen", callback_data=f"weg:{aufgaben_id}"),
        ],
    ])


def _knoepfe_art(aufgaben_id: int) -> InlineKeyboardMarkup:
    knoepfe = [
        InlineKeyboardButton(
            f"{nachrichten.ART_SYMBOLE[art]} {nachrichten.ART_NAMEN[art]}",
            callback_data=f"setzeart:{aufgaben_id}:{art}",
        )
        for art in ARTEN
    ]
    zurueck = InlineKeyboardButton("↩️ Zurück", callback_data=f"zurueck:{aufgaben_id}")
    return InlineKeyboardMarkup([knoepfe[0:2], knoepfe[2:4], [knoepfe[4], zurueck]])


def _knoepfe_prio(aufgaben_id: int) -> InlineKeyboardMarkup:
    knoepfe = [
        InlineKeyboardButton(
            f"{nachrichten.PRIO_SYMBOLE[prio]} {prio}", callback_data=f"setzeprio:{aufgaben_id}:{prio}"
        )
        for prio in PRIORITAETEN
    ]
    return InlineKeyboardMarkup([knoepfe, [InlineKeyboardButton("↩️ Zurück", callback_data=f"zurueck:{aufgaben_id}")]])


def _knoepfe_erledigt(aufgaben: list[Aufgabe]) -> InlineKeyboardMarkup:
    heute = jetzt().date()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(nachrichten.knopf_text(a, heute), callback_data=f"fertig:{a.id}")]
        for a in nachrichten.nach_datum(aufgaben)[:30]
    ])


async def _bearbeiten(query, text: str, knoepfe: InlineKeyboardMarkup | None = None) -> None:
    """Ändert die Nachricht, unter der ein Knopf gedrückt wurde."""
    try:
        await query.edit_message_text(text, reply_markup=knoepfe)
    except BadRequest as fehler:
        # Telegram meldet einen Fehler, wenn sich gar nichts geändert hat. Das ist egal.
        if "not modified" not in str(fehler).lower():
            raise


# ---------------------------------------------------------------------------
# Befehle
# ---------------------------------------------------------------------------

async def befehl_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(nachrichten.hilfe(config.BOT_NAME, config.MORGENNACHRICHT_UHRZEIT))


async def befehl_heute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = nachrichten.heute_liste(_offene(context), jetzt().date(), config.AUSBLICK_TAGE)
    await update.message.reply_text(text)


async def befehl_morgen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tag = jetzt().date() + timedelta(days=1)
    await update.message.reply_text(nachrichten.tag_liste(_offene(context), tag, jetzt().date()))


async def befehl_woche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(nachrichten.wochen_liste(_offene(context), jetzt().date()))


async def befehl_alle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(nachrichten.alle_liste(_offene(context), jetzt().date()))


async def befehl_erledigt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    offene = _offene(context)
    if not offene:
        await update.message.reply_text("Es ist nichts offen. 🎉")
        return
    await update.message.reply_text("Was hast du erledigt? Tipp es an:", reply_markup=_knoepfe_erledigt(offene))


async def unbekannter_befehl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Diesen Befehl kenne ich (noch) nicht. /hilfe zeigt, was ich kann.")


async def kein_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Im Moment verstehe ich nur Text. Schreib mir einfach, was ansteht. 🙂")


# ---------------------------------------------------------------------------
# Normale Nachrichten
# ---------------------------------------------------------------------------

async def nachricht(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wird für jede normale Textnachricht aufgerufen."""
    eingabe, angesprochen = name_entfernen(update.message.text, config.BOT_NAME)

    # Wartet der Bot gerade auf ein neues Datum? (Knopf "Datum" wurde gedrückt)
    if "datum_fuer" in context.user_data:
        await _datum_aendern(update, context, eingabe)
        return

    if not eingabe:
        if angesprochen:
            await update.message.reply_text("Ja? 😊 Schreib mir, was ansteht, oder tippe /hilfe.")
        return
    if _GRUSS.match(eingabe):
        await update.message.reply_text("Hi! 👋 Schreib mir, was ansteht, oder tippe /heute für deine Übersicht.")
        return
    if _DANK.match(eingabe):
        await update.message.reply_text("Gern! 😊")
        return
    if eingabe.endswith("?") or _FRAGEWORT.match(eingabe):
        await _frage_beantworten(update, context, eingabe)
        return

    # Alles andere ist ein neuer Eintrag.
    heute = jetzt().date()
    erkannt = erkenne(eingabe, heute, config.FAECHER)
    aufgabe = _db(context).hinzufuegen(
        titel=erkannt.titel,
        art=erkannt.art,
        fach=erkannt.fach,
        faellig_am=erkannt.datum,
        uhrzeit=erkannt.uhrzeit,
        prioritaet=erkannt.prioritaet,
    )
    await update.message.reply_text(
        nachrichten.bestaetigung(aufgabe, heute) + "\n\nStimmt etwas nicht? Tipp auf einen Knopf.",
        reply_markup=_knoepfe_aufgabe(aufgabe.id),
    )


async def _frage_beantworten(update: Update, context: ContextTypes.DEFAULT_TYPE, frage: str) -> None:
    klein = frage.lower()
    heute = jetzt().date()
    if re.search(r"(?:ü|ue)bermorgen", klein):
        antwort = nachrichten.tag_liste(_offene(context), heute + timedelta(days=2), heute)
    elif "morgen" in klein and "heute morgen" not in klein:
        antwort = nachrichten.tag_liste(_offene(context), heute + timedelta(days=1), heute)
    elif "woche" in klein:
        antwort = nachrichten.wochen_liste(_offene(context), heute)
    elif re.search(r"\balles?\b|\boffen", klein):
        antwort = nachrichten.alle_liste(_offene(context), heute)
    elif "heute" in klein or re.search(r"steht an|ansteht|zu tun|auf dem plan", klein):
        antwort = nachrichten.heute_liste(_offene(context), heute, config.AUSBLICK_TAGE)
    else:
        antwort = (
            "Das kann ich (noch) nicht beantworten. Probier /heute, /morgen, /woche oder /alle.\n"
            "Falls das ein neuer Eintrag sein sollte: Schreib ihn bitte ohne Fragezeichen."
        )
    await update.message.reply_text(antwort)


async def _datum_aendern(update: Update, context: ContextTypes.DEFAULT_TYPE, eingabe: str) -> None:
    """Zweiter Schritt nach dem Knopf "Datum": Du hast das neue Datum geschrieben."""
    db = _db(context)
    aufgaben_id = context.user_data["datum_fuer"]
    aufgabe = db.hole(aufgaben_id)
    klein = eingabe.lower().strip(" .!")
    heute = jetzt().date()

    if aufgabe is None or klein in ("abbrechen", "abbruch", "stopp", "stop"):
        del context.user_data["datum_fuer"]
        await update.message.reply_text("Okay, es bleibt, wie es ist.")
        return

    if klein in ("kein datum", "ohne datum", "keins", "kein"):
        db.aendern(aufgaben_id, faellig_am=None, uhrzeit=None)
    else:
        datum, uhrzeit = finde_datum_und_zeit(eingabe, heute)
        if datum is None and uhrzeit is None:
            await update.message.reply_text(
                "Das Datum habe ich nicht verstanden. Schreib z. B. „Freitag“, „3.12.“ oder "
                "„morgen 15 Uhr“. Mit „abbrechen“ bleibt alles, wie es ist."
            )
            return
        aenderung = {}
        if datum is not None:
            aenderung["faellig_am"] = datum
        if uhrzeit is not None:
            aenderung["uhrzeit"] = uhrzeit
        db.aendern(aufgaben_id, **aenderung)

    del context.user_data["datum_fuer"]
    await update.message.reply_text(
        nachrichten.bestaetigung(db.hole(aufgaben_id), heute, kopf="📅 Geändert"),
        reply_markup=_knoepfe_aufgabe(aufgaben_id),
    )


# ---------------------------------------------------------------------------
# Knopfdruck
# ---------------------------------------------------------------------------

async def knopf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wird aufgerufen, wenn du einen Knopf unter einer Nachricht antippst."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != context.bot_data["user_id"]:
        return

    aktion, aufgaben_id, *rest = query.data.split(":")
    aufgaben_id = int(aufgaben_id)
    db = _db(context)
    aufgabe = db.hole(aufgaben_id)
    heute = jetzt().date()

    if aufgabe is None:
        await _bearbeiten(query, "Diesen Eintrag gibt es nicht mehr.")
    elif aktion == "art":
        await _bearbeiten(query, nachrichten.bestaetigung(aufgabe, heute, kopf="✏️ Welche Art ist"), _knoepfe_art(aufgaben_id))
    elif aktion == "prio":
        await _bearbeiten(query, nachrichten.bestaetigung(aufgabe, heute, kopf="⚡ Wie wichtig ist"), _knoepfe_prio(aufgaben_id))
    elif aktion == "setzeart" and rest[0] in ARTEN:
        db.aendern(aufgaben_id, art=rest[0])
        await _bearbeiten(query, nachrichten.bestaetigung(db.hole(aufgaben_id), heute, kopf="✅ Geändert"), _knoepfe_aufgabe(aufgaben_id))
    elif aktion == "setzeprio" and rest[0] in PRIORITAETEN:
        db.aendern(aufgaben_id, prioritaet=rest[0])
        await _bearbeiten(query, nachrichten.bestaetigung(db.hole(aufgaben_id), heute, kopf="✅ Geändert"), _knoepfe_aufgabe(aufgaben_id))
    elif aktion == "zurueck":
        await _bearbeiten(query, nachrichten.bestaetigung(aufgabe, heute), _knoepfe_aufgabe(aufgaben_id))
    elif aktion == "datum":
        context.user_data["datum_fuer"] = aufgaben_id
        await query.message.reply_text(
            f"📅 Auf wann soll ich <b>{escape(aufgabe.titel)}</b> legen?\n"
            "Schreib z. B. „Freitag“, „3.12.“ oder „morgen 15 Uhr“.\n"
            "„kein Datum“ entfernt das Datum, „abbrechen“ lässt alles, wie es ist."
        )
    elif aktion == "weg":
        db.loeschen(aufgaben_id)
        await _bearbeiten(query, f"🗑 Gelöscht: <s>{escape(aufgabe.titel)}</s>")
    elif aktion == "fertig":
        db.erledigen(aufgaben_id)
        kopf = f"✅ Erledigt: <b>{escape(aufgabe.titel)}</b>"
        offene = _offene(context)
        if offene:
            await _bearbeiten(query, kopf + "\n\nNoch etwas? Tipp es an:", _knoepfe_erledigt(offene))
        else:
            await _bearbeiten(query, kopf + "\n\nDamit ist alles erledigt! 🎉")


# ---------------------------------------------------------------------------
# Morgennachricht
# ---------------------------------------------------------------------------

async def morgennachricht_senden(app: Application) -> bool:
    """Schickt die Morgennachricht, aber höchstens einmal pro Tag."""
    db: Datenbank = app.bot_data["db"]
    heute = jetzt().date()
    if db.einstellung("letzte_morgennachricht") == heute.isoformat():
        return False
    db.vergangene_termine_abschliessen(heute)
    text = nachrichten.morgennachricht(db.offene(), heute, config.AUSBLICK_TAGE)
    try:
        await app.bot.send_message(chat_id=app.bot_data["user_id"], text=text)
    except (Forbidden, BadRequest) as fehler:
        # Passiert, wenn du dem Bot noch nie geschrieben hast: Er darf dich nicht zuerst anschreiben.
        log.warning("Morgennachricht nicht zugestellt (%s). Schreib dem Bot einmal /start.", fehler)
        return False
    db.einstellung_setzen("letzte_morgennachricht", heute.isoformat())
    return True


async def _morgennachricht_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await morgennachricht_senden(context.application)


async def _nach_dem_start(app: Application) -> None:
    """Läuft einmal direkt nach dem Start des Bots."""
    await app.bot.set_my_commands([
        BotCommand("heute", "Was heute ansteht"),
        BotCommand("morgen", "Was morgen ansteht"),
        BotCommand("woche", "Die nächsten 7 Tage"),
        BotCommand("alle", "Alles Offene"),
        BotCommand("erledigt", "Etwas abhaken"),
        BotCommand("hilfe", "Was ich kann"),
    ])
    stunde, minute = config.MORGENNACHRICHT_UHRZEIT
    print(f"{config.BOT_NAME} läuft. Morgennachricht täglich um {stunde}:{minute:02d} Uhr. Beenden mit Strg+C.")
    # Lief der Bot um 8:00 Uhr nicht (z. B. Laptop aus)? Dann jetzt nachholen.
    uhrzeit = jetzt().time()
    if time(*config.MORGENNACHRICHT_UHRZEIT) <= uhrzeit < time(config.MORGENNACHRICHT_NACHHOLEN_BIS, 0):
        await morgennachricht_senden(app)


# ---------------------------------------------------------------------------
# Einrichtung: Solange keine Telegram-ID eingetragen ist
# ---------------------------------------------------------------------------

async def _nach_dem_start_einrichtung(app: Application) -> None:
    print("Einrichtung: Schreib deinem Bot in Telegram irgendeine Nachricht.")
    print("Er antwortet mit deiner Telegram-ID. Trag sie in .env ein und starte neu. Beenden mit Strg+C.")


async def zeige_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat and update.effective_user:
        await update.effective_chat.send_message(
            f"Deine Telegram-ID ist <code>{update.effective_user.id}</code>\n\n"
            "Trag sie in der Datei .env bei TELEGRAM_USER_ID ein und starte den Bot neu. "
            "Danach antworte ich nur noch dir."
        )


async def _fehler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Fehler beim Verarbeiten einer Nachricht", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await update.effective_chat.send_message("Ups, da ist etwas schiefgelaufen. Versuch es bitte nochmal.")
        except Exception:  # noqa: BLE001 - beim Melden eines Fehlers soll nichts mehr schiefgehen
            pass


# ---------------------------------------------------------------------------
# Alles zusammenbauen
# ---------------------------------------------------------------------------

def baue_app(token: str, user_id: int | None, db: Datenbank, request=None) -> Application:
    """Baut den fertigen Bot. request wird nur für die automatischen Tests gebraucht."""
    builder = ApplicationBuilder().token(token).defaults(Defaults(parse_mode=ParseMode.HTML, tzinfo=ZONE))
    if request is not None:
        builder = builder.request(request).get_updates_request(request)

    if user_id is None:
        # Einrichtungsmodus: Der Bot verrät jedem nur die eigene ID, sonst nichts.
        app = builder.post_init(_nach_dem_start_einrichtung).build()
        app.add_handler(MessageHandler(filters.ALL, zeige_id))
        return app

    app = builder.post_init(_nach_dem_start).build()
    app.bot_data["db"] = db
    app.bot_data["user_id"] = user_id

    # Whitelist: Nur du, und nur im privaten Chat. Alle anderen werden ignoriert.
    nur_ich = filters.User(user_id=user_id) & filters.ChatType.PRIVATE

    app.add_handler(CommandHandler(["start", "hilfe", "help"], befehl_start, filters=nur_ich))
    app.add_handler(CommandHandler("heute", befehl_heute, filters=nur_ich))
    app.add_handler(CommandHandler("morgen", befehl_morgen, filters=nur_ich))
    app.add_handler(CommandHandler("woche", befehl_woche, filters=nur_ich))
    app.add_handler(CommandHandler("alle", befehl_alle, filters=nur_ich))
    app.add_handler(CommandHandler("erledigt", befehl_erledigt, filters=nur_ich))
    app.add_handler(CallbackQueryHandler(knopf))
    app.add_handler(MessageHandler(filters.COMMAND & nur_ich, unbekannter_befehl))
    app.add_handler(MessageHandler(filters.TEXT & nur_ich, nachricht))
    app.add_handler(MessageHandler(nur_ich, kein_text))
    app.add_error_handler(_fehler)

    stunde, minute = config.MORGENNACHRICHT_UHRZEIT
    app.job_queue.run_daily(_morgennachricht_job, time=time(stunde, minute, tzinfo=ZONE), name="morgennachricht")
    return app
