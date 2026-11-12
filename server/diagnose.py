"""Fehlersuche: zeigt Mitglieder (ohne Geheimnisse) und die letzten Einträge im Protokoll.

Auf PythonAnywhere: Reiter „Consoles“ → „Bash“ und dann
    python3 ~/schweinehund/diagnose.py
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
os.environ["SCHWEINEHUND_KEIN_START"] = "1"

import app as server_app  # noqa: E402
from kern import datenbank  # noqa: E402


def main():
    a = server_app.erstellen()
    con = datenbank.verbinden(a.config["DATENBANK"])
    print("Version:", open(os.path.join(HIER, "VERSION")).read().strip() if os.path.exists(os.path.join(HIER, "VERSION")) else "?")
    print("\nMitglieder:")
    for m in con.execute("SELECT id, name, rolle, beigetreten, schluessel, geraet_id FROM mitglieder ORDER BY id"):
        print(f"  {m['id']:>2} {m['name']:<12} {m['rolle']:<9} beigetreten={'ja' if m['beigetreten'] else 'nein'}"
              f"  Schlüssel={(m['schluessel'] or '')[:8] or 'KEINER'}  Gerät={(m['geraet_id'] or '')[:10]}")
    offen = con.execute("SELECT COUNT(*) FROM einladungen").fetchone()[0]
    print(f"\nOffene Einladungen: {offen}")
    print("\nLetzte 40 Protokoll-Einträge (neueste zuerst):")
    for z in con.execute("SELECT zeit, ereignis, details FROM protokoll ORDER BY id DESC LIMIT 40"):
        print(f"  {z['zeit']}  {z['ereignis']:<22} {z['details']}")
    con.close()


if __name__ == "__main__":
    main()
