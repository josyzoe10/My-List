"""Startet den Bot.  Aufruf:  python main.py

Beenden mit Strg+C (auf dem Mac: Control+C).
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.error import InvalidToken, NetworkError

import config
from bot.datenbank import Datenbank
from bot.handler import baue_app


class _OhneFehlerdetails(logging.Filter):
    """Kürzt Meldungen der Telegram-Bibliothek zu Verbindungsproblemen."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        record.exc_text = None
        return True


def main() -> None:
    # Liest die Datei .env und stellt den Inhalt als Umgebungsvariablen bereit.
    load_dotenv()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or ":" not in token:
        sys.exit(
            "Es fehlt der Bot-Token.\n"
            "Starte zuerst die Einrichtung:  python einrichten.py\n"
            "Dort fügst du den Token ein, den du von @BotFather bekommen hast."
        )

    id_text = os.environ.get("TELEGRAM_USER_ID", "").strip()
    if id_text and not id_text.isdigit():
        sys.exit("TELEGRAM_USER_ID muss eine Zahl sein, z. B. 123456789. Korrigiere sie mit:  python einrichten.py")
    user_id = int(id_text) if id_text else None

    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%d.%m. %H:%M:%S", level=logging.INFO)
    # Diese Bibliothek würde sonst bei jeder Anfrage den geheimen Token ins Protokoll schreiben.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Der Zeitplaner meldet sonst jeden einzelnen Schritt.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    # Verbindungsfehler als eine Zeile statt als seitenlange Fehlermeldung.
    logging.getLogger("telegram.ext").addFilter(_OhneFehlerdetails())

    # Die Datenbank liegt immer im Ordner dieses Programms, egal von wo du es startest.
    db = Datenbank(str(Path(__file__).parent / config.DATENBANK_DATEI))
    app = baue_app(token, user_id, db)

    print("Verbinde mit Telegram ...")
    # Fragt Telegram in einer Schleife nach neuen Nachrichten, bis du das Programm beendest.
    try:
        app.run_polling(allowed_updates=["message", "callback_query"])
    except InvalidToken:
        sys.exit("Telegram kennt diesen Token nicht. Trag ihn neu ein mit:  python einrichten.py")
    except NetworkError as fehler:
        sys.exit(f"Keine Verbindung zu Telegram ({fehler}).\nPrüf deine Internetverbindung und starte den Bot neu.")


if __name__ == "__main__":
    main()
