import sqlite3
from pathlib import Path

import sqlite_vec

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
  place_key      TEXT PRIMARY KEY,
  canonical_name TEXT,
  category       TEXT,
  address        TEXT,
  country_code   TEXT,
  lat REAL, lng REAL,
  source_flags   TEXT,
  enriched_at    TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
  review_id     INTEGER PRIMARY KEY,
  place_key     TEXT NOT NULL REFERENCES places(place_key),
  rating        INTEGER,
  text          TEXT,
  reviewed_at   TIMESTAMP,
  structured_qa TEXT
);
CREATE TABLE IF NOT EXISTS photos (
  photo_id   INTEGER PRIMARY KEY,
  place_key  TEXT REFERENCES places(place_key),
  taken_at   TIMESTAMP NOT NULL,
  lat REAL, lng REAL,
  media_type TEXT
);
CREATE TABLE IF NOT EXISTS visits (
  visit_id    INTEGER PRIMARY KEY,
  place_key   TEXT NOT NULL REFERENCES places(place_key),
  occurred_at TIMESTAMP,
  source      TEXT NOT NULL,
  session_id  TEXT
);
CREATE INDEX IF NOT EXISTS visits_place ON visits(place_key);
CREATE TABLE IF NOT EXISTS transitions (
  from_place_key TEXT REFERENCES places(place_key),
  to_place_key   TEXT REFERENCES places(place_key),
  travel_mode    TEXT,
  PRIMARY KEY (from_place_key, to_place_key, travel_mode)
);
CREATE TABLE IF NOT EXISTS trips (
  trip_id       INTEGER PRIMARY KEY,
  started_at    TIMESTAMP,
  ended_at      TIMESTAMP,
  country_code  TEXT,
  lead_category TEXT,
  place_count   INTEGER,
  lat REAL, lng REAL
);
CREATE TABLE IF NOT EXISTS trip_places (
  trip_id   INTEGER REFERENCES trips(trip_id) ON DELETE CASCADE,
  place_key TEXT REFERENCES places(place_key),
  PRIMARY KEY (trip_id, place_key)
);
CREATE TABLE IF NOT EXISTS pref_vectors (
  category    TEXT PRIMARY KEY,
  vector      BLOB,
  n_reviews   INTEGER,
  computed_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS candidate_cache (
  city       TEXT,
  category   TEXT,
  payload    TEXT,
  fetched_at TIMESTAMP,
  PRIMARY KEY (city, category)
);
CREATE VIRTUAL TABLE IF NOT EXISTS place_fts USING fts5(place_key UNINDEXED, rendered_text);
"""

VEC_TABLE = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS place_vec USING vec0("
    "place_key TEXT PRIMARY KEY, embedding FLOAT[384])"
)


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(VEC_TABLE)
    conn.commit()
