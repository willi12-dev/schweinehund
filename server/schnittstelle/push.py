"""Push-Probe (REQ-000): Die App meldet ihr Geräte-Token, der Server schickt sofort eine Testnachricht zurück."""
from flask import Blueprint, jsonify, request

from kern import datenbank, geraete, push

bp = Blueprint("push", __name__, url_prefix="/api/push")


@bp.post("/probe")
def probe():
    daten = request.get_json(silent=True) or {}
    token = str(daten.get("token", "")).strip()
    if not geraete.gueltig(token):
        return jsonify(ok=False, fehler="Ungültiges Geräte-Token."), 400
    if geraete.gebremst(request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()):
        return jsonify(ok=False, fehler="Zu viele Proben – bitte in ein paar Minuten noch einmal."), 429
    con = datenbank.db()
    geraete.merken(con, token, str(daten.get("plattform", "android"))[:20])
    try:
        push.senden(token, "Schweinehund", "Test-Push angekommen. Horst ist wach – leider.")
    except push.PushFehler as e:
        datenbank.protokoll(con, "Push-Probe fehlgeschlagen", str(e))
        con.commit()
        return jsonify(ok=False, fehler=str(e)), 502
    datenbank.protokoll(con, "Push-Probe gesendet")
    con.commit()
    return jsonify(ok=True)
