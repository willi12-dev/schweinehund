"""REQ-003: Familien-Läufe und Karte (Sichtbarkeit pro Lauf seit REQ-013 entfallen)."""
import io
import os

from hilfen import WURZEL, angemeldeter_server

from kern import dateien

DATEN = os.path.join(WURZEL, "tests", "daten")


def _datei(name):
    with open(os.path.join(DATEN, name), "rb") as f:
        return f.read()


def _teilen_und_speichern(c, name, **mehr):
    v = c.post("/api/laeufe/vorschau", data={"datei": (io.BytesIO(_datei(name)), name)},
               content_type="multipart/form-data").get_json()
    r = c.post("/api/laeufe/bestaetigen", json={"entwurf": v["entwurf"], **mehr})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["id"]


def _zweites_mitglied(c):
    code = c.post("/api/mitglieder", json={"name": "Testläufer B"}).get_json()["code"]
    s = c.application.test_client().post(f"/api/einladung/{code}", json={"geraet_id": "geraet-test-0002"}).get_json()["schluessel"]
    b = c.application.test_client()
    b.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + s
    return b


def test_karte_aus_testlauf():
    l = dateien.lesen(_datei("huawei_lauf_b.tcx"))
    k = dateien.karte(l["punkte"], l["distanz_m"])
    assert 300 < len(k["punkte"]) <= 801
    assert {p[2] for p in k["punkte"]} == {0, 1, 2, 3, 4}
    assert [m[2] for m in k["km"]] == [1, 2, 3, 4]                     # 4,93 km → vier Marken
    # Zeiten als Sekunden (wie in der Datenbank) liefern dasselbe
    t0 = l["punkte"][0][3]
    sek = [(p[0], p[1], p[2], (p[3] - t0).total_seconds()) for p in l["punkte"]]
    assert dateien.karte(sek, l["distanz_m"]) == k


def test_karte_ohne_zeiten_und_zu_kurz():
    assert dateien.karte([]) == {"punkte": [], "km": []}
    k = dateien.karte([(50.0, 8.0, None, None), (50.001, 8.0, None, None)])
    assert [p[2] for p in k["punkte"]] == [2, 2] and k["km"] == []


def test_familie_sieht_laeufe_aller():
    _, a, _ = angemeldeter_server()
    b = _zweites_mitglied(a)
    _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    _teilen_und_speichern(b, "garmin_lauf_c.gpx")
    liste = b.get("/api/laeufe/familie").get_json()["laeufe"]
    assert [(l["mitglied"]["name"], l["eigen"]) for l in liste] == [("Testläufer B", True), ("Testläufer A", False)]
    assert "linie" not in liste[0] and "karte" not in liste[0]
    a_id = liste[1]["mitglied"]["id"]
    assert [l["distanz_km"] for l in b.get(f"/api/laeufe?mitglied={a_id}").get_json()["laeufe"]] == ["4,93"]
    detail = b.get(f"/api/laeufe/{liste[1]['id']}").get_json()["lauf"]
    assert detail["hat_strecke"] and len(detail["karte"]["km"]) == 4


def test_familie_sieht_immer_die_strecke():
    """REQ-013: „nur für mich“ gibt es nicht mehr – auch ein alter Wunsch „ich“ beim Speichern wird ignoriert."""
    _, a, _ = angemeldeter_server()
    b = _zweites_mitglied(a)
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx", sichtbarkeit="ich")
    fremd = b.get(f"/api/laeufe/{lauf_id}").get_json()["lauf"]
    assert fremd["hat_strecke"] and fremd["karte"]["punkte"] and "sichtbarkeit" not in fremd
    assert a.post(f"/api/laeufe/{lauf_id}/sichtbarkeit", json={"sichtbarkeit": "ich"}).status_code in (404, 405)
    assert "standard_sichtbarkeit" not in a.post("/api/ich", json={"standard_sichtbarkeit": "ich"}).get_json()["ich"]


def test_nur_eigene_laeufe_loeschen():
    _, a, _ = angemeldeter_server()
    b = _zweites_mitglied(a)
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    assert b.delete(f"/api/laeufe/{lauf_id}").status_code == 403
    assert a.delete("/api/laeufe/999").status_code == 404
    assert a.delete(f"/api/laeufe/{lauf_id}").status_code == 200
    assert a.get("/api/laeufe/familie").get_json()["laeufe"] == []
