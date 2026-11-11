"""Datenbank-Änderungen in nummerierten Schritten (Muster aus Zeugnis).

`schema.sql` beschreibt immer den vollständigen, aktuellen Stand – eine neue Datenbank entsteht direkt daraus und
bekommt die Nummer des letzten Schritts (`PRAGMA user_version`). Eine bestehende Datenbank durchläuft beim Start nur
die Schritte nach ihrer Nummer, jeden genau einmal. Vor dem ersten offenen Schritt wird die Datenbank gesichert.

Neue Änderung anlegen:
  1. schema.sql auf den neuen Stand bringen,
  2. hier eine Funktion _schritt_N(con) schreiben, die eine alte Datenbank dorthin bringt (nur ergänzen, nie löschen),
  3. sie in SCHRITTE eintragen – tests/test_migrationen.py prüft, dass alt + Schritte = neu.
"""
import os
import sqlite3
from datetime import datetime

from kern.datenbank import SERVER_DIR, TZ, protokoll


def _schritt_1(con):
    """Grundstand v0.1.0 – Tabellen entstehen aus schema.sql (CREATE … IF NOT EXISTS)."""


def _schritt_2(con):
    """v0.2.0 (REQ-001): Tabellen laeufe und entwuerfe – entstehen aus schema.sql."""


def _schritt_3(con):
    """v0.2.0: Garmin-Dateien ohne eigene Summen gelten als Schätzung, damit Health Connect sie korrigieren darf.
    Erkennbar an einer selbst gerechneten (nicht ganzzahligen) Distanz – Uhren liefern ganze Meter."""
    con.execute("UPDATE laeufe SET zahlen_quelle = 'datei-geschaetzt' "
                "WHERE zahlen_quelle = 'datei' AND distanz_m IS NOT NULL AND distanz_m != ROUND(distanz_m)")


SCHRITTE = [
    (1, "Grundstand v0.1.0: Einstellungen, Protokoll, Geräte", _schritt_1),
    (2, "v0.2.0: Läufe und Entwürfe (REQ-001)", _schritt_2),
    (3, "v0.2.0: Garmin-Zahlen als Schätzung markieren", _schritt_3),
]
STAND = SCHRITTE[-1][0]


def schema_text():
    with open(os.path.join(SERVER_DIR, "schema.sql"), encoding="utf-8") as f:
        return f.read()


def nummer(con):
    return con.execute("PRAGMA user_version").fetchone()[0]


def sichern(pfad, ordner, version):
    """Kopie der Datenbank vor einer Änderung."""
    os.makedirs(ordner, exist_ok=True)
    ziel = os.path.join(ordner, f"schweinehund_{datetime.now(TZ):%Y-%m-%d_%H%M%S}_v{version}_vor-aenderung.db")
    quelle, kopie = sqlite3.connect(pfad, timeout=30), sqlite3.connect(ziel)
    try:
        quelle.backup(kopie)
    finally:
        kopie.close()
        quelle.close()
    return ziel


def einrichten(con, pfad=None, sicherung_ordner=None, version="?"):
    """Datenbank auf den Stand dieser Version bringen. Ergebnis: Liste der ausgeführten Schritte."""
    frisch = not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'einstellungen'").fetchone()
    if frisch:
        con.executescript(schema_text())
        con.execute(f"PRAGMA user_version = {STAND}")
        protokoll(con, "Datenbank angelegt", f"Stand {STAND}")
        con.commit()
        return []
    offen = [s for s in SCHRITTE if s[0] > nummer(con)]
    if offen and pfad and sicherung_ordner:
        con.commit()
        sichern(pfad, sicherung_ordner, version)
    con.executescript(schema_text())
    for n, text, schritt in offen:
        schritt(con)
        con.execute(f"PRAGMA user_version = {n}")
        protokoll(con, f"Datenbank-Änderung {n}", text)
    con.commit()
    return [n for n, _, _ in offen]
