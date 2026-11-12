"""Läufe speichern, zusammenführen und für die App aufbereiten (REQ-001).

Ablauf beim Teilen: Datei/Bildtext → `entwurf_anlegen` (Kontrollkarte in der App) → `bestaetigen` → gespeichert.
Health Connect speichert direkt (`aus_health_connect`).

Derselbe Lauf kann mehrfach kommen (Datei + Bild + Health Connect). Gleiche Startzeit (± 2 Min.) beim selben
Familienmitglied = derselbe Lauf: Die Angaben werden zusammengeführt. Distanz/Dauer/Anstieg kommen aus der besten Quelle
(Datei vor Health Connect vor Bild – eine Datei ohne eigene Summen, z. B. von Garmin, zählt nur als Schätzung
und weicht den Zahlen der Uhr aus Health Connect und vom Bild); Puls, Kadenz, Schritte und kcal ergänzt jede Quelle, die sie hat.
"""
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from kern import dateien
from kern.datenbank import TZ, jetzt_text

FENSTER_S = 120
RANG = {"datei-geschaetzt": 0, "bild": 1, "health-connect": 2, "datei": 3}
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
ZUSATZ = ("puls_avg", "kadenz", "schritte", "kcal")


# ------------------------------------------------------------------ Entwürfe (Kontrollkarte)
def _nach_json(lauf):
    d = {k: v for k, v in lauf.items() if k != "punkte"}
    d["start"] = lauf["start"].isoformat() if lauf.get("start") else None
    t0 = lauf["start"]
    d["punkte"] = [[round(p[0], 7), round(p[1], 7), p[2], round((p[3] - t0).total_seconds()) if p[3] and t0 else None]
                   for p in lauf.get("punkte") or []]
    return d


def _aus_json(d):
    lauf = dict(d)
    lauf["start"] = datetime.fromisoformat(d["start"]) if d.get("start") else None
    t0 = lauf["start"]
    lauf["punkte"] = [(p[0], p[1], p[2], t0 + timedelta(seconds=p[3]) if p[3] is not None and t0 else None)
                      for p in d.get("punkte") or []]
    return lauf


def entwurf_anlegen(con, lauf, quelle):
    con.execute("DELETE FROM entwuerfe WHERE angelegt < ?", (time.time() - 3600,))
    eid = uuid.uuid4().hex
    daten = _nach_json(lauf)
    daten["quelle"] = quelle
    con.execute("INSERT INTO entwuerfe (id, daten, angelegt) VALUES (?, ?, ?)", (eid, json.dumps(daten), time.time()))
    return eid


def entwurf_holen(con, eid):
    zeile = con.execute("SELECT daten FROM entwuerfe WHERE id = ? AND angelegt >= ?", (eid, time.time() - 3600)).fetchone()
    return _aus_json(json.loads(zeile["daten"])) if zeile else None


def besitzer(mitglied, geraet_id=""):
    """Wem ein Lauf gehört: das angemeldete Mitglied (und von welchem Handy er kam)."""
    return {"mitglied_id": mitglied["id"], "name": mitglied["name"], "geraet_id": geraet_id or mitglied.get("geraet_id") or ""}


def bestaetigen(con, eid, wem):
    lauf = entwurf_holen(con, eid)
    if lauf is None:
        return None
    con.execute("DELETE FROM entwuerfe WHERE id = ?", (eid,))
    return speichern(con, wem, lauf, lauf["quelle"])


# ------------------------------------------------------------------ Speichern und Zusammenführen
def _passender(con, mitglied_id, start):
    von = (start - timedelta(seconds=FENSTER_S)).isoformat()
    bis = (start + timedelta(seconds=FENSTER_S)).isoformat()
    return con.execute("SELECT * FROM laeufe WHERE mitglied_id = ? AND start BETWEEN ? AND ? ORDER BY id LIMIT 1",
                       (mitglied_id, von, bis)).fetchone()


