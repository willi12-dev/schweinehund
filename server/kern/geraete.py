"""Geräte, die Push-Nachrichten empfangen (Token von Firebase)."""
import re
import time

from kern.datenbank import jetzt_text

TOKEN_MUSTER = re.compile(r"^[A-Za-z0-9_\-:.]{20,4096}$")
_versuche = {}            # IP -> Zeitstempel der letzten Probe-Anfragen (einfache Bremse, ein Prozess auf PA)
GRENZE, FENSTER = 5, 600  # höchstens 5 Proben je 10 Minuten


def gueltig(token):
    return bool(token) and bool(TOKEN_MUSTER.match(token))


def merken(con, token, plattform="android"):
    jetzt = jetzt_text()
    con.execute("INSERT INTO geraete (token, plattform, angelegt, zuletzt) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(token) DO UPDATE SET zuletzt = excluded.zuletzt, plattform = excluded.plattform",
                (token, plattform, jetzt, jetzt))


def anzahl(con):
    return con.execute("SELECT COUNT(*) FROM geraete").fetchone()[0]


def gebremst(ip, jetzt=None):
    """True, wenn diese Adresse in den letzten 10 Minuten schon zu oft gefragt hat (zählt die Anfrage mit)."""
    jetzt = jetzt if jetzt is not None else time.time()
    liste = [t for t in _versuche.get(ip, []) if t > jetzt - FENSTER]
    if len(liste) >= GRENZE:
        _versuche[ip] = liste
        return True
    _versuche[ip] = liste + [jetzt]
    return False
