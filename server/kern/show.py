"""Sonntagsshow (REQ-005): Sonntag 19 Uhr wird die Woche eingefroren und als Show enthüllt.

Die Show ist ein fester Stand (Tabelle shows): spätere Läufe ändern sie nicht mehr. Sie entsteht beim ersten Abruf
nach Sonntag 19 Uhr oder durch die tägliche Aufgabe, die auch den Push verschickt.
"""
import json
from datetime import datetime, timedelta

from kern import punkte, push
from kern.datenbank import TZ, einstellung, einstellung_setzen, jetzt_text, protokoll

SHOW_UHRZEIT = 19
WETTE_SCHLUESSEL = "familienwette"


def woche_schluessel(montag):
    jahr, kw, _ = montag.isocalendar()
    return f"{jahr}-W{kw:02d}"


def faellig_ab(montag):
    """Sonntag 19 Uhr der Woche, die an diesem Montag beginnt."""
    return (montag + timedelta(days=6)).replace(hour=SHOW_UHRZEIT, minute=0, second=0, microsecond=0)


def letzte_faellige_woche(jetzt):
    """Montag der jüngsten Woche, deren Show schon fällig ist."""
    montag = punkte.wochenbeginn(jetzt.astimezone(TZ))
    return montag if jetzt >= faellig_ab(montag) else montag - timedelta(days=7)


def _namen(zeilen):
    return [z["mitglied"]["name"] for z in zeilen]


def _preise(con, montag):
    """Sonderpreise der Woche. Gleichstand = mehrere Gewinner. Ohne passende Läufe kein Preis."""
    von, bis = montag, montag + timedelta(days=7)
    laeufe = [dict(z) for z in punkte._laeufe(con, von, bis)]
    namen = {m["id"]: m["name"] for m in con.execute("SELECT id, name FROM mitglieder")}
    preise = []

    def preis(titel, zeichen, text, werte, besser, format_):
        """werte: {mitglied_id: wert}; besser: max oder min."""
        werte = {k: v for k, v in werte.items() if v is not None}
        if not werte:
            return
        bester = besser(werte.values())
        gewinner = sorted(namen[k] for k, v in werte.items() if v == bester)
        preise.append({"titel": titel, "zeichen": zeichen, "text": text, "gewinner": gewinner, "wert": format_(bester)})

    hm = {}
    for l in laeufe:
        hm[l["mitglied_id"]] = hm.get(l["mitglied_id"], 0) + (l["anstieg_m"] or 0)
    preis("Bergziege", "⛰️", "meiste Höhenmeter", {k: round(v) for k, v in hm.items() if v > 0}, max, lambda v: f"{v} m")

    frueh = {}
    for l in laeufe:
        lokal = datetime.fromisoformat(l["start"]).astimezone(TZ)
        minuten = lokal.hour * 60 + lokal.minute
        frueh[l["mitglied_id"]] = min(frueh.get(l["mitglied_id"], 24 * 60), minuten)
    preis("Frühaufsteher", "🌅", "frühester Laufstart", frueh, min, lambda v: f"{v // 60}:{v % 60:02d} Uhr")

    weit = {}
    for l in laeufe:
        weit[l["mitglied_id"]] = max(weit.get(l["mitglied_id"], 0), round(l["distanz_m"] or 0))
    preis("Dauerläufer", "🛣️", "längster Lauf", weit, max, lambda v: f"{punkte.zahl(v / 1000)} km")

    schnell = {}
    for l in laeufe:
        km = json.loads(l["km_zeiten"]).get("km", []) if l["km_zeiten"] else []
        for s in km:
            if s > 0:
                schnell[l["mitglied_id"]] = min(schnell.get(l["mitglied_id"], s), s)
    preis("Tempomacher", "⚡", "schnellster Kilometer", schnell, min, lambda v: f"{v // 60}:{v % 60:02d} /km")

    jetzt_lk, vor_lk = {}, {}
    for l in laeufe:
        jetzt_lk[l["mitglied_id"]] = jetzt_lk.get(l["mitglied_id"], 0) + punkte.lk(l["distanz_m"], l["anstieg_m"])
    for l in punkte._laeufe(con, von - timedelta(days=7), von):
        vor_lk[l["mitglied_id"]] = vor_lk.get(l["mitglied_id"], 0) + punkte.lk(l["distanz_m"], l["anstieg_m"])
    plus = {k: round(v - vor_lk.get(k, 0), 2) for k, v in jetzt_lk.items()}
    preis("Comeback", "🚀", "größte Steigerung zur Vorwoche", {k: v for k, v in plus.items() if v > 0}, max,
          lambda v: f"+{punkte.zahl(v)} LK")
    return preise


def _monat(con, montag):
    """Monatsauflösung, wenn in dieser Woche ein Monat endet – sonst None."""
    for i in range(7):
        tag = montag + timedelta(days=i)
        if (tag + timedelta(days=1)).month != tag.month:
            r = punkte.rangliste(con, "monat", tag.replace(hour=12))
            spitze = [z for z in r["zeilen"] if z["platz"] == 1 and z["lk_wert"] > 0]
            return {"titel": r["titel"], "zeilen": r["zeilen"], "sieger": _namen(spitze)}
    return None


