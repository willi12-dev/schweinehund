"""Familie, Mitglieder und Anmeldung per Einladungslink (REQ-002).

Ablauf: Der erste Mensch gründet die Familie und wird Verwalter. Der Verwalter legt Mitglieder an; jedes bekommt
einen Einladungscode (einmal gültig, 7 Tage). Wer ihn einlöst, bekommt einen geheimen Schlüssel für sein Handy.
Gespeichert werden nur Prüfsummen (SHA-256) von Codes und Schlüsseln – ein Blick in die Datenbank verrät keinen Zugang.
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta

from kern.datenbank import TZ, jetzt_text

GUELTIG_TAGE = 7
CODE_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # ohne 0/O und 1/I – lässt sich auch abtippen
CODE_LAENGE = 10
FARBEN = ["#EF7448", "#5B8DEF", "#9CC65A", "#B07CE0", "#E8B33F", "#3FB8AF", "#E06A8C", "#8A94A6"]
FARBE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class FamilienFehler(Exception):
    """Fehler mit einem Satz für die App und einem HTTP-Code."""

    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def pruefsumme(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def code_normal(code):
    return re.sub(r"[^A-Z0-9]", "", str(code).upper())


def _name(name):
    name = " ".join(str(name or "").split())[:30]
    if len(name) < 2:
        raise FamilienFehler("Bitte einen Namen mit mindestens zwei Zeichen angeben.")
    return name


def _farbe(con, farbe):
    farbe = str(farbe or "")
    if FARBE.match(farbe):
        return farbe.upper()
    belegt = {z["farbe"] for z in con.execute("SELECT farbe FROM mitglieder")}
    return next((f for f in FARBEN if f not in belegt), FARBEN[0])


def _kuerzel(name):
    teile = name.split()
    return (teile[0][0] + teile[1][0]).upper() if len(teile) > 1 else name[:2].capitalize()


def gegruendet(con):
    return con.execute("SELECT 1 FROM mitglieder LIMIT 1").fetchone() is not None


def _neuer_schluessel(con, mitglied_id, geraet_id):
    schluessel = secrets.token_urlsafe(32)
    con.execute("UPDATE mitglieder SET schluessel = ?, geraet_id = ?, beigetreten = COALESCE(beigetreten, ?) WHERE id = ?",
                (pruefsumme(schluessel), geraet_id or "", jetzt_text(), mitglied_id))
    # Läufe, die dieses Handy schon vor der Anmeldung geschickt hat (Datentest), gehören jetzt dem Mitglied.
    if geraet_id:
        con.execute("UPDATE laeufe SET mitglied_id = ? WHERE geraet_id = ? AND mitglied_id IS NULL", (mitglied_id, geraet_id))
    return schluessel


def gruenden(con, name, farbe, geraet_id):
    """Erstes Mitglied anlegen (Verwalter). Ergebnis: (mitglied, schluessel)."""
    if gegruendet(con):
        raise FamilienFehler("Die Familie gibt es schon – bitte um einen Einladungslink.", 409)
    jetzt = jetzt_text()
    name = _name(name)
    cur = con.execute("INSERT INTO mitglieder (name, farbe, kuerzel, rolle, angelegt) VALUES (?, ?, ?, 'verwalter', ?)",
                      (name, _farbe(con, farbe), _kuerzel(name), jetzt))
    schluessel = _neuer_schluessel(con, cur.lastrowid, geraet_id)
    return mitglied(con, cur.lastrowid), schluessel


def mitglied(con, mitglied_id):
    z = con.execute("SELECT * FROM mitglieder WHERE id = ?", (mitglied_id,)).fetchone()
    return dict(z) if z else None


def angemeldet(con, schluessel):
    """Mitglied zu einem Schlüssel aus der App – oder None."""
    if not schluessel or len(schluessel) > 200:
        return None
    z = con.execute("SELECT * FROM mitglieder WHERE schluessel = ?", (pruefsumme(schluessel),)).fetchone()
    return dict(z) if z else None


def anlegen(con, verwalter, name, farbe):
    """Neues Mitglied mit Einladung. Ergebnis: (mitglied, code)."""
    _nur_verwalter(verwalter)
    name = _name(name)
    if con.execute("SELECT 1 FROM mitglieder WHERE lower(name) = lower(?)", (name,)).fetchone():
        raise FamilienFehler(f"{name} gibt es in der Familie schon.", 409)
    cur = con.execute("INSERT INTO mitglieder (name, farbe, kuerzel, rolle, angelegt) VALUES (?, ?, ?, 'mitglied', ?)",
                      (name, _farbe(con, farbe), _kuerzel(name), jetzt_text()))
    return mitglied(con, cur.lastrowid), einladen(con, verwalter, cur.lastrowid)


def einladen(con, verwalter, mitglied_id):
    """Neuen Einladungscode für ein Mitglied. Ältere Codes und der bisherige Handy-Schlüssel werden ungültig
    (verlorenes oder neues Handy)."""
    _nur_verwalter(verwalter)
    if mitglied(con, mitglied_id) is None:
        raise FamilienFehler("Dieses Familienmitglied gibt es nicht.", 404)
    if mitglied_id == verwalter["id"]:
        raise FamilienFehler("Einen neuen Link für dich selbst erzeugt ein zweiter Verwalter.", 409)
    con.execute("DELETE FROM einladungen WHERE mitglied_id = ?", (mitglied_id,))
    con.execute("UPDATE mitglieder SET schluessel = NULL WHERE id = ?", (mitglied_id,))
    code = "".join(secrets.choice(CODE_ZEICHEN) for _ in range(CODE_LAENGE))
    bis = (datetime.now(TZ) + timedelta(days=GUELTIG_TAGE)).isoformat(timespec="seconds")
    con.execute("INSERT INTO einladungen (code, mitglied_id, gueltig_bis, angelegt) VALUES (?, ?, ?, ?)",
                (pruefsumme(code), mitglied_id, bis, jetzt_text()))
    return code


def einladung(con, code):
    """Gültige Einladung (mit Mitglied) zu einem Code – sonst FamilienFehler."""
    z = con.execute("SELECT e.*, m.name, m.farbe FROM einladungen e JOIN mitglieder m ON m.id = e.mitglied_id "
                    "WHERE e.code = ?", (pruefsumme(code_normal(code)),)).fetchone()
    if z is None:
        raise FamilienFehler("Diesen Einladungslink gibt es nicht (mehr). Bitte um einen neuen.", 404)
    if datetime.fromisoformat(z["gueltig_bis"]) < datetime.now(TZ):
        raise FamilienFehler("Der Einladungslink ist abgelaufen. Bitte um einen neuen.", 410)
    return dict(z)


def einloesen(con, code, geraet_id):
    """Einladung einlösen. Ergebnis: (mitglied, schluessel). Jeder Code gilt genau einmal."""
    e = einladung(con, code)
    con.execute("DELETE FROM einladungen WHERE id = ?", (e["id"],))
    schluessel = _neuer_schluessel(con, e["mitglied_id"], geraet_id)
    return mitglied(con, e["mitglied_id"]), schluessel


def farbe_aendern(con, ich, farbe):
    if not FARBE.match(str(farbe or "")):
        raise FamilienFehler("Unbekannte Farbe.")
    con.execute("UPDATE mitglieder SET farbe = ? WHERE id = ?", (farbe.upper(), ich["id"]))
    return mitglied(con, ich["id"])


def _nur_verwalter(m):
    if not m or m["rolle"] != "verwalter":
        raise FamilienFehler("Das darf nur der Familien-Verwalter.", 403)


def wochenbeginn(jetzt=None):
    """Montag 00:00 (Berliner Zeit) der laufenden Woche."""
    jetzt = jetzt or datetime.now(TZ)
    return (jetzt - timedelta(days=jetzt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def uebersicht(con, ich, jetzt=None):
    """Alle Mitglieder mit letztem Lauf und Kilometern dieser Woche – für die Seite „Familie“."""
    from kern import laeufe   # erst hier: laeufe braucht familie nicht, vermeidet Kreis-Import
    ab = wochenbeginn(jetzt).astimezone(laeufe.timezone.utc).isoformat()
    liste = []
    for m in con.execute("SELECT * FROM mitglieder ORDER BY rolle = 'verwalter' DESC, name"):
        letzter = con.execute("SELECT start, distanz_m FROM laeufe WHERE mitglied_id = ? ORDER BY start DESC LIMIT 1",
                              (m["id"],)).fetchone()
        woche = con.execute("SELECT COALESCE(SUM(distanz_m), 0), COUNT(*) FROM laeufe WHERE mitglied_id = ? AND start >= ?",
                            (m["id"], ab)).fetchone()
        offen = con.execute("SELECT 1 FROM einladungen WHERE mitglied_id = ?", (m["id"],)).fetchone() is not None
        liste.append({
            "id": m["id"], "name": m["name"], "farbe": m["farbe"], "kuerzel": m["kuerzel"], "rolle": m["rolle"],
            "ich": m["id"] == ich["id"], "beigetreten": bool(m["beigetreten"]) and m["schluessel"] is not None,
            "einladung_offen": offen,
            "letzter_lauf": None if letzter is None else {
                "start_text": laeufe.start_text(datetime.fromisoformat(letzter["start"])),
                "distanz_km": laeufe.km_text(letzter["distanz_m"])},
            "km_woche": laeufe.km_text(woche[0]) if woche[1] else "0", "laeufe_woche": woche[1],
        })
    return liste


def fuer_app(m):
    return {"id": m["id"], "name": m["name"], "farbe": m["farbe"], "kuerzel": m["kuerzel"], "rolle": m["rolle"]}
