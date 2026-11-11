"""Schweinehund-Server: Start, Konfiguration, Blueprints.

Läuft lokal (`python server/app.py`) und auf PythonAnywhere (WSGI importiert `app`).
Einstellungen kommen aus der Umgebung bzw. aus der Datei .env im selben Ordner (schreibt das Deploy-Skript).
"""
import os
import sys

from flask import Flask

HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)

from kern import datenbank, migrationen, version  # noqa: E402
from schnittstelle import allgemein, familie, laeufe, punkte, push, show  # noqa: E402


def _env_laden(pfad):
    if not os.path.isfile(pfad):
        return
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile and not zeile.startswith("#") and "=" in zeile:
                k, v = zeile.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def erstellen(datenbank_pfad=None, sicherung_ordner=None):
    _env_laden(os.path.join(HIER, ".env"))
    app = Flask(__name__)
    app.config["DATENBANK"] = datenbank_pfad or os.environ.get("DATENBANK") or os.path.join(HIER, "schweinehund.db")
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
    app.json.ensure_ascii = False
    ordner = sicherung_ordner or os.path.join(os.path.dirname(app.config["DATENBANK"]), "sicherungen")
    con = datenbank.verbinden(app.config["DATENBANK"])
    try:
        migrationen.einrichten(con, app.config["DATENBANK"], ordner, version.version())
    finally:
        con.close()
    app.register_blueprint(allgemein.bp)
    app.register_blueprint(push.bp)
    app.register_blueprint(laeufe.bp)
    app.register_blueprint(familie.bp)
    app.register_blueprint(punkte.bp)
    app.register_blueprint(show.bp)
    app.teardown_appcontext(datenbank.schliessen)
    return app


app = erstellen() if __name__ != "__main__" and os.environ.get("SCHWEINEHUND_KEIN_START") != "1" else None

if __name__ == "__main__":
    erstellen().run(port=int(os.environ.get("PORT", "5000")), debug=True)
