"""REQ-000: Version, Status und Startseite des Servers."""
from hilfen import WURZEL, neuer_server


def test_version_aus_datei():
    _, c, _ = neuer_server()
    soll = open(f"{WURZEL}/VERSION").read().strip()
    d = c.get("/version").get_json()
    assert d["version"] == soll, d
    assert "umgebung" in d and "build" in d


def test_status_meldet_push_nicht_eingerichtet_ohne_konto():
    _, c, _ = neuer_server(FIREBASE_KONTO_DATEI="")
    d = c.get("/api/status").get_json()
    assert d == {"server": "ok", "version": open(f"{WURZEL}/VERSION").read().strip(), "push": "nicht eingerichtet", "familie": False}, d


def test_startseite_deutsch():
    _, c, _ = neuer_server()
    r = c.get("/")
    assert r.status_code == 200 and "Schweinehund-Server" in r.get_data(as_text=True)


def test_version_gleich_in_app():
    """Die App zeigt dieselbe Version wie der Server (Gradle liest VERSION)."""
    gradle = open(f"{WURZEL}/app/composeApp/build.gradle.kts", encoding="utf-8").read()
    assert 'rootProject.file("../VERSION")' in gradle
