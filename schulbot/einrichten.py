"""Legt die Datei .env mit deinen Geheimnissen an oder ändert sie.

Aufruf:  python einrichten.py

Die Datei .env bleibt nur auf deinem Gerät. Sie wird nie zu GitHub hochgeladen.
"""

import shutil
from pathlib import Path

from dotenv import dotenv_values, set_key

ORDNER = Path(__file__).parent
DATEI = ORDNER / ".env"
VORLAGE = ORDNER / ".env.example"


def frage(text: str, bisher: str, pruefung, fehlertext: str) -> str:
    """Fragt so lange, bis die Eingabe passt. Enter behält den alten Wert."""
    hinweis = f" [Enter = behalten: {bisher[:6]}…]" if bisher else ""
    while True:
        eingabe = input(f"{text}{hinweis}: ").strip() or bisher
        if pruefung(eingabe):
            return eingabe
        print(f"  {fehlertext}")


def main() -> None:
    if not DATEI.exists():
        shutil.copy(VORLAGE, DATEI)
    werte = dotenv_values(DATEI)

    print("Einrichtung deines Bots. Die Angaben werden in der Datei .env gespeichert.\n")
    token = frage(
        "1) Bot-Token von @BotFather",
        werte.get("TELEGRAM_BOT_TOKEN") or "",
        lambda t: ":" in t and " " not in t,
        "Das sieht nicht nach einem Token aus. Er hat die Form 123456789:ABC-DEF...",
    )
    print("\n   Deine Telegram-ID kennst du noch nicht? Dann drück einfach Enter,")
    print("   starte den Bot und schreib ihm. Er nennt dir die ID.")
    user_id = frage(
        "2) Deine Telegram-ID (eine Zahl)",
        werte.get("TELEGRAM_USER_ID") or "",
        lambda i: i == "" or i.isdigit(),
        "Die ID besteht nur aus Ziffern, z. B. 123456789.",
    )

    set_key(DATEI, "TELEGRAM_BOT_TOKEN", token)
    set_key(DATEI, "TELEGRAM_USER_ID", user_id)

    print("\nGespeichert. Starte den Bot jetzt mit:  python main.py")
    if not user_id:
        print("Danach: dem Bot schreiben, ID merken und dieses Programm noch einmal starten.")


if __name__ == "__main__":
    main()
