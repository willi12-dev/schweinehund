"""Deployment der TEST-Umgebung auf PythonAnywhere über die offizielle API (läuft in GitHub Actions bei jedem Push auf
„entwicklung“; Muster aus Zeugnis).

Benötigte Umgebungsvariablen (aus den GitHub-Secrets):
  PA_USERNAME, PA_API_TOKEN, PA_HOST (eu.pythonanywhere.com oder www.pythonanywhere.com)
Optional: FIREBASE_KONTO (Dienstkonto-JSON für Push), GIT_SHA, BACKUP_DIR, UMGEBUNG (Standard TEST)

Ablauf:
  1. Datenbank sichern (falls vorhanden) – der Workflow legt sie 30 Tage als Artefakt ab
  2. Server-Dateien, VERSION, .env und (falls vorhanden) das Firebase-Dienstkonto hochladen
  3. Web-App anlegen (nur beim ersten Mal), WSGI-Datei, HTTPS
  4. Web-App neu laden
  5. Prüfen, ob /version die neue Version meldet
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
PY_VERSIONS = ["python313", "python312", "python311", "python310"]


def dateien():
    """Alles, was der Server braucht – relativ zu server/."""
    liste = ["app.py", "schema.sql", "aufgabe_sonntagsshow.py"]
    for ordner in ("kern", "schnittstelle"):
        liste += [str(p.relative_to(SERVER)) for p in sorted((SERVER / ordner).glob("*.py"))]
    return liste


def env(name, required=True, default=""):
    v = os.environ.get(name, default).strip()
    if required and not v:
        sys.exit(f"FEHLER: GitHub-Secret {name} fehlt oder ist leer. Bitte unter Settings → Secrets and variables → Actions anlegen.")
    return v


def main():
    user = env("PA_USERNAME")
    token = env("PA_API_TOKEN")
    host = env("PA_HOST", required=False, default="eu.pythonanywhere.com").replace("https://", "").strip("/")
    domain = f"{user}.pythonanywhere.com" if host.startswith("www") else f"{user}.eu.pythonanywhere.com"
    api = os.environ.get("PA_API_URL") or f"https://{host}/api/v0/user/{user}/"
    site = os.environ.get("SITE_URL") or f"https://{domain}"
    appdir = f"/home/{user}/schweinehund"
    s = requests.Session()
    s.headers["Authorization"] = f"Token {token}"

    def call(method, path, expect=(200, 201), **kw):
        url = path if path.startswith("http") else api + path.lstrip("/")
        for _ in range(6):
            r = s.request(method, url, timeout=60, **kw)
            if r.status_code != 429:
                break
            time.sleep(15)
        if expect and r.status_code not in expect:
            if r.status_code in (401, 403):
                sys.exit(f"FEHLER: PythonAnywhere lehnt den Zugriff ab ({r.status_code}). PA_USERNAME, PA_API_TOKEN und PA_HOST prüfen.")
            sys.exit(f"FEHLER bei {method} {url}: {r.status_code} {r.text[:300]}")
        return r

    def upload(remote, inhalt: bytes):
        call("POST", f"files/path{remote}", files={"content": ("f", inhalt)})
        time.sleep(float(os.environ.get("UPLOAD_PAUSE", "1.0")))

    sha = os.environ.get("GIT_SHA", "")[:12]
    version = (ROOT / "VERSION").read_text().strip()
    print(f"Deploy Schweinehund v{version} ({sha}) nach https://{domain}")

    # 1. Datenbank sichern
    backup = Path(os.environ.get("BACKUP_DIR", ROOT / "backup"))
    backup.mkdir(parents=True, exist_ok=True)
    r = call("GET", f"files/path{appdir}/schweinehund.db", expect=None)
    if r.status_code == 200:
        ziel = backup / f"schweinehund_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.db"
        ziel.write_bytes(r.content)
        print(f"  Datenbank gesichert: {ziel.name} ({len(r.content)} Bytes)")
    else:
        print("  Noch keine Datenbank vorhanden (Erstinstallation).")

    # 2. Dateien hochladen
    for rel in dateien():
        upload(f"{appdir}/{rel}", (SERVER / rel).read_bytes())
        print(f"  hochgeladen: {rel}")
    upload(f"{appdir}/VERSION", (ROOT / "VERSION").read_bytes())
    upload(f"{appdir}/BUILD_INFO", f"{sha} {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC".encode())
    zeilen = [f"SECRET_KEY={hashlib.sha256(('schweinehund:' + token).encode()).hexdigest()}",
              f"UMGEBUNG={os.environ.get('UMGEBUNG', 'TEST')}"]
    konto = os.environ.get("FIREBASE_KONTO", "").strip()
    if konto:
        try:
            json.loads(konto)
        except ValueError:
            sys.exit("FEHLER: FIREBASE_KONTO ist kein gültiges JSON. Bitte den kompletten Inhalt der Dienstkonto-Datei als Secret eintragen.")
        upload(f"{appdir}/geheim/firebase_konto.json", konto.encode())
        zeilen.append(f"FIREBASE_KONTO_DATEI={appdir}/geheim/firebase_konto.json")
        print("  Firebase-Dienstkonto hochgeladen")
    else:
        print("  Kein FIREBASE_KONTO – Push bleibt „nicht eingerichtet“.")
    upload(f"{appdir}/.env", ("\n".join(zeilen) + "\n").encode())

    # 3. Web-App einrichten (idempotent)
    apps = {a["domain_name"]: a for a in call("GET", "webapps/").json()}
    if domain not in apps:
        for pv in PY_VERSIONS:
            r = call("POST", "webapps/", expect=None, data={"domain_name": domain, "python_version": pv})
            if r.status_code in (200, 201):
                print(f"  Web-App angelegt ({pv})")
                break
        else:
            sys.exit(f"FEHLER: Web-App konnte nicht angelegt werden: {r.status_code} {r.text[:300]}")
    wsgi = (f'import sys\npath = "{appdir}"\nif path not in sys.path:\n    sys.path.insert(0, path)\n'
            f'from app import app as application  # noqa\n')
    upload(f"/var/www/{domain.replace('.', '_').lower()}_wsgi.py", wsgi.encode())
    call("PATCH", f"webapps/{domain}/", expect=None, data={"force_https": "true"})

    # 3b. Sonntagsshow: Der kostenlose Tarif hat keine geplanten Aufgaben – .github/workflows/sonntagsshow.yml weckt
    #     den Server sonntags über POST /api/aufgabe/sonntagsshow (Schlüssel aus SECRET_KEY abgeleitet).

    # 4. Neu laden
    call("POST", f"webapps/{domain}/reload/")
    print("  Web-App neu geladen")

    # 5. Prüfen
    for _ in range(12):
        time.sleep(5)
        try:
            v = requests.get(f"{site}/version", timeout=20).json()
            if v.get("version") == version and v.get("build", "").startswith(sha):
                st = requests.get(f"{site}/api/status", timeout=20).json()
                print(f"OK: https://{domain} meldet v{version} ({sha}) · Push: {st.get('push')}")
                return
            print(f"  warte … Seite meldet {v}")
        except Exception as e:  # noqa: BLE001
            print(f"  warte … ({e.__class__.__name__})")
    sys.exit("FEHLER: Die Seite meldet nicht die neue Version. Error log im PythonAnywhere-Reiter Web prüfen.")


if __name__ == "__main__":
    main()
