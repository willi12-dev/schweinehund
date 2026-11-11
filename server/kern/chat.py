"""Familienchat, Reaktionen, Kommentare, Horst-Meldungen und Push-Auslöser (REQ-006).

Die eine Stelle dafür, wer wann eine Nachricht bekommt. Push-Arten (einzeln abschaltbar):
lauf (neuer Lauf in der Familie), chat (neue Chatnachricht), reaktion (Reaktion/Kommentar auf meinen Lauf),
ueberholt (jemand hat mich in der Wochenrangliste überholt).
"""
import json
import random
from datetime import datetime, timedelta, timezone

from kern import punkte, push
from kern.datenbank import TZ

ARTEN = ("lauf", "chat", "reaktion", "ueberholt")
EMOJIS = ("👏", "🔥", "💪", "😂", "🐷")
MAX_TEXT = 500
MAX_PRO_MINUTE = 30
MELDEN_TAGE = 3          # ältere Läufe (z. B. beim ersten Health-Connect-Abgleich) meldet Horst nicht mehr

HORST_LAUF = [
    "{name} ist {km} km gelaufen. Horst beißt ins Sofakissen.",
    "{name}: {km} km. Horst tut so, als hätte er es nicht gesehen.",
    "{km} km von {name}. Horst murmelt etwas von „Glück gehabt“.",
    "{name} war {km} km unterwegs. Horst bestellt sich aus Frust eine Pizza.",
    "Schon wieder {name}! {km} km. Horst zieht die Decke über den Kopf.",
]
HORST_REKORD = {
    "weit": "Neuer Bestwert für {name}: längster Lauf mit {wert}! Horst muss sich setzen. Er saß schon.",
    "hoch": "Neuer Bestwert für {name}: {wert} bergauf! Horst hat schon beim Lesen Muskelkater.",
    "schnell": "Neuer Bestwert für {name}: schnellster Kilometer in {wert}! Horst hat nur den Fahrtwind gespürt.",
}
HORST_UEBERHOLT = "{name} hat {andere} in der Wochenrangliste überholt. Horst holt Popcorn."


class ChatFehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def _jetzt():
    return datetime.now(timezone.utc)


def _zeit(t=None):
    return (t or _jetzt()).isoformat(timespec="seconds")


def _text(text):
    text = str(text or "").strip()
    if not text:
        raise ChatFehler("Bitte etwas schreiben.")
    if len(text) > MAX_TEXT:
        raise ChatFehler(f"Höchstens {MAX_TEXT} Zeichen.")
    return text


def _mitglied(con, mitglied_id):
    z = con.execute("SELECT * FROM mitglieder WHERE id = ?", (mitglied_id,)).fetchone()
    return dict(z) if z else None


def _lauf(con, lauf_id):
    z = con.execute("SELECT * FROM laeufe WHERE id = ?", (lauf_id,)).fetchone()
    if z is None or z["mitglied_id"] is None:
        raise ChatFehler("Lauf nicht gefunden.", 404)
    return dict(z)


# ------------------------------------------------------------------ Push
def _zustellen(token, titel, text, daten):
    """Eine Nachricht an ein Handy – Tests ersetzen diese Funktion."""
    push.senden(token, titel, text, daten=daten)


def push_an(con, empfaenger_ids, art, titel, text, daten=None):
    """Push an Mitglieder, die diese Art nicht abgeschaltet haben und ein Handy gemeldet haben. Ergebnis: Anzahl."""
    n = 0
    for mid in set(empfaenger_ids):
        m = _mitglied(con, mid)
        if not m or not m["push_token"] or art in (m.get("push_aus") or "").split(","):
            continue
        try:
            _zustellen(m["push_token"], titel, text, dict(daten or {}, art=art))
            n += 1
        except push.PushFehler:
            pass
    return n


def _alle_ausser(con, mitglied_id):
    return [z["id"] for z in con.execute("SELECT id FROM mitglieder WHERE id != ?", (mitglied_id,))]


