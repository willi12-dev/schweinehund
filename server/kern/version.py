"""Version und Build-Kennung – stehen in /version und in der App."""
import os

from kern.datenbank import SERVER_DIR


def _lesen(name):
    for ordner in (SERVER_DIR, os.path.dirname(SERVER_DIR)):
        p = os.path.join(ordner, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
    return ""


def version():
    return _lesen("VERSION") or "0.0.0"


def build():
    return _lesen("BUILD_INFO")
