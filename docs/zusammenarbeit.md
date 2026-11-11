# Zusammenarbeit mit Claude

## Umgebungen
| Umgebung | Branch | Wo | Daten |
|---|---|---|---|
| **TEST** | `entwicklung` | PythonAnywhere (kostenloses Konto) | nur erfundene Demo-Daten |
| **PROD** | `main` | zunächst PythonAnywhere, später ggf. Synology | echte Läufe der Familie |

## Ablauf für jede Änderung
1. **Anforderung besprechen** – „Neue Anforderung: …“. Claude stellt Rückfragen und legt eine Datei unter
   `docs/anforderungen/` an (Status *geplant*).
2. **Bestätigen** – erst nach „Ja, so umsetzen“ (o. Ä.) wird entwickelt.
3. **Entwickeln** – auf `entwicklung`, mit Tests und Screenshots, Status *in Entwicklung*,
   CHANGELOG-Abschnitt `## vX.Y.Z (in Entwicklung)`. Noch nichts live.
4. **Einspielen** – nur nach ausdrücklichem „Einspielen“: CHANGELOG mit Datum, Anforderungen auf *umgesetzt*,
   alle Tests grün, Push nach `main`, Deploy prüfen (`/version`).
5. **Zurückrollen** – Actions → „Deploy“ → „Run workflow“ mit Version (Daten bleiben).

| Sie schreiben | Was passiert |
|---|---|
| „Neue Anforderung: …“ | Rückfragen, Anforderung zum Bestätigen vorlegen |
| „Zeige mir vor Erstellung die Anforderung“ | nur Beschreibung, noch kein Code |
| „Fehler: …“ | Ursache suchen, beheben, Test ergänzen, Ergebnis zeigen |
| „Zeig mal“ | Screenshots des Entwicklungsstands |
| „Einspielen“ | neue Version live |
| „Zurück auf v0.x.x“ | auf eine ältere Version zurück (Daten bleiben) |
| „Merk dir für später: …“ | neue Anforderung mit Status *geplant* |

Versionsnummern: neue Funktion = mittlere Zahl (v0.2.0), Fehlerbehebung = letzte Zahl (v0.2.1).

## Grundregeln
- Alles auf Deutsch: Chat, Code-Namen, Kommentare, Doku, Commits, Oberfläche.
- **Keine echten Namen** im Repo, in der Doku und in Demo-Daten. Testdateien werden anonymisiert
  (Start und Ziel verschoben). Echte Namen gibt es nur in den PROD-Daten.
- **Keine Geheimnisse im Chat.** Secrets legt der Nutzer selbst in GitHub an; Claude nennt nur die Namen.
- Git-Autor und -Committer: `Schweinehund <schweinehund@noreply.local>`.
- Plattformspezifisches (Android / iOS) gehört nur ins Gesundheits-Modul der App; alles andere läuft auf beiden.
- Punkte, Auszeichnungen und Datenschutzregeln rechnet ausschließlich der Server.
- Design „weiches Grau“: Schiefergrau statt Schwarz, warmes Orange als Akzent, Inter + Lora kursiv für Horst.

## Secrets (Namen; Werte legt der Nutzer an)
GitHub → Settings → Secrets and variables → Actions:
`PA_USERNAME`, `PA_API_TOKEN`, `PA_HOST`, `FIREBASE_KONTO`, `FIREBASE_APP_KONFIG`.
