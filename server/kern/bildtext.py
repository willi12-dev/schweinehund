"""Werte aus dem Text eines Teilen-Bildes (Screenshot aus Huawei Health) lesen.

Die App erkennt den Text auf dem Handy (Texterkennung) und schickt nur den Text. Weil die Texterkennung zweispaltige
Kacheln oft vermischt („Dauer Gesamtkalorien / 00:42:12 504 kcal“), suchen wir Werte über ihre Einheit
(bpm, Schritte/Min., kcal …) und nur wo nötig über das Etikett davor.
"""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
ZAHL = r"(?<![\d:])(\d{1,3}(?:\.\d{3})+|\d+)"


def _zahl(text):
    return float(text.replace(".", "").replace(",", ".")) if text else None


def _dezimal(text):
    return float(text.replace(",", ".")) if text else None


def _sekunden(hms):
    teile = [int(x) for x in hms.split(":")]
    while len(teile) < 3:
        teile.insert(0, 0)
    return teile[0] * 3600 + teile[1] * 60 + teile[2]


def _nach(text, etikett, muster, reichweite=60):
    m = re.search(etikett, text, re.I)
    if not m:
        return None
    return re.search(muster, text[m.end():m.end() + reichweite], re.I)


def lesen(text: str):
    """Ergebnis: dict mit den gefundenen Werten (fehlende = None). Mindestens Distanz oder Dauer muss da sein."""
    t = text.replace(" ", " ")
    werte = {"format": "bild", "art": "laufen" if re.search(r"lauf|run", t, re.I) else "", "punkte": [],
             "distanz_m": None, "dauer_s": None, "anstieg_m": None, "puls_avg": None, "kadenz": None,
             "schritte": None, "kcal": None, "start": None}

    m = re.search(r"(\d{1,3}[,.]\d{1,2})\s*km(?!\s*/\s*h)(?!/)", t, re.I)
    if m:
        werte["distanz_m"] = round(_dezimal(m.group(1)) * 1000)

    m = _nach(t, r"Dauer", r"(\d{1,2}:\d{2}:\d{2})") or re.search(r"(\d{1,2}:\d{2}:\d{2})(?!\s*/\s*km)", t)
    if m:
        werte["dauer_s"] = _sekunden(m.group(1))

    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4}),?\s+(\d{1,2}):(\d{2})", t)
    if m:
        tag, monat, jahr, std, minute = map(int, m.groups())
        try:
            werte["start"] = datetime(jahr, monat, tag, std, minute, tzinfo=TZ).astimezone(timezone.utc)
        except ValueError:
            pass

    m = re.search(r"(\d{2,3})\s*bpm", t, re.I)
    if m:
        werte["puls_avg"] = int(m.group(1))
    m = re.search(r"(\d{2,3})\s*Schritte\s*/\s*Min", t, re.I)
    if m:
        werte["kadenz"] = int(m.group(1))
    m = re.search(ZAHL + r"\s*Schritte(?!\s*/)", t)
    if m:
        werte["schritte"] = int(_zahl(m.group(1)))
    m = re.search(ZAHL + r"\s*kcal", t, re.I)
    if m:
        werte["kcal"] = int(_zahl(m.group(1)))
    m = _nach(t, r"H[öo]henunterschied|Anstieg", r"(\d{1,4}(?:[,.]\d)?)\s*m\b")
    if m:
        werte["anstieg_m"] = _dezimal(m.group(1))

    if not werte["distanz_m"] and not werte["dauer_s"]:
        return None
    return werte
