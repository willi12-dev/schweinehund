"""REQ-001: Läufe aus GPX, TCX, Bildtext und Health Connect – mit den (anonymisierten) echten Huawei-Exporten."""
import io
import os

from hilfen import WURZEL, neuer_server

from kern import bildtext, dateien, geraete, laeufe, push

DATEN = os.path.join(WURZEL, "tests", "daten")
GERAET = "geraet-test-0001"


def _datei(name):
    with open(os.path.join(DATEN, name), "rb") as f:
        return f.read()


def _text(name):
    with open(os.path.join(DATEN, name), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ Dateien lesen
def test_gpx_werte_wie_auf_der_uhr():
    l = dateien.lesen(_datei("huawei_lauf_a.gpx"))
    assert len(l["punkte"]) == 2584
    assert l["distanz_m"] == 4970 and l["dauer_s"] == 2587          # 43:07
    assert round(l["anstieg_m"], 1) == 95.3
    assert l["start"].isoformat() == "2026-05-28T03:42:46+00:00"
    assert abs(l["gemessen_m"] - l["distanz_m"]) / l["distanz_m"] < 0.02


def test_tcx_werte_wie_auf_der_uhr():
    l = dateien.lesen(_datei("huawei_lauf_b.tcx"))
    assert len(l["punkte"]) == 2411
    assert l["distanz_m"] == 4930 and l["dauer_s"] == 2532          # 42:12
    assert l["anstieg_m"] == 72.0
    assert l["start"].isoformat() == "2026-06-01T04:13:06+00:00"


def test_kilometerzeiten_hoechstens_zehn_sekunden_daneben():
    uhr = [489, 534, 561, 483]                                     # 8:09 · 8:54 · 9:21 · 8:03 (Huawei Health)
    km = dateien.lesen(_datei("huawei_lauf_b.tcx"))["km_zeiten"]
    assert len(km["km"]) == 4
    assert all(abs(a - b) <= 10 for a, b in zip(km["km"], uhr)), km
    assert abs(km["rest_s"] - 465) <= 10                           # „Weniger als 1 km 07:45“


def test_linie_ist_normiert_und_kurz():
    linie = dateien.linie(dateien.lesen(_datei("huawei_lauf_a.gpx"))["punkte"])
    assert 50 < len(linie) <= 401
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in linie)


def test_testdateien_verraten_keinen_wohnort():
    for name in ("huawei_lauf_a.gpx", "huawei_lauf_b.tcx"):
        p = dateien.lesen(_datei(name))["punkte"][0]
        assert not (49.9 < p[0] < 50.5 and 8.0 < p[1] < 8.8), name


def test_kaputte_oder_boese_dateien_werden_abgelehnt():
    for inhalt in (b"", b"hallo welt" * 10, b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'b'>]><gpx/>" * 2,
                   b"<?xml version='1.0'?><gpx><trk><trkseg></trkseg></trk></gpx>" * 2, b"<html><body>nix</body></html>" * 5):
        try:
            dateien.lesen(inhalt)
        except dateien.DateiFehler:
            continue
        raise AssertionError(inhalt[:40])


# ------------------------------------------------------------------ Bildtext (Texterkennung)
def test_bildtext_zweispaltig_und_einspaltig():
    for name in ("huawei_bild_spalten.txt", "huawei_bild_einspaltig.txt"):
        w = bildtext.lesen(_text(name))
        assert (w["distanz_m"], w["dauer_s"], w["puls_avg"], w["kadenz"], w["schritte"], w["kcal"], w["anstieg_m"]) == \
               (4930, 2532, 144, 148, 6280, 504, 72.0), (name, w)
        assert w["start"].isoformat() == "2026-06-01T04:13:00+00:00"   # 06:13 Uhr Sommerzeit


def test_bildtext_ohne_laufwerte():
    assert bildtext.lesen("Einkaufsliste: Milch, Brot") is None


