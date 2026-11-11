"""Echte Lauf-Dateien für die Tests anonymisieren: alle Koordinaten werden um einen festen Betrag verschoben,
damit kein echter Wohnort ins Repo gelangt. Breitengrad nur minimal (Längenmaßstab bleibt gleich), Längengrad
deutlich – Form, Distanzen, Zeiten und Höhen bleiben unverändert.

  python tools/anonymisieren.py <eingabe.gpx|.tcx> <ausgabe>
"""
import re
import sys

VERSATZ_BREITE = 0.0373
VERSATZ_LAENGE = 2.9561


def anonymisieren(text: str) -> str:
    def breite(m):
        return f"{m.group(1)}{float(m.group(2)) + VERSATZ_BREITE:.9f}{m.group(3)}"

    def laenge(m):
        return f"{m.group(1)}{float(m.group(2)) + VERSATZ_LAENGE:.9f}{m.group(3)}"

    text = re.sub(r'(lat=")([-\d.]+)(")', breite, text)
    text = re.sub(r'(lon=")([-\d.]+)(")', laenge, text)
    text = re.sub(r"(<LatitudeDegrees>)([-\d.]+)(</LatitudeDegrees>)", breite, text)
    text = re.sub(r"(<LongitudeDegrees>)([-\d.]+)(</LongitudeDegrees>)", laenge, text)
    return text


if __name__ == "__main__":
    quelle, ziel = sys.argv[1], sys.argv[2]
    with open(quelle, encoding="utf-8") as f:
        inhalt = anonymisieren(f.read())
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(inhalt)
    print(f"anonymisiert: {ziel}")
