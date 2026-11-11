# Änderungen

## v0.2.0 (in Entwicklung)
- REQ-001 Datentest: Läufe per „Teilen“ übernehmen – GPX und TCX (Huawei Health, Garmin Connect), Teilen-Bild
  per Texterkennung auf dem Handy (Puls, Kadenz, Schritte), Läufe aus Health Connect (Garmin).
- Kontrollkarte vor dem Speichern; derselbe Lauf aus mehreren Quellen wird zusammengeführt (Startzeit ± 2 Min.).
- Offizielle Summen aus der Datei (Distanz, Dauer, Anstieg), Kilometerzeiten auf die Summe skaliert.
- Seite „Meine Läufe“ mit Detailansicht und Strecke als Linie; Push „Lauf angekommen“ nach dem Speichern.
- Datenbank-Änderung 2: Tabellen für Läufe und Entwürfe.

## v0.1.0 (11.11.2026)
- REQ-000 Infrastruktur: Server-Gerüst (Flask + SQLite) mit `/version` und `/api/status`,
  nummerierte Datenbank-Migrationen mit Sicherung, Push-Probe über Firebase,
  App-Gerüst (Kotlin Multiplatform, Android) mit Startseite „Server erreichbar“,
  GitHub Actions für Prüfen, App-Bau und TEST-Umgebung auf PythonAnywhere.
- Test-App immer unter derselben Adresse: GitHub → Releases → „Test-Version“ → `schweinehund-test.apk`.
- Anleitung `docs/anleitung-firebase.md` für die Push-Einrichtung.
