"""Fotos zum Lauf (REQ-013): bis zu drei Bilder pro Lauf, für die ganze Familie sichtbar.

Die App verkleinert vor dem Hochladen schon; der Server rechnet trotzdem jedes Bild neu:
  - richtig herum drehen (Handy-Ausrichtung), höchstens 1280 px lange Seite, JPEG,
  - dabei fallen alle Zusatzdaten weg (EXIF, GPS-Standort, Kameramodell),
  - dazu ein quadratisches Vorschaubild (320 px) für die Lauf-Liste.
Die Dateien liegen im Ordner `fotos/` neben der Datenbank (nicht im Repo), in der Datenbank nur ihr Name.

REQ-014: Wo ein Foto auf der Strecke sitzt, bestimmt seine Aufnahmezeit (nicht der GPS-Standort im Bild – den
entfernen Android und wir ohnehin). Vor dem Start → Start, nach dem Ende oder ohne Zeit → Ziel.
"""
import bisect
import io
import json
import os
import random
import uuid
from datetime import datetime, timezone

from PIL import Image, ImageOps, UnidentifiedImageError

from kern import dateien, datenbank
from kern.datenbank import TZ

MAX_FOTOS = 3
MAX_BYTES = 8 * 1024 * 1024
MAX_SEITE = 1280
VORSCHAU = 320
Image.MAX_IMAGE_PIXELS = 50_000_000      # Schutz vor „Bildbomben“ (riesige Pixelzahl in kleiner Datei)

HORST_FOTO = [
    "{name} zeigt Gesicht. Horst schaut weg.",
    "Beweisfoto von {name}! Horst behauptet, es sei gestellt.",
    "{name} hat ein Lauf-Selfie hochgeladen. Horst sucht sein Sofakissen zum Draufsetzen.",
    "Frisch gelaufen und schon fotografiert: {name}. Horst wird ein bisschen rot.",
]


class FotoFehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def ordner():
    """Neben der Datenbank – so landen Fotos und Datenbank immer zusammen (auch in den Tests)."""
    pfad = os.path.join(os.path.dirname(os.path.abspath(datenbank.pfad())), "fotos")
    os.makedirs(pfad, exist_ok=True)
    return pfad


def _jpeg(bild, qualitaet):
    puffer = io.BytesIO()
    bild.save(puffer, "JPEG", quality=qualitaet, optimize=True, progressive=True)   # ohne exif= → keine Zusatzdaten
    return puffer.getvalue()