def speichern(con, wem, lauf, quelle):
    """Ergebnis: (id, neu). Ohne Startzeit kann ein Lauf nicht gespeichert werden."""
    if not lauf.get("start"):
        raise ValueError("Der Lauf hat keine Startzeit.")
    start = lauf["start"].astimezone(timezone.utc).replace(microsecond=0)
    jetzt = jetzt_text()
    punkte = _nach_json(lauf)["punkte"] if lauf.get("punkte") else []
    rang = "datei-geschaetzt" if quelle == "datei" and lauf.get("geschaetzt") else quelle
    alt = _passender(con, wem["mitglied_id"], start)
    if alt is None:
        cur = con.execute(
            "INSERT INTO laeufe (mitglied_id, geraet_id, laeufer, start, art, distanz_m, dauer_s, anstieg_m, "
            "puls_avg, kadenz, schritte, kcal, km_zeiten, punkte, quellen, zahlen_quelle, angelegt, geaendert) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (wem["mitglied_id"], wem["geraet_id"], wem["name"], start.isoformat(), lauf.get("art") or "laufen", lauf.get("distanz_m"),
             lauf.get("dauer_s"), lauf.get("anstieg_m"), *(lauf.get(k) for k in ZUSATZ),
             json.dumps(lauf["km_zeiten"]) if lauf.get("km_zeiten") else "", json.dumps(punkte) if punkte else "",
             quelle, rang, jetzt, jetzt))
        return cur.lastrowid, True

    felder = {"laeufer": wem["name"], "geaendert": jetzt,
              "quellen": ",".join(sorted(set(filter(None, alt["quellen"].split(","))) | {quelle}))}
    zahlen_neu = RANG[rang] >= RANG.get(alt["zahlen_quelle"], 0)
    if zahlen_neu:
        felder.update(distanz_m=lauf.get("distanz_m") or alt["distanz_m"], dauer_s=lauf.get("dauer_s") or alt["dauer_s"],
                      anstieg_m=lauf.get("anstieg_m") if lauf.get("anstieg_m") is not None else alt["anstieg_m"],
                      zahlen_quelle=rang)
    if quelle == "datei":
        felder["start"] = start.isoformat()   # die Datei hat die sekundengenaue Startzeit
    if punkte:
        felder["punkte"] = json.dumps(punkte)
    # Kilometerzeiten immer auf die gültige Distanz umrechnen (Strecke aus der Datei, Distanz ggf. von der Uhr).
    gueltige_punkte = punkte or (json.loads(alt["punkte"]) if alt["punkte"] else [])
    if gueltige_punkte:
        distanz = felder.get("distanz_m", alt["distanz_m"])
        t0 = datetime.fromisoformat(felder.get("start", alt["start"]))
        tupel = [(p[0], p[1], p[2], t0 + timedelta(seconds=p[3]) if p[3] is not None else None) for p in gueltige_punkte]
        felder["km_zeiten"] = json.dumps(dateien.km_zeiten(tupel, distanz))
    for k in ZUSATZ:
        if lauf.get(k) is not None:
            felder[k] = lauf[k]
    con.execute(f"UPDATE laeufe SET {', '.join(f'{k} = ?' for k in felder)} WHERE id = ?", (*felder.values(), alt["id"]))
    return alt["id"], False


