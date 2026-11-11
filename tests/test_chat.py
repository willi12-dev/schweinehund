"""REQ-006: Familienchat, Reaktionen, Kommentare, Horst-Meldungen und Push-Empfänger."""
import io
import os
from datetime import datetime, timedelta, timezone

from hilfen import WURZEL, angemeldeter_server

from kern import chat
from kern.datenbank import verbinden

TOKEN = "fGeraetTokenBeispiel_1234567890:APA91b"


class Postbote:
    """Ersetzt die Zustellung: merkt sich (Token, Titel, Text, Daten)."""

    def __init__(self):
        self.post = []
        self.alt = chat._zustellen
        chat._zustellen = lambda token, titel, text, daten: self.post.append((token, titel, text, daten))

    def an(self, token):
        return [p for p in self.post if p[0] == token]

    def fertig(self):
        chat._zustellen = self.alt


def _familie():
    """A (Verwalter) und B, beide mit Push-Token; Client a und b."""
    _, a, ordner = angemeldeter_server()
    code = a.post("/api/mitglieder", json={"name": "Testläufer B"}).get_json()["code"]
    s = a.application.test_client().post(f"/api/einladung/{code}", json={"geraet_id": "geraet-test-0002"}).get_json()["schluessel"]
    b = a.application.test_client()
    b.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + s
    a.post("/api/ich/push", json={"token": TOKEN + "A"})
    b.post("/api/ich/push", json={"token": TOKEN + "B"})
    return a, b, verbinden(f"{ordner}/test.db")


def _teilen(c, name, **mehr):
    with open(os.path.join(WURZEL, "tests", "daten", name), "rb") as f:
        v = c.post("/api/laeufe/vorschau", data={"datei": (io.BytesIO(f.read()), name)}, content_type="multipart/form-data").get_json()
    return c.post("/api/laeufe/bestaetigen", json={"entwurf": v["entwurf"], **mehr}).get_json()


def _lauf_jetzt(con, mitglied_name, km, hm=0, km_zeiten=None, tage=0):
    mid = con.execute("SELECT id FROM mitglieder WHERE name = ?", (mitglied_name,)).fetchone()[0]
    start = (datetime.now(timezone.utc) - timedelta(days=tage, hours=1)).isoformat()
    import json
    cur = con.execute("INSERT INTO laeufe (mitglied_id, geraet_id, start, distanz_m, anstieg_m, km_zeiten, angelegt, geaendert) "
                      "VALUES (?, 'g', ?, ?, ?, ?, 'x', 'x')", (mid, start, km * 1000, hm, json.dumps({"km": km_zeiten or []})))
    con.commit()
    return cur.lastrowid, mid


def test_chat_senden_lesen_loeschen_und_push():
    a, b, con = _familie()
    p = Postbote()
    try:
        n = a.post("/api/chat", json={"text": "  Wer läuft morgen?  "}).get_json()["nachricht"]
        assert n["text"] == "Wer läuft morgen?" and n["eigen"] and n["absender"]["name"] == "Testläufer A"
        assert [x[1] for x in p.post] == ["Testläufer A im Familienchat"] and p.an(TOKEN + "B")
        assert p.post[0][3] == {"ziel": "chat", "art": "chat"}
        liste = b.get("/api/chat").get_json()
        assert liste["ungelesen"] == 1 and liste["nachrichten"][0]["eigen"] is False
        assert b.post("/api/chat/gelesen", json={"bis": n["id"]}).get_json()["ungelesen"] == 0
        assert b.get(f"/api/chat?nach={n['id']}").get_json()["nachrichten"] == []
        assert b.delete(f"/api/chat/{n['id']}").status_code == 403
        assert a.delete(f"/api/chat/{n['id']}").status_code == 200
        assert a.post("/api/chat", json={"text": "   "}).status_code == 400
        assert a.post("/api/chat", json={"text": "x" * 501}).status_code == 400
    finally:
        p.fertig()


def test_flutschutz():
    a, b, con = _familie()
    for i in range(30):
        assert a.post("/api/chat", json={"text": f"Nachricht {i}"}).status_code == 200
    assert a.post("/api/chat", json={"text": "eine zu viel"}).status_code == 429


def test_reaktion_an_aus_und_push_nur_an_den_laeufer():
    a, b, con = _familie()
    lauf_id, _ = _lauf_jetzt(con, "Testläufer A", 5.0)
    p = Postbote()
    try:
        r = b.post(f"/api/laeufe/{lauf_id}/reaktion", json={"emoji": "🔥"}).get_json()["reaktionen"]
        assert r == [{"emoji": "🔥", "anzahl": 1, "ich": True, "namen": ["Testläufer B"]}]
        assert [x[0] for x in p.post] == [TOKEN + "A"] and "🔥" in p.post[0][1] and p.post[0][3]["lauf_id"] == str(lauf_id) or \
            p.post[0][3]["lauf_id"] == lauf_id
        a.post(f"/api/laeufe/{lauf_id}/reaktion", json={"emoji": "👏"})              # eigener Lauf: kein Push
        assert len(p.post) == 1
        assert b.post(f"/api/laeufe/{lauf_id}/reaktion", json={"emoji": "🔥"}).get_json()["reaktionen"] == \
            [{"emoji": "👏", "anzahl": 1, "ich": False, "namen": ["Testläufer A"]}]       # zurückgenommen
        assert b.post(f"/api/laeufe/{lauf_id}/reaktion", json={"emoji": "🍕"}).status_code == 400
        assert b.post("/api/laeufe/999/reaktion", json={"emoji": "🔥"}).status_code == 404
        familie = b.get("/api/laeufe/familie").get_json()["laeufe"]
        assert familie[0]["reaktionen"][0]["emoji"] == "👏"
    finally:
        p.fertig()


