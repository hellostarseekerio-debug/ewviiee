// SQLite persistence for reservations, enquiries and newsletter sign-ups.
// better-sqlite3 is synchronous and fast — ideal for a single-venue booking load.

import Database from "better-sqlite3";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, "..", "data");
fs.mkdirSync(dataDir, { recursive: true });

const dbPath = process.env.DB_PATH || path.join(dataDir, "queenvictoria.db");
const db = new Database(dbPath);

db.pragma("journal_mode = WAL");
db.pragma("foreign_keys = ON");

db.exec(`
  CREATE TABLE IF NOT EXISTS reservations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    reference     TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    phone         TEXT NOT NULL,
    party_size    INTEGER NOT NULL,
    date          TEXT NOT NULL,            -- YYYY-MM-DD
    time          TEXT NOT NULL,            -- HH:MM (24h)
    occasion      TEXT,
    notes         TEXT,
    status        TEXT NOT NULL DEFAULT 'confirmed', -- confirmed | pending | cancelled
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE INDEX IF NOT EXISTS idx_res_slot ON reservations (date, time, status);

  CREATE TABLE IF NOT EXISTS enquiries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT,
    subject     TEXT,
    message     TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'general', -- general | private-event | feedback
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS subscribers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT UNIQUE NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

export const statements = {
  insertReservation: db.prepare(`
    INSERT INTO reservations (reference, name, email, phone, party_size, date, time, occasion, notes, status)
    VALUES (@reference, @name, @email, @phone, @party_size, @date, @time, @occasion, @notes, @status)
  `),
  countSeatsForSlot: db.prepare(`
    SELECT COALESCE(SUM(party_size), 0) AS seats
    FROM reservations
    WHERE date = ? AND time = ? AND status != 'cancelled'
  `),
  findByReference: db.prepare(`SELECT * FROM reservations WHERE reference = ?`),
  cancelByReference: db.prepare(`UPDATE reservations SET status = 'cancelled' WHERE reference = ? AND status != 'cancelled'`),
  seatsByDate: db.prepare(`
    SELECT time, COALESCE(SUM(party_size), 0) AS seats
    FROM reservations
    WHERE date = ? AND status != 'cancelled'
    GROUP BY time
  `),
  insertEnquiry: db.prepare(`
    INSERT INTO enquiries (name, email, phone, subject, message, type)
    VALUES (@name, @email, @phone, @subject, @message, @type)
  `),
  insertSubscriber: db.prepare(`
    INSERT INTO subscribers (email) VALUES (?)
    ON CONFLICT(email) DO NOTHING
  `),
};

export default db;
