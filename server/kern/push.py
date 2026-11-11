"""Push-Nachrichten über Firebase Cloud Messaging (HTTP v1).

Firebase speichert keine Läufe – es stellt nur kurze Nachrichten zu. Der Server meldet sich mit dem Dienstkonto aus
dem Secret FIREBASE_KONTO an (JSON-Datei auf dem Server, Pfad in FIREBASE_KONTO_DATEI) und schickt die Nachricht an
das Geräte-Token, das die App gemeldet hat. Ohne Dienstkonto meldet push.status() „nicht eingerichtet“.
"""
import base64
import json
import os
import time

import requests

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_URL = "https://fcm.googleapis.com/v1/projects/{projekt}/messages:send"
_zugang = {"token": "", "bis": 0.0}


class PushFehler(Exception):
    """Die Nachricht konnte nicht zugestellt werden (Text ist für Menschen gedacht)."""


def konto_datei():
    return os.environ.get("FIREBASE_KONTO_DATEI", "").strip()


def konto():
    """Dienstkonto als dict – oder None, wenn Push nicht eingerichtet ist."""
    datei = konto_datei()
    if not datei or not os.path.isfile(datei):
        return None
    with open(datei, encoding="utf-8") as f:
        daten = json.load(f)
    if not all(daten.get(k) for k in ("project_id", "client_email", "private_key")):
        return None
    return daten


def status():
    return "bereit" if konto() else "nicht eingerichtet"


def _b64(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode()


def anmeldung_jwt(k, jetzt=None):
    """Signiertes JWT (RS256), mit dem sich das Dienstkonto bei Google meldet."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    jetzt = int(jetzt if jetzt is not None else time.time())
    kopf = {"alg": "RS256", "typ": "JWT"}
    inhalt = {"iss": k["client_email"], "scope": SCOPE, "aud": k.get("token_uri") or "https://oauth2.googleapis.com/token",
              "iat": jetzt, "exp": jetzt + 3600}
    teil = f"{_b64(json.dumps(kopf, separators=(',', ':')).encode())}.{_b64(json.dumps(inhalt, separators=(',', ':')).encode())}"
    schluessel = serialization.load_pem_private_key(k["private_key"].encode(), password=None)
    signatur = schluessel.sign(teil.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{teil}.{_b64(signatur)}"


def zugangstoken(k, post=None):
    post = post or requests.post
    if _zugang["token"] and _zugang["bis"] > time.time() + 60:
        return _zugang["token"]
    r = post(k.get("token_uri") or "https://oauth2.googleapis.com/token", timeout=20,
             data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": anmeldung_jwt(k)})
    if r.status_code != 200:
        raise PushFehler(f"Anmeldung bei Google fehlgeschlagen ({r.status_code}).")
    daten = r.json()
    _zugang.update(token=daten["access_token"], bis=time.time() + int(daten.get("expires_in", 3600)))
    return _zugang["token"]


def nachricht(geraet_token, titel, text, daten=None):
    m = {"message": {"token": geraet_token, "notification": {"title": titel, "body": text},
                     "android": {"priority": "high", "notification": {"channel_id": "familie"}}}}
    if daten:
        m["message"]["data"] = {str(k): str(v) for k, v in daten.items()}   # z. B. ziel=chat / ziel=lauf, lauf_id=12
    return m


def senden(geraet_token, titel, text, post=None, daten=None):
    post = post or requests.post
    k = konto()
    if not k:
        raise PushFehler("Push ist auf dem Server noch nicht eingerichtet (Secret FIREBASE_KONTO fehlt).")
    try:
        r = post(FCM_URL.format(projekt=k["project_id"]), timeout=20, json=nachricht(geraet_token, titel, text, daten),
                 headers={"Authorization": f"Bearer {zugangstoken(k, post)}"})
    except requests.RequestException as e:
        raise PushFehler(f"Firebase nicht erreichbar ({e.__class__.__name__}).")
    if r.status_code == 404 or (r.status_code == 400 and "registration" in r.text.lower()):
        raise PushFehler("Dieses Gerät ist bei Firebase nicht (mehr) bekannt.")
    if r.status_code != 200:
        raise PushFehler(f"Firebase lehnt die Nachricht ab ({r.status_code}).")
    return r.json().get("name", "")
