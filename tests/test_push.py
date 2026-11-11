"""REQ-000: Push-Probe über Firebase – ohne echtes Netz (Anfragen werden abgefangen)."""
import base64
import json
import os
import tempfile

from hilfen import neuer_server

from kern import geraete, push

TOKEN = "fGeraetTokenBeispiel_1234567890:APA91b-abc"


def _konto_datei():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    schluessel = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = schluessel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()).decode()
    pfad = os.path.join(tempfile.mkdtemp(), "konto.json")
    json.dump({"project_id": "schweinehund-test", "client_email": "push@schweinehund-test.iam.gserviceaccount.com",
               "private_key": pem, "token_uri": "https://oauth2.googleapis.com/token"}, open(pfad, "w"))
    return pfad, schluessel.public_key()


class Antwort:
    def __init__(self, code, daten=None, text=""):
        self.status_code, self._d, self.text = code, daten or {}, text

    def json(self):
        return self._d


def test_jwt_ist_gueltig_signiert():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    pfad, oeffentlich = _konto_datei()
    os.environ["FIREBASE_KONTO_DATEI"] = pfad
    jwt = push.anmeldung_jwt(push.konto(), jetzt=1_700_000_000)
    kopf, inhalt, sig = jwt.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    daten = json.loads(base64.urlsafe_b64decode(pad(inhalt)))
    assert daten["scope"] == push.SCOPE and daten["exp"] - daten["iat"] == 3600
    oeffentlich.verify(base64.urlsafe_b64decode(pad(sig)), f"{kopf}.{inhalt}".encode(), padding.PKCS1v15(), hashes.SHA256())


def test_probe_schickt_nachricht_an_firebase():
    pfad, _ = _konto_datei()
    push._zugang.update(token="", bis=0)
    geraete._versuche.clear()
    _, c, _ = neuer_server(FIREBASE_KONTO_DATEI=pfad)
    gesendet = []

    def post(url, **kw):
        gesendet.append((url, kw))
        if "oauth2" in url:
            return Antwort(200, {"access_token": "zugang", "expires_in": 3600})
        return Antwort(200, {"name": "projects/schweinehund-test/messages/1"})

    alt = push.requests.post
    push.requests.post = post
    try:
        r = c.post("/api/push/probe", json={"token": TOKEN})
    finally:
        push.requests.post = alt
    assert r.status_code == 200 and r.get_json() == {"ok": True}, r.get_json()
    url, kw = gesendet[-1]
    assert url.endswith("/projects/schweinehund-test/messages:send")
    assert kw["json"]["message"]["token"] == TOKEN
    assert kw["headers"]["Authorization"] == "Bearer zugang"


def test_probe_ohne_konto_meldet_klaren_fehler():
    geraete._versuche.clear()
    _, c, _ = neuer_server(FIREBASE_KONTO_DATEI="")
    r = c.post("/api/push/probe", json={"token": TOKEN})
    assert r.status_code == 502 and "noch nicht eingerichtet" in r.get_json()["fehler"]


def test_probe_lehnt_unsinniges_token_ab():
    _, c, _ = neuer_server()
    assert c.post("/api/push/probe", json={"token": "<script>"}).status_code == 400
    assert c.post("/api/push/probe", data="kein json").status_code == 400


def test_bremse_nach_fuenf_proben():
    geraete._versuche.clear()
    ergebnisse = [geraete.gebremst("1.2.3.4", jetzt=1000 + i) for i in range(6)]
    assert ergebnisse == [False] * 5 + [True]
    assert geraete.gebremst("1.2.3.4", jetzt=1000 + geraete.FENSTER + 10) is False