def push_einstellen(con, ich, art, an):
    if art not in ARTEN:
        raise ChatFehler("Unbekannte Push-Art.")
    aus = {a for a in (ich.get("push_aus") or "").split(",") if a}
    (aus.discard if an else aus.add)(art)
    wert = ",".join(sorted(aus))
    con.execute("UPDATE mitglieder SET push_aus = ? WHERE id = ?", (wert, ich["id"]))
    return {a: a not in aus for a in ARTEN}


def push_stand(ich):
    aus = (ich.get("push_aus") or "").split(",")
    return {a: a not in aus for a in ARTEN}


# ------------------------------------------------------------------ Chat
def _fuer_app(con, z, ich_id):
    absender = None
    if z["mitglied_id"] is not None:
        m = _mitglied(con, z["mitglied_id"])
        absender = {"id": m["id"], "name": m["name"], "farbe": m["farbe"], "kuerzel": m["kuerzel"]} if m else None
    lokal = datetime.fromisoformat(z["zeit"]).astimezone(TZ)
    return {"id": z["id"], "text": z["text"], "horst": z["mitglied_id"] is None, "absender": absender,
            "eigen": z["mitglied_id"] == ich_id, "lauf_id": z["lauf_id"],
            "zeit": z["zeit"], "zeit_text": f"{lokal:%d.%m. %H:%M}"}


def senden(con, ich, text):
    text = _text(text)
    seit = _zeit(_jetzt() - timedelta(minutes=1))
    if con.execute("SELECT COUNT(*) FROM nachrichten WHERE mitglied_id = ? AND zeit >= ?", (ich["id"], seit)).fetchone()[0] \
            >= MAX_PRO_MINUTE:
        raise ChatFehler("Langsam! Höchstens 30 Nachrichten pro Minute.", 429)
    cur = con.execute("INSERT INTO nachrichten (mitglied_id, text, zeit) VALUES (?, ?, ?)", (ich["id"], text, _zeit()))
    con.execute("UPDATE mitglieder SET chat_gelesen = ? WHERE id = ?", (cur.lastrowid, ich["id"]))
    push_an(con, _alle_ausser(con, ich["id"]), "chat", f"{ich['name']} im Familienchat", text[:120], {"ziel": "chat"})
    return _fuer_app(con, con.execute("SELECT * FROM nachrichten WHERE id = ?", (cur.lastrowid,)).fetchone(), ich["id"])


def horst(con, text, lauf_id=None):
    con.execute("INSERT INTO nachrichten (mitglied_id, text, lauf_id, zeit) VALUES (NULL, ?, ?, ?)", (text, lauf_id, _zeit()))


def loeschen(con, ich, nachricht_id):
    z = con.execute("SELECT mitglied_id FROM nachrichten WHERE id = ?", (nachricht_id,)).fetchone()
    if z is None:
        raise ChatFehler("Nachricht nicht gefunden.", 404)
    if z["mitglied_id"] != ich["id"]:
        raise ChatFehler("Nur eigene Nachrichten lassen sich löschen.", 403)
    con.execute("DELETE FROM nachrichten WHERE id = ?", (nachricht_id,))


def liste(con, ich, nach_id=0, anzahl=100):
    """Die neuesten Nachrichten (älteste zuerst); mit nach_id nur neuere – für das Nachfragen bei offenem Chat."""
    if nach_id:
        zeilen = con.execute("SELECT * FROM nachrichten WHERE id > ? ORDER BY id LIMIT ?", (nach_id, anzahl)).fetchall()
    else:
        zeilen = con.execute("SELECT * FROM (SELECT * FROM nachrichten ORDER BY id DESC LIMIT ?) ORDER BY id",
                             (anzahl,)).fetchall()
    return [_fuer_app(con, z, ich["id"]) for z in zeilen]


def gelesen(con, ich, bis_id):
    con.execute("UPDATE mitglieder SET chat_gelesen = MAX(chat_gelesen, ?) WHERE id = ?", (int(bis_id), ich["id"]))


def ungelesen(con, ich):
    stand = con.execute("SELECT chat_gelesen FROM mitglieder WHERE id = ?", (ich["id"],)).fetchone()[0]
    return con.execute("SELECT COUNT(*) FROM nachrichten WHERE id > ? AND (mitglied_id IS NULL OR mitglied_id != ?)",
                       (stand, ich["id"])).fetchone()[0]


