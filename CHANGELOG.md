# Änderungen

## v0.5.0 (in Entwicklung)
- REQ-004 Punkte und Rangliste: Leistungskilometer (km + Höhenmeter ÷ 100), Rangliste Woche/Monat,
  Horst-o-Meter mit Familienziel (Start 40 LK, Verwalter ändert), eigener Fortschritt (8 Wochen),
  Serie „Wochen in Folge“, Bestwerte; LK an jedem Lauf. Es zählen Läufe ab 1 km.

## v0.4.0 (in Entwicklung)
- REQ-003 Läufe und Karte: Läufe der ganzen Familie (Reiter „Familie“ / „Meine“, Tipp auf ein Mitglied zeigt
  dessen Läufe), Detailansicht mit echter Karte (MapLibre + OpenFreeMap), Strecke nach Tempo eingefärbt,
  Start/Ziel und Kilometer-Marken.
- Sichtbarkeit pro Lauf: „Familie“ oder „nur ich“ (Familie sieht Zahlen ohne Karte, zählt trotzdem); Standard
  für neue Läufe unter „Ich“; eigene Läufe löschen.
- Karte mit Zoom-Knöpfen + / −; App nur noch für 64-Bit-Handys (38 statt 97 MB).
- Datenbank-Änderung 6: Sichtbarkeit an Läufen und Mitgliedern; 7: Testdatensatz (Praxistest-Läufe am 10.11.).

## v0.3.0 (in Entwicklung)
- REQ-002 Grundgerüst: Familie gründen (erster = Verwalter), Mitglieder per Einladungslink über WhatsApp
  (einmal gültig, 7 Tage, auch als Code eintippbar), Anmeldung ohne Passwort per Handy-Schlüssel.
- Neuer Link für ein Mitglied meldet dessen altes Handy ab; Läufe aus dem Datentest gehen beim Beitreten über.
- Vier Bereiche: Familie (Wochenkilometer, letzter Lauf), Läufe, Rangliste (Platzhalter), Ich (Farbe, Abmelden).
- Server liefert Daten nur noch mit gültigem Schlüssel; Einladungsseite im Browser, App-Links (assetlinks.json).
- Datenbank-Änderung 5: Mitglieder und Einladungen, Läufe gehören einem Mitglied.

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
