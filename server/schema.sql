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
