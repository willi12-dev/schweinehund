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
from datetime import datetime, timedelta, timezone

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



def _schritt_4(con):
    """v0.2.0: Unplausible Schrittzahlen aus der Texterkennung (Diagramm-Achse statt Kachel) entfernen."""
    con.execute("UPDATE laeufe SET schritte = NULL WHERE schritte IS NOT NULL AND schritte < 100")



def _schritt_5(con):
    """v0.3.0 (REQ-002): Familie – Tabellen mitglieder/einladungen (aus schema.sql), Läufe bekommen ein Mitglied."""
    spalten = {z[1] for z in con.execute("PRAGMA table_info(laeufe)")}
    if "mitglied_id" not in spalten:
        con.execute("ALTER TABLE laeufe ADD COLUMN mitglied_id INTEGER")



def _schritt_6(con):
    """v0.4.0 (REQ-003): Sichtbarkeit pro Lauf und Standard pro Mitglied."""
    if "sichtbarkeit" not in {z[1] for z in con.execute("PRAGMA table_info(laeufe)")}:
        con.execute("ALTER TABLE laeufe ADD COLUMN sichtbarkeit TEXT NOT NULL DEFAULT 'familie'")
    if "standard_sichtbarkeit" not in {z[1] for z in con.execute("PRAGMA table_info(mitglieder)")}:
        con.execute("ALTER TABLE mitglieder ADD COLUMN standard_sichtbarkeit TEXT NOT NULL DEFAULT 'familie'")



# Testdatensatz der Familie (11.11.2026): Die beiden Praxistest-Läufe sollen in derselben Woche liegen, damit
# Familienseite und Rangliste etwas zu zeigen haben. Erkennbar nur an ihren Startzeiten (keine Namen im Repo).
TESTLAUF_VERSCHIEBEN = ("2026-06-01T04:11:00+00:00", "2026-06-01T04:16:00+00:00")   # Lauf 01.06. ~06:13 (Berlin)
TESTLAUF_FAMILIE = ("2026-11-10T09:20:00+00:00", "2026-11-10T09:25:00+00:00")       # Lauf 10.11. ~10:22 (Berlin)
VERSCHIEBUNG = timedelta(days=162, hours=1)   # 01.06. 06:13 Sommerzeit → 10.11. 06:13 Winterzeit


def _schritt_7(con):
    """v0.4.0: Testdatensatz – Praxistest-Lauf vom 01.06. auf den 10.11. legen, beide für die Familie sichtbar."""
    for z in con.execute("SELECT id, start FROM laeufe WHERE start BETWEEN ? AND ?", TESTLAUF_VERSCHIEBEN).fetchall():
        neu = (datetime.fromisoformat(z["start"]) + VERSCHIEBUNG).isoformat()
        con.execute("UPDATE laeufe SET start = ?, sichtbarkeit = 'familie' WHERE id = ?", (neu, z["id"]))
        protokoll(con, "Testdatensatz", f"Lauf {z['id']}: Start {z['start']} → {neu}")
    con.execute("UPDATE laeufe SET sichtbarkeit = 'familie' WHERE start BETWEEN ? AND ?", TESTLAUF_FAMILIE)



def _schritt_8(con):
    """v0.4.0: Testdatensatz – Läufe vom Handy des Praxistest-Laufs 10.11. (Testläufer B) dem eingeladenen, noch nicht
    beigetretenen Mitglied zuordnen. Nur eindeutig: genau ein Mitglied ohne Verwalter-Rolle."""
    z = con.execute("SELECT geraet_id FROM laeufe WHERE start BETWEEN ? AND ? AND mitglied_id IS NULL LIMIT 1",
                    TESTLAUF_FAMILIE).fetchone()
    kandidaten = con.execute("SELECT id FROM mitglieder WHERE rolle = 'mitglied'").fetchall()
    if z is None or len(kandidaten) != 1:
        return
    mitglied_id = kandidaten[0]["id"]
    n = con.execute("UPDATE laeufe SET mitglied_id = ? WHERE geraet_id = ? AND mitglied_id IS NULL",
                    (mitglied_id, z["geraet_id"])).rowcount
    con.execute("UPDATE mitglieder SET geraet_id = ? WHERE id = ? AND geraet_id = ''", (z["geraet_id"], mitglied_id))
    protokoll(con, "Testdatensatz", f"{n} Läufe Mitglied {mitglied_id} zugeordnet")



