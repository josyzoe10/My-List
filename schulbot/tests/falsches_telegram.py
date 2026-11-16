"""Ein Ersatz für Telegram, damit die Tests ohne Internet und ohne Token laufen.

Der Bot "verschickt" seine Nachrichten an dieses Objekt. Die Tests schauen
dann nach, was er verschickt hätte.
"""

import json

from telegram import Update
from telegram.request import BaseRequest

ICH = 4242      # die erlaubte Telegram-ID in den Tests
FREMD = 6666    # jemand anderes


class FalschesTelegram(BaseRequest):
    def __init__(self):
        self.gesendet: list[tuple[str, dict]] = []
        self.blockiert = False  # True = so tun, als hättest du den Bot nie gestartet
        self.dateiinhalt = b""   # Inhalt der Datei, die der Bot als Nächstes herunterlädt
        self._naechste_id = 100

    @property
    def read_timeout(self):
        return 5.0

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **kwargs):
        if method == "GET":  # der Bot lädt eine Datei herunter
            return 200, self.dateiinhalt
        endpunkt = url.rsplit("/", 1)[-1]
        parameter = dict(request_data.parameters) if request_data else {}
        if endpunkt == "sendDocument":
            parameter["dateien"] = request_data.multipart_data
        self.gesendet.append((endpunkt, parameter))

        if endpunkt == "getMe":
            ergebnis = {"id": 999, "is_bot": True, "first_name": "Testbot", "username": "test_bot"}
        elif endpunkt == "getFile":
            ergebnis = {"file_id": "f1", "file_unique_id": "u1", "file_path": "documents/datei.csv"}
        elif endpunkt in ("sendMessage", "editMessageText", "sendDocument"):
            if self.blockiert:
                fehler = {"ok": False, "error_code": 403, "description": "Forbidden: bot can't initiate conversation"}
                return 403, json.dumps(fehler).encode()
            self._naechste_id += 1
            ergebnis = {
                "message_id": self._naechste_id,
                "date": 0,
                "chat": {"id": parameter.get("chat_id", ICH), "type": "private"},
                "text": parameter.get("text", ""),
            }
        else:
            ergebnis = True
        return 200, json.dumps({"ok": True, "result": ergebnis}).encode()

    # ----- Hilfen für die Tests ------------------------------------------

    def nachrichten(self) -> list[dict]:
        """Alles, was der Bot geschrieben oder geändert hat."""
        return [p for endpunkt, p in self.gesendet if endpunkt in ("sendMessage", "editMessageText")]

    def letzte(self) -> dict:
        return self.nachrichten()[-1]

    def letzte_knoepfe(self) -> list[tuple[str, str]]:
        """Die Knöpfe unter der letzten Nachricht als (Beschriftung, Daten)."""
        markup = self.letzte().get("reply_markup")
        if not markup:
            return []
        if isinstance(markup, str):
            markup = json.loads(markup)
        return [(k["text"], k["callback_data"]) for reihe in markup["inline_keyboard"] for k in reihe]


_zaehler = 0


def _nummer() -> int:
    global _zaehler
    _zaehler += 1
    return _zaehler


def _person(user_id: int) -> dict:
    return {"id": user_id, "is_bot": False, "first_name": "Test"}


def text_update(bot, text: str, user_id: int = ICH, chat_typ: str = "private") -> Update:
    """Baut eine Nachricht so, wie Telegram sie an den Bot schicken würde."""
    nachricht = {
        "message_id": _nummer(),
        "date": 0,
        "chat": {"id": user_id, "type": chat_typ},
        "from": _person(user_id),
        "text": text,
    }
    if text.startswith("/"):
        nachricht["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    return Update.de_json({"update_id": _nummer(), "message": nachricht}, bot)


def datei_update(bot, dateiname: str, user_id: int = ICH) -> Update:
    """Baut eine Nachricht mit einer angehängten Datei."""
    nachricht = {
        "message_id": _nummer(),
        "date": 0,
        "chat": {"id": user_id, "type": "private"},
        "from": _person(user_id),
        "document": {"file_id": "f1", "file_unique_id": "u1", "file_name": dateiname, "file_size": 500},
    }
    return Update.de_json({"update_id": _nummer(), "message": nachricht}, bot)


def knopf_update(bot, daten: str, user_id: int = ICH) -> Update:
    """Baut einen Knopfdruck."""
    return Update.de_json(
        {
            "update_id": _nummer(),
            "callback_query": {
                "id": str(_nummer()),
                "from": _person(user_id),
                "chat_instance": "test",
                "data": daten,
                "message": {
                    "message_id": _nummer(),
                    "date": 0,
                    "chat": {"id": user_id, "type": "private"},
                    "text": "alte Nachricht",
                },
            },
        },
        bot,
    )
