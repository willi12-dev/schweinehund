"""REQ-005: Sonntagsshow – Zeitpunkt, eingefrorener Stand, Sonderpreise, Wette, Monat, Push, Ruhmeshalle."""
import json
from datetime import datetime, timedelta, timezone

from hilfen import angemeldeter_server

from kern import push, show
from kern.datenbank import TZ, verbinden

MO = datetime(2026, 11, 9, tzinfo=TZ)                 # KW 46
SO_18 = datetime(2026, 11, 15, 18, 59, tzinfo=TZ)
SO_19 = datetime(2026, 11, 15, 19, 0, tzinfo=TZ)


def _db(ordner):
    return verbinden(f"{ordner}/test.db")


def _mitglied(con, name, rolle="mitglied", token=""):
    return con.execute("INSERT INTO mitglieder (name, farbe, kuerzel, rolle, angelegt, push_token) "
                       "VALUES (?, '#5B8DEF', ?, ?, 'x', ?)", (name, name[:2], rolle, token)).lastrowid


def _lauf(con, mitglied_id, wann, km, hm=0, km_zeiten=None):
    con.execute("INSERT INTO laeufe (mitglied_id, geraet_id, start, distanz_m, anstieg_m, km_zeiten, angelegt, geaendert) "
                "VALUES (?, 'g', ?, ?, ?, ?, 'x', 'x')",
                (mitglied_id, wann.astimezone(timezone.utc).isoformat(), km * 1000, hm,
                 json.dumps({"km": km_zeiten}) if km_zeiten else ""))


def _familie():
    _, c, ordner = angemeldeter_server()
    con = _db(ordner)
    a = con.execute("SELECT id FROM mitglieder").fetchone()[0]
    b = _mitglied(con, "Testläufer B")
    d = _mitglied(con, "Testläufer D")
    # Testdatensatz: A 4,93 km / 72 m um 06:13, B 6,11 km / 34 m um 10:22
    _lauf(con, a, datetime(2026, 11, 10, 6, 13, tzinfo=TZ), 4.93, 72, [489, 534, 560, 483])
    _lauf(con, b, datetime(2026, 11, 10, 10, 22, tzinfo=TZ), 6.11, 34, [340, 375, 389, 390, 397, 368])
    _lauf(con, d, datetime(2026, 11, 3, 7, 0, tzinfo=TZ), 5.0, 0)        # nur Vorwoche
    con.commit()
    return c, con, a, b, d


def test_zeitpunkt_sonntag_19_uhr():
    assert show.faellig_ab(MO) == SO_19
    assert show.letzte_faellige_woche(SO_18) == MO - timedelta(days=7)
    assert show.letzte_faellige_woche(SO_19) == MO
    assert show.woche_schluessel(MO) == "2026-W46"


def test_show_mit_testdatensatz():
    c, con, a, b, d = _familie()
    s = show.erstellen(con, MO)
    assert s["member_of_week"] == ["Testläufer B"]
    assert [(z["mitglied"]["name"], z["platz"]) for z in s["zeilen"]] == [("Testläufer B", 1), ("Testläufer A", 2), ("Testläufer D", 3)]
    preise = {p["titel"]: (p["gewinner"], p["wert"]) for p in s["preise"]}
    assert preise["Bergziege"] == (["Testläufer A"], "72 m")
    assert preise["Frühaufsteher"] == (["Testläufer A"], "6:13 Uhr")
    assert preise["Dauerläufer"] == (["Testläufer B"], "6,11 km")
    assert preise["Tempomacher"] == (["Testläufer B"], "5:40 /km")
    assert preise["Comeback"][0] == ["Testläufer B"]                     # beide +, B mit mehr
    assert s["horst"]["ist"] == "12,10" and s["monat"] is None and s["wette"] is None


def test_eingefroren_spaetere_laeufe_aendern_die_show_nicht():
    c, con, a, b, d = _familie()
    show.aktuelle(con, SO_19)
    _lauf(con, a, datetime(2026, 11, 15, 20, 0, tzinfo=TZ), 20.0, 300)
    con.commit()
    assert show.aktuelle(con, SO_19 + timedelta(hours=2))["member_of_week"] == ["Testläufer B"]


def test_vor_sonntag_keine_neue_show_vorgezogen_aber_schon():
    c, con, a, b, d = _familie()
    assert show.aktuelle(con, SO_18) is not None and show.aktuelle(con, SO_18)["woche"] == "2026-W45"
    v = show.vorziehen(con, datetime(2026, 11, 11, 21, 0, tzinfo=TZ))
    assert v["woche"] == "2026-W46" and v["vorgezogen"]
    assert show.aktuelle(con, SO_18)["woche"] == "2026-W46"
    # zum echten Termin wird die vorgezogene Show neu berechnet
    _lauf(con, a, datetime(2026, 11, 14, 9, 0, tzinfo=TZ), 10.0, 0)
    con.commit()
    echt = show.aktuelle(con, SO_19)
    assert echt["vorgezogen"] is False and echt["member_of_week"] == ["Testläufer A"]


