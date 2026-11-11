"""Punkte und Rangliste (REQ-004) – die eine Stelle für die Punkteregeln.

Leistungskilometer (LK) = Kilometer + Anstieg ÷ 100. Es zählen Läufe ab 1 km; die Sichtbarkeit der Strecke spielt
keine Rolle. Wochen laufen Montag bis Sonntag, Monate nach Kalender – beides in Berliner Zeit.
"""
import json
from datetime import datetime, timedelta, timezone

from kern.datenbank import TZ, einstellung, einstellung_setzen

MINDEST_M = 1000
ZIEL_STANDARD = 40.0
ZIEL_SCHLUESSEL = "familienziel_lk"
HORST = [   # (ab Prozent, Spruch) – je voller das Horst-o-Meter, desto kleinlauter Horst
    (0, "Horst liegt auf dem Sofa und lacht euch aus."),
    (25, "Horst wird unruhig und sucht die Fernbedienung."),
    (50, "Horst schwitzt. Er hat das nicht kommen sehen."),
    (75, "Horst packt heimlich seine Sachen."),
    (100, "Horst ist besiegt – für diese Woche."),
]


def lk(distanz_m, anstieg_m):
    return (distanz_m or 0) / 1000 + (anstieg_m or 0) / 100


def zaehlt(lauf):
    return (lauf["art"] or "laufen") == "laufen" and (lauf["distanz_m"] or 0) >= MINDEST_M


def zahl(wert, stellen=2):
    return f"{wert:.{stellen}f}".replace(".", ",")


