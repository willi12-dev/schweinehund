"""Gemeinsame Hilfen für die Regeltests: frischer Server in einem Temp-Ordner."""
import os
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(WURZEL, "server")
os.environ["SCHWEINEHUND_KEIN_START"] = "1"
if SERVER not in sys.path:
    sys.path.insert(0, SERVER)


def neuer_server(**umgebung):
    """Flask-Testclient mit eigener Datenbank. umgebung setzt Umgebungsvariablen für diesen Test."""
    for k, v in umgebung.items():
        os.environ[k] = v
    import app as server_app
    ordner = tempfile.mkdtemp(prefix="sh_test_")
    a = server_app.erstellen(os.path.join(ordner, "test.db"), os.path.join(ordner, "sicherungen"))
    a.testing = True
    return a, a.test_client(), ordner


def angemeldeter_server(name="Testläufer A", geraet_id="geraet-test-0001", **umgebung):
    """Wie neuer_server, aber die Familie ist gegründet und der Client schickt den Schlüssel des Verwalters mit."""
    a, c, ordner = neuer_server(**umgebung)
    from kern import geraete
    geraete._versuche.clear()
    r = c.post("/api/familie/gruenden", json={"name": name, "geraet_id": geraet_id})
    assert r.status_code == 200, r.get_json()
    c.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + r.get_json()["schluessel"]
    return a, c, ordner