def _aufnahmezeit(bild):
    """Aufnahmezeit aus den EXIF-Daten (falls die App sie nicht schon entfernt hat), sonst None."""
    try:
        exif = bild.getexif().get_ifd(0x8769)
        text = exif.get(36867) or bild.getexif().get(306)          # DateTimeOriginal, sonst DateTime
        if not text:
            return None
        zeit = datetime.strptime(str(text).strip(), "%Y:%m:%d %H:%M:%S")
        versatz = exif.get(36881)                                  # OffsetTimeOriginal, z. B. "+01:00"
        if versatz:
            return datetime.fromisoformat(zeit.isoformat() + str(versatz).strip())
        return zeit.replace(tzinfo=TZ)
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def zeit_lesen(text):
    """Aufnahmezeit aus der App (ISO 8601). Ohne Zeitzone gilt Berliner Zeit."""
    try:
        t = datetime.fromisoformat(str(text or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=TZ)


def aufbereiten(daten):
    """Rohes Bild → (großes JPEG, Vorschau-JPEG, breite, hoehe, aufnahmezeit). Wirft FotoFehler bei Unbrauchbarem."""
    if not daten:
        raise FotoFehler("Kein Bild übergeben.")
    if len(daten) > MAX_BYTES:
        raise FotoFehler("Das Bild ist zu groß (höchstens 8 MB).", 413)
    try:
        bild = Image.open(io.BytesIO(daten))
        if bild.format not in ("JPEG", "PNG", "WEBP"):
            raise FotoFehler("Bitte ein Foto als JPEG, PNG oder WebP schicken.", 415)
        bild.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise FotoFehler("Das ist kein lesbares Bild.", 415)
    aufgenommen = _aufnahmezeit(bild)
    bild = ImageOps.exif_transpose(bild)          # Ausrichtung übernehmen, bevor die EXIF-Daten wegfallen
    if bild.mode != "RGB":
        hintergrund = Image.new("RGB", bild.size, (243, 244, 247))
        hintergrund.paste(bild, mask=bild.convert("RGBA").split()[-1])
        bild = hintergrund
    gross = bild.copy()
    gross.thumbnail((MAX_SEITE, MAX_SEITE), Image.LANCZOS)
    klein = ImageOps.fit(bild, (VORSCHAU, VORSCHAU), Image.LANCZOS, centering=(0.5, 0.4))
    return _jpeg(gross, 82), _jpeg(klein, 78), gross.width, gross.height, aufgenommen


def _lauf(con, lauf_id):
    z = con.execute("SELECT id, mitglied_id FROM laeufe WHERE id = ?", (lauf_id,)).fetchone()
    if z is None:
        raise FotoFehler("Lauf nicht gefunden.", 404)
    return z


def hochladen(con, ich, lauf_id, daten, aufgenommen=None):
    """Foto an den eigenen Lauf hängen. aufgenommen: Aufnahmezeit aus der App (ISO), sonst aus dem Bild.
    Ergebnis: das Foto für die App."""
    lauf = _lauf(con, lauf_id)
    if lauf["mitglied_id"] != ich["id"]:
        raise FotoFehler("Fotos kannst du nur an deine eigenen Läufe hängen.", 403)
    vorhanden = con.execute("SELECT COUNT(*) FROM fotos WHERE lauf_id = ?", (lauf_id,)).fetchone()[0]
    if vorhanden >= MAX_FOTOS:
        raise FotoFehler(f"Höchstens {MAX_FOTOS} Fotos pro Lauf – lösch erst eins.", 409)
    gross, klein, breite, hoehe, aus_bild = aufbereiten(daten)
    zeit = zeit_lesen(aufgenommen) if aufgenommen else aus_bild
    name = uuid.uuid4().hex
    with open(os.path.join(ordner(), name + ".jpg"), "wb") as f:
        f.write(gross)
    with open(os.path.join(ordner(), name + "_klein.jpg"), "wb") as f:
        f.write(klein)
    cur = con.execute("INSERT INTO fotos (lauf_id, mitglied_id, datei, breite, hoehe, angelegt, aufgenommen) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (lauf_id, ich["id"], name, breite, hoehe, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       zeit.astimezone(timezone.utc).isoformat(timespec="seconds") if zeit else None))
    positionen(con, lauf_id)
    if vorhanden == 0:   # Horst meldet nur das erste Foto eines Laufs
        from kern import chat
        chat.horst(con, random.choice(HORST_FOTO).format(name=ich["name"]), lauf_id)
    return _fuer_app(con.execute("SELECT * FROM fotos WHERE id = ?", (cur.lastrowid,)).fetchone())


def _dateien_weg(name):
    for endung in (".jpg", "_klein.jpg"):
        try:
            os.remove(os.path.join(ordner(), name + endung))
        except FileNotFoundError:
            pass


def loeschen(con, ich, foto_id):
    z = con.execute("SELECT * FROM fotos WHERE id = ?", (foto_id,)).fetchone()
    if z is None:
        raise FotoFehler("Foto nicht gefunden.", 404)
    if z["mitglied_id"] != ich["id"]:
        raise FotoFehler("Das ist nicht dein Foto.", 403)
    con.execute("DELETE FROM fotos WHERE id = ?", (foto_id,))
    _dateien_weg(z["datei"])


def lauf_geloescht(con, lauf_id):
    """Ein Lauf ist weg – seine Fotos auch."""
    for z in con.execute("SELECT datei FROM fotos WHERE lauf_id = ?", (lauf_id,)).fetchall():
        _dateien_weg(z["datei"])
    con.execute("DELETE FROM fotos WHERE lauf_id = ?", (lauf_id,))


def datei(con, foto_id, klein=False):
    """Pfad der Bilddatei (für alle Familienmitglieder) oder None."""
    z = con.execute("SELECT datei FROM fotos WHERE id = ?", (foto_id,)).fetchone()
    if z is None:
        return None
    pfad = os.path.join(ordner(), z["datei"] + ("_klein.jpg" if klein else ".jpg"))
    return pfad if os.path.isfile(pfad) else None


def _fuer_app(z):
    d = {"id": z["id"], "breite": z["breite"], "hoehe": z["hoehe"],
         "url": f"/api/laeufe/fotos/{z['id']}", "vorschau": f"/api/laeufe/fotos/{z['id']}?klein=1",
         "lat": z["lat"], "lon": z["lon"], "km": z["km"], "ort_text": ""}
    teile = []
    if z["km"] is not None:
        teile.append("am Start" if z["km"] < 0.05 else f"bei km {z['km']:.1f}".replace(".", ","))
    if z["aufgenommen"]:
        teile.append(f"{datetime.fromisoformat(z['aufgenommen']).astimezone(TZ):%H:%M}")
    d["ort_text"] = " · ".join(teile)
    return d


# ------------------------------------------------------------------ REQ-014: Position auf der Strecke
def stelle(punkte, start, distanz_m, aufgenommen):
    """Streckenpunkt zur Aufnahmezeit. punkte: [[lat, lon, hoehe, sekunde_seit_start], …] wie in der Datenbank.
    Ergebnis: (lat, lon, km) oder None (keine Strecke)."""
    if len(punkte) < 2:
        return None
    kum = [0.0]
    for i in range(1, len(punkte)):
        kum.append(kum[-1] + dateien.abstand_m(punkte[i - 1], punkte[i]))
    faktor = (distanz_m / kum[-1]) if distanz_m and kum[-1] else 1.0
    sekunden = [p[3] for p in punkte]
    i = len(punkte) - 1                                  # ohne Zeit: am Ziel
    if aufgenommen is not None and start is not None and all(s is not None for s in sekunden):
        t = (aufgenommen - start).total_seconds()
        if t <= sekunden[0]:
            i = 0
        elif t < sekunden[-1]:
            i = min(bisect.bisect_left(sekunden, t), len(punkte) - 1)
    return punkte[i][0], punkte[i][1], round(kum[i] * faktor / 1000, 2)


def positionen(con, lauf_id):
    """Alle Fotos eines Laufs (neu) auf die Strecke setzen – nach dem Hochladen und wenn die Strecke neu kommt."""
    lauf = con.execute("SELECT start, punkte, distanz_m FROM laeufe WHERE id = ?", (lauf_id,)).fetchone()
    if lauf is None:
        return
    punkte = json.loads(lauf["punkte"]) if lauf["punkte"] else []
    start = datetime.fromisoformat(lauf["start"])
    for z in con.execute("SELECT id, aufgenommen FROM fotos WHERE lauf_id = ?", (lauf_id,)).fetchall():
        zeit = datetime.fromisoformat(z["aufgenommen"]) if z["aufgenommen"] else None
        ort = stelle(punkte, start, lauf["distanz_m"], zeit)
        con.execute("UPDATE fotos SET lat = ?, lon = ?, km = ? WHERE id = ?",
                    (*(ort or (None, None, None)), z["id"]))


def zu_laeufen(con, lauf_ids):
    """{lauf_id: [foto, …]} in der Reihenfolge des Hochladens."""
    if not lauf_ids:
        return {}
    ergebnis = {}
    for z in con.execute("SELECT * FROM fotos WHERE lauf_id IN (%s) ORDER BY id" % ",".join("?" * len(lauf_ids)),
                         list(lauf_ids)):
        ergebnis.setdefault(z["lauf_id"], []).append(_fuer_app(z))
    return ergebnis