# ------------------------------------------------------------------ Über die Schnittstelle
def _teilen(c, name):
    r = c.post("/api/laeufe/vorschau", data={"datei": (io.BytesIO(_datei(name)), name)}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _bestaetigen(c, entwurf, **mehr):
    r = c.post("/api/laeufe/bestaetigen", json={"entwurf": entwurf, "geraet_id": GERAET, "laeufer": "Testläufer A", **mehr})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_teilen_kontrollkarte_und_speichern():
    _, c, _ = neuer_server()
    v = _teilen(c, "huawei_lauf_b.tcx")
    assert v["lauf"]["distanz_km"] == "4,93" and v["lauf"]["dauer"] == "42:12" and v["lauf"]["start_text"] == "Mo 01.06. 06:13"
    assert c.get(f"/api/laeufe?geraet_id={GERAET}").get_json()["laeufe"] == []      # erst nach Bestätigen
    b = _bestaetigen(c, v["entwurf"])
    assert b["neu"] is True and b["lauf"]["hat_strecke"] and len(b["lauf"]["linie"]) > 50
    liste = c.get(f"/api/laeufe?geraet_id={GERAET}").get_json()["laeufe"]
    assert [l["distanz_km"] for l in liste] == ["4,93"] and "linie" not in liste[0]
    assert c.get(f"/api/laeufe?geraet_id=anderes-geraet-1").get_json()["laeufe"] == []


def test_doppelt_geteilt_wird_zusammengefuehrt():
    _, c, _ = neuer_server()
    _bestaetigen(c, _teilen(c, "huawei_lauf_b.tcx")["entwurf"])
    v = c.post("/api/laeufe/vorschau", json={"text": _text("huawei_bild_spalten.txt")}).get_json()
    assert v["lauf"]["puls_avg"] == 144
    b = _bestaetigen(c, v["entwurf"])
    assert b["neu"] is False
    liste = c.get(f"/api/laeufe?geraet_id={GERAET}").get_json()["laeufe"]
    assert len(liste) == 1
    lauf = liste[0]
    assert sorted(lauf["quellen"]) == ["bild", "datei"]
    assert lauf["puls_avg"] == 144 and lauf["kadenz"] == 148 and lauf["distanz_km"] == "4,93" and lauf["hat_strecke"]
    assert lauf["start"] == "2026-06-01T04:13:06+00:00"                 # Startzeit aus der Datei (genauer)


def test_bild_zuerst_dann_datei_liefert_strecke_nach():
    _, c, _ = neuer_server()
    _bestaetigen(c, c.post("/api/laeufe/vorschau", json={"text": _text("huawei_bild_einspaltig.txt")}).get_json()["entwurf"])
    _bestaetigen(c, _teilen(c, "huawei_lauf_b.tcx")["entwurf"])
    lauf = c.get(f"/api/laeufe?geraet_id={GERAET}").get_json()["laeufe"]
    assert len(lauf) == 1 and lauf[0]["hat_strecke"] and lauf[0]["puls_avg"] == 144


def test_health_connect_neu_und_ergaenzt():
    _, c, _ = neuer_server()
    _bestaetigen(c, _teilen(c, "huawei_lauf_a.gpx")["entwurf"])
    sitzungen = [{"start": "2026-05-28T03:43:30Z", "ende": "2026-05-28T04:26:00Z", "distanz_m": 4950, "puls_avg": 141},
                 {"start": "2026-06-03T16:00:00Z", "ende": "2026-06-03T16:31:10Z", "distanz_m": 5210.4, "anstieg_m": 33}]
    r = c.post("/api/laeufe/health-connect", json={"geraet_id": GERAET, "laeufer": "Testläufer B", "sitzungen": sitzungen})
    assert r.get_json() == {"ok": True, "neu": 1, "ergaenzt": 1}
    liste = c.get(f"/api/laeufe?geraet_id={GERAET}").get_json()["laeufe"]
    assert [l["distanz_km"] for l in liste] == ["5,21", "4,97"]          # Datei schlägt Health Connect bei der Distanz
    assert liste[1]["puls_avg"] == 141 and sorted(liste[1]["quellen"]) == ["datei", "health-connect"]
    assert liste[0]["dauer"] == "31:10"
    # zweimal dieselben Sitzungen → nichts Neues
    r = c.post("/api/laeufe/health-connect", json={"geraet_id": GERAET, "sitzungen": sitzungen})
    assert r.get_json()["neu"] == 0


def test_fehlerfaelle_der_schnittstelle():
    _, c, _ = neuer_server()
    r = c.post("/api/laeufe/vorschau", data={"datei": (io.BytesIO(b"kein lauf" * 20), "x.gpx")}, content_type="multipart/form-data")
    assert r.status_code == 422 and "GPX" in r.get_json()["fehler"]
    assert c.post("/api/laeufe/vorschau", json={"text": "nichts"}).status_code == 422
    assert c.post("/api/laeufe/bestaetigen", json={"entwurf": "gibtsnicht", "geraet_id": GERAET}).status_code == 410
    assert c.post("/api/laeufe/bestaetigen", json={"entwurf": "x", "geraet_id": "<b>"}).status_code == 400
    assert c.get("/api/laeufe?geraet_id=x").status_code == 400
    assert c.get(f"/api/laeufe/999?geraet_id={GERAET}").status_code == 404


def test_push_nach_dem_speichern():
    from test_push import Antwort, _konto_datei
    pfad, _ = _konto_datei()
    push._zugang.update(token="", bis=0)
    geraete._versuche.clear()
    _, c, _ = neuer_server(FIREBASE_KONTO_DATEI=pfad)
    gesendet = []

    def post(url, **kw):
        gesendet.append(kw)
        return Antwort(200, {"access_token": "z", "expires_in": 3600}) if "oauth2" in url else Antwort(200, {"name": "x"})

    alt = push.requests.post
    push.requests.post = post
    try:
        _bestaetigen(c, _teilen(c, "huawei_lauf_b.tcx")["entwurf"], push_token="fGeraetTokenBeispiel_1234567890:APA91b")
    finally:
        push.requests.post = alt
    texte = [kw["json"]["message"]["notification"]["body"] for kw in gesendet if "json" in kw]
    assert texte and texte[-1].startswith("4,93 km in 42:12")


def test_textbausteine():
    assert laeufe.dauer_text(2532) == "42:12" and laeufe.dauer_text(3725) == "1:02:05" and laeufe.km_text(4930) == "4,93"
