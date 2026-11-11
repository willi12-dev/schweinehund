"""REQ-002: Familie gründen, Mitglieder einladen, Anmeldung per Schlüssel."""
from datetime import datetime, timedelta

from hilfen import angemeldeter_server, neuer_server

from kern import familie, geraete
from kern.datenbank import TZ, verbinden


def _db(ordner):
    return verbinden(f"{ordner}/test.db")


def _als(c, schluessel):
    neu = c.application.test_client()
    neu.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + schluessel
    return neu


def _einladen(c, name="Testläufer B"):
    r = c.post("/api/mitglieder", json={"name": name})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_gruenden_nur_einmal_und_status():
    _, c, _ = neuer_server()
    geraete._versuche.clear()
    assert c.get("/api/status").get_json()["familie"] is False
    r = c.post("/api/familie/gruenden", json={"name": "Testläufer A", "geraet_id": "geraet-test-0001"}).get_json()
    assert r["ok"] and r["ich"]["rolle"] == "verwalter" and len(r["schluessel"]) > 30
    assert c.get("/api/status").get_json()["familie"] is True
    assert c.post("/api/familie/gruenden", json={"name": "Jemand"}).status_code == 409


def test_ohne_schluessel_keine_daten():
    _, c, _ = angemeldeter_server()
    fremd = c.application.test_client()
    for pfad in ("/api/familie", "/api/laeufe", "/api/laeufe/1"):
        assert fremd.get(pfad).status_code == 401
    assert fremd.post("/api/mitglieder", json={"name": "X"}).status_code == 401
    assert _als(c, "falscher-schluessel").get("/api/familie").status_code == 401
    assert fremd.get("/version").status_code == 200 and fremd.get("/api/status").status_code == 200


def test_einladen_und_einloesen():
    _, c, ordner = angemeldeter_server()
    e = _einladen(c)
    code = e["code"]
    assert len(code) == 10 and e["link"].endswith("/e/" + code) and code in e["text"]
    vorschau = c.application.test_client().get(f"/api/einladung/{code.lower()}").get_json()
    assert vorschau["name"] == "Testläufer B"
    r = c.application.test_client().post(f"/api/einladung/{code}", json={"geraet_id": "geraet-test-0002"}).get_json()
    assert r["ok"] and r["ich"]["name"] == "Testläufer B" and r["ich"]["rolle"] == "mitglied"
    b = _als(c, r["schluessel"])
    namen = [m["name"] for m in b.get("/api/familie").get_json()["mitglieder"]]
    assert namen == ["Testläufer A", "Testläufer B"]
    # Code gilt nur einmal, Mitglieder dürfen niemanden einladen
    assert c.application.test_client().post(f"/api/einladung/{code}", json={}).status_code == 404
    assert b.post("/api/mitglieder", json={"name": "Testläufer C"}).status_code == 403
    # In der Datenbank stehen nur Prüfsummen
    con = _db(ordner)
    roh = " ".join(str(v) for z in con.execute("SELECT * FROM mitglieder") for v in tuple(z))
    roh += " ".join(str(v) for z in con.execute("SELECT * FROM einladungen") for v in tuple(z))
    assert r["schluessel"] not in roh and code not in roh


def test_doppelter_name_und_zu_kurz():
    _, c, _ = angemeldeter_server()
    _einladen(c)
    assert c.post("/api/mitglieder", json={"name": "testläufer b"}).status_code == 409
    assert c.post("/api/mitglieder", json={"name": "X"}).status_code == 400


def test_abgelaufene_einladung():
    _, c, ordner = angemeldeter_server()
    code = _einladen(c)["code"]
    con = _db(ordner)
    con.execute("UPDATE einladungen SET gueltig_bis = ?", ((datetime.now(TZ) - timedelta(minutes=1)).isoformat(),))
    con.commit()
    r = c.application.test_client().post(f"/api/einladung/{code}", json={})
    assert r.status_code == 410 and "abgelaufen" in r.get_json()["fehler"]


def test_neuer_link_sperrt_altes_handy():
    _, c, _ = angemeldeter_server()
    e = _einladen(c)
    alt = c.application.test_client().post(f"/api/einladung/{e['code']}", json={}).get_json()["schluessel"]
    mitglied_id = [m for m in c.get("/api/familie").get_json()["mitglieder"] if not m["ich"]][0]["id"]
    neu = c.post(f"/api/mitglieder/{mitglied_id}/einladung").get_json()
    assert _als(c, alt).get("/api/familie").status_code == 401
    assert c.application.test_client().post(f"/api/einladung/{e['code']}", json={}).status_code == 404
    s = c.application.test_client().post(f"/api/einladung/{neu['code']}", json={}).get_json()["schluessel"]
    assert _als(c, s).get("/api/familie").status_code == 200
    # sich selbst aussperren geht nicht
    ich = [m for m in c.get("/api/familie").get_json()["mitglieder"] if m["ich"]][0]["id"]
    assert c.post(f"/api/mitglieder/{ich}/einladung").status_code == 409


