"""REQ-013: Fotos zum Lauf – bis zu drei, für die ganze Familie sichtbar, ohne Standortdaten."""
import io
import os

from PIL import Image

from hilfen import angemeldeter_server
from test_karte import _teilen_und_speichern, _zweites_mitglied


def _foto(breite=3000, hoehe=4000, format="JPEG", mit_gps=True, drehen=False):
    """Erfundenes Testbild: einfarbig, auf Wunsch mit GPS-Standort und Handy-Ausrichtung in den EXIF-Daten."""
    bild = Image.new("RGB", (breite, hoehe), (239, 116, 72))
    exif = Image.Exif()
    if mit_gps:
        exif[0x8825] = {1: "N", 2: (50.0, 6.0, 0.0), 3: "E", 4: (8.0, 30.0, 0.0)}   # erfundener Standort
        exif[0x0110] = "Testkamera"
    if drehen:
        exif[0x0112] = 6                                                          # „um 90° drehen“
    puffer = io.BytesIO()
    bild.save(puffer, format, **({"exif": exif} if format == "JPEG" else {}))
    return puffer.getvalue()


def _hochladen(c, lauf_id, daten, name="selfie.jpg"):
    return c.post(f"/api/laeufe/{lauf_id}/fotos", data={"foto": (io.BytesIO(daten), name)},
                  content_type="multipart/form-data")


def test_foto_hochladen_und_alle_sehen_es():
    _, a, ordner = angemeldeter_server()
    b = _zweites_mitglied(a)
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    r = _hochladen(a, lauf_id, _foto())
    assert r.status_code == 200, r.get_json()
    fotos = r.get_json()["lauf"]["fotos"]
    assert len(fotos) == 1 and (fotos[0]["breite"], fotos[0]["hoehe"]) == (960, 1280)
    # Familie sieht das Foto in der Liste und im Lauf
    liste = b.get("/api/laeufe/familie").get_json()["laeufe"]
    assert liste[0]["fotos"][0]["id"] == fotos[0]["id"]
    assert b.get(f"/api/laeufe/{lauf_id}").get_json()["lauf"]["fotos"] == fotos
    gross = b.get(fotos[0]["url"])
    assert gross.status_code == 200 and gross.mimetype == "image/jpeg"
    klein = b.get(fotos[0]["vorschau"])
    assert Image.open(io.BytesIO(klein.data)).size == (320, 320)
    assert len(os.listdir(os.path.join(ordner, "fotos"))) == 2


def test_standort_und_kamera_fallen_weg_ausrichtung_bleibt():
    _, a, _ = angemeldeter_server()
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    foto = _hochladen(a, lauf_id, _foto(4000, 3000, drehen=True)).get_json()["lauf"]["fotos"][0]
    bild = Image.open(io.BytesIO(a.get(foto["url"]).data))
    assert bild.size == (960, 1280)                     # quer aufgenommen, hochkant gehalten → hochkant
    assert dict(bild.getexif()) == {} and "exif" not in bild.info


def test_hoechstens_drei_fotos_und_loeschen():
    _, a, ordner = angemeldeter_server()
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    for _ in range(3):
        assert _hochladen(a, lauf_id, _foto(800, 600)).status_code == 200
    r = _hochladen(a, lauf_id, _foto(800, 600))
    assert r.status_code == 409 and "Höchstens 3" in r.get_json()["fehler"]
    fotos = a.get(f"/api/laeufe/{lauf_id}").get_json()["lauf"]["fotos"]
    r = a.delete(fotos[0]["url"])
    assert r.status_code == 200 and [f["id"] for f in r.get_json()["lauf"]["fotos"]] == [f["id"] for f in fotos[1:]]
    assert a.get(fotos[0]["url"]).status_code == 404
    assert _hochladen(a, lauf_id, _foto(800, 600)).status_code == 200
    assert len(os.listdir(os.path.join(ordner, "fotos"))) == 6


def test_nur_an_eigene_laeufe_und_nur_eigene_loeschen():
    _, a, _ = angemeldeter_server()
    b = _zweites_mitglied(a)
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    assert _hochladen(b, lauf_id, _foto(800, 600)).status_code == 403
    assert _hochladen(a, 999, _foto(800, 600)).status_code == 404
    foto = _hochladen(a, lauf_id, _foto(800, 600)).get_json()["lauf"]["fotos"][0]
    assert b.delete(foto["url"]).status_code == 403
    assert a.delete("/api/laeufe/fotos/999").status_code == 404


def test_ohne_schluessel_kein_foto():
    _, a, _ = angemeldeter_server()
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    foto = _hochladen(a, lauf_id, _foto(800, 600)).get_json()["lauf"]["fotos"][0]
    fremd = a.application.test_client()
    assert fremd.get(foto["url"]).status_code == 401
    assert _hochladen(fremd, lauf_id, _foto(800, 600)).status_code == 401


def test_falsche_dateien_werden_abgelehnt():
    _, a, _ = angemeldeter_server()
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    assert _hochladen(a, lauf_id, b"kein bild", "x.jpg").status_code == 415
    assert a.post(f"/api/laeufe/{lauf_id}/fotos", data={}, content_type="multipart/form-data").status_code == 400
    puffer = io.BytesIO()
    Image.new("RGB", (50, 50)).save(puffer, "GIF")
    assert _hochladen(a, lauf_id, puffer.getvalue(), "x.gif").status_code == 415
    # PNG mit Transparenz geht (wird JPEG)
    puffer = io.BytesIO()
    Image.new("RGBA", (400, 300), (0, 0, 0, 0)).save(puffer, "PNG")
    assert _hochladen(a, lauf_id, puffer.getvalue(), "x.png").status_code == 200


def test_lauf_loeschen_nimmt_fotos_mit():
    _, a, ordner = angemeldeter_server()
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    foto = _hochladen(a, lauf_id, _foto(800, 600)).get_json()["lauf"]["fotos"][0]
    assert a.delete(f"/api/laeufe/{lauf_id}").status_code == 200
    assert os.listdir(os.path.join(ordner, "fotos")) == []
    assert a.get(foto["url"]).status_code == 404


def test_horst_meldet_nur_das_erste_foto():
    _, a, _ = angemeldeter_server()
    lauf_id = _teilen_und_speichern(a, "huawei_lauf_b.tcx")
    vorher = len(a.get("/api/chat").get_json()["nachrichten"])
    _hochladen(a, lauf_id, _foto(800, 600))
    _hochladen(a, lauf_id, _foto(800, 600))
    neu = a.get("/api/chat").get_json()["nachrichten"][vorher:]
    assert len(neu) == 1 and neu[0]["horst"] and neu[0]["lauf_id"] == lauf_id and "Testläufer A" in neu[0]["text"]