def test_leere_woche_ohne_preise_und_ohne_sieger():
    _, c, ordner = angemeldeter_server()
    con = _db(ordner)
    s = show.erstellen(con, MO)
    assert s["preise"] == [] and s["member_of_week"] == []


def test_gleichstand_mehrere_gewinner_und_wette():
    _, c, ordner = angemeldeter_server()
    con = _db(ordner)
    a = con.execute("SELECT id FROM mitglieder").fetchone()[0]
    b = _mitglied(con, "Testläufer B")
    d = _mitglied(con, "Testläufer D")
    for m in (a, b):
        _lauf(con, m, datetime(2026, 11, 12, 7, 0, tzinfo=TZ), 5.0, 50)
    show.wette_setzen(con, "  Wer Letzter wird,   backt Kuchen ")
    con.commit()
    s = show.erstellen(con, MO)
    assert s["member_of_week"] == ["Testläufer A", "Testläufer B"]
    assert {p["titel"]: p["gewinner"] for p in s["preise"]}["Bergziege"] == ["Testläufer A", "Testläufer B"]
    assert s["wette"] == {"text": "Wer Letzter wird, backt Kuchen", "verlierer": ["Testläufer D"]}


def test_monatsaufloesung_nur_in_der_woche_mit_monatsende():
    c, con, a, b, d = _familie()
    assert show.erstellen(con, MO)["monat"] is None
    _lauf(con, b, datetime(2026, 11, 28, 8, 0, tzinfo=TZ), 10.0, 0)
    con.commit()
    m = show.erstellen(con, datetime(2026, 11, 23, tzinfo=TZ))["monat"]   # Woche 23.–29.11. – Monatsende 30.11. liegt in KW 49
    assert m is None
    m = show.erstellen(con, datetime(2026, 11, 30, tzinfo=TZ))["monat"]   # Woche 30.11.–06.12.
    assert m["titel"] == "November 2026" and m["sieger"] == ["Testläufer B"]


def test_aufgabe_schickt_push_genau_einmal():
    c, con, a, b, d = _familie()
    con.execute("UPDATE mitglieder SET push_token = 'fGeraetTokenBeispiel_1234567890:APA91b' WHERE id IN (?, ?)", (a, b))
    con.commit()
    gesendet = []

    def post(url, **kw):
        from test_push import Antwort
        gesendet.append(kw)
        return Antwort(200, {"access_token": "z", "expires_in": 3600}) if "oauth2" in url else Antwort(200, {"name": "x"})

    from test_push import _konto_datei
    import os
    pfad, _ = _konto_datei()
    os.environ["FIREBASE_KONTO_DATEI"] = pfad
    push._zugang.update(token="", bis=0)
    try:
        assert show.aufgabe(con, datetime(2026, 11, 12, 19, 0, tzinfo=TZ), post) == "keine Show fällig"
        assert show.aufgabe(con, SO_19, post) == "Push an 2 Handys"
        assert show.aufgabe(con, SO_19 + timedelta(hours=1), post) == "schon angekündigt"
    finally:
        os.environ.pop("FIREBASE_KONTO_DATEI", None)
    texte = [kw["json"]["message"]["notification"] for kw in gesendet if "json" in kw]
    assert len(texte) == 2 and "Sonntagsshow" in texte[0]["title"] and "Testläufer" not in texte[0]["body"]


def test_schnittstellen():
    _, c, ordner = angemeldeter_server()
    assert c.get("/api/show").get_json()["show"] is None
    assert c.post("/api/familie/wette", json={"text": "Letzter backt Kuchen"}).get_json()["wette"] == "Letzter backt Kuchen"
    v = c.post("/api/show/vorziehen").get_json()["show"]
    assert v["vorgezogen"] and v["wette"]["text"] == "Letzter backt Kuchen"
    assert c.get("/api/show").get_json()["show"]["woche"] == v["woche"]
    assert c.get(f"/api/show/{v['woche']}").get_json()["show"]["titel"] == v["titel"]
    assert c.get("/api/show/1999-W01").status_code == 404
    assert [s["woche"] for s in c.get("/api/shows").get_json()["shows"]] == [v["woche"]]
    assert c.post("/api/ich/push", json={"token": "kurz"}).status_code == 400
    assert c.post("/api/ich/push", json={"token": "fGeraetTokenBeispiel_1234567890:APA91b"}).status_code == 200
    code = c.post("/api/mitglieder", json={"name": "Testläufer B"}).get_json()["code"]
    s = c.application.test_client().post(f"/api/einladung/{code}", json={}).get_json()["schluessel"]
    b = c.application.test_client()
    b.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + s
    assert b.post("/api/show/vorziehen").status_code == 403 and b.post("/api/familie/wette", json={"text": "x"}).status_code == 403
