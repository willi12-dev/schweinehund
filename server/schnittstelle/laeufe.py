"""Läufe übernehmen und anzeigen (REQ-001)."""
import re

from flask import Blueprint, jsonify, request

from kern import bildtext, dateien, datenbank, laeufe, push

bp = Blueprint("laeufe", __name__, url_prefix="/api/laeufe")
GERAET = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def _fehler(text, code=400):
    return jsonify(ok=False, fehler=text), code


def _geraet(quelle):
    g = str(quelle.get("geraet_id", "")).strip()
    return g if GERAET.match(g) else None


@bp.post("/vorschau")
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
def bestaetigen():
    daten = request.get_json(silent=True) or {}
    geraet = _geraet(daten)
    if not geraet:
        return _fehler("Unbekanntes Gerät.")
    laeufer = str(daten.get("laeufer", "")).strip()[:40]
    con = datenbank.db()
    ergebnis = laeufe.bestaetigen(con, str(daten.get("entwurf", "")), geraet, laeufer)
    if ergebnis is None:
        return _fehler("Die Vorschau ist abgelaufen – bitte die Datei noch einmal teilen.", 410)
    lauf_id, neu = ergebnis
    datenbank.protokoll(con, "Lauf gespeichert" if neu else "Lauf ergänzt", f"Lauf {lauf_id}")
    con.commit()
    lauf = laeufe.detail(con, lauf_id, geraet)
    token = str(daten.get("push_token", "")).strip()
    if token and push.konto():
        try:
            push.senden(token, "Lauf angekommen", f"{lauf['distanz_km']} km in {lauf['dauer']} – Horst ist beeindruckt.")
        except push.PushFehler:
            pass
    return jsonify(ok=True, id=lauf_id, neu=neu,
                   text="Lauf gespeichert." if neu else "Mit dem vorhandenen Lauf zusammengeführt.", lauf=lauf)


@bp.post("/health-connect")
def health_connect():
    daten = request.get_json(silent=True) or {}
    geraet = _geraet(daten)
    if not geraet:
        return _fehler("Unbekanntes Gerät.")
    sitzungen = daten.get("sitzungen")
    if not isinstance(sitzungen, list):
        return _fehler("Keine Sitzungen übergeben.")
    con = datenbank.db()
    neu, ergaenzt = laeufe.aus_health_connect(con, geraet, str(daten.get("laeufer", "")).strip()[:40],
                                             [s for s in sitzungen if isinstance(s, dict)])
    if neu or ergaenzt:
        datenbank.protokoll(con, "Health Connect", f"{neu} neu, {ergaenzt} ergänzt")
    con.commit()
    return jsonify(ok=True, neu=neu, ergaenzt=ergaenzt)


@bp.get("")
def liste():
    geraet = _geraet(request.args)
    if not geraet:
        return _fehler("Unbekanntes Gerät.")
    return jsonify(ok=True, laeufe=laeufe.liste(datenbank.db(), geraet))


@bp.get("/<int:lauf_id>")
def detail(lauf_id):
    geraet = _geraet(request.args)
    lauf = laeufe.detail(datenbank.db(), lauf_id, geraet) if geraet else None
    return jsonify(ok=True, lauf=lauf) if lauf else _fehler("Lauf nicht gefunden.", 404)
