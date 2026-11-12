"""Notausgang: Der Verwalter kommt selbst nicht mehr in die App (App gelöscht oder neues Handy).

Auf PythonAnywhere: Reiter „Consoles“ → „Bash“ und dann
    python3 ~/schweinehund/verwalter_code.py
Das Skript zeigt einen neuen Einladungscode (7 Tage gültig, einmal). In der App „Mit Einladung beitreten“ eingeben.
Ein eventuell noch angemeldetes altes Handy des Verwalters wird dabei abgemeldet. Läufe und Daten bleiben.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
os.environ["SCHWEINEHUND_KEIN_START"] = "1"

import app as server_app  # noqa: E402
from kern import datenbank, familie  # noqa: E402


def main():
    a = server_app.erstellen()
    con = datenbank.verbinden(a.config["DATENBANK"])
    try:
        name, code = familie.verwalter_code(con)
        datenbank.protokoll(con, "Verwalter-Code", "über die Server-Konsole erzeugt")
        con.commit()
    finally:
        con.close()
    print(f"Neuer Code für {name}: {code}")
    print("In der App unter „Mit Einladung beitreten“ eingeben (7 Tage gültig, nur einmal).")


if __name__ == "__main__":
    main()