def test_kommentare():
    a, b, con = _familie()
    lauf_id, _ = _lauf_jetzt(con, "Testläufer A", 5.0)
    p = Postbote()
    try:
        k = b.post(f"/api/laeufe/{lauf_id}/kommentar", json={"text": "Stark!"}).get_json()["kommentare"]
        assert k[0]["text"] == "Stark!" and k[0]["eigen"] and p.an(TOKEN + "A")
        d = a.get(f"/api/laeufe/{lauf_id}").get_json()["lauf"]
        assert d["kommentare"][0]["absender"]["name"] == "Testläufer B" and d["kommentare_anzahl"] == 1
        assert a.delete(f"/api/kommentare/{k[0]['id']}").status_code == 403
        assert b.delete(f"/api/kommentare/{k[0]['id']}").status_code == 200
    finally:
        p.fertig()


def test_horst_meldet_neuen_lauf_aber_nicht_das_zusammenfuehren():
    a, b, con = _familie()
    p = Postbote()
    chat.MELDEN_TAGE = 100000                     # Testdatei ist vom 01.06.2026
    try:
        r = _teilen(a, "huawei_lauf_b.tcx")
        assert r["neu"]
        horst = [n for n in b.get("/api/chat").get_json()["nachrichten"] if n["horst"]]
        assert len(horst) == 1 and "Testläufer A" in horst[0]["text"] and "4,93" in horst[0]["text"]
        assert horst[0]["lauf_id"] == r["id"]
        assert p.an(TOKEN + "B") and not p.an(TOKEN + "A")             # Läufer bekommt keinen „Lauf“-Push
        anzahl = len(p.post)
        hc = [{"start": "2026-06-01T04:13:30Z", "ende": "2026-06-01T04:55:00Z", "distanz_m": 4930, "puls_avg": 144}]
        assert a.post("/api/laeufe/health-connect", json={"sitzungen": hc}).get_json()["ergaenzt"] == 1
        assert len([n for n in b.get("/api/chat").get_json()["nachrichten"] if n["horst"]]) == 1 and len(p.post) == anzahl
    finally:
        chat.MELDEN_TAGE = 3
        p.fertig()


def test_alte_laeufe_meldet_horst_nicht():
    a, b, con = _familie()
    _teilen(a, "huawei_lauf_b.tcx")               # 01.06.2026 – älter als 3 Tage
    assert [n for n in b.get("/api/chat").get_json()["nachrichten"] if n["horst"]] == []


def test_bestwert_und_ueberholt():
    a, b, con = _familie()
    _lauf_jetzt(con, "Testläufer A", 5.0, 20, [400])
    _lauf_jetzt(con, "Testläufer B", 4.0, 0, [420])
    p = Postbote()
    try:
        stand = chat.vorher(con, None)
        ich = dict(con.execute("SELECT * FROM mitglieder WHERE name = 'Testläufer B'").fetchone())
        lauf_id, _ = _lauf_jetzt(con, "Testläufer B", 4.5, 30, [390])
        texte = chat.lauf_melden(con, ich, lauf_id, stand)
        assert any("längster Lauf mit 4,50 km" in t for t in texte)
        assert any("30 m bergauf" in t for t in texte)
        assert any("6:30" in t for t in texte)
        assert any("überholt" in t for t in texte)                      # B: 4,0 → 8,8 LK > A 5,2 LK
        ueberholt = [x for x in p.post if x[3]["art"] == "ueberholt"]
        assert [x[0] for x in ueberholt] == [TOKEN + "A"] and "Testläufer B hat dich" in ueberholt[0][1]
    finally:
        p.fertig()


def test_push_arten_abschalten():
    a, b, con = _familie()
    assert b.get("/api/ich/push-arten").get_json()["arten"] == {"lauf": True, "chat": True, "reaktion": True, "ueberholt": True}
    assert b.post("/api/ich/push-arten", json={"art": "chat", "an": False}).get_json()["arten"]["chat"] is False
    assert b.post("/api/ich/push-arten", json={"art": "spam", "an": False}).status_code == 400
    p = Postbote()
    try:
        a.post("/api/chat", json={"text": "Hallo"})
        assert p.post == []
        b.post("/api/ich/push-arten", json={"art": "chat", "an": True})
        a.post("/api/chat", json={"text": "Hallo nochmal"})
        assert p.an(TOKEN + "B")
    finally:
        p.fertig()
    f = b.get("/api/familie").get_json()
    assert f["chat_ungelesen"] == 2 and f["push_arten"]["chat"] is True


def test_ohne_schluessel_nichts():
    a, b, con = _familie()
    fremd = a.application.test_client()
    assert fremd.get("/api/chat").status_code == 401 and fremd.post("/api/chat", json={"text": "x"}).status_code == 401