# ------------------------------------------------------------------ Reaktionen und Kommentare
def reaktion_umschalten(con, ich, lauf_id, emoji):
    if emoji not in EMOJIS:
        raise ChatFehler("Diese Reaktion gibt es nicht.")
    lauf = _lauf(con, lauf_id)
    da = con.execute("SELECT 1 FROM reaktionen WHERE lauf_id = ? AND mitglied_id = ? AND emoji = ?",
                     (lauf_id, ich["id"], emoji)).fetchone()
    if da:
        con.execute("DELETE FROM reaktionen WHERE lauf_id = ? AND mitglied_id = ? AND emoji = ?", (lauf_id, ich["id"], emoji))
    else:
        con.execute("INSERT INTO reaktionen (lauf_id, mitglied_id, emoji, zeit) VALUES (?, ?, ?, ?)",
                    (lauf_id, ich["id"], emoji, _zeit()))
        if lauf["mitglied_id"] != ich["id"]:
            push_an(con, [lauf["mitglied_id"]], "reaktion", f"{ich['name']} reagiert {emoji}",
                    f"auf deinen Lauf über {punkte.zahl((lauf['distanz_m'] or 0) / 1000)} km",
                    {"ziel": "lauf", "lauf_id": lauf_id})
    return reaktionen(con, [lauf_id], ich["id"]).get(lauf_id, [])


def reaktionen(con, lauf_ids, ich_id):
    """{lauf_id: [{emoji, anzahl, ich, namen}]} in fester Emoji-Reihenfolge."""
    if not lauf_ids:
        return {}
    fragen = ",".join("?" * len(lauf_ids))
    roh = {}
    for z in con.execute(f"SELECT r.lauf_id, r.emoji, r.mitglied_id, m.name FROM reaktionen r "
                         f"JOIN mitglieder m ON m.id = r.mitglied_id WHERE r.lauf_id IN ({fragen}) ORDER BY r.zeit",
                         list(lauf_ids)):
        e = roh.setdefault(z["lauf_id"], {}).setdefault(z["emoji"], {"emoji": z["emoji"], "anzahl": 0, "ich": False, "namen": []})
        e["anzahl"] += 1
        e["ich"] = e["ich"] or z["mitglied_id"] == ich_id
        e["namen"].append(z["name"])
    return {lid: [r[e] for e in EMOJIS if e in r] for lid, r in roh.items()}


def kommentieren(con, ich, lauf_id, text):
    text = _text(text)
    lauf = _lauf(con, lauf_id)
    con.execute("INSERT INTO kommentare (lauf_id, mitglied_id, text, zeit) VALUES (?, ?, ?, ?)",
                (lauf_id, ich["id"], text, _zeit()))
    if lauf["mitglied_id"] != ich["id"]:
        push_an(con, [lauf["mitglied_id"]], "reaktion", f"{ich['name']} kommentiert deinen Lauf", text[:120],
                {"ziel": "lauf", "lauf_id": lauf_id})
    return kommentare(con, lauf_id, ich["id"])


def kommentar_loeschen(con, ich, kommentar_id):
    z = con.execute("SELECT mitglied_id FROM kommentare WHERE id = ?", (kommentar_id,)).fetchone()
    if z is None:
        raise ChatFehler("Kommentar nicht gefunden.", 404)
    if z["mitglied_id"] != ich["id"]:
        raise ChatFehler("Nur eigene Kommentare lassen sich löschen.", 403)
    con.execute("DELETE FROM kommentare WHERE id = ?", (kommentar_id,))


def kommentare(con, lauf_id, ich_id):
    liste = []
    for z in con.execute("SELECT k.*, m.name, m.farbe, m.kuerzel FROM kommentare k JOIN mitglieder m ON m.id = k.mitglied_id "
                         "WHERE k.lauf_id = ? ORDER BY k.id", (lauf_id,)):
        lokal = datetime.fromisoformat(z["zeit"]).astimezone(TZ)
        liste.append({"id": z["id"], "text": z["text"], "eigen": z["mitglied_id"] == ich_id,
                      "absender": {"id": z["mitglied_id"], "name": z["name"], "farbe": z["farbe"], "kuerzel": z["kuerzel"]},
                      "zeit_text": f"{lokal:%d.%m. %H:%M}"})
    return liste


