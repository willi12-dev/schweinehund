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


def test_laeufe_aus_v020_bekommen_mitglied_spalte():
    """Datenbank von v0.2.0 (Läufe ohne Mitglied) → Schritt 5 ergänzt die Spalte, Läufe bleiben erhalten."""
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, "v020.db")
    con = sqlite3.connect(pfad)
    alt = migrationen.schema_text().split("-- REQ-002: Familie")[0].replace(
        "    mitglied_id   INTEGER,                    -- REQ-002: wem der Lauf gehört (NULL = Handy noch nicht angemeldet)\n", "")
    con.executescript(alt)
    con.execute("INSERT INTO laeufe (geraet_id, start, angelegt, geaendert) VALUES ('geraet-alt-0001', '2026-06-01T04:13:06+00:00', 'x', 'x')")
    con.execute("PRAGMA user_version = 4")
    con.commit()
    con.close()
    con = datenbank.verbinden(pfad)
    assert migrationen.einrichten(con, pfad, os.path.join(ordner, "sich"), "0.2.0") == [5, 6, 7, 8]
    spalten = {z[1] for z in con.execute("PRAGMA table_info(laeufe)")}
    assert "mitglied_id" in spalten and con.execute("SELECT COUNT(*) FROM laeufe").fetchone()[0] == 1
    assert con.execute("SELECT 1 FROM sqlite_master WHERE name = 'laeufe_mitglied_start'").fetchone()


def test_v030_bekommt_sichtbarkeit():
    """Datenbank von v0.3.0 → Schritt 6 ergänzt Sichtbarkeit an Läufen und Standard an Mitgliedern."""
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, "v030.db")
    con = sqlite3.connect(pfad)
    alt = migrationen.schema_text()
    alt = alt.replace("    sichtbarkeit  TEXT NOT NULL DEFAULT 'familie',  -- REQ-003: 'familie' oder 'ich' (Strecke nur für den Läufer)\n", "")
    alt = alt.replace("    beigetreten TEXT,\n    standard_sichtbarkeit TEXT NOT NULL DEFAULT 'familie'   -- REQ-003: Sichtbarkeit neuer Läufe\n",
                      "    beigetreten TEXT\n")
    assert "sichtbarkeit" not in alt
    con.executescript(alt)
    con.execute("INSERT INTO laeufe (geraet_id, start, angelegt, geaendert) VALUES ('g-alt-0001', '2026-06-01T04:13:06+00:00', 'x', 'x')")
    con.execute("PRAGMA user_version = 5")
    con.commit()
    con.close()
    con = datenbank.verbinden(pfad)
    assert migrationen.einrichten(con, pfad, os.path.join(ordner, "sich"), "0.3.0") == [6, 7, 8]
    assert con.execute("SELECT sichtbarkeit FROM laeufe").fetchone()[0] == "familie"
    assert "standard_sichtbarkeit" in {z[1] for z in con.execute("PRAGMA table_info(mitglieder)")}


def test_testdatensatz_legt_praxislaeufe_in_dieselbe_woche():
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, "v6.db")
    con = datenbank.verbinden(pfad)
    migrationen.einrichten(con)
    for start, sicht in (("2026-06-01T04:13:06+00:00", "ich"), ("2026-11-10T09:22:28+00:00", "ich"), ("2026-05-28T03:42:46+00:00", "ich")):
        con.execute("INSERT INTO laeufe (geraet_id, start, sichtbarkeit, angelegt, geaendert) VALUES ('g', ?, ?, 'x', 'x')", (start, sicht))
    con.execute("PRAGMA user_version = 6")
    con.commit()
    assert migrationen.einrichten(con, pfad, os.path.join(ordner, "s"), "0.4.0") == [7, 8]
    zeilen = [tuple(z) for z in con.execute("SELECT start, sichtbarkeit FROM laeufe ORDER BY id")]
    assert zeilen == [("2026-11-10T05:13:06+00:00", "familie"), ("2026-11-10T09:22:28+00:00", "familie"),
                      ("2026-05-28T03:42:46+00:00", "ich")]


def test_testdatensatz_ordnet_laeufe_dem_eingeladenen_mitglied_zu():
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, "v7.db")
    con = datenbank.verbinden(pfad)
    migrationen.einrichten(con)
    con.execute("INSERT INTO mitglieder (name, farbe, kuerzel, rolle, angelegt) VALUES ('A', '#EF7448', 'A', 'verwalter', 'x')")
    con.execute("INSERT INTO mitglieder (name, farbe, kuerzel, rolle, angelegt) VALUES ('B', '#5B8DEF', 'B', 'mitglied', 'x')")
    for g, start in (("g-b", "2026-11-10T09:22:28+00:00"), ("g-b", "2026-10-01T09:00:00+00:00"), ("g-c", "2026-10-02T09:00:00+00:00")):
        con.execute("INSERT INTO laeufe (geraet_id, start, angelegt, geaendert) VALUES (?, ?, 'x', 'x')", (g, start))
    con.execute("PRAGMA user_version = 7")
    con.commit()
    assert migrationen.einrichten(con, pfad, os.path.join(ordner, "s"), "0.4.0") == [8]
    assert [tuple(z) for z in con.execute("SELECT geraet_id, mitglied_id FROM laeufe ORDER BY id")] == [("g-b", 2), ("g-b", 2), ("g-c", None)]
    assert con.execute("SELECT geraet_id FROM mitglieder WHERE id = 2").fetchone()[0] == "g-b"
