"""Läufe übernehmen und anzeigen (REQ-001) – seit REQ-002 nur für angemeldete Familienmitglieder."""
import re

from flask import Blueprint, g, jsonify, request

from kern import bildtext, dateien, datenbank, laeufe, push
from schnittstelle.familie import angemeldet_noetig

bp = Blueprint("laeufe", __name__, url_prefix="/api/laeufe")
GERAET = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def _fehler(text, code=400):
    return jsonify(ok=False, fehler=text), code


def _wem(quelle):
    geraet = str(quelle.get("geraet_id", "")).strip()
    return laeufe.besitzer(g.ich, geraet if GERAET.match(geraet) else "")


@bp.post("/vorschau")
@angemeldet_noetig
def vorschau():
    """Datei (Formularfeld „datei“) oder erkannter Bildtext ({"text": …}) → Kontrollkarte."""
    con = datenbank.db()
    datei = request.files.get("datei")
    if datei is not None:
        try:
            lauf = dateien.lesen(datei.read(), datei.filename or "")
        except dateien.DateiFehler as e:
            return _fehler(str(e), 422)
        quelle = "datei"
    else:
        daten = request.get_json(silent=True) or {}
        text = str(daten.get("text", ""))[:20000]
        lauf = bildtext.lesen(text) if text.strip() else None
        if lauf is None:
            return _fehler("Auf dem Bild wurden keine Laufwerte erkannt (Distanz oder Dauer fehlen).", 422)
        quelle = "bild"
    if not lauf.get("start"):
        return _fehler("Der Lauf hat keine erkennbare Startzeit.", 422)
    eid = laeufe.entwurf_anlegen(con, lauf, quelle)
    con.commit()
    return jsonify(ok=True, entwurf=eid, lauf=laeufe.fuer_app(lauf, [quelle]))


@bp.post("/bestaetigen")
@angemeldet_noetig
def bestaetigen():
    daten = request.get_json(silent=True) or {}
    con = datenbank.db()
    ergebnis = laeufe.bestaetigen(con, str(daten.get("entwurf", "")), _wem(daten), daten.get("sichtbarkeit"))
    if ergebnis is None:
        return _fehler("Die Vorschau ist abgelaufen – bitte die Datei noch einmal teilen.", 410)
    lauf_id, neu = ergebnis
    datenbank.protokoll(con, "Lauf gespeichert" if neu else "Lauf ergänzt", f"Lauf {lauf_id}")
    con.commit()
    lauf = laeufe.detail(con, lauf_id, g.ich["id"])
    token = str(daten.get("push_token", "")).strip()
    if token and push.konto():
        try:
            push.senden(token, "Lauf angekommen", f"{lauf['distanz_km']} km in {lauf['dauer']} – Horst ist beeindruckt.")
        except push.PushFehler:
            pass
    return jsonify(ok=True, id=lauf_id, neu=neu,
                   text="Lauf gespeichert." if neu else "Mit dem vorhandenen Lauf zusammengeführt.", lauf=lauf)


@bp.post("/health-connect")
@angemeldet_noetig
def health_connect():
    daten = request.get_json(silent=True) or {}
    sitzungen = daten.get("sitzungen")
    if not isinstance(sitzungen, list):
        return _fehler("Keine Sitzungen übergeben.")
    con = datenbank.db()
    neu, ergaenzt = laeufe.aus_health_connect(con, _wem(daten), [s for s in sitzungen if isinstance(s, dict)])
    if neu or ergaenzt:
        datenbank.protokoll(con, "Health Connect", f"{neu} neu, {ergaenzt} ergänzt")
    con.commit()
    return jsonify(ok=True, neu=neu, ergaenzt=ergaenzt)


@bp.get("")
@angemeldet_noetig
def liste():
    """Eigene Läufe – oder mit ?mitglied=<id> die Läufe eines anderen Familienmitglieds."""
    wer = request.args.get("mitglied", type=int) or g.ich["id"]
    return jsonify(ok=True, laeufe=laeufe.liste(datenbank.db(), wer, g.ich["id"]))


@bp.get("/familie")
@angemeldet_noetig
def familie_liste():
    return jsonify(ok=True, laeufe=laeufe.familie_liste(datenbank.db(), g.ich["id"]))


_STAND = {"fehlt": ("Lauf nicht gefunden.", 404), "fremd": ("Das ist nicht dein Lauf.", 403),
          "ungueltig": ("Unbekannte Sichtbarkeit.", 400)}


@bp.post("/<int:lauf_id>/sichtbarkeit")
@angemeldet_noetig
def sichtbarkeit(lauf_id):
    con = datenbank.db()
    stand = laeufe.sichtbarkeit_setzen(con, lauf_id, g.ich["id"], (request.get_json(silent=True) or {}).get("sichtbarkeit"))
    if stand != "ok":
        return _fehler(*_STAND[stand])
    con.commit()
    return jsonify(ok=True, lauf=laeufe.detail(con, lauf_id, g.ich["id"]))


@bp.delete("/<int:lauf_id>")
@angemeldet_noetig
def loeschen(lauf_id):
    con = datenbank.db()
    stand = laeufe.loeschen(con, lauf_id, g.ich["id"])
    if stand != "ok":
        return _fehler(*_STAND[stand])
    datenbank.protokoll(con, "Lauf gelöscht", f"Lauf {lauf_id}")
    con.commit()
    return jsonify(ok=True)


@bp.get("/<int:lauf_id>")
@angemeldet_noetig
def detail(lauf_id):
    lauf = laeufe.detail(datenbank.db(), lauf_id, g.ich["id"])
    return jsonify(ok=True, lauf=lauf) if lauf else _fehler("Lauf nicht gefunden.", 404)
