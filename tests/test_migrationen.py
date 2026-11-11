"""REQ-000: nummerierte Datenbank-Migrationen mit Sicherung."""
import os
import sqlite3
import tempfile

import hilfen  # noqa: F401  (setzt Pfade)
from kern import datenbank, migrationen


def _tabellen(con):
    return {r[0]: r[1] for r in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def test_neue_datenbank_hat_stand_und_protokoll():
    ordner = tempfile.mkdtemp()
    con = datenbank.verbinden(os.path.join(ordner, "n.db"))
    assert migrationen.einrichten(con) == []
    assert migrationen.nummer(con) == migrationen.STAND
    assert con.execute("SELECT COUNT(*) FROM protokoll").fetchone()[0] == 1


def test_alte_datenbank_wird_gesichert_und_nachgezogen():
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, "alt.db")
    con = sqlite3.connect(pfad)
    con.execute("CREATE TABLE einstellungen (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL DEFAULT '')")
    con.execute("PRAGMA user_version = 0")
    con.commit()
    con.close()
    con = datenbank.verbinden(pfad)
    ausgefuehrt = migrationen.einrichten(con, pfad, os.path.join(ordner, "sich"), "0.1.0")
    assert ausgefuehrt == [n for n, _, _ in migrationen.SCHRITTE]
    assert len(os.listdir(os.path.join(ordner, "sich"))) == 1
    neu = datenbank.verbinden(os.path.join(ordner, "neu.db"))
    migrationen.einrichten(neu)
    assert set(_tabellen(con)) == set(_tabellen(neu))
    assert migrationen.nummer(con) == migrationen.nummer(neu) == migrationen.STAND


def test_zweiter_start_aendert_nichts():
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, "x.db")
    con = datenbank.verbinden(pfad)
    migrationen.einrichten(con, pfad, os.path.join(ordner, "s"))
    assert migrationen.einrichten(con, pfad, os.path.join(ordner, "s")) == []
    assert not os.path.exists(os.path.join(ordner, "s"))


def test_schritte_lueckenlos():
    nummern = [n for n, _, _ in migrationen.SCHRITTE]
    assert nummern == list(range(1, len(nummern) + 1))
