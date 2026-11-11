"""Sonntagsshow, Ruhmeshalle, Familienwette und Push-Anmeldung (REQ-005)."""
from flask import Blueprint, g, jsonify, request

from kern import datenbank, geraete, show
from schnittstelle.familie import angemeldet_noetig, fehler

bp = Blueprint("show", __name__)


def _nur_verwalter():
    return None if g.ich["rolle"] == "verwalter" else fehler("Das darf nur der Verwalter.", 403)


@bp.get("/api/show")
@angemeldet_noetig
def aktuelle():
    con = datenbank.db()
    d = show.aktuelle(con)
    con.commit()
    return jsonify(ok=True, show=d, wette=show.wette(con))


@bp.get("/api/show/<woche>")
@angemeldet_noetig
def eine(woche):
    d = show.holen(datenbank.db(), woche)
    return jsonify(ok=True, show=d) if d else fehler("Diese Show gibt es nicht.", 404)


@bp.get("/api/shows")
@angemeldet_noetig
def ruhmeshalle():
    return jsonify(ok=True, shows=show.ruhmeshalle(datenbank.db()))


@bp.post("/api/show/vorziehen")
@angemeldet_noetig
def vorziehen():
    nein = _nur_verwalter()
    if nein:
        return nein
    con = datenbank.db()
    d = show.vorziehen(con)
    datenbank.protokoll(con, "Sonntagsshow vorgezogen", d["woche"])
    con.commit()
    return jsonify(ok=True, show=d)


@bp.post("/api/familie/wette")
@angemeldet_noetig
def wette():
    nein = _nur_verwalter()
    if nein:
        return nein
    con = datenbank.db()
    text = show.wette_setzen(con, (request.get_json(silent=True) or {}).get("text"))
    datenbank.protokoll(con, "Familienwette", text or "(keine)")
    con.commit()
    return jsonify(ok=True, wette=text)


@bp.post("/api/ich/push")
@angemeldet_noetig
def push_merken():
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    if not geraete.gueltig(token):
        return fehler("Ungültiges Geräte-Token.")
    con = datenbank.db()
    con.execute("UPDATE mitglieder SET push_token = ? WHERE id = ?", (token, g.ich["id"]))
    con.commit()
    return jsonify(ok=True)