def wochenbeginn(jetzt):
    return (jetzt - timedelta(days=jetzt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def zeitraum(art, jetzt=None):
    """(von, bis, Beschriftung) in Berliner Zeit für „woche“ oder „monat“."""
    jetzt = (jetzt or datetime.now(TZ)).astimezone(TZ)
    if art == "monat":
        von = jetzt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        bis = (von + timedelta(days=32)).replace(day=1)
        monate = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                  "November", "Dezember"]
        return von, bis, f"{monate[von.month - 1]} {von.year}"
    von = wochenbeginn(jetzt)
    return von, von + timedelta(days=7), f"KW {von.isocalendar()[1]} · {von:%d.%m.} – {von + timedelta(days=6):%d.%m.}"


def _utc(t):
    return t.astimezone(timezone.utc).isoformat()


def _laeufe(con, von, bis, mitglied_id=None):
    sql = "SELECT * FROM laeufe WHERE mitglied_id IS NOT NULL AND start >= ? AND start < ?"
    werte = [_utc(von), _utc(bis)]
    if mitglied_id is not None:
        sql += " AND mitglied_id = ?"
        werte.append(mitglied_id)
    return [z for z in con.execute(sql, werte) if zaehlt(z)]


def rangliste(con, art="woche", jetzt=None):
    von, bis, text = zeitraum(art, jetzt)
    summen = {}
    for z in _laeufe(con, von, bis):
        s = summen.setdefault(z["mitglied_id"], {"lk": 0.0, "km": 0.0, "hm": 0.0, "laeufe": 0})
        s["lk"] += lk(z["distanz_m"], z["anstieg_m"])
        s["km"] += (z["distanz_m"] or 0) / 1000
        s["hm"] += z["anstieg_m"] or 0
        s["laeufe"] += 1
    zeilen = []
    for m in con.execute("SELECT * FROM mitglieder"):
        s = summen.get(m["id"], {"lk": 0.0, "km": 0.0, "hm": 0.0, "laeufe": 0})
        zeilen.append({"mitglied": {"id": m["id"], "name": m["name"], "farbe": m["farbe"], "kuerzel": m["kuerzel"]},
                       "lk_wert": round(s["lk"], 2), "lk": zahl(s["lk"]), "km": zahl(s["km"]),
                       "hm": round(s["hm"]), "laeufe": s["laeufe"]})
    zeilen.sort(key=lambda r: (-r["lk_wert"], r["mitglied"]["name"].lower()))
    platz, vorher = 0, None
    for i, r in enumerate(zeilen, 1):
        if r["lk_wert"] != vorher:
            platz, vorher = i, r["lk_wert"]
        r["platz"] = platz
    return {"zeitraum": art, "titel": text, "zeilen": zeilen}


def ziel(con):
    try:
        return float(einstellung(con, ZIEL_SCHLUESSEL, str(ZIEL_STANDARD)))
    except ValueError:
        return ZIEL_STANDARD


def ziel_setzen(con, wert):
    wert = float(wert)
    if not 5 <= wert <= 1000:
        raise ValueError("Das Familienziel muss zwischen 5 und 1000 LK liegen.")
    einstellung_setzen(con, ZIEL_SCHLUESSEL, round(wert, 1))


def horst_o_meter(con, jetzt=None):
    von, bis, _ = zeitraum("woche", jetzt)
    ist = sum(lk(z["distanz_m"], z["anstieg_m"]) for z in _laeufe(con, von, bis))
    soll = ziel(con)
    prozent = round(100 * ist / soll) if soll else 0
    spruch = [t for ab, t in HORST if prozent >= ab][-1]
    return {"ziel": zahl(soll, 0) if soll == int(soll) else zahl(soll, 1), "ziel_wert": soll, "ist": zahl(ist),
            "prozent": prozent, "spruch": spruch}


def fortschritt(con, mitglied_id, jetzt=None, wochen=8):
    """LK der letzten Wochen (älteste zuerst), die laufende Woche zuletzt."""
    beginn = wochenbeginn((jetzt or datetime.now(TZ)).astimezone(TZ))
    liste = []
    for i in range(wochen - 1, -1, -1):
        von = beginn - timedelta(days=7 * i)
        wert = sum(lk(z["distanz_m"], z["anstieg_m"]) for z in _laeufe(con, von, von + timedelta(days=7), mitglied_id))
        liste.append({"woche": f"KW {von.isocalendar()[1]}", "lk_wert": round(wert, 2), "lk": zahl(wert, 1)})
    return liste


def serie(con, mitglied_id, jetzt=None):
    """Wochen in Folge mit mindestens einem zählenden Lauf. Die laufende Woche zählt mit, bricht aber nicht."""
    beginn = wochenbeginn((jetzt or datetime.now(TZ)).astimezone(TZ))
    diese = bool(_laeufe(con, beginn, beginn + timedelta(days=7), mitglied_id))
    n, von = (1 if diese else 0), beginn - timedelta(days=7)
    while n < 520 and _laeufe(con, von, von + timedelta(days=7), mitglied_id):
        n, von = n + 1, von - timedelta(days=7)
    return {"wochen": n, "diese_woche": diese}


def bestwerte(con, mitglied_id):
    from kern.laeufe import dauer_text, km_text, start_text   # erst hier: vermeidet Kreis-Import
    laeufe = [z for z in con.execute("SELECT * FROM laeufe WHERE mitglied_id = ?", (mitglied_id,)) if zaehlt(z)]

    def wann(z):
        return start_text(datetime.fromisoformat(z["start"])).split(" ")[1]

    ergebnis = {}
    if laeufe:
        weit = max(laeufe, key=lambda z: z["distanz_m"] or 0)
        ergebnis["laengster"] = {"wert": f"{km_text(weit['distanz_m'])} km", "wann": wann(weit)}
        hoch = max(laeufe, key=lambda z: z["anstieg_m"] or 0)
        if hoch["anstieg_m"]:
            ergebnis["hoechster"] = {"wert": f"{round(hoch['anstieg_m'])} m", "wann": wann(hoch)}
        schnell = None
        for z in laeufe:
            km = json.loads(z["km_zeiten"]).get("km", []) if z["km_zeiten"] else []
            for s in km:
                if s > 0 and (schnell is None or s < schnell[0]):
                    schnell = (s, z)
        if schnell:
            ergebnis["schnellster_km"] = {"wert": f"{dauer_text(schnell[0])} /km", "wann": wann(schnell[1])}
    return ergebnis


def uebersicht(con, ich_id, art="woche", jetzt=None):
    return {"rangliste": rangliste(con, art, jetzt), "horst": horst_o_meter(con, jetzt),
            "ich": {"fortschritt": fortschritt(con, ich_id, jetzt), "serie": serie(con, ich_id, jetzt),
                    "bestwerte": bestwerte(con, ich_id)}}
