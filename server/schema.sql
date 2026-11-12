-- Vollständiger, aktueller Stand der Datenbank. Eine neue Datenbank entsteht direkt hieraus;
-- bestehende Datenbanken werden über die nummerierten Schritte in kern/migrationen.py nachgezogen.

CREATE TABLE IF NOT EXISTS einstellungen (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS protokoll (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    zeit     TEXT NOT NULL,
    ereignis TEXT NOT NULL,
    details  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS geraete (
    token     TEXT PRIMARY KEY,
    plattform TEXT NOT NULL DEFAULT 'android',
    angelegt  TEXT NOT NULL,
    zuletzt   TEXT NOT NULL
);

-- REQ-001: Läufe (aus Datei, Bild oder Health Connect; gleiche Startzeit ± 2 Min. = derselbe Lauf)
CREATE TABLE IF NOT EXISTS laeufe (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    geraet_id     TEXT NOT NULL,
    mitglied_id   INTEGER,                    -- REQ-002: wem der Lauf gehört (NULL = Handy noch nicht angemeldet)
    sichtbarkeit  TEXT NOT NULL DEFAULT 'familie',  -- REQ-003: 'familie' oder 'ich' (Strecke nur für den Läufer)
    laeufer       TEXT NOT NULL DEFAULT '',
    start         TEXT NOT NULL,              -- UTC, ISO 8601
    art           TEXT NOT NULL DEFAULT 'laufen',
    distanz_m     REAL,
    dauer_s       REAL,
    anstieg_m     REAL,
    puls_avg      INTEGER,
    kadenz        INTEGER,
    schritte      INTEGER,
    kcal          INTEGER,
    km_zeiten     TEXT NOT NULL DEFAULT '',   -- JSON {"km": [s, …], "rest_m": m, "rest_s": s}
    punkte        TEXT NOT NULL DEFAULT '',   -- JSON [[lat, lon, hoehe, sekunde], …]
    quellen       TEXT NOT NULL DEFAULT '',   -- z. B. "datei,bild"
    zahlen_quelle TEXT NOT NULL DEFAULT '',   -- woher Distanz/Dauer/Anstieg stammen
    angelegt      TEXT NOT NULL,
    geaendert     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS laeufe_geraet_start ON laeufe (geraet_id, start);

-- Erkannte, noch nicht bestätigte Läufe (Kontrollkarte in der App); werden nach einer Stunde verworfen.
CREATE TABLE IF NOT EXISTS entwuerfe (
    id       TEXT PRIMARY KEY,
    daten    TEXT NOT NULL,
    angelegt REAL NOT NULL
);

-- REQ-002: Familie. Schlüssel und Einladungscodes nur als Prüfsumme (SHA-256).
CREATE TABLE IF NOT EXISTS mitglieder (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    farbe       TEXT NOT NULL,
    kuerzel     TEXT NOT NULL,
    rolle       TEXT NOT NULL DEFAULT 'mitglied',   -- 'verwalter' oder 'mitglied'
    schluessel  TEXT UNIQUE,                         -- Prüfsumme des Handy-Schlüssels; NULL = nicht angemeldet
    geraet_id   TEXT NOT NULL DEFAULT '',
    angelegt    TEXT NOT NULL,
    beigetreten TEXT,
    standard_sichtbarkeit TEXT NOT NULL DEFAULT 'familie',  -- REQ-003: Sichtbarkeit neuer Läufe
    push_token  TEXT NOT NULL DEFAULT '',                   -- REQ-005: Firebase-Token des Handys
    push_aus    TEXT NOT NULL DEFAULT '',                   -- REQ-006: abgeschaltete Push-Arten, z. B. "chat,lauf"
    chat_gelesen INTEGER NOT NULL DEFAULT 0                 -- REQ-006: letzte gelesene Chatnachricht
);

CREATE TABLE IF NOT EXISTS einladungen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,                -- Prüfsumme des Codes
    mitglied_id INTEGER NOT NULL,
    gueltig_bis TEXT NOT NULL,
    angelegt    TEXT NOT NULL
);

-- REQ-005: Sonntagsshow – eingefrorener Stand je Woche (z. B. "2026-W46")
CREATE TABLE IF NOT EXISTS shows (
    woche         TEXT PRIMARY KEY,
    erstellt      TEXT NOT NULL,
    daten         TEXT NOT NULL,           -- JSON: Horst, Preise, Platzierung, Wette, ggf. Monat
    push_gesendet TEXT                     -- wann der Push „Die Sonntagsshow ist da!“ rausging
);

-- REQ-006: Familienchat (Menschen und Horst), Reaktionen und Kommentare an Läufen
CREATE TABLE IF NOT EXISTS nachrichten (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mitglied_id INTEGER,                   -- NULL = Horst
    text        TEXT NOT NULL,
    lauf_id     INTEGER,                   -- Horst-Meldungen verweisen auf den Lauf
    zeit        TEXT NOT NULL              -- UTC, ISO
);

CREATE TABLE IF NOT EXISTS reaktionen (
    lauf_id     INTEGER NOT NULL,
    mitglied_id INTEGER NOT NULL,
    emoji       TEXT NOT NULL,
    zeit        TEXT NOT NULL,
    PRIMARY KEY (lauf_id, mitglied_id, emoji)
);

CREATE TABLE IF NOT EXISTS kommentare (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lauf_id     INTEGER NOT NULL,
    mitglied_id INTEGER NOT NULL,
    text        TEXT NOT NULL,
    zeit        TEXT NOT NULL
);

-- REQ-013: „nur für mich“ entfällt – die beiden Spalten dazu oben stehen seitdem immer auf 'familie'.
-- REQ-013: Fotos zum Lauf (bis zu drei). Die Bilder liegen im Ordner fotos/ neben der Datenbank:
-- <datei>.jpg (höchstens 1280 px) und <datei>_klein.jpg (Vorschau 320 px), ohne Zusatzdaten (EXIF/GPS).
CREATE TABLE IF NOT EXISTS fotos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lauf_id     INTEGER NOT NULL,
    mitglied_id INTEGER NOT NULL,
    datei       TEXT NOT NULL,             -- Name ohne Endung
    breite      INTEGER NOT NULL,
    hoehe       INTEGER NOT NULL,
    angelegt    TEXT NOT NULL              -- UTC, ISO
);
CREATE INDEX IF NOT EXISTS fotos_lauf ON fotos (lauf_id);
