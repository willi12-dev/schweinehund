"""Datenbankverbindung und Einstellungen – die eine Stelle für den Datenbankpfad.

Zeitzone: immer Europe/Berlin über TZ / jetzt_text() – Server und GitHub-Runner laufen in UTC.
"""
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app, g

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # Ordner server/ (bzw. App-Ordner auf PA)
TZ = ZoneInfo("Europe/Berlin")


def jetzt_text():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def verbinden(pfad):
    con = sqlite3.connect(pfad, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def pfad():
    """Datei der Datenbank – die eine Stelle, an der das entschieden wird."""
    return current_app.config["DATENBANK"]


def db():
    """Eine Verbindung pro Anfrage."""
    if "db" not in g:
        g.db = verbinden(pfad())
    return g.db


def schliessen(_fehler=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def einstellung(con, schluessel, standard=""):
    zeile = con.execute("SELECT wert FROM einstellungen WHERE schluessel = ?", (schluessel,)).fetchone()
    return zeile["wert"] if zeile else standard


def einstellung_setzen(con, schluessel, wert):
    con.execute("INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES (?, ?)", (schluessel, str(wert)))


def protokoll(con, ereignis, details=""):
    con.execute("INSERT INTO protokoll (zeit, ereignis, details) VALUES (?, ?, ?)", (jetzt_text(), ereignis, details))
