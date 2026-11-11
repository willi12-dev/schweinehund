# Ergebnisbericht Datentest (REQ-001, v0.2.0)

Stand 11.11.2026 · Praxistest mit zwei Samsung-Handys, Huawei-Uhr (Testläufer A) und Garmin-Uhr (Testläufer B).

## Ergebnis in einem Satz
Läufe beider Uhren-Welten kommen **kostenlos und vollständig** in die App – Zahlen wie auf der Uhr und GPS-Strecke.
Für die Strecke braucht Garmin noch einen Umweg über die Garmin-Webseite.

## Praxistest
| Weg | Lauf | Uhr | App | Bewertung |
|---|---|---|---|---|
| A: Huawei TCX/GPX teilen | 01.06., 4,93 km | 42:12 · ↑ 72 m · km 8:09 / 8:54 / 9:21 / 8:03 · Rest 7:45 | 42:12 · ↑ 72 m · km 8:09 / 8:54 / 9:20 / 8:05 · Rest 7:45 | ✅ Summen exakt, km-Zeiten ≤ 2 s |
| A: Huawei Teilen-Bild | 01.06. | Puls 144 · Kadenz 148 · 6.280 Schritte | gleich, demselben Lauf zugeordnet | ✅ (nach Korrektur, s. u.) |
| B: Garmin GPX (Webseite) | 10.11., 6,11 km | 38:23 · ↑ 35 m · Puls 155 | geschätzt 6,11 km · ↑ 34 m · Puls 155 | ✅ |
| B: Health Connect | 10.11. | 6,11 km | 6,11 km, mit der Datei zu **einem** Lauf zusammengeführt | ✅ |
| Push „Lauf angekommen“ | – | – | kommt nach dem Speichern | ✅ |

Regeltests: 35 Server-Tests mit den anonymisierten echten Dateien (Huawei GPX/TCX, Garmin GPX, Bildtexte) – alle grün.

## Gefundene und behobene Fehler
1. **Teilen brach den Upload selbst ab** („Server nicht erreichbar“, eigentlich `CancellationException`):
   Die App räumte die geteilte Datei weg und beendete dabei den laufenden Upload. Behoben; Baunummer in der App
   macht Test-Versionen unterscheidbar.
2. **Garmin-GPX ohne Summen:** Garmin schreibt keine Distanz/Anstieg in die Datei. Reine Punkt-Summe ergab
   6,18 km und 24 m. Jetzt geglättet (6,11 km / 34 m), geschätzte Werte haben den niedrigsten Rang und werden von
   Health Connect (Zahlen der Uhr) ersetzt; km-Zeiten werden umgerechnet.
3. **Schritte aus dem Bild:** Die Texterkennung las die Puls-Diagrammachse (83) als Schritte. Jetzt nur noch
   Werte aus derselben Zeile und passend zu Kadenz × Dauer.
4. **Installation:** wechselnde Debug-Signatur → „App nicht installiert“. Feste Test-Signatur.

## Was nicht geht (geprüft)
- **Garmin-Strecke über Health Connect:** Garmin schreibt Trainings ohne GPS-Route.
- **Garmin-Link teilen:** Download nur mit Anmeldung; der kostenlose Server darf Garmin nicht erreichen.
- **Strava:** Strava-Daten dürfen in fremden Apps nur dem jeweiligen Nutzer gezeigt werden – keine Familienwertung.
- **Offizielle Garmin-Schnittstelle:** nur für Firmen.

## Empfehlung
- **REQ-002 (Grundgerüst)** kann auf diesem Datenweg aufbauen: Datei + Bild + Health Connect, Zusammenführen über
  die Startzeit, Zahlen der Uhr haben Vorrang.
- **Garmin-Strecke komfortabel:** in REQ-011 prüfen, ob „Health Sync“ die GPS-Route nach Health Connect bringt;
  bis dahin Garmin-Webseite → „Als GPX exportieren“ → Teilen.
- **FIT-Dateien** erst, wenn ein Weg sie kostenlos aufs Handy bringt (die Garmin-App exportiert keine Dateien).
- **App-Größe** (≈ 58 MB durch die eingebaute Texterkennung) später verkleinern.
- Anzeige der Karte mit Straßen folgt mit REQ-003, Leistungskilometer mit Anstieg mit REQ-004.
