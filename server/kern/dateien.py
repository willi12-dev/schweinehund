"""Lauf-Dateien lesen: GPX (1.0/1.1) und TCX, wie sie Huawei Health und Garmin Connect exportieren.

Ergebnis ist immer ein einheitliches dict (siehe `Lauf`); die Summenwerte (Distanz, Dauer, Anstieg) werden aus der
Datei übernommen, wenn sie dort stehen – so zeigt die App dieselben Zahlen wie die Uhr. Fehlen sie, rechnen wir sie
aus den Punkten nach. Der Anstieg kommt nie aus den Einzelhöhen (Höhenmesser driften), nur aus der Datei-Summe
oder – ersatzweise – geglättet aus den Punkten.
"""
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


class DateiFehler(Exception):
    """Die Datei ist kein lesbarer Lauf (Text ist für Menschen gedacht)."""


def _zeit(text):
    text = (text or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    t = datetime.fromisoformat(text)
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _name(tag):
    return tag.rsplit("}", 1)[-1]


def _kinder(el, name):
    return [k for k in el if _name(k.tag) == name]


def _erstes(el, name):
    for k in el.iter():
        if _name(k.tag) == name:
            return k
    return None


def _zahl(el, name):
    k = _erstes(el, name) if el is not None else None
    try:
        return float(k.text) if k is not None and k.text else None
    except ValueError:
        return None


def abstand_m(a, b):
    """Haversine-Abstand zweier Punkte (lat, lon) in Metern."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _sicher_parsen(daten: bytes):
    kopf = daten[:2000].decode("utf-8", "ignore").upper()
    if "<!DOCTYPE" in kopf or "<!ENTITY" in kopf:
        raise DateiFehler("Die Datei enthält nicht erlaubte XML-Bestandteile.")
    try:
        return ET.fromstring(daten)
    except ET.ParseError:
        raise DateiFehler("Die Datei ist kein gültiges GPX/TCX (XML fehlerhaft).")


def lesen(daten: bytes, dateiname: str = ""):
    """Erkennt das Format am Inhalt (nicht an der Endung – Huawei verschickt oft ohne klaren Typ)."""
    if not daten or len(daten) < 50:
        raise DateiFehler("Die Datei ist leer.")
    wurzel = _sicher_parsen(daten)
    art = _name(wurzel.tag)
    if art == "gpx":
        lauf = _gpx(wurzel)
    elif art == "TrainingCenterDatabase":
        lauf = _tcx(wurzel)
    else:
        raise DateiFehler("Unbekanntes Dateiformat – erwartet wird GPX oder TCX.")
    if len(lauf["punkte"]) < 2:
        raise DateiFehler("In der Datei ist keine GPS-Strecke enthalten.")
    return _vervollstaendigen(lauf)


def _gpx(wurzel):
    trk = next((k for k in wurzel.iter() if _name(k.tag) == "trk"), None)
    if trk is None:
        raise DateiFehler("Die GPX-Datei enthält keine aufgezeichnete Strecke (trk).")
    punkte = []
    for p in trk.iter():
        if _name(p.tag) != "trkpt":
            continue
        ele, t = _zahl(p, "ele"), _erstes(p, "time")
        punkte.append((float(p.get("lat")), float(p.get("lon")), ele, _zeit(t.text if t is not None else "")))
    ext = next((k for k in trk if _name(k.tag) == "extensions"), None)
    art = _erstes(trk, "type")
    return {"format": "gpx", "art": (art.text or "").strip() if art is not None else "",
            "punkte": punkte, "distanz_m": _zahl(ext, "totalDistance"), "dauer_s": _zahl(ext, "totalTime"),
            "anstieg_m": _zahl(ext, "cumulativeClimb"), "puls_avg": None}


def _tcx(wurzel):
    akt = _erstes(wurzel, "Activity")
    if akt is None:
        raise DateiFehler("Die TCX-Datei enthält keine Aktivität.")
    punkte, puls, distanz, dauer, anstieg = [], [], 0.0, 0.0, 0.0
    hat_distanz = hat_dauer = hat_anstieg = False
    for lap in _kinder(akt, "Lap"):
        d, z, a = _zahl(lap, "DistanceMeters"), _zahl(lap, "TotalTimeSeconds"), _zahl(lap, "CumulativeClimb")
        if d is not None:
            distanz, hat_distanz = distanz + d, True
        if z is not None:
            dauer, hat_dauer = dauer + z, True
        if a is not None:
            anstieg, hat_anstieg = anstieg + a, True
        for tp in lap.iter():
            if _name(tp.tag) != "Trackpoint":
                continue
            la, lo = _zahl(tp, "LatitudeDegrees"), _zahl(tp, "LongitudeDegrees")
            hf = _erstes(tp, "HeartRateBpm")
            if hf is not None:
                wert = _zahl(hf, "Value")
                if wert:
                    puls.append(wert)
            if la is None or lo is None:
                continue
            t = _erstes(tp, "Time")
            punkte.append((la, lo, _zahl(tp, "AltitudeMeters"), _zeit(t.text if t is not None else "")))
    return {"format": "tcx", "art": akt.get("Sport", ""), "punkte": punkte,
            "distanz_m": distanz if hat_distanz else None, "dauer_s": dauer if hat_dauer else None,
            "anstieg_m": anstieg if hat_anstieg else None,
            "puls_avg": round(sum(puls) / len(puls)) if puls else None}


def _vervollstaendigen(lauf):
    punkte = lauf["punkte"]
    gemessen = sum(abstand_m(punkte[i - 1], punkte[i]) for i in range(1, len(punkte)))
    zeiten = [p[3] for p in punkte if p[3]]
    start = zeiten[0] if zeiten else None
    if not lauf["distanz_m"]:
        lauf["distanz_m"] = gemessen
    if not lauf["dauer_s"] and len(zeiten) >= 2:
        lauf["dauer_s"] = (zeiten[-1] - zeiten[0]).total_seconds()
    if lauf["anstieg_m"] is None:
        lauf["anstieg_m"] = anstieg_geglaettet([p[2] for p in punkte if p[2] is not None])
    lauf["start"] = start
    lauf["gemessen_m"] = gemessen
    lauf["km_zeiten"] = km_zeiten(punkte, lauf["distanz_m"])
    lauf["art"] = _laufart(lauf["art"])
    return lauf


def _laufart(text):
    t = (text or "").lower()
    return "laufen" if not t or re.search(r"lauf|run", t) else t


def anstieg_geglaettet(hoehen, schwelle=3.0):
    """Ersatz, wenn die Datei keine Summe hat: zählt nur Anstiege über der Schwelle (gegen Messrauschen)."""
    if not hoehen:
        return 0.0
    summe, basis = 0.0, hoehen[0]
    for h in hoehen[1:]:
        if h - basis >= schwelle:
            summe, basis = summe + (h - basis), h
        elif basis - h >= schwelle:
            basis = h
    return round(summe, 1)


def km_zeiten(punkte, distanz_summe):
    """Zeiten je voller Kilometer in Sekunden, auf die offizielle Distanz skaliert, plus Rest (m, s)."""
    mit_zeit = [p for p in punkte if p[3]]
    if len(mit_zeit) < 2:
        return {"km": [], "rest_m": 0, "rest_s": 0}
    kumuliert = [0.0]
    for i in range(1, len(mit_zeit)):
        kumuliert.append(kumuliert[-1] + abstand_m(mit_zeit[i - 1], mit_zeit[i]))
    faktor = (distanz_summe / kumuliert[-1]) if distanz_summe and kumuliert[-1] else 1.0
    t0 = mit_zeit[0][3]
    marken, naechster = [], 1000.0
    for i in range(1, len(mit_zeit)):
        while kumuliert[i] * faktor >= naechster:
            vorher, jetzt = kumuliert[i - 1] * faktor, kumuliert[i] * faktor
            anteil = (naechster - vorher) / (jetzt - vorher) if jetzt > vorher else 1.0
            sek = (mit_zeit[i - 1][3] - t0).total_seconds() + anteil * (mit_zeit[i][3] - mit_zeit[i - 1][3]).total_seconds()
            marken.append(sek)
            naechster += 1000.0
    km = [round(b - a) for a, b in zip([0.0] + marken[:-1], marken)]
    gesamt = (mit_zeit[-1][3] - t0).total_seconds()
    return {"km": km, "rest_m": round(kumuliert[-1] * faktor - len(km) * 1000),
            "rest_s": round(gesamt - (marken[-1] if marken else 0.0))}


def linie(punkte, hoechstens=400):
    """Strecke als normierte Linie (0..1, Norden oben, seitenrichtig) – für die Vorschau ohne Kartenkacheln."""
    if len(punkte) < 2:
        return []
    schritt = max(1, math.ceil(len(punkte) / hoechstens))
    auswahl = punkte[::schritt] + ([punkte[-1]] if (len(punkte) - 1) % schritt else [])
    lat0 = sum(p[0] for p in auswahl) / len(auswahl)
    k = math.cos(math.radians(lat0))
    xs = [p[1] * k for p in auswahl]
    ys = [-p[0] for p in auswahl]
    ausdehnung = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    return [[round((x - min(xs)) / ausdehnung, 4), round((y - min(ys)) / ausdehnung, 4)] for x, y in zip(xs, ys)]
