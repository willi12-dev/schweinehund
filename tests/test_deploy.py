"""REQ-000: Das Deploy-Skript lädt alle Server-Dateien hoch und bricht ohne Secrets mit klarer Meldung ab."""
import importlib.util
import os
import subprocess
import sys

from hilfen import WURZEL


def _modul():
    spec = importlib.util.spec_from_file_location("pa_deploy", os.path.join(WURZEL, "deploy", "pa_deploy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_alle_server_dateien_werden_hochgeladen():
    liste = _modul().dateien()
    for pflicht in ("app.py", "schema.sql", "kern/datenbank.py", "kern/migrationen.py", "kern/push.py",
                    "schnittstelle/allgemein.py", "schnittstelle/push.py"):
        assert pflicht in liste, pflicht
    vorhanden = {os.path.relpath(os.path.join(d, f), os.path.join(WURZEL, "server"))
                 for d, _, fs in os.walk(os.path.join(WURZEL, "server")) for f in fs if f.endswith(".py")}
    assert vorhanden - set(liste) == set(), vorhanden - set(liste)


def test_ohne_secret_klare_meldung():
    umgebung = {k: v for k, v in os.environ.items() if not k.startswith("PA_")}
    r = subprocess.run([sys.executable, os.path.join(WURZEL, "deploy", "pa_deploy.py")], env=umgebung,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "PA_USERNAME fehlt" in (r.stderr + r.stdout)