def aus_health_connect(con, wem, sitzungen, neue_ids=None):
    """sitzungen: Liste von dicts mit start, ende (ISO), distanz_m, anstieg_m, puls_avg, art. Ergebnis: (neu, ergänzt).
    neue_ids (Liste) sammelt die Nummern neu angelegter Läufe."""
    neu = ergaenzt = 0
    for s in sitzungen[:200]:
        try:
            start = datetime.fromisoformat(str(s["start"]).replace("Z", "+00:00"))
            ende = datetime.fromisoformat(str(s["ende"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        lauf = {"start": start, "dauer_s": max(0.0, (ende - start).total_seconds()), "art": s.get("art") or "laufen",
                "distanz_m": _float(s.get("distanz_m")), "anstieg_m": _float(s.get("anstieg_m")),
                "puls_avg": _int(s.get("puls_avg")), "punkte": [], "km_zeiten": None}
        lauf_id, ist_neu = speichern(con, wem, lauf, "health-connect")
        if ist_neu and neue_ids is not None:
            neue_ids.append(lauf_id)
        neu, ergaenzt = neu + ist_neu, ergaenzt + (not ist_neu)
    return neu, ergaenzt


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(v):
    f = _float(v)
    return round(f) if f is not None else None


# ------------------------------------------------------------------ Aufbereitung für die App
def dauer_text(sek):
    if sek is None:
        return "–"
    sek = round(sek)
    h, rest = divmod(sek, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def km_text(meter):
    return "–" if meter is None else f"{meter / 1000:.2f}".replace(".", ",")


def start_text(start):
    lokal = start.astimezone(TZ)
    return f"{WOCHENTAGE[lokal.weekday()]} {lokal:%d.%m.} {lokal:%H:%M}"


def _tempo(distanz, dauer):
    if not distanz or not dauer:
        return "–"
    return dauer_text(dauer / (distanz / 1000)) + " /km"


def fuer_app(lauf, quellen, mit_linie=True, lauf_id=None):
    start = lauf["start"] if isinstance(lauf["start"], datetime) else datetime.fromisoformat(lauf["start"])
    km = lauf.get("km_zeiten") or {}
    if isinstance(km, str):
        km = json.loads(km) if km else {}
    punkte = lauf.get("punkte") or []
    if isinstance(punkte, str):
        punkte = [tuple(p) for p in json.loads(punkte)] if punkte else []
    d = {"id": lauf_id, "start": start.isoformat(), "start_text": start_text(start), "art": lauf.get("art") or "laufen",
         "distanz_km": km_text(lauf.get("distanz_m")), "dauer": dauer_text(lauf.get("dauer_s")),
         "tempo": _tempo(lauf.get("distanz_m"), lauf.get("dauer_s")),
         "anstieg_m": None if lauf.get("anstieg_m") is None else round(lauf["anstieg_m"]),
         "puls_avg": lauf.get("puls_avg"), "kadenz": lauf.get("kadenz"), "schritte": lauf.get("schritte"),
         "quellen": quellen, "hat_strecke": len(punkte) >= 2,
         "lk": f"{(lauf.get('distanz_m') or 0) / 1000 + (lauf.get('anstieg_m') or 0) / 100:.2f}".replace(".", ","),
         "km_zeiten": [dauer_text(s) for s in km.get("km", [])],
         "rest": f"{km['rest_m']} m in {dauer_text(km['rest_s'])}" if km.get("rest_m", 0) >= 50 else ""}
    if mit_linie:
        d["linie"] = dateien.linie(punkte)
    return d


_MIT_MITGLIED = ("SELECT l.*, m.name AS m_name, m.farbe AS m_farbe, m.kuerzel AS m_kuerzel "
                 "FROM laeufe l JOIN mitglieder m ON m.id = l.mitglied_id")


def _fuer(z, ich_id, detail):
    """Ein Lauf aus Sicht eines Familienmitglieds. Seit REQ-013 sieht die Familie alles (kein „nur für mich“ mehr)."""
    z = dict(z)
    d = fuer_app(z, z["quellen"].split(","), mit_linie=detail, lauf_id=z["id"])
    d.update(eigen=z["mitglied_id"] == ich_id,
             mitglied={"id": z["mitglied_id"], "name": z["m_name"], "farbe": z["m_farbe"], "kuerzel": z["m_kuerzel"]})
    if detail and d["hat_strecke"]:
        punkte = [tuple(p) for p in json.loads(z["punkte"])]
        d["karte"] = dateien.karte(punkte, z.get("distanz_m"))
    return d


def _mit_reaktionen(con, liste, ich_id):
    """Reaktionen, Kommentarzahl und Fotos (REQ-013) an jeden Lauf hängen."""
    from kern import chat, fotos   # erst hier: vermeidet Kreis-Import
    r = chat.reaktionen(con, [l["id"] for l in liste], ich_id)
    f = fotos.zu_laeufen(con, [l["id"] for l in liste])
    k = {z[0]: z[1] for z in con.execute(
        "SELECT lauf_id, COUNT(*) FROM kommentare WHERE lauf_id IN (%s) GROUP BY lauf_id" % ",".join("?" * len(liste)),
        [l["id"] for l in liste])} if liste else {}
    for l in liste:
        l["reaktionen"] = r.get(l["id"], [])
        l["kommentare_anzahl"] = k.get(l["id"], 0)
        l["fotos"] = f.get(l["id"], [])
    return liste


def liste(con, mitglied_id, ich_id=None, anzahl=50):
    """Die neuesten Läufe eines Mitglieds (auch ältere Läufe, die nachträglich geteilt werden)."""
    ich_id = mitglied_id if ich_id is None else ich_id
    zeilen = con.execute(_MIT_MITGLIED + " WHERE l.mitglied_id = ? ORDER BY l.start DESC LIMIT ?", (mitglied_id, anzahl))
    return _mit_reaktionen(con, [_fuer(z, ich_id, False) for z in zeilen], ich_id)


def familie_liste(con, ich_id, anzahl=50):
    """Die neuesten Läufe der ganzen Familie (REQ-003)."""
    zeilen = con.execute(_MIT_MITGLIED + " ORDER BY l.start DESC LIMIT ?", (anzahl,))
    return _mit_reaktionen(con, [_fuer(z, ich_id, False) for z in zeilen], ich_id)


def detail(con, lauf_id, ich_id):
    from kern import chat
    z = con.execute(_MIT_MITGLIED + " WHERE l.id = ?", (lauf_id,)).fetchone()
    if not z:
        return None
    d = _mit_reaktionen(con, [_fuer(z, ich_id, True)], ich_id)[0]
    d["kommentare"] = chat.kommentare(con, lauf_id, ich_id)
    return d


def _eigener(con, lauf_id, ich_id):
    z = con.execute("SELECT id, mitglied_id FROM laeufe WHERE id = ?", (lauf_id,)).fetchone()
    if z is None:
        return "fehlt"
    return "ok" if z["mitglied_id"] == ich_id else "fremd"


def loeschen(con, lauf_id, ich_id):
    stand = _eigener(con, lauf_id, ich_id)
    if stand == "ok":
        from kern import fotos
        fotos.lauf_geloescht(con, lauf_id)
        con.execute("DELETE FROM laeufe WHERE id = ?", (lauf_id,))
    return stand