def test_laeufe_aus_dem_datentest_gehen_aufs_mitglied_ueber():
    _, c, ordner = neuer_server()
    geraete._versuche.clear()
    con = _db(ordner)
    for g in ("geraet-test-0001", "geraet-test-0002"):
        con.execute("INSERT INTO laeufe (geraet_id, start, distanz_m, dauer_s, angelegt, geaendert) "
                    "VALUES (?, '2026-06-01T04:13:06+00:00', 4930, 2532, 'x', 'x')", (g,))
    con.commit()
    a = c.post("/api/familie/gruenden", json={"name": "Testläufer A", "geraet_id": "geraet-test-0001"}).get_json()
    va = _als(c, a["schluessel"])
    assert [l["distanz_km"] for l in va.get("/api/laeufe").get_json()["laeufe"]] == ["4,93"]
    code = va.post("/api/mitglieder", json={"name": "Testläufer B"}).get_json()["code"]
    b = c.post(f"/api/einladung/{code}", json={"geraet_id": "geraet-test-0002"}).get_json()
    vb = _als(c, b["schluessel"])
    eigene = vb.get("/api/laeufe").get_json()["laeufe"]
    assert len(eigene) == 1
    # Läufe der anderen sind sichtbar (REQ-003), aber nicht als eigene
    fremd_id = va.get("/api/laeufe").get_json()["laeufe"][0]["id"]
    assert vb.get(f"/api/laeufe/{fremd_id}").get_json()["lauf"]["eigen"] is False


def test_familienuebersicht_mit_wochenkilometern():
    _, c, ordner = angemeldeter_server()
    _einladen(c)
    jetzt = datetime.now(TZ)
    con = _db(ordner)
    ich = con.execute("SELECT id FROM mitglieder WHERE rolle = 'verwalter'").fetchone()[0]
    from datetime import timezone
    for tage, m in ((0, 5000), (0, 3210), (8, 7000)):
        start = (jetzt - timedelta(days=tage, seconds=1)).astimezone(timezone.utc).isoformat()
        con.execute("INSERT INTO laeufe (mitglied_id, geraet_id, start, distanz_m, angelegt, geaendert) "
                    "VALUES (?, 'g', ?, ?, 'x', 'x')", (ich, start, m))
    con.commit()
    liste = c.get("/api/familie").get_json()["mitglieder"]
    a, b = liste
    assert a["ich"] and a["km_woche"] == "8,21" and a["laeufe_woche"] == 2 and a["letzter_lauf"]["distanz_km"] in ("5,00", "3,21")
    assert not b["beigetreten"] and b["einladung_offen"] and b["km_woche"] == "0" and b["letzter_lauf"] is None


def test_wochenbeginn_ist_montag_null_uhr():
    w = familie.wochenbeginn(datetime(2026, 11, 11, 19, 30, tzinfo=TZ))   # Mittwoch
    assert (w.weekday(), w.hour, w.minute, w.day) == (0, 0, 0, 9)


def test_farbe_aendern():
    _, c, _ = angemeldeter_server()
    assert c.post("/api/ich", json={"farbe": "#5b8def"}).get_json()["ich"]["farbe"] == "#5B8DEF"
    assert c.post("/api/ich", json={"farbe": "rot"}).status_code == 400


def test_einladungsseite_und_app_verknuepfung():
    _, c, _ = angemeldeter_server()
    code = _einladen(c)["code"]
    seite = c.get(f"/e/{code}").get_data(as_text=True)
    assert "Hallo Testläufer B" in seite and "intent://" in seite and "package=app.schweinehund" in seite
    assert "nicht gültig" in c.get("/e/FALSCH12345").get_data(as_text=True)
    links = c.get("/.well-known/assetlinks.json").get_json()
    assert links[0]["target"]["package_name"] == "app.schweinehund"
    assert links[0]["target"]["sha256_cert_fingerprints"][0].startswith("55:57:77")


def test_bremse_beim_raten_von_codes():
    _, c, _ = angemeldeter_server()
    geraete._versuche.clear()
    codes = [c.application.test_client().post(f"/api/einladung/RATEN{i:05d}", json={}).status_code for i in range(21)]
    assert codes[:20] == [404] * 20 and codes[20] == 429
