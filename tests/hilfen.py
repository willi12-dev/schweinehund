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
