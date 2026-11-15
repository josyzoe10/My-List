"""Baut die Texte, die der Bot verschickt (Morgennachricht, Listen, Bestätigungen).

Hier wird nichts gespeichert und nichts verschickt. Die Funktionen bekommen
Aufgaben und das heutige Datum und geben fertigen Text zurück.
Der Text nutzt ein bisschen HTML, weil Telegram damit fett schreiben kann.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from html import escape

from bot.datenbank import Aufgabe

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

def tagesuebersicht(aufgaben: list[Aufgabe], heute: date, kopf: str, ausblick_tage: int) -> str:
    """Die Übersicht für heute. Wird für /heute und die Morgennachricht benutzt."""
    zeilen = [kopf, ""]
    zeilen += _ueberfaellig_block(aufgaben, heute)

    heutige = [a for a in aufgaben if a.faellig_am == heute]
    ereignisse = nach_uhrzeit([a for a in heutige if a.art in _EREIGNISSE])
    zu_erledigen = nach_prioritaet([a for a in heutige if a.art not in _EREIGNISSE])
    if ereignisse:
        zeilen += ["📅 <b>Termine heute</b>"] + [zeile(a) for a in ereignisse] + [""]
    if zu_erledigen:
        zeilen += ["📋 <b>Heute zu erledigen</b>"] + [zeile(a) for a in zu_erledigen] + [""]
    if not heutige:
        zeilen += ["Für heute ist nichts eingetragen. 🎉", ""]

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


def morgennachricht(aufgaben: list[Aufgabe], heute: date, ausblick_tage: int) -> str:
    kopf = f"☀️ <b>Guten Morgen!</b> Heute ist {datum_lang(heute)}"
    return tagesuebersicht(aufgaben, heute, kopf, ausblick_tage)


def heute_liste(aufgaben: list[Aufgabe], heute: date, ausblick_tage: int) -> str:
    return tagesuebersicht(aufgaben, heute, f"📆 <b>Heute, {datum_lang(heute)}</b>", ausblick_tage)


def tag_liste(aufgaben: list[Aufgabe], tag: date, heute: date) -> str:
    """Was an einem bestimmten Tag ansteht, z. B. für /morgen."""
    wann = datum_nah(tag, heute)
    kopf = f"📆 <b>{wann.capitalize()}, {datum_lang(tag)}</b>" if wann in ("heute", "morgen") else f"📆 <b>{datum_lang(tag)}</b>"
    eintraege = [a for a in aufgaben if a.faellig_am == tag]
    if not eintraege:
        return f"{kopf}\n\nDa ist nichts eingetragen. 🎉"
    return "\n".join([kopf, ""] + _tagesblock(eintraege))


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


def bestaetigung(aufgabe: Aufgabe, heute: date, kopf: str = "✅ Gespeichert") -> str:
    """Kurze Rückmeldung, wie der Bot etwas einsortiert hat."""
    teile = [f"{ART_SYMBOLE[aufgabe.art]} {ART_NAMEN[aufgabe.art]}"]
    if aufgabe.fach:
        teile.append(escape(aufgabe.fach))
    if aufgabe.faellig_am:
        wann = datum_nah(aufgabe.faellig_am, heute)
        if wann in ("heute", "morgen"):
            wann += f" ({datum_kurz(aufgabe.faellig_am, heute)})"
        if aufgabe.uhrzeit:
            wann += f" um {aufgabe.uhrzeit:%H:%M}"
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


def hilfe(name: str, morgens: tuple[int, int]) -> str:
    return (
        f"Hi, ich bin <b>{escape(name)}</b>, dein Assistent für Schule und Alltag. 👋\n\n"
        "Schreib mir einfach, was ansteht, zum Beispiel:\n"
        "• Bio-Referat bis Freitag\n"
        "• morgen 15 Uhr Zahnarzt\n"
        "• Mathe-Klausur am 3.12.\n"
        "• Mathe S. 45 Nr. 3\n\n"
        "Ich sage dir, wie ich es einsortiert habe, und du kannst es per Knopf korrigieren.\n\n"
        "<b>Befehle</b>\n"
        "/heute – was heute ansteht\n"
        "/morgen – was morgen ansteht\n"
        "/woche – die nächsten 7 Tage\n"
        "/alle – alles Offene\n"
        "/erledigt – etwas abhaken\n"
        "/hilfe – diese Übersicht\n\n"
        f"Jeden Morgen um {morgens[0]}:{morgens[1]:02d} Uhr schicke ich dir deine Übersicht."
    )
