"""Rangliste, Horst-o-Meter und eigener Fortschritt (REQ-004)."""
from flask import Blueprint, g, jsonify, request

from kern import datenbank, punkte
from schnittstelle.familie import angemeldet_noetig, fehler

bp = Blueprint("punkte", __name__)


@bp.get("/api/rangliste")
@angemeldet_noetig
def rangliste():
    art = request.args.get("zeitraum", "woche")
    if art not in ("woche", "monat"):
        return fehler("Zeitraum ist „woche“ oder „monat“.")
    return jsonify(ok=True, **punkte.uebersicht(datenbank.db(), g.ich["id"], art))


@bp.post("/api/familie/ziel")
@angemeldet_noetig
def ziel_setzen():
    if g.ich["rolle"] != "verwalter":
        return fehler("Das Familienziel stellt der Verwalter ein.", 403)
    con = datenbank.db()
    try:
        punkte.ziel_setzen(con, (request.get_json(silent=True) or {}).get("lk"))
    except (TypeError, ValueError) as e:
        return fehler(str(e) if isinstance(e, ValueError) and "Familienziel" in str(e) else "Bitte eine Zahl angeben.")
    datenbank.protokoll(con, "Familienziel", f"{punkte.ziel(con)} LK")
    con.commit()
    return jsonify(ok=True, horst=punkte.horst_o_meter(con))