def _braucht_neu(con, schluessel):
    """Keine Show – oder nur eine vorgezogene, die zum echten Termin neu berechnet wird."""
    d = holen(con, schluessel)
    return d is None or d.get("vorgezogen", False)


def erstellen(con, montag, jetzt=None, vorgezogen=False):
    """Show für die Woche ab montag berechnen und einfrieren (überschreibt eine vorhandene)."""
    mitte = montag + timedelta(days=3)
    r = punkte.rangliste(con, "woche", mitte)
    zeilen = r["zeilen"]
    sieger = [z for z in zeilen if z["platz"] == 1 and z["lk_wert"] > 0]
    wette_text = wette(con)
    wette_daten = None
    if wette_text and zeilen:
        letzter = max(z["platz"] for z in zeilen)
        wette_daten = {"text": wette_text, "verlierer": _namen([z for z in zeilen if z["platz"] == letzter])}
    daten = {
        "woche": woche_schluessel(montag), "titel": r["titel"],
        "horst": punkte.horst_o_meter(con, mitte),
        "preise": _preise(con, montag),
        "zeilen": zeilen,
        "member_of_week": _namen(sieger),
        "wette": wette_daten,
        "monat": _monat(con, montag),
        "vorgezogen": vorgezogen,
    }
    con.execute("INSERT INTO shows (woche, erstellt, daten) VALUES (?, ?, ?) "
                "ON CONFLICT(woche) DO UPDATE SET erstellt = excluded.erstellt, daten = excluded.daten",
                (daten["woche"], (jetzt or datetime.now(TZ)).strftime("%Y-%m-%d %H:%M:%S"), json.dumps(daten)))
    return daten


def holen(con, woche):
    z = con.execute("SELECT * FROM shows WHERE woche = ?", (woche,)).fetchone()
    return json.loads(z["daten"]) if z else None


def aktuelle(con, jetzt=None):
    """Die jüngste fällige Show – beim ersten Abruf nach Sonntag 19 Uhr wird sie erstellt.
    Gibt es eine neuere, vorgezogene Show (Test), gilt die."""
    jetzt = jetzt or datetime.now(TZ)
    montag = letzte_faellige_woche(jetzt)
    schluessel = woche_schluessel(montag)
    if _braucht_neu(con, schluessel) and con.execute("SELECT 1 FROM laeufe LIMIT 1").fetchone():
        erstellen(con, montag, jetzt)
    z = con.execute("SELECT daten FROM shows ORDER BY woche DESC LIMIT 1").fetchone()
    return json.loads(z["daten"]) if z else None


def vorziehen(con, jetzt=None):
    """Show der laufenden Woche sofort erstellen (zum Testen / für den Verwalter)."""
    jetzt = jetzt or datetime.now(TZ)
    return erstellen(con, punkte.wochenbeginn(jetzt.astimezone(TZ)), jetzt, vorgezogen=True)


def ruhmeshalle(con):
    liste = []
    for z in con.execute("SELECT daten FROM shows ORDER BY woche DESC"):
        d = json.loads(z["daten"])
        liste.append({"woche": d["woche"], "titel": d["titel"], "member_of_week": d["member_of_week"],
                      "member_of_month": (d.get("monat") or {}).get("sieger") or [],
                      "monat": (d.get("monat") or {}).get("titel")})
    return liste


def wette(con):
    return einstellung(con, WETTE_SCHLUESSEL, "")


def wette_setzen(con, text):
    text = " ".join(str(text or "").split())[:140]
    einstellung_setzen(con, WETTE_SCHLUESSEL, text)
    return text


def push_an_alle(con, titel, text, post=None):
    """Push an jedes Mitglied mit gemeldetem Token. Ergebnis: Anzahl zugestellter Nachrichten."""
    n = 0
    for m in con.execute("SELECT id, push_token FROM mitglieder WHERE push_token != ''").fetchall():
        try:
            push.senden(m["push_token"], titel, text, post=post)
            n += 1
        except push.PushFehler:
            pass
    return n


def aufgabe(con, jetzt=None, post=None):
    """Tägliche Aufgabe: Ist eine Show fällig und noch nicht angekündigt, erstellen und Push an alle – genau einmal."""
    jetzt = jetzt or datetime.now(TZ)
    montag = letzte_faellige_woche(jetzt)
    if jetzt - faellig_ab(montag) > timedelta(days=1):
        return "keine Show fällig"
    schluessel = woche_schluessel(montag)
    if _braucht_neu(con, schluessel):
        erstellen(con, montag, jetzt)
    z = con.execute("SELECT push_gesendet FROM shows WHERE woche = ?", (schluessel,)).fetchone()
    if z["push_gesendet"]:
        return "schon angekündigt"
    d = holen(con, schluessel)
    n = push_an_alle(con, "Die Sonntagsshow ist da! 🎬",
                     f"{d['titel'].split(' ·')[0]}: Wer ist Member of the Week? Jetzt enthüllen.", post)
    con.execute("UPDATE shows SET push_gesendet = ? WHERE woche = ?", (jetzt_text(), schluessel))
    protokoll(con, "Sonntagsshow", f"{schluessel}: Push an {n} Handys")
    return f"Push an {n} Handys"
