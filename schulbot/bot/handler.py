"""Der Telegram-Teil: reagiert auf deine Nachrichten, Befehle und Knöpfe.

Ablauf: Telegram schickt jede Nachricht an dieses Programm. Je nach Inhalt
ruft die Bibliothek eine der Funktionen hier unten auf ("Handler").
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from html import escape

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
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
from bot import nachrichten, stundenplan, zeit, zeitplan
from bot.datenbank import Aufgabe, Datenbank, Stunde
from bot.erkennung import ARTEN, PRIORITAETEN, erkenne, finde_datum_und_zeit, finde_fach

log = logging.getLogger("schulbot")

_GRUSS = re.compile(
    r"^(?:hi|hallo|hey|moin|servus|na|guten\s+(?:morgen|tag|abend)|gute\s+nacht)[\s!.,]*$", re.IGNORECASE
)
_DANK = re.compile(
    r"^(?:danke(?:sch(?:ö|oe)n)?|dank\s+dir|thx|merci|super|ok|okay|top|cool|alles\s+klar|passt)[\s!.,]*$",
    re.IGNORECASE,
)
_FRAGEWORT = re.compile(r"^(?:was|wann|wer|wie|wo|welche[rs]?|zeige?|liste)\b", re.IGNORECASE)

# Bei diesen Arten zeigt die Bestätigung, bei welcher Lehrkraft das Fach ist.
_MIT_LEHRKRAFT = ("hausaufgabe", "klausur", "abgabe")


# ---------------------------------------------------------------------------
# Kleine Helfer
# ---------------------------------------------------------------------------

def _db(context: ContextTypes.DEFAULT_TYPE) -> Datenbank:
    return context.bot_data["db"]


def _offene(context: ContextTypes.DEFAULT_TYPE) -> list[Aufgabe]:
    """Alle offenen Aufgaben. Vergangene Termine werden vorher abgehakt."""
    db = _db(context)
    db.vergangene_termine_abschliessen(zeit.jetzt().date())
    return db.offene()


def _plan(db: Datenbank, tag: date) -> list[str]:
    """Die Stundenplan-Zeilen für ein Datum."""
    return nachrichten.plan_fuer_tag(db.stundenplan(), tag, config.STUNDENZEITEN, config.FERIEN)


def _faecher(db: Datenbank) -> dict[str, list[str]]:
    """Alle Fächer, die der Bot erkennt: die aus config.py und die aus dem Stundenplan."""
    return stundenplan.alle_faecher(db.stundenplan(), config.FAECHER)


def _bestaetigung(db: Datenbank, aufgabe: Aufgabe, kopf: str = "✅ Gespeichert", frist_hinweis: str | None = None) -> str:
    """Die Rückmeldung zu einem Eintrag, bei Schulsachen mit der Lehrkraft aus dem Stundenplan."""
    lehrkraft = None
    if aufgabe.fach and aufgabe.art in _MIT_LEHRKRAFT:
        stunde = stundenplan.lehrkraft_fuer(db.stundenplan(), aufgabe.fach)
        lehrkraft = stunde.lehrkraft if stunde else None
    return nachrichten.bestaetigung(aufgabe, zeit.jetzt().date(), kopf, lehrkraft, frist_hinweis)


def _frist_aus_stundenplan(db: Datenbank, fach: str | None) -> date | None:
    """Das Datum der nächsten Stunde in diesem Fach. Das ist die Frist für Hausaufgaben."""
    if not fach:
        return None
    return stundenplan.naechste_stunde(db.stundenplan(), fach, zeit.jetzt().date(), config.FERIEN)


async def _antworten(update: Update, text: str) -> None:
    """Antwortet auf deine Nachricht. Sehr lange Texte werden auf mehrere Nachrichten verteilt."""
    stueck = ""
    for zeile in text.split("\n"):
        if stueck and len(stueck) + len(zeile) > 3800:
            await update.effective_message.reply_text(stueck)
            stueck = zeile
        else:
            stueck = f"{stueck}\n{zeile}" if stueck else zeile
    if stueck:
        await update.effective_message.reply_text(stueck)


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


def _knoepfe_liste(aufgaben: list[Aufgabe], aktion: str) -> InlineKeyboardMarkup:
    """Ein Knopf pro offenem Eintrag. aktion sagt, was beim Antippen passiert."""
    heute = zeit.jetzt().date()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(nachrichten.knopf_text(a, heute), callback_data=f"{aktion}:{a.id}")]
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
# Befehle: Übersichten
# ---------------------------------------------------------------------------

async def befehl_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        nachrichten.hilfe(config.BOT_NAME, config.MORGENNACHRICHT_UHRZEIT, config.ABENDNACHRICHT_UHRZEIT)
    )


async def befehl_heute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    heute = zeit.jetzt().date()
    plan = _plan(_db(context), heute)
    await _antworten(update, nachrichten.heute_liste(_offene(context), heute, config.AUSBLICK_TAGE, plan))


async def befehl_morgen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    heute = zeit.jetzt().date()
    morgen = heute + timedelta(days=1)
    await _antworten(update, nachrichten.tag_liste(_offene(context), morgen, heute, _plan(_db(context), morgen)))


async def befehl_woche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _antworten(update, nachrichten.wochen_liste(_offene(context), zeit.jetzt().date()))


async def befehl_alle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _antworten(update, nachrichten.alle_liste(_offene(context), zeit.jetzt().date()))


async def _liste_mit_knoepfen(update: Update, context: ContextTypes.DEFAULT_TYPE, frage: str, aktion: str) -> None:
    offene = _offene(context)
    if not offene:
        await update.message.reply_text("Es ist nichts offen. 🎉")
        return
    await update.message.reply_text(frage, reply_markup=_knoepfe_liste(offene, aktion))


async def befehl_erledigt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _liste_mit_knoepfen(update, context, "Was hast du erledigt? Tipp es an:", "fertig")


async def befehl_verschieben(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _liste_mit_knoepfen(update, context, "Was möchtest du verschieben? Tipp es an:", "datum")


async def befehl_loeschen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _liste_mit_knoepfen(update, context, "Was soll ich löschen? Tipp es an:", "loesch")


async def unbekannter_befehl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Diesen Befehl kenne ich (noch) nicht. /hilfe zeigt, was ich kann.")


async def kein_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Im Moment verstehe ich nur Text. Schreib mir einfach, was ansteht. 🙂")


# ---------------------------------------------------------------------------
# Befehle: Stundenplan und Lehrkräfte
# ---------------------------------------------------------------------------

async def befehl_stundenplan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stundenplan zeigt den Plan, /stundenplan datei schickt ihn als Tabelle, /stundenplan hilfe erklärt das Ändern."""
    stunden = _db(context).stundenplan()
    wunsch = context.args[0].lower() if context.args else ""

    if wunsch in ("hilfe", "ändern", "aendern", "bearbeiten"):
        await update.message.reply_text(nachrichten.STUNDENPLAN_HILFE)
    elif wunsch in ("datei", "csv", "tabelle") and stunden:
        inhalt = stundenplan.tabelle_schreiben(stunden).encode("utf-8-sig")
        await update.message.reply_document(
            InputFile(inhalt, filename="stundenplan.csv"),
            caption="Dein Stundenplan als Tabelle. Du kannst sie ändern und mir zurückschicken.",
        )
    else:
        text = nachrichten.stundenplan_text(stunden, config.STUNDENZEITEN)
        if stunden:
            text += "\n\nÄndern: /stundenplan hilfe"
        await _antworten(update, text)


