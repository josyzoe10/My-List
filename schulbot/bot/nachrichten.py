"""Baut die Texte, die der Bot verschickt (Morgennachricht, Listen, Bestätigungen).

Hier wird nichts gespeichert und nichts verschickt. Die Funktionen bekommen
Aufgaben und das heutige Datum und geben fertigen Text zurück.
Der Text nutzt ein bisschen HTML, weil Telegram damit fett schreiben kann.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from html import escape

from bot import stundenplan
from bot.datenbank import Aufgabe, Lehrkraft, Stunde

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WOCHENTAGE_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

ART_NAMEN = {
    "todo": "To-do",
    "hausaufgabe": "Hausaufgabe",
    "termin": "Termin",
    "klausur": "Klausur/Test",
    "abgabe": "Abgabe",
}
ART_SYMBOLE = {"todo": "☑️", "hausaufgabe": "📚", "termin": "📅", "klausur": "✍️", "abgabe": "📤"}
PRIO_SYMBOLE = {"hoch": "🔴", "mittel": "🟡", "niedrig": "🟢"}
_PRIO_RANG = {"hoch": 0, "mittel": 1, "niedrig": 2}

# Termine und Klausuren finden zu einer Zeit statt. Alles andere ist "zu erledigen".
_EREIGNISSE = ("termin", "klausur")


# ---------------------------------------------------------------------------
# Datum schreiben
# ---------------------------------------------------------------------------

def datum_kurz(tag: date, heute: date) -> str:
    """Fr, 20.11. (mit Jahr, wenn es nicht dieses Jahr ist)"""
    text = f"{WOCHENTAGE_KURZ[tag.weekday()]}, {tag.day}.{tag.month}."
    return text + str(tag.year) if tag.year != heute.year else text


def datum_lang(tag: date) -> str:
    """Montag, 16.11."""
    return f"{WOCHENTAGE[tag.weekday()]}, {tag.day}.{tag.month}."


def datum_nah(tag: date, heute: date) -> str:
    """heute, morgen oder Fr, 20.11."""
    if tag == heute:
        return "heute"
    if tag == heute + timedelta(days=1):
        return "morgen"
    return datum_kurz(tag, heute)


# ---------------------------------------------------------------------------
# Sortieren und einzelne Zeilen
# ---------------------------------------------------------------------------

def nach_prioritaet(aufgaben: list[Aufgabe]) -> list[Aufgabe]:
    return sorted(aufgaben, key=lambda a: (_PRIO_RANG[a.prioritaet], a.uhrzeit or time.max, a.id))


def nach_uhrzeit(aufgaben: list[Aufgabe]) -> list[Aufgabe]:
    return sorted(aufgaben, key=lambda a: (a.uhrzeit or time.max, a.id))


def nach_datum(aufgaben: list[Aufgabe]) -> list[Aufgabe]:
    """Überfälliges und Baldiges zuerst, Aufgaben ohne Datum ans Ende."""
    return sorted(aufgaben, key=lambda a: (a.faellig_am or date.max, _PRIO_RANG[a.prioritaet], a.id))


def ist_ueberfaellig(aufgabe: Aufgabe, heute: date) -> bool:
    return (
        aufgabe.faellig_am is not None
        and aufgabe.faellig_am < heute
        and aufgabe.art not in _EREIGNISSE
    )


def bei(name: str) -> str:
    """Für Sätze mit "bei": aus "Herr Muster" wird "bei Herrn Muster"."""
    return "bei " + escape("Herrn " + name[5:] if name.startswith("Herr ") else name)


def zeile(aufgabe: Aufgabe) -> str:
    """Eine Zeile für Listen, z. B. '🔴 Bio-Referat · Abgabe' oder '🕒 15:00 Zahnarzt'."""
    titel = escape(aufgabe.titel)
    if aufgabe.art in _EREIGNISSE:
        symbol = "✍️" if aufgabe.art == "klausur" else ("🕒" if aufgabe.uhrzeit else "📅")
        uhrzeit = f"{aufgabe.uhrzeit:%H:%M} " if aufgabe.uhrzeit else ""
        return f"{symbol} {uhrzeit}{titel}"
    art = f" · {ART_NAMEN[aufgabe.art]}" if aufgabe.art != "todo" else ""
    uhrzeit = f" ({aufgabe.uhrzeit:%H:%M})" if aufgabe.uhrzeit else ""
    return f"{PRIO_SYMBOLE[aufgabe.prioritaet]} {titel}{art}{uhrzeit}"


def _tagesblock(aufgaben: list[Aufgabe]) -> list[str]:
    """Die Zeilen für einen Tag: erst Termine nach Uhrzeit, dann Aufgaben nach Priorität."""
    ereignisse = nach_uhrzeit([a for a in aufgaben if a.art in _EREIGNISSE])
    zu_erledigen = nach_prioritaet([a for a in aufgaben if a.art not in _EREIGNISSE])
    return [zeile(a) for a in ereignisse + zu_erledigen]


def _ueberfaellig_block(aufgaben: list[Aufgabe], heute: date) -> list[str]:
    ueberfaellig = nach_datum([a for a in aufgaben if ist_ueberfaellig(a, heute)])
    if not ueberfaellig:
        return []
    zeilen = ["⚠️ <b>ÜBERFÄLLIG</b>"]
    zeilen += [f"{zeile(a)} (seit {datum_kurz(a.faellig_am, heute)})" for a in ueberfaellig]
    return zeilen + [""]


# ---------------------------------------------------------------------------
# Ganze Nachrichten
# ---------------------------------------------------------------------------

def tagesuebersicht(
    aufgaben: list[Aufgabe], heute: date, kopf: str, ausblick_tage: int, plan: list[str] | None = None
) -> str:
    """Die Übersicht für heute. Wird für /heute und die Morgennachricht benutzt.

    plan sind die fertigen Zeilen des Stundenplans von heute (siehe plan_fuer_tag).
    """
    zeilen = [kopf, ""]
    zeilen += _ueberfaellig_block(aufgaben, heute)
    if plan:
        zeilen += ["🏫 <b>Stundenplan</b>"] + plan + [""]

    heutige = [a for a in aufgaben if a.faellig_am == heute]
    ereignisse = nach_uhrzeit([a for a in heutige if a.art in _EREIGNISSE])
    zu_erledigen = nach_prioritaet([a for a in heutige if a.art not in _EREIGNISSE])
    if ereignisse:
        zeilen += ["📅 <b>Termine heute</b>"] + [zeile(a) for a in ereignisse] + [""]
    if zu_erledigen:
        zeilen += ["📋 <b>Heute zu erledigen</b>"] + [zeile(a) for a in zu_erledigen] + [""]
    if not heutige:
        zeilen += ["Sonst ist für heute nichts eingetragen. 🎉" if plan else "Für heute ist nichts eingetragen. 🎉", ""]

    ohne_datum = nach_prioritaet([a for a in aufgaben if a.faellig_am is None])
    if ohne_datum:
        zeilen.append("📌 <b>Ohne Datum</b>")
        zeilen += [zeile(a) for a in ohne_datum[:5]]
        if len(ohne_datum) > 5:
            zeilen.append(f"… und {len(ohne_datum) - 5} weitere (/alle)")
        zeilen.append("")

    bald = nach_datum([
        a for a in aufgaben
        if a.faellig_am and heute < a.faellig_am <= heute + timedelta(days=ausblick_tage)
    ])
    if bald:
        zeilen.append("🔜 <b>In den nächsten Tagen</b>")
        zeilen += [f"{datum_nah(a.faellig_am, heute).capitalize()}: {zeile(a)}" for a in bald]

    return "\n".join(zeilen).strip()


def morgennachricht(aufgaben: list[Aufgabe], heute: date, ausblick_tage: int, plan: list[str] | None = None) -> str:
    kopf = f"☀️ <b>Guten Morgen!</b> Heute ist {datum_lang(heute)}"
    return tagesuebersicht(aufgaben, heute, kopf, ausblick_tage, plan)


def heute_liste(aufgaben: list[Aufgabe], heute: date, ausblick_tage: int, plan: list[str] | None = None) -> str:
    return tagesuebersicht(aufgaben, heute, f"📆 <b>Heute, {datum_lang(heute)}</b>", ausblick_tage, plan)


def tag_liste(aufgaben: list[Aufgabe], tag: date, heute: date, plan: list[str] | None = None) -> str:
    """Was an einem bestimmten Tag ansteht, z. B. für /morgen."""
    wann = datum_nah(tag, heute)
    kopf = f"📆 <b>{wann.capitalize()}, {datum_lang(tag)}</b>" if wann in ("heute", "morgen") else f"📆 <b>{datum_lang(tag)}</b>"
    zeilen = [kopf, ""]
    if plan:
        zeilen += ["🏫 <b>Stundenplan</b>"] + plan + [""]
    eintraege = [a for a in aufgaben if a.faellig_am == tag]
    if eintraege:
        zeilen += ["📋 <b>Einträge</b>"] if plan else []
        zeilen += _tagesblock(eintraege)
    else:
        zeilen.append("Sonst ist nichts eingetragen. 🎉" if plan else "Da ist nichts eingetragen. 🎉")
    return "\n".join(zeilen).strip()


def abendnachricht(
    aufgaben: list[Aufgabe], heute: date, tage_vorher: tuple[int, ...], plan_morgen: list[str] | None = None
) -> str | None:
    """Die Erinnerung am Abend. Gibt None zurück, wenn es nichts zu erinnern gibt."""
    morgen = heute + timedelta(days=1)
    zeilen = _ueberfaellig_block(aufgaben, heute)

    heute_offen = nach_prioritaet([a for a in aufgaben if a.faellig_am == heute and a.art not in _EREIGNISSE])
    if heute_offen:
        zeilen += ["⏳ <b>Heute noch offen</b>"] + [zeile(a) for a in heute_offen] + [""]

    morgige = [a for a in aufgaben if a.faellig_am == morgen]
    hausaufgaben = nach_prioritaet([a for a in morgige if a.art == "hausaufgabe"])
    if hausaufgaben:
        zeilen += ["📚 <b>Hausaufgaben für morgen</b>"] + [zeile(a) for a in hausaufgaben] + [""]
    sonstige = [a for a in morgige if a.art != "hausaufgabe"]
    if sonstige:
        zeilen += ["📋 <b>Außerdem morgen</b>"] + _tagesblock(sonstige) + [""]

    bald = []
    for tage in sorted(t for t in tage_vorher if t > 1):
        tag = heute + timedelta(days=tage)
        for a in nach_prioritaet([a for a in aufgaben if a.faellig_am == tag and a.art in ("klausur", "abgabe")]):
            bald.append(f"In {tage} Tagen ({datum_kurz(tag, heute)}): {zeile(a)}")
    if bald:
        zeilen += ["📣 <b>Bald</b>"] + bald + [""]

    ohne_datum = nach_prioritaet([a for a in aufgaben if a.faellig_am is None])
    if ohne_datum:
        zeilen.append("📌 <b>Offene To-dos ohne Datum</b>")
        zeilen += [zeile(a) for a in ohne_datum[:5]]
        if len(ohne_datum) > 5:
            zeilen.append(f"… und {len(ohne_datum) - 5} weitere (/alle)")
        zeilen.append("")

    if not zeilen:
        return None
    if plan_morgen:
        zeilen += ["🏫 <b>Stundenplan morgen</b>"] + plan_morgen
    return "\n".join([f"🌙 <b>Für morgen, {datum_lang(morgen)}</b>", ""] + zeilen).strip()


def termin_erinnerung(aufgabe: Aufgabe, minuten: int) -> str:
    """Kurze Erinnerung vor einem Termin mit Uhrzeit."""
    wann = "in 1 Stunde" if 55 <= minuten <= 65 else f"in {minuten} Minuten"
    return f"⏰ <b>{escape(aufgabe.titel)}</b> um {aufgabe.uhrzeit:%H:%M} Uhr ({wann})"


def wochen_liste(aufgaben: list[Aufgabe], heute: date) -> str:
    """Die nächsten 7 Tage, nach Tagen gegliedert."""
    zeilen = ["🗓 <b>Die nächsten 7 Tage</b>", ""]
    zeilen += _ueberfaellig_block(aufgaben, heute)
    etwas_gefunden = False
    for abstand in range(7):
        tag = heute + timedelta(days=abstand)
        eintraege = [a for a in aufgaben if a.faellig_am == tag]
        if eintraege:
            etwas_gefunden = True
            zeilen += [f"<b>{datum_nah(tag, heute).capitalize() if abstand < 2 else datum_lang(tag)}</b>"]
            zeilen += _tagesblock(eintraege) + [""]
    if not etwas_gefunden:
        zeilen.append("In den nächsten 7 Tagen ist nichts eingetragen. 🎉")
    return "\n".join(zeilen).strip()


def alle_liste(aufgaben: list[Aufgabe], heute: date) -> str:
    """Alles, was noch offen ist."""
    if not aufgaben:
        return "Es ist nichts offen. 🎉"
    zeilen = [f"📚 <b>Alles Offene</b> ({len(aufgaben)})", ""]
    zeilen += _ueberfaellig_block(aufgaben, heute)

    kommend = [a for a in aufgaben if a.faellig_am and not ist_ueberfaellig(a, heute)]
    for tag in sorted({a.faellig_am for a in kommend}):
        zeilen.append(f"<b>{datum_nah(tag, heute).capitalize()}</b>")
        zeilen += _tagesblock([a for a in kommend if a.faellig_am == tag]) + [""]

    ohne_datum = nach_prioritaet([a for a in aufgaben if a.faellig_am is None])
    if ohne_datum:
        zeilen += ["📌 <b>Ohne Datum</b>"] + [zeile(a) for a in ohne_datum]
    return "\n".join(zeilen).strip()


def bestaetigung(
    aufgabe: Aufgabe,
    heute: date,
    kopf: str = "✅ Gespeichert",
    lehrkraft: str | None = None,
    frist_hinweis: str | None = None,
) -> str:
    """Kurze Rückmeldung, wie der Bot etwas einsortiert hat.

    frist_hinweis erklärt ein automatisch gesetztes Datum, z. B. "nächste Mathe-Stunde".
    """
    teile = [f"{ART_SYMBOLE[aufgabe.art]} {ART_NAMEN[aufgabe.art]}"]
    if aufgabe.fach:
        teile.append(escape(aufgabe.fach) + (f" {bei(lehrkraft)}" if lehrkraft else ""))
    if aufgabe.faellig_am:
        wann = datum_nah(aufgabe.faellig_am, heute)
        if wann in ("heute", "morgen"):
            wann += f" ({datum_kurz(aufgabe.faellig_am, heute)})"
        if aufgabe.uhrzeit:
            wann += f" um {aufgabe.uhrzeit:%H:%M}"
        if frist_hinweis:
            wann += f", {escape(frist_hinweis)}"
        teile.append(wann)
    else:
        teile.append(f"{aufgabe.uhrzeit:%H:%M} Uhr, kein Datum" if aufgabe.uhrzeit else "kein Datum")
    teile.append(f"Priorität {aufgabe.prioritaet}")
    return f"{kopf}: <b>{escape(aufgabe.titel)}</b>\n" + " · ".join(teile)


def knopf_text(aufgabe: Aufgabe, heute: date) -> str:
    """Beschriftung für einen Knopf, z. B. in /erledigt."""
    titel = aufgabe.titel if len(aufgabe.titel) <= 38 else aufgabe.titel[:37] + "…"
    if aufgabe.faellig_am:
        return f"{titel} · {datum_nah(aufgabe.faellig_am, heute)}"
    return titel


def hilfe(name: str, morgens: tuple[int, int], abends: tuple[int, int]) -> str:
    return (
        f"Hi, ich bin <b>{escape(name)}</b>, dein Assistent für Schule und Alltag. 👋\n\n"
        "Schreib mir einfach, was ansteht, zum Beispiel:\n"
        "• Bio-Referat bis Freitag\n"
        "• morgen 15 Uhr Zahnarzt\n"
        "• Mathe-Klausur am 3.12.\n"
        "• Mathe S. 45 Nr. 3 (Frist: die nächste Mathe-Stunde)\n\n"
        "Ich sage dir, wie ich es einsortiert habe, und du kannst es per Knopf korrigieren.\n\n"
        "Du kannst mich auch fragen:\n"
        "• Was hab ich morgen?\n"
        "• Wer unterrichtet Bio?\n\n"
        "<b>Befehle</b>\n"
        "/heute – was heute ansteht\n"
        "/morgen – was morgen ansteht\n"
        "/woche – die nächsten 7 Tage\n"
        "/alle – alles Offene\n"
        "/erledigt – etwas abhaken\n"
        "/verschieben – ein neues Datum geben\n"
        "/loeschen – etwas löschen\n"
        "/stundenplan – Stundenplan anzeigen oder ändern\n"
        "/lehrkraft – Lehrkräfte und ihre E-Mail-Adressen\n"
        "/hilfe – diese Übersicht\n\n"
        f"Um {morgens[0]}:{morgens[1]:02d} Uhr schicke ich dir deine Übersicht für den Tag, "
        f"um {abends[0]}:{abends[1]:02d} Uhr erinnere ich dich an morgen."
    )


# ---------------------------------------------------------------------------
# Stundenplan
# ---------------------------------------------------------------------------

def plan_zeilen(
    bloecke: list[stundenplan.Block], stundenzeiten: dict[int, tuple[str, str]], mit_lehrkraft: bool = False
) -> list[str]:
    """Eine Zeile pro Block, z. B. '9:50–11:20 · Mathe · 112'."""
    zeilen = []
    for block in bloecke:
        teile = [stundenplan.zeitspanne(block, stundenzeiten), escape(block.fach)]
        if block.raum:
            teile.append(escape(block.raum))
        if mit_lehrkraft and block.lehrkraft:
            teile.append(escape(block.lehrkraft))
        zeilen.append(" · ".join(teile))
    return zeilen


def plan_fuer_tag(
    stunden: list[Stunde], tag: date, stundenzeiten: dict[int, tuple[str, str]], ferien: list[tuple[str, str]]
) -> list[str]:
    """Die Stundenplan-Zeilen für ein bestimmtes Datum. In den Ferien leer."""
    return plan_zeilen(stundenplan.bloecke(stundenplan.stunden_am(stunden, tag, ferien)), stundenzeiten)


STUNDENPLAN_HILFE = (
    "<b>So änderst du den Stundenplan</b>\n"
    "Eine Stunde eintragen oder ersetzen:\n"
    "<code>/stunde Mi 3-4 Mathe 112 Frau Beispiel</code>\n"
    "Eine Stunde löschen:\n"
    "<code>/stunde Mi 3-4 frei</code>\n"
    "Den ganzen Plan auf einmal: Schick mir eine Tabelle als Nachricht oder als CSV-Datei, "
    "mit dieser ersten Zeile:\n"
    "<code>Tag;Stunde;Fach;Raum;Lehrkraft;E-Mail</code>\n"
    "Den Plan als Datei bekommen: <code>/stundenplan datei</code>"
)


def stundenplan_text(stunden: list[Stunde], stundenzeiten: dict[int, tuple[str, str]]) -> str:
    """Der ganze Stundenplan der Woche."""
    if not stunden:
        return "🏫 Es ist noch kein Stundenplan eingetragen.\n\n" + STUNDENPLAN_HILFE
    zeilen = ["🏫 <b>Stundenplan</b>"]
    for wochentag in sorted({s.wochentag for s in stunden}):
        zeilen += ["", f"<b>{stundenplan.TAGE[wochentag]}</b>"]
        tages_bloecke = stundenplan.bloecke([s for s in stunden if s.wochentag == wochentag])
        zeilen += plan_zeilen(tages_bloecke, stundenzeiten, mit_lehrkraft=True)
    return "\n".join(zeilen)


def fach_auskunft(
    fach: str,
    stunden: list[Stunde],
    stundenzeiten: dict[int, tuple[str, str]],
    naechste: date | None,
    heute: date,
    offene_im_fach: list[Aufgabe],
) -> str:
    """Antwort auf Fragen wie "Wer unterrichtet Bio?" oder "Wann hab ich Mathe?"."""
    fach_stunden = [s for s in stunden if s.fach == fach]
    lehrkraefte = sorted({s.lehrkraft for s in fach_stunden if s.lehrkraft})
    zeilen = [f"<b>{escape(fach)}</b>" + (f" {bei(lehrkraefte[0])}" if len(lehrkraefte) == 1 else "")]
    for block in stundenplan.bloecke(fach_stunden):
        teile = [f"{stundenplan.TAGE_KURZ[block.wochentag]} {stundenplan.zeitspanne(block, stundenzeiten)}"]
        if block.raum:
            teile.append(escape(block.raum))
        if len(lehrkraefte) > 1 and block.lehrkraft:
            teile.append(escape(block.lehrkraft))
        zeilen.append(" · ".join(teile))
    if naechste:
        wann = datum_nah(naechste, heute)
        zeilen.append(f"Nächste Stunde: {wann}" + (f" ({datum_kurz(naechste, heute)})" if wann in ("heute", "morgen") else ""))
    for name in lehrkraefte:
        email = next((s.email for s in fach_stunden if s.lehrkraft == name and s.email), None)
        if email:
            zeilen.append(f"📧 {escape(name)}: {escape(email)}")
    if offene_im_fach:
        zeilen += ["", "<b>Offen in diesem Fach</b>"]
        for a in nach_datum(offene_im_fach):
            zeilen.append(zeile(a) + (f" ({datum_nah(a.faellig_am, heute)})" if a.faellig_am else ""))
    return "\n".join(zeilen)


def lehrkraefte_text(lehrkraefte: list[Lehrkraft]) -> str:
    if not lehrkraefte:
        return "Es sind noch keine Lehrkräfte eingetragen. Sie kommen mit dem Stundenplan (/stundenplan)."
    zeilen = ["👩‍🏫 <b>Lehrkräfte</b>"]
    for lehrkraft in lehrkraefte:
        faecher = ", ".join(lehrkraft.faecher) or "kein Fach"
        zeilen.append(f"{escape(lehrkraft.name)} · {escape(faecher)} · {escape(lehrkraft.email or 'keine E-Mail')}")
    zeilen += ["", "E-Mail eintragen: <code>/lehrkraft Beispiel name@schule.de</code>"]
    return "\n".join(zeilen)
