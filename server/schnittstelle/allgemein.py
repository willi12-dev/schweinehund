"""Version und Status – damit App und Deploy prüfen können, was läuft."""
import os

from flask import Blueprint, jsonify

from kern import datenbank, familie, push, version

bp = Blueprint("allgemein", __name__)


@bp.get("/")
def start():
    return (f"Schweinehund-Server v{version.version()} läuft. Die App spricht mit /api/…\n",
            200, {"Content-Type": "text/plain; charset=utf-8"})


@bp.get("/version")
def version_anzeigen():
    return jsonify(version=version.version(), build=version.build(), umgebung=os.environ.get("UMGEBUNG", "LOKAL"))


@bp.get("/api/status")
def status():
    return jsonify(server="ok", version=version.version(), push=push.status(),
                   familie=familie.gegruendet(datenbank.db()))