async def befehl_stunde(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stunde Mi 3-4 Mathe 112 Frau Beispiel   oder   /stunde Mi 3-4 frei"""
    args = context.args
    tag = stundenplan.wochentag_lesen(args[0]) if len(args) >= 3 else None
    nummern = stundenplan.stunden_lesen(args[1]) if len(args) >= 3 else None
    if tag is None or nummern is None:
        await update.message.reply_text(
            "So trägst du eine Stunde ein:\n"
            "<code>/stunde Mi 3-4 Mathe 112 Frau Beispiel</code>\n"
            "Also: Tag, Stunde(n), Fach, Raum, Lehrkraft. Raum und Lehrkraft dürfen fehlen. "
            "Ohne Raum, aber mit Lehrkraft schreibst du einen Strich: "
            "<code>/stunde Mi 3-4 Mathe - Frau Beispiel</code>\n"
            "Löschen: <code>/stunde Mi 3-4 frei</code>"
        )
        return

    db = _db(context)
    if args[2].lower() in ("frei", "löschen", "loeschen", "-"):
        for nummer in nummern:
            db.stunde_loeschen(tag, nummer)
    else:
        fach = stundenplan.fach_name(args[2], config.FAECHER)
        raum = args[3] if len(args) > 3 and args[3] != "-" else None
        lehrkraft = " ".join(args[4:]) or None
        for nummer in nummern:
            db.stunde_setzen(Stunde(tag, nummer, fach, raum, lehrkraft))

    tages_bloecke = stundenplan.bloecke([s for s in db.stundenplan() if s.wochentag == tag])
    zeilen = nachrichten.plan_zeilen(tages_bloecke, config.STUNDENZEITEN, mit_lehrkraft=True)
    tagname = stundenplan.TAGE[tag]
    if zeilen:
        await update.message.reply_text(f"✅ <b>{tagname}</b> sieht jetzt so aus:\n" + "\n".join(zeilen))
    else:
        await update.message.reply_text(f"✅ Am <b>{tagname}</b> ist jetzt nichts mehr eingetragen.")


async def befehl_lehrkraft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/lehrkraft zeigt alle, /lehrkraft Beispiel name@schule.de trägt eine E-Mail-Adresse ein."""
    db = _db(context)
    args = context.args
    if len(args) < 2 or not (stundenplan.ist_email(args[-1]) or args[-1] == "-"):
        text = nachrichten.lehrkraefte_text(db.lehrkraefte())
        if args:
            text = "Dahinter fehlt die E-Mail-Adresse, z. B. <code>/lehrkraft Beispiel name@schule.de</code>\n\n" + text
        await _antworten(update, text)
        return

    name = " ".join(args[:-1])
    treffer = db.lehrkraft_suchen(name)
    if len(treffer) != 1:
        grund = "kenne ich nicht" if not treffer else "passt zu mehreren Lehrkräften"
        await _antworten(update, f"„{escape(name)}“ {grund}.\n\n" + nachrichten.lehrkraefte_text(db.lehrkraefte()))
        return
    email = None if args[-1] == "-" else args[-1]
    db.lehrkraft_email_setzen(treffer[0].id, email)
    await update.message.reply_text(
        f"✅ {escape(treffer[0].name)}: {escape(email) if email else 'E-Mail-Adresse entfernt'}"
    )


async def _stundenplan_importieren(update: Update, context: ContextTypes.DEFAULT_TYPE, tabelle: str) -> None:
    """Ersetzt den Stundenplan durch die Tabelle. Bei Fehlern in der Tabelle ändert sich nichts."""
    db = _db(context)
    stunden, fehler = stundenplan.tabelle_lesen(tabelle, config.FAECHER)
    if fehler:
        await _antworten(update, "In der Tabelle stimmt etwas nicht. Ich habe nichts geändert.\n" + "\n".join(escape(f) for f in fehler[:10]))
        return
    if not stunden:
        await update.effective_message.reply_text("In der Tabelle habe ich keine Stunden gefunden.")
        return
    db.stundenplan_ersetzen(stunden)
    tage = len({s.wochentag for s in stunden})
    await _antworten(
        update,
        f"✅ Stundenplan gespeichert: {len(stunden)} Stunden an {tage} Tagen.\n\n"
        + nachrichten.stundenplan_text(db.stundenplan(), config.STUNDENZEITEN),
    )


async def datei(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Du hast eine Datei geschickt. Eine CSV-Datei wird als Stundenplan gelesen."""
    dokument = update.message.document
    if not (dokument.file_name or "").lower().endswith((".csv", ".txt")):
        await update.message.reply_text(
            "Mit dieser Datei kann ich nichts anfangen. Für den Stundenplan brauche ich eine CSV-Datei."
        )
        return
    if dokument.file_size and dokument.file_size > 200_000:
        await update.message.reply_text("Die Datei ist zu groß für einen Stundenplan.")
        return
    telegram_datei = await dokument.get_file()
    roh = bytes(await telegram_datei.download_as_bytearray())
    try:
        tabelle = roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        tabelle = roh.decode("cp1252", errors="replace")  # so speichert Excel auf Windows
    await _stundenplan_importieren(update, context, tabelle)


# ---------------------------------------------------------------------------
# Normale Nachrichten
# ---------------------------------------------------------------------------

async def nachricht(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wird für jede normale Textnachricht aufgerufen."""
    if stundenplan.sieht_aus_wie_tabelle(update.message.text):
        await _stundenplan_importieren(update, context, update.message.text)
        return

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
    db = _db(context)
    erkannt = erkenne(eingabe, zeit.jetzt().date(), _faecher(db))
    frist_hinweis = None
    if erkannt.art == "hausaufgabe" and erkannt.datum is None:
        # Hausaufgabe ohne Datum: fällig zur nächsten Stunde in diesem Fach.
        erkannt.datum = _frist_aus_stundenplan(db, erkannt.fach)
        if erkannt.datum:
            frist_hinweis = f"nächste {erkannt.fach}-Stunde"
    aufgabe = db.hinzufuegen(
        titel=erkannt.titel,
        art=erkannt.art,
        fach=erkannt.fach,
        faellig_am=erkannt.datum,
        uhrzeit=erkannt.uhrzeit,
        prioritaet=erkannt.prioritaet,
    )
    zeitplan.erinnerung_auslassen_wenn_zu_knapp(db, aufgabe)
    await update.message.reply_text(
        _bestaetigung(db, aufgabe, frist_hinweis=frist_hinweis) + "\n\nStimmt etwas nicht? Tipp auf einen Knopf.",
        reply_markup=_knoepfe_aufgabe(aufgabe.id),
    )


async def _frage_beantworten(update: Update, context: ContextTypes.DEFAULT_TYPE, frage: str) -> None:
    db = _db(context)
    stunden = db.stundenplan()
    klein = frage.lower()
    heute = zeit.jetzt().date()
    fach = finde_fach(frage, _faecher(db))

    if fach and any(s.fach == fach for s in stunden):
        # "Wer unterrichtet Bio?", "Wann hab ich Mathe?", "Wo ist Deutsch?"
        naechste = stundenplan.naechste_stunde(stunden, fach, heute - timedelta(days=1), config.FERIEN)
        offene_im_fach = [a for a in _offene(context) if a.fach == fach]
        antwort = nachrichten.fach_auskunft(fach, stunden, config.STUNDENZEITEN, naechste, heute, offene_im_fach)
    elif fach and re.search(r"\b(?:wer|wann|wo)\b|unterrichtet|lehrer|raum", klein):
        antwort = f"{escape(fach)} steht nicht in deinem Stundenplan (/stundenplan)."
    elif "stundenplan" in klein:
        antwort = nachrichten.stundenplan_text(stunden, config.STUNDENZEITEN)
    elif "woche" in klein:
        antwort = nachrichten.wochen_liste(_offene(context), heute)
    elif re.search(r"\balles?\b|\boffen", klein):
        antwort = nachrichten.alle_liste(_offene(context), heute)
    else:
        # "Was hab ich morgen?", "Was steht am Donnerstag an?"
        tag, _ = finde_datum_und_zeit(frage, heute)
        if tag is None and re.search(r"steht an|ansteht|zu tun|auf dem plan|\bhabe? ich\b", klein):
            tag = heute
        if tag == heute:
            antwort = nachrichten.heute_liste(_offene(context), heute, config.AUSBLICK_TAGE, _plan(db, heute))
        elif tag is not None:
            antwort = nachrichten.tag_liste(_offene(context), tag, heute, _plan(db, tag))
        else:
            antwort = (
                "Das kann ich (noch) nicht beantworten. Probier /heute, /morgen, /woche oder /alle.\n"
                "Falls das ein neuer Eintrag sein sollte: Schreib ihn bitte ohne Fragezeichen."
            )
    await _antworten(update, antwort)


async def _datum_aendern(update: Update, context: ContextTypes.DEFAULT_TYPE, eingabe: str) -> None:
    """Zweiter Schritt nach dem Knopf "Datum": Du hast das neue Datum geschrieben."""
    db = _db(context)
    aufgaben_id = context.user_data["datum_fuer"]
    aufgabe = db.hole(aufgaben_id)
    klein = eingabe.lower().strip(" .!")

    if aufgabe is None or klein in ("abbrechen", "abbruch", "stopp", "stop"):
        del context.user_data["datum_fuer"]
        await update.message.reply_text("Okay, es bleibt, wie es ist.")
        return

    if klein in ("kein datum", "ohne datum", "keins", "kein"):
        db.aendern(aufgaben_id, faellig_am=None, uhrzeit=None)
    else:
        datum, uhrzeit = finde_datum_und_zeit(eingabe, zeit.jetzt().date())
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
    aufgabe = db.hole(aufgaben_id)
    zeitplan.erinnerung_auslassen_wenn_zu_knapp(db, aufgabe)
    await update.message.reply_text(
        _bestaetigung(db, aufgabe, kopf="📅 Geändert"), reply_markup=_knoepfe_aufgabe(aufgaben_id)
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

    if aufgabe is None:
        await _bearbeiten(query, "Diesen Eintrag gibt es nicht mehr.")
    elif aktion == "art":
        await _bearbeiten(query, _bestaetigung(db, aufgabe, kopf="✏️ Welche Art ist"), _knoepfe_art(aufgaben_id))
    elif aktion == "prio":
        await _bearbeiten(query, _bestaetigung(db, aufgabe, kopf="⚡ Wie wichtig ist"), _knoepfe_prio(aufgaben_id))
    elif aktion == "setzeart" and rest[0] in ARTEN:
        db.aendern(aufgaben_id, art=rest[0])
        frist_hinweis = None
        if rest[0] == "hausaufgabe" and aufgabe.faellig_am is None:
            frist = _frist_aus_stundenplan(db, aufgabe.fach)
            if frist:
                db.aendern(aufgaben_id, faellig_am=frist)
                frist_hinweis = f"nächste {aufgabe.fach}-Stunde"
        text = _bestaetigung(db, db.hole(aufgaben_id), kopf="✅ Geändert", frist_hinweis=frist_hinweis)
        await _bearbeiten(query, text, _knoepfe_aufgabe(aufgaben_id))
    elif aktion == "setzeprio" and rest[0] in PRIORITAETEN:
        db.aendern(aufgaben_id, prioritaet=rest[0])
        await _bearbeiten(query, _bestaetigung(db, db.hole(aufgaben_id), kopf="✅ Geändert"), _knoepfe_aufgabe(aufgaben_id))
    elif aktion == "zurueck":
        await _bearbeiten(query, _bestaetigung(db, aufgabe), _knoepfe_aufgabe(aufgaben_id))
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
    elif aktion in ("fertig", "loesch"):
        # Knopf aus der Liste von /erledigt oder /loeschen: danach die restliche Liste zeigen.
        if aktion == "fertig":
            db.erledigen(aufgaben_id)
            kopf, nochmal, ende = f"✅ Erledigt: <b>{escape(aufgabe.titel)}</b>", "Noch etwas? Tipp es an:", "Damit ist alles erledigt! 🎉"
        else:
            db.loeschen(aufgaben_id)
            kopf, nochmal, ende = f"🗑 Gelöscht: <s>{escape(aufgabe.titel)}</s>", "Noch etwas löschen?", "Jetzt ist nichts mehr offen."
        offene = _offene(context)
        if offene:
            await _bearbeiten(query, f"{kopf}\n\n{nochmal}", _knoepfe_liste(offene, aktion))
        else:
            await _bearbeiten(query, f"{kopf}\n\n{ende}")


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

async def _nach_dem_start(app: Application) -> None:
    """Läuft einmal direkt nach dem Start des Bots."""
    await app.bot.set_my_commands([
        BotCommand("heute", "Was heute ansteht"),
        BotCommand("morgen", "Was morgen ansteht"),
        BotCommand("woche", "Die nächsten 7 Tage"),
        BotCommand("alle", "Alles Offene"),
        BotCommand("erledigt", "Etwas abhaken"),
        BotCommand("verschieben", "Ein neues Datum geben"),
        BotCommand("loeschen", "Etwas löschen"),
        BotCommand("stundenplan", "Stundenplan anzeigen oder ändern"),
        BotCommand("lehrkraft", "Lehrkräfte und E-Mail-Adressen"),
        BotCommand("hilfe", "Was ich kann"),
    ])
    morgens, abends = config.MORGENNACHRICHT_UHRZEIT, config.ABENDNACHRICHT_UHRZEIT
    print(
        f"{config.BOT_NAME} läuft. Morgennachricht um {morgens[0]}:{morgens[1]:02d} Uhr, "
        f"Abendnachricht um {abends[0]}:{abends[1]:02d} Uhr. Beenden mit Strg+C."
    )
    # Gleich einmal nachsehen, ob etwas fällig ist (z. B. die Morgennachricht nach einem späten Start).
    await zeitplan.takt(app)


async def _nach_dem_start_einrichtung(app: Application) -> None:
    print("Einrichtung: Schreib deinem Bot in Telegram irgendeine Nachricht.")
    print("Er antwortet mit deiner Telegram-ID. Trag sie in .env ein und starte neu. Beenden mit Strg+C.")


async def zeige_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Einrichtung: Solange keine Telegram-ID eingetragen ist, nennt der Bot nur die ID."""
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


def baue_app(token: str, user_id: int | None, db: Datenbank, request=None) -> Application:
    """Baut den fertigen Bot. request wird nur für die automatischen Tests gebraucht."""
    builder = ApplicationBuilder().token(token).defaults(Defaults(parse_mode=ParseMode.HTML, tzinfo=zeit.ZONE))
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

    befehle = {
        ("start", "hilfe", "help"): befehl_start,
        ("heute",): befehl_heute,
        ("morgen",): befehl_morgen,
        ("woche",): befehl_woche,
        ("alle",): befehl_alle,
        ("erledigt",): befehl_erledigt,
        ("verschieben",): befehl_verschieben,
        ("loeschen",): befehl_loeschen,
        ("stundenplan",): befehl_stundenplan,
        ("stunde",): befehl_stunde,
        ("lehrkraft", "lehrkraefte"): befehl_lehrkraft,
    }
    for namen, funktion in befehle.items():
        app.add_handler(CommandHandler(list(namen), funktion, filters=nur_ich))
    app.add_handler(CallbackQueryHandler(knopf))
    app.add_handler(MessageHandler(filters.COMMAND & nur_ich, unbekannter_befehl))
    app.add_handler(MessageHandler(filters.TEXT & nur_ich, nachricht))
    app.add_handler(MessageHandler(filters.Document.ALL & nur_ich, datei))
    app.add_handler(MessageHandler(nur_ich, kein_text))
    app.add_error_handler(_fehler)

    zeitplan.einrichten(app)
    return app
