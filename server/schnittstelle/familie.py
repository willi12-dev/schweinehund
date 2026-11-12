"""Familie, Mitglieder und Einladungen (REQ-002).

Die App schickt ihren Schlüssel als „Authorization: Bearer …“. Ohne gültigen Schlüssel gibt es nur /version,
/api/status, die Einladungsseite und das Einlösen einer Einladung.
"""
import functools
import html
import json
import os

from flask import Blueprint, Response, g, jsonify, request

from kern import datenbank, familie, geraete

bp = Blueprint("familie", __name__)

# Fingerabdruck (SHA-256) der festen Test-Signatur der App – damit Android Einladungslinks direkt in der App öffnet.
APP_PAKET = "app.schweinehund"
APP_FINGERABDRUCK = os.environ.get(
    "APP_FINGERABDRUCK",
    "55:57:77:4E:8B:3B:CB:2C:5B:8C:AC:DA:62:9C:24:8C:0C:E0:65:32:BA:19:10:2F:20:F2:FD:8E:C3:75:AB:A7")
APK_LINK = "https://github.com/willi12-dev/schweinehund/releases/download/test/schweinehund-test.apk"


def fehler(text, code=400):
    return jsonify(ok=False, fehler=text), code


def schluessel_aus_anfrage():
    kopf = request.headers.get("Authorization", "")
    return kopf[7:].strip() if kopf.startswith("Bearer ") else ""


def angemeldet_noetig(fn):
    """Nur für angemeldete Familienmitglieder; das Mitglied steht danach in g.ich."""
    @functools.wraps(fn)
    def huelle(*args, **kwargs):
        ich = familie.angemeldet(datenbank.db(), schluessel_aus_anfrage())
        if ich is None:
            _abweisung_merken()
            return fehler("Nicht angemeldet – bitte den Einladungslink öffnen.", 401)
        g.ich = ich
        return fn(*args, **kwargs)
    return huelle


_abweisungen = []   # Zeitstempel (ein Prozess auf PA) – höchstens 60 Einträge pro Stunde ins Protokoll


def _abweisung_merken():
    """Fehlersuche 12.11.2026: Jede Abweisung (401) mit Pfad, Gerät und Schlüssel-Kennung ins Protokoll –
    so sieht man, ob ein alter Schlüssel, gar keiner oder ein unbekannter kam. Kennung = Anfang der Prüfsumme."""
    import time
    jetzt = time.time()
    _abweisungen[:] = [t for t in _abweisungen if t > jetzt - 3600]
    if len(_abweisungen) >= 60:
        return
    _abweisungen.append(jetzt)
    s = schluessel_aus_anfrage()
    kennung = familie.pruefsumme(s)[:8] if s else "ohne"
    geraet = request.headers.get("X-Geraet", "")[:12]
    con = datenbank.db()
    datenbank.protokoll(con, "Abgewiesen (401)", f"{request.method} {request.path} · Schlüssel {kennung} · {geraet}")
    con.commit()