# ------------------------------------------------------------------ Neue Läufe: Horst und Push
def _bestwerte(con, mitglied_id, ohne_lauf=None):
    weit = hoch = 0.0
    schnell = None
    n = 0
    for z in con.execute("SELECT * FROM laeufe WHERE mitglied_id = ? AND id != ?", (mitglied_id, ohne_lauf or 0)):
        if not punkte.zaehlt(z):
            continue
        n += 1
        weit = max(weit, z["distanz_m"] or 0)
        hoch = max(hoch, z["anstieg_m"] or 0)
        for s in (json.loads(z["km_zeiten"]).get("km", []) if z["km_zeiten"] else []):
            if s > 0:
                schnell = s if schnell is None else min(schnell, s)
    return {"n": n, "weit": weit, "hoch": hoch, "schnell": schnell}


def vorher(con, ich):
    """Stand vor dem Speichern: Wochen-LK aller (für „überholt“)."""
    return {z["mitglied"]["id"]: z["lk_wert"] for z in punkte.rangliste(con, "woche")["zeilen"]}


def lauf_melden(con, ich, lauf_id, stand_vorher, jetzt=None):
    """Nach einem NEU gespeicherten Lauf: Horst meldet sich, Pushes für Lauf, Bestwert und Überholen.
    Zu alte Läufe (Health-Connect-Nachlese) und nicht zählende Läufe bleiben still."""
    lauf = _lauf(con, lauf_id)
    jetzt = jetzt or _jetzt()
    if not punkte.zaehlt(lauf) or datetime.fromisoformat(lauf["start"]) < jetzt - timedelta(days=MELDEN_TAGE):
        return []
    name, km = ich["name"], punkte.zahl((lauf["distanz_m"] or 0) / 1000)
    meldungen = [random.choice(HORST_LAUF).format(name=name, km=km)]
    push_an(con, _alle_ausser(con, ich["id"]), "lauf", f"{name} ist gelaufen 🏃", f"{km} km – und du?",
            {"ziel": "lauf", "lauf_id": lauf_id})

    alt = _bestwerte(con, ich["id"], ohne_lauf=lauf_id)
    if alt["n"]:
        if (lauf["distanz_m"] or 0) > alt["weit"]:
            meldungen.append(HORST_REKORD["weit"].format(name=name, wert=f"{km} km"))
        if (lauf["anstieg_m"] or 0) > alt["hoch"] and lauf["anstieg_m"]:
            meldungen.append(HORST_REKORD["hoch"].format(name=name, wert=f"{round(lauf['anstieg_m'])} m"))
        km_neu = [s for s in (json.loads(lauf["km_zeiten"]).get("km", []) if lauf["km_zeiten"] else []) if s > 0]
        if km_neu and alt["schnell"] and min(km_neu) < alt["schnell"]:
            s = min(km_neu)
            meldungen.append(HORST_REKORD["schnell"].format(name=name, wert=f"{s // 60}:{s % 60:02d}"))

    nachher = vorher(con, ich)
    mein_vorher, mein_nachher = stand_vorher.get(ich["id"], 0), nachher.get(ich["id"], 0)
    ueberholt = [mid for mid, lk in nachher.items()
                 if mid != ich["id"] and lk > 0 and mein_vorher <= lk < mein_nachher]
    if ueberholt:
        namen = [_mitglied(con, mid)["name"] for mid in ueberholt]
        meldungen.append(HORST_UEBERHOLT.format(name=name, andere=" und ".join(namen)))
        push_an(con, ueberholt, "ueberholt", f"{name} hat dich gerade überholt 😱", "Wochenrangliste – Zeit für einen Lauf?",
                {"ziel": "rangliste"})
    for text in meldungen:
        horst(con, text, lauf_id)
    return meldungen
