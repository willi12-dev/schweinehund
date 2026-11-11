"""Tägliche Aufgabe auf PythonAnywhere (REQ-005): Sonntagsshow erstellen und Push an alle – genau einmal pro Woche.

PythonAnywhere startet das Skript täglich zur selben UTC-Uhrzeit (18:00 UTC = 19 Uhr Winter / 20 Uhr Sommer).
An anderen Tagen tut es nichts.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
os.environ["SCHWEINEHUND_KEIN_START"] = "1"

import app as server_app  # noqa: E402
from kern import datenbank, show  # noqa: E402


def main():
    a = server_app.erstellen()
    con = datenbank.verbinden(a.config["DATENBANK"])
    try:
        print("Sonntagsshow:", show.aufgabe(con))
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    main()
