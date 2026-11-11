"""REQ-004: Leistungskilometer, Rangliste, Horst-o-Meter, Fortschritt, Serie, Bestwerte."""
import json
from datetime import datetime, timedelta, timezone

from hilfen import angemeldeter_server

from kern import punkte
from kern.datenbank import TZ, verbinden

JETZT = datetime(2026, 11, 11, 20, 0, tzinfo=TZ)     # Mittwoch, KW 46


def _db(ordner):
    return verbinden(f"{ordner}/test.db")


def _mitglied(con, name, rolle="mitglied"):
    return con.execute("INSERT INTO mitglieder (name, farbe, kuerzel, rolle, angelegt) VALUES (?, '#5B8DEF', ?, ?, 'x')",
                       (name, name[:2], rolle)).lastrowid


def _lauf(con, mitglied_id, wann, km, hm=None, art="laufen", km_zeiten=None):
    start = wann.astimezone(timezone.utc).isoformat()
    con.execute("INSERT INTO laeufe (mitglied_id, geraet_id, start, art, distanz_m, anstieg_m, km_zeiten, angelegt, geaendert) "
                "VALUES (?, 'g', ?, ?, ?, ?, ?, 'x', 'x')",
                (mitglied_id, start, art, km * 1000, hm, json.dumps({"km": km_zeiten}) if km_zeiten else ""))


def test_lk_formel_und_mindestlauf():
    assert round(punkte.lk(6110, 34), 2) == 6.45 and round(punkte.lk(4930, 72), 2) == 5.65
    assert punkte.lk(5000, None) == 5.0
    assert punkte.zaehlt({"art": "laufen", "distanz_m": 1000}) and not punkte.zaehlt({"art": "laufen", "distanz_m": 999})
    assert not punkte.zaehlt({"art": "gehen", "distanz_m": 5000})


def test_zeitraeume_in_berliner_zeit():
    von, bis, text = punkte.zeitraum("woche", JETZT)
    assert (von.day, von.hour, (bis - von).days) == (9, 0, 7) and text.startswith("KW 46")
    von, bis, text = punkte.zeitraum("monat", JETZT)
    assert (von.day, bis.month, text) == (1, 12, "November 2026")
    von, bis, _ = punkte.zeitraum("monat", datetime(2026, 12, 31, 23, 0, tzinfo=TZ))
    assert (bis.year, bis.month) == (2027, 1)


def test_rangliste_woche_und_monat_mit_testdatensatz():
    _, c, ordner = angemeldeter_server()
    con = _db(ordner)
    a = con.execute("SELECT id FROM mitglieder").fetchone()[0]
    b = _mitglied(con, "Testläufer B")
    d = _mitglied(con, "Testläufer D")
    _lauf(con, b, datetime(2026, 11, 10, 10, 22, tzinfo=TZ), 6.11, 34)
    _lauf(con, a, datetime(2026, 11, 10, 6, 13, tzinfo=TZ), 4.93, 72)
    _lauf(con, a, datetime(2026, 11, 3, 6, 0, tzinfo=TZ), 5.0, 0)          # Vorwoche: nur im Monat
    _lauf(con, d, datetime(2026, 11, 9, 0, 30, tzinfo=TZ), 0.8, 0)        # zu kurz
    _lauf(con, d, datetime(2026, 11, 8, 23, 59, tzinfo=TZ), 3.0, 0)       # Sonntag davor
    con.commit()
    w = punkte.rangliste(con, "woche", JETZT)["zeilen"]
    assert [(r["mitglied"]["name"], r["lk"], r["platz"]) for r in w] == [
        ("Testläufer B", "6,45", 1), ("Testläufer A", "5,65", 2), ("Testläufer D", "0,00", 3)]
    m = punkte.rangliste(con, "monat", JETZT)["zeilen"]
    assert [(r["mitglied"]["name"], r["lk"], r["laeufe"]) for r in m] == [
        ("Testläufer A", "10,65", 2), ("Testläufer B", "6,45", 1), ("Testläufer D", "3,00", 1)]
    h = punkte.horst_o_meter(con, JETZT)
    assert (h["ist"], h["ziel"], h["prozent"]) == ("12,10", "40", 30) and "unruhig" in h["spruch"]


def test_gleichstand_gleicher_platz():
    _, c, ordner = angemeldeter_server()
    con = _db(ordner)
    a = con.execute("SELECT id FROM mitglieder").fetchone()[0]
    b = _mitglied(con, "Testläufer B")
    for m in (a, b):
        _lauf(con, m, datetime(2026, 11, 10, 7, 0, tzinfo=TZ), 5.0, 0)
    con.commit()
    assert [r["platz"] for r in punkte.rangliste(con, "woche", JETZT)["zeilen"]] == [1, 1]


def test_serie_fortschritt_bestwerte():
    _, c, ordner = angemeldeter_server()
    con = _db(ordner)
    a = con.execute("SELECT id FROM mitglieder").fetchone()[0]
    for wochen_zurueck in (1, 2, 3, 5):
        _lauf(con, a, JETZT - timedelta(days=7 * wochen_zurueck), 5.0, 10 * wochen_zurueck, km_zeiten=[400 + wochen_zurueck])
    con.commit()
    s = punkte.serie(con, a, JETZT)
    assert s == {"wochen": 3, "diese_woche": False}                      # laufende Woche bricht nicht
    _lauf(con, a, JETZT - timedelta(hours=1), 8.0, 0, km_zeiten=[380, 390])
    con.commit()
    assert punkte.serie(con, a, JETZT) == {"wochen": 4, "diese_woche": True}
    f = punkte.fortschritt(con, a, JETZT)
    assert len(f) == 8 and f[-1]["woche"] == "KW 46" and f[-1]["lk"] == "8,0" and f[-2]["lk"] == "5,1"
    b = punkte.bestwerte(con, a)
    assert b["laengster"]["wert"] == "8,00 km" and b["hoechster"]["wert"] == "50 m" and b["schnellster_km"]["wert"] == "6:20 /km"


def test_horst_stufen():
    sprueche = [t for _, t in punkte.HORST]
    assert len(sprueche) == 5 and "besiegt" in sprueche[-1]


def test_schnittstelle_rangliste_und_ziel():
    _, c, _ = angemeldeter_server()
    r = c.get("/api/rangliste?zeitraum=monat").get_json()
    assert r["ok"] and r["rangliste"]["zeitraum"] == "monat" and r["horst"]["ziel"] == "40"
    assert "fortschritt" in r["ich"] and "serie" in r["ich"]
    assert c.get("/api/rangliste?zeitraum=jahr").status_code == 400
    assert c.post("/api/familie/ziel", json={"lk": 60}).get_json()["horst"]["ziel"] == "60"
    assert c.post("/api/familie/ziel", json={"lk": 2}).status_code == 400
    assert c.post("/api/familie/ziel", json={"lk": "viel"}).status_code == 400
    code = c.post("/api/mitglieder", json={"name": "Testläufer B"}).get_json()["code"]
    s = c.application.test_client().post(f"/api/einladung/{code}", json={}).get_json()["schluessel"]
    b = c.application.test_client()
    b.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + s
    assert b.post("/api/familie/ziel", json={"lk": 80}).status_code == 403
    assert c.application.test_client().get("/api/rangliste").status_code == 401


def test_lk_am_lauf():
    from kern import laeufe
    d = laeufe.fuer_app({"start": "2026-11-10T09:22:28+00:00", "distanz_m": 6110, "anstieg_m": 34}, ["datei"], mit_linie=False)
    assert d["lk"] == "6,45"
