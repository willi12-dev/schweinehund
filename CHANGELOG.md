# Änderungen

## v0.2.0 (11.11.2026)
- REQ-001 Datentest: Läufe per „Teilen“ übernehmen – GPX und TCX (Huawei Health, Garmin Connect), Teilen-Bild
  per Texterkennung auf dem Handy (Puls, Kadenz, Schritte), Läufe aus Health Connect (Garmin).
- Kontrollkarte vor dem Speichern; derselbe Lauf aus mehreren Quellen wird zusammengeführt (Startzeit ± 2 Min.).
- Offizielle Summen aus der Datei (Distanz, Dauer, Anstieg), Kilometerzeiten auf die Summe skaliert.
- Seite „Meine Läufe“ mit Detailansicht und Strecke als Linie; Push „Lauf angekommen“ nach dem Speichern.
- Garmin-GPX (ohne eigene Summen): Distanz und Anstieg geglättet geschätzt, Puls aus der Datei; die Zahlen der
  Uhr aus Health Connect ersetzen die Schätzung, Kilometerzeiten werden umgerechnet.
- Teilen bricht den Upload nicht mehr selbst ab; Baunummer in der App sichtbar.
- Datenbank-Änderungen 2 (Läufe, Entwürfe) und 3 (Garmin-Zahlen als Schätzung markieren).

## v0.1.0 (11.11.2026)
- REQ-000 Infrastruktur: Server-Gerüst (Flask + SQLite) mit `/version` und `/api/status`,
  nummerierte Datenbank-Migrationen mit Sicherung, Push-Probe über Firebase,
  App-Gerüst (Kotlin Multiplatform, Android) mit Startseite „Server erreichbar“,
  GitHub Actions für Prüfen, App-Bau und TEST-Umgebung auf PythonAnywhere.
- Test-App immer unter derselben Adresse: GitHub → Releases → „Test-Version“ → `schweinehund-test.apk`.
- Anleitung `docs/anleitung-firebase.md` für die Push-Einrichtung.
