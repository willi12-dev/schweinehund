"""Familienchat, Reaktionen, Kommentare und Push-Einstellungen (REQ-006)."""
import functools

from flask import Blueprint, g, jsonify, request

from kern import chat, datenbank
from schnittstelle.familie import angemeldet_noetig, fehler

bp = Blueprint("chat", __name__)


def _chatfehler(fn):
    @functools.wraps(fn)
    def huelle(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except chat.ChatFehler as e:
            return fehler(str(e), e.code)
    return huelle


def _daten():
    return request.get_json(silent=True) or {}


@bp.get("/api/chat")
@angemeldet_noetig
def liste():
    con = datenbank.db()
    nach = request.args.get("nach", default=0, type=int)
    return jsonify(ok=True, nachrichten=chat.liste(con, g.ich, nach), ungelesen=chat.ungelesen(con, g.ich))


@bp.post("/api/chat")
@angemeldet_noetig
@_chatfehler
def senden():
    con = datenbank.db()
    n = chat.senden(con, g.ich, _daten().get("text"))
    con.commit()
    return jsonify(ok=True, nachricht=n)


@bp.delete("/api/chat/<int:nachricht_id>")
@angemeldet_noetig
@_chatfehler
def loeschen(nachricht_id):
    con = datenbank.db()
    chat.loeschen(con, g.ich, nachricht_id)
    con.commit()
    return jsonify(ok=True)


@bp.post("/api/chat/gelesen")
@angemeldet_noetig
def gelesen():
    con = datenbank.db()
    try:
        chat.gelesen(con, g.ich, int(_daten().get("bis", 0)))
    except (TypeError, ValueError):
        return fehler("bis fehlt.")
    con.commit()
    return jsonify(ok=True, ungelesen=chat.ungelesen(con, g.ich))


@bp.get("/api/laeufe/<int:lauf_id>/reaktionen")
@angemeldet_noetig
def lauf_reaktionen(lauf_id):
    con = datenbank.db()
    return jsonify(ok=True, reaktionen=chat.reaktionen(con, [lauf_id], g.ich["id"]).get(lauf_id, []),
                   kommentare=chat.kommentare(con, lauf_id, g.ich["id"]))


@bp.post("/api/laeufe/<int:lauf_id>/reaktion")
@angemeldet_noetig
@_chatfehler
def reaktion(lauf_id):
    con = datenbank.db()
    r = chat.reaktion_umschalten(con, g.ich, lauf_id, _daten().get("emoji"))
    con.commit()
    return jsonify(ok=True, reaktionen=r)


@bp.post("/api/laeufe/<int:lauf_id>/kommentar")
@angemeldet_noetig
@_chatfehler
def kommentar(lauf_id):
    con = datenbank.db()
    k = chat.kommentieren(con, g.ich, lauf_id, _daten().get("text"))
    con.commit()
    return jsonify(ok=True, kommentare=k)


@bp.delete("/api/kommentare/<int:kommentar_id>")
@angemeldet_noetig
@_chatfehler
def kommentar_loeschen(kommentar_id):
    con = datenbank.db()
    chat.kommentar_loeschen(con, g.ich, kommentar_id)
    con.commit()
    return jsonify(ok=True)


@bp.get("/api/ich/push-arten")
@angemeldet_noetig
def push_arten():
    return jsonify(ok=True, arten=chat.push_stand(g.ich))


@bp.post("/api/ich/push-arten")
@angemeldet_noetig
@_chatfehler
def push_arten_setzen():
    d = _daten()
    con = datenbank.db()
    arten = chat.push_einstellen(con, g.ich, d.get("art"), bool(d.get("an")))
    con.commit()
    return jsonify(ok=True, arten=arten)
