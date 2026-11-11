# Firebase für Push-Nachrichten einrichten (einmalig, ca. 10 Minuten)

Firebase stellt nur Push-Nachrichten zu – Läufe, Karten und Chat liegen ausschließlich auf unserem Server.
Am besten am PC erledigen (zwei Dateien müssen als Text in GitHub-Secrets kopiert werden).

## 1. Projekt anlegen
1. <https://console.firebase.google.com> mit dem Google-Konto öffnen → **Projekt erstellen**.
2. Name: `schweinehund` → Google Analytics **ausschalten** → **Projekt erstellen**.

## 2. Android-App anmelden → Secret `FIREBASE_APP_KONFIG`
1. Auf der Projektseite das **Android-Symbol** wählen.
2. Android-Paketname: **`app.schweinehund`** (genau so), App-Spitzname: `Schweinehund` → **App registrieren**.
3. **google-services.json herunterladen**. Die restlichen Schritte des Assistenten überspringen („Weiter“).
4. Datei mit einem Texteditor öffnen, **gesamten Inhalt** kopieren.
5. GitHub → Repo `schweinehund` → Settings → Secrets and variables → Actions → **New repository secret**:
   Name `FIREBASE_APP_KONFIG`, Inhalt einfügen, speichern.

## 3. Dienstkonto für den Server → Secret `FIREBASE_KONTO`
1. In Firebase oben links auf das **Zahnrad** → **Projekteinstellungen** → Reiter **Dienstkonten**.
2. **Neuen privaten Schlüssel generieren** → bestätigen → eine JSON-Datei wird heruntergeladen.
3. Datei im Texteditor öffnen, **gesamten Inhalt** kopieren.
4. GitHub → New repository secret: Name `FIREBASE_KONTO`, Inhalt einfügen, speichern.
5. Die heruntergeladene Datei danach löschen – sie ist ein Schlüssel.

## 4. Fertig
Claude Bescheid geben. Beim nächsten Push auf `entwicklung` bekommt der Server das Dienstkonto
(`/api/status` meldet dann „Push: bereit“) und die App wird mit Push gebaut.
Neue App installieren → **Test-Push anfordern** → die Nachricht sollte nach wenigen Sekunden erscheinen.
