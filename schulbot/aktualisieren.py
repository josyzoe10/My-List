"""Holt die neueste Version des Bots von GitHub.

Aufruf:  python aktualisieren.py

Deine Geheimnisse (.env) und deine Einträge (schulbot.db) bleiben unverändert.
Beende den Bot vorher mit Strg+C und starte ihn danach wieder mit python main.py.
"""

import io
import subprocess
import sys
import zipfile
from pathlib import Path

import httpx

ZIP_ADRESSE = (
    "https://github.com/josyzoe10/My-List/archive/refs/heads/"
    "claude/personal-school-assistant-bot-w6ow46.zip"
)
ORDNER = Path(__file__).resolve().parent


def main() -> None:
    print("Lade die neueste Version von GitHub ...")
    try:
        antwort = httpx.get(ZIP_ADRESSE, follow_redirects=True, timeout=60)
        antwort.raise_for_status()
    except httpx.HTTPError as fehler:
        sys.exit(f"Das Herunterladen hat nicht geklappt ({fehler}). Prüf deine Internetverbindung.")

    geaendert = 0
    with zipfile.ZipFile(io.BytesIO(antwort.content)) as archiv:
        for eintrag in archiv.infolist():
            # Im Archiv heißen die Dateien "<Ordnername>/schulbot/...". Nur die brauchen wir.
            teile = Path(eintrag.filename).parts
            if eintrag.is_dir() or len(teile) < 3 or teile[1] != "schulbot":
                continue
            ziel = ORDNER.joinpath(*teile[2:]).resolve()
            if ORDNER not in ziel.parents:
                continue  # Sicherheit: nichts außerhalb dieses Ordners schreiben
            neu = archiv.read(eintrag)
            if ziel.exists() and ziel.read_bytes() == neu:
                continue
            if ziel.name == "config.py" and ziel.exists():
                # Deine bisherigen Einstellungen bleiben als Kopie erhalten.
                (ORDNER / "config_alt.py").write_bytes(ziel.read_bytes())
                print("Hinweis: config.py wurde erneuert. Falls du dort selbst etwas geändert hattest,")
                print("         findest du deine alte Fassung in config_alt.py.")
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(neu)
            geaendert += 1

    if geaendert == 0:
        print("Du hast schon die neueste Version.")
        return
    print(f"{geaendert} Dateien aktualisiert. Prüfe die Bibliotheken ...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(ORDNER / "requirements.txt")], check=False)
    print("Fertig. Starte den Bot jetzt mit:  python main.py")


if __name__ == "__main__":
    main()
