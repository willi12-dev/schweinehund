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
    beigetreten TEXT
);

CREATE TABLE IF NOT EXISTS einladungen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,                -- Prüfsumme des Codes
    mitglied_id INTEGER NOT NULL,
    gueltig_bis TEXT NOT NULL,
    angelegt    TEXT NOT NULL
);