def _familienfehler(fn):
    @functools.wraps(fn)
    def huelle(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except familie.FamilienFehler as e:
            return fehler(str(e), e.code)
    return huelle


def _link(code):
    return request.host_url.rstrip("/").replace("http://", "https://", 1) + "/e/" + code


def _daten():
    return request.get_json(silent=True) or {}


# ------------------------------------------------------------------ Gründen und Anmelden
@bp.post("/api/familie/gruenden")
@_familienfehler
def gruenden():
    if geraete.gebremst(geraete.adresse(request), topf="gruenden"):
        return fehler("Zu viele Versuche – bitte in ein paar Minuten noch einmal.", 429)
    d = _daten()
    con = datenbank.db()
    ich, schluessel = familie.gruenden(con, d.get("name"), d.get("farbe"), _geraet(d))
    datenbank.protokoll(con, "Familie gegründet", ich["name"])
    con.commit()
    return jsonify(ok=True, schluessel=schluessel, ich=familie.fuer_app(ich))


@bp.get("/api/einladung/<code>")
@_familienfehler
def einladung_ansehen(code):
    if geraete.gebremst(geraete.adresse(request), topf="einladung", grenze=20):
        return fehler("Zu viele Versuche – bitte in ein paar Minuten noch einmal.", 429)
    e = familie.einladung(datenbank.db(), code)
    return jsonify(ok=True, name=e["name"], farbe=e["farbe"])


@bp.post("/api/einladung/<code>")
@_familienfehler
def einladung_einloesen(code):
    if geraete.gebremst(geraete.adresse(request), topf="einladung", grenze=20):
        return fehler("Zu viele Versuche – bitte in ein paar Minuten noch einmal.", 429)
    con = datenbank.db()
    ich, schluessel = familie.einloesen(con, code, _geraet(_daten()))
    datenbank.protokoll(con, "Einladung eingelöst", f"{ich['name']} · Schlüssel {familie.pruefsumme(schluessel)[:8]}")
    con.commit()
    return jsonify(ok=True, schluessel=schluessel, ich=familie.fuer_app(ich))


def _geraet(d):
    g_id = str(d.get("geraet_id", "")).strip()
    return g_id if 8 <= len(g_id) <= 64 and g_id.replace("-", "").isalnum() else ""


# ------------------------------------------------------------------ Familie (angemeldet)
@bp.get("/api/familie")
@angemeldet_noetig
def uebersicht():
    con = datenbank.db()
    from kern import chat
    return jsonify(ok=True, ich=familie.fuer_app(g.ich), mitglieder=familie.uebersicht(con, g.ich),
                   chat_ungelesen=chat.ungelesen(con, g.ich), push_arten=chat.push_stand(g.ich))


@bp.post("/api/mitglieder")
@angemeldet_noetig
@_familienfehler
def mitglied_anlegen():
    d = _daten()
    con = datenbank.db()
    neu, code = familie.anlegen(con, g.ich, d.get("name"), d.get("farbe"))
    datenbank.protokoll(con, "Mitglied angelegt", neu["name"])
    con.commit()
    return jsonify(ok=True, mitglied=familie.fuer_app(neu), code=code, link=_link(code),
                   text=_einladungstext(neu["name"], code))


@bp.post("/api/mitglieder/<int:mitglied_id>/einladung")
@angemeldet_noetig
@_familienfehler
def neue_einladung(mitglied_id):
    con = datenbank.db()
    code = familie.einladen(con, g.ich, mitglied_id)
    m = familie.mitglied(con, mitglied_id)
    datenbank.protokoll(con, "Neue Einladung", m["name"])
    con.commit()
    return jsonify(ok=True, code=code, link=_link(code), text=_einladungstext(m["name"], code))


@bp.post("/api/ich")
@angemeldet_noetig
@_familienfehler
def ich_aendern():
    con = datenbank.db()
    d = _daten()
    ich = g.ich
    if "farbe" in d:
        ich = familie.farbe_aendern(con, ich, d.get("farbe"))
    con.commit()
    return jsonify(ok=True, ich=familie.fuer_app(ich))


def _einladungstext(name, code):
    return (f"Hallo {name}, du bist zur Schweinehund-Challenge eingeladen! 🐷\n"
            f"1. App installieren (falls noch nicht): {APK_LINK}\n"
            f"2. Diesen Link antippen: {_link(code)}\n"
            f"Oder in der App den Code eingeben: {code}\n"
            f"Der Link gilt {familie.GUELTIG_TAGE} Tage.")


# ------------------------------------------------------------------ Einladungsseite im Browser
@bp.get("/e/<code>")
def einladungsseite(code):
    """Öffnet Android den Link nicht direkt in der App, landet man hier: Knopf „In der App öffnen“ + Installation."""
    sauber = familie.code_normal(code)
    try:
        e = familie.einladung(datenbank.db(), sauber)
        titel = f"Hallo {html.escape(e['name'])}!"
        text = "Du bist zur Schweinehund-Challenge der Familie eingeladen."
        gueltig = True
    except familie.FamilienFehler as f:
        titel, text, gueltig = "Einladung nicht gültig", html.escape(str(f)), False
    host = request.host
    app_link = f"intent://{host}/e/{sauber}#Intent;scheme=https;package={APP_PAKET};end"
    knoepfe = (f'<a class="k" href="{html.escape(app_link)}">In der App öffnen</a>'
               f'<p>Noch keine App? <a href="{APK_LINK}">Schweinehund herunterladen</a>, installieren und diesen Link '
               f'noch einmal antippen – oder in der App den Code <b>{sauber}</b> eingeben.</p>') if gueltig else ""
    seite = f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Schweinehund – Einladung</title>
<style>body{{font-family:system-ui,sans-serif;background:#F3F4F7;color:#2E3340;margin:0;padding:32px 22px}}
.m{{font-weight:800;letter-spacing:.1em;font-size:14px}}.m span{{color:#EF7448}}h1{{font-size:30px;margin:28px 0 8px}}
p{{line-height:1.5;color:#454B5A}}.k{{display:block;text-align:center;background:#EF7448;color:#fff;font-weight:700;
padding:16px;border-radius:14px;text-decoration:none;margin:26px 0 18px}}a{{color:#EF7448}}</style></head>
<body><div class="m">SCHWEINEHUND<span>.</span></div><h1>{titel}</h1><p>{text}</p>{knoepfe}</body></html>"""
    return Response(seite, mimetype="text/html")


@bp.get("/.well-known/assetlinks.json")
def assetlinks():
    inhalt = [{"relation": ["delegate_permission/common.handle_all_urls"],
               "target": {"namespace": "android_app", "package_name": APP_PAKET,
                          "sha256_cert_fingerprints": [APP_FINGERABDRUCK]}}]
    return Response(json.dumps(inhalt), mimetype="application/json")