def _schritt_9(con):
    """v0.6.0 (REQ-005): Sonntagsshow – Tabelle shows (aus schema.sql), Push-Schlüssel am Mitglied."""
    if "push_token" not in {z[1] for z in con.execute("PRAGMA table_info(mitglieder)")}:
        con.execute("ALTER TABLE mitglieder ADD COLUMN push_token TEXT NOT NULL DEFAULT ''")



def _schritt_10(con):
    """v0.7.0 (REQ-006): Chat, Reaktionen, Kommentare (aus schema.sql), Push-Einstellungen am Mitglied."""
    spalten = {z[1] for z in con.execute("PRAGMA table_info(mitglieder)")}
    if "push_aus" not in spalten:
        con.execute("ALTER TABLE mitglieder ADD COLUMN push_aus TEXT NOT NULL DEFAULT ''")
    if "chat_gelesen" not in spalten:
        con.execute("ALTER TABLE mitglieder ADD COLUMN chat_gelesen INTEGER NOT NULL DEFAULT 0")


HORST_ALLES_SICHTBAR = ("Neu: Zu jedem Lauf passen jetzt bis zu drei Fotos – und „nur für mich“ gibt es nicht mehr. "
                        "Ab sofort sieht die Familie alle Strecken. Horst findet das übergriffig.")


def _schritt_11(con):
    """v0.8.0 (REQ-013): Tabelle fotos (aus schema.sql); „nur für mich“ entfällt – alle Läufe für die Familie sichtbar."""
    n = con.execute("UPDATE laeufe SET sichtbarkeit = 'familie' WHERE sichtbarkeit != 'familie'").rowcount
    con.execute("UPDATE mitglieder SET standard_sichtbarkeit = 'familie'")
    if n:
        protokoll(con, "Sichtbarkeit aufgehoben", f"{n} Läufe jetzt für die Familie sichtbar")
    if con.execute("SELECT 1 FROM mitglieder LIMIT 1").fetchone():
        con.execute("INSERT INTO nachrichten (mitglied_id, text, lauf_id, zeit) VALUES (NULL, ?, NULL, ?)",
                    (HORST_ALLES_SICHTBAR, datetime.now(timezone.utc).isoformat(timespec="seconds")))


# Indizes auf Spalten, die erst ein Schritt anlegt – laufen nach den Schritten (auch bei neuer Datenbank).
NACHLAUF = "CREATE INDEX IF NOT EXISTS laeufe_mitglied_start ON laeufe (mitglied_id, start);"


SCHRITTE = [
    (1, "Grundstand v0.1.0: Einstellungen, Protokoll, Geräte", _schritt_1),
    (2, "v0.2.0: Läufe und Entwürfe (REQ-001)", _schritt_2),
    (3, "v0.2.0: Garmin-Zahlen als Schätzung markieren", _schritt_3),
    (4, "v0.2.0: unplausible Schrittzahlen entfernen", _schritt_4),
    (5, "v0.3.0: Familie und Mitglieder (REQ-002)", _schritt_5),
    (6, "v0.4.0: Sichtbarkeit pro Lauf (REQ-003)", _schritt_6),
    (7, "v0.4.0: Testdatensatz – Praxistest-Läufe in dieselbe Woche", _schritt_7),
    (8, "v0.4.0: Testdatensatz – Läufe dem eingeladenen Mitglied zuordnen", _schritt_8),
    (9, "v0.6.0: Sonntagsshow (REQ-005)", _schritt_9),
    (10, "v0.7.0: Chat, Reaktionen, Kommentare (REQ-006)", _schritt_10),
    (11, "v0.8.0: Fotos zum Lauf, alle Läufe sichtbar (REQ-013)", _schritt_11),
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
        con.executescript(NACHLAUF)
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
    con.executescript(NACHLAUF)
    con.commit()
    return [n for n, _, _ in offen]
