# querencia database schema

SQLite (+ `sqlite-vec`). All entities unify on `place_key` — `pid:<hex>` (Google place id),
`cid:<hex>` (question/cid), `geo:<lat>,<lng>` (geocoded point), or `visit:<id>` (commute leg
without coordinates).

```sql
-- Unified place node. One row per distinct place_key; source_flags is a comma-joined
-- set of the ingesters that contributed (review|photo|label|commute|question).
CREATE TABLE places (
  place_key      TEXT PRIMARY KEY,
  canonical_name TEXT,
  category       TEXT,
  address        TEXT,
  country_code   TEXT,
  lat REAL, lng REAL,
  source_flags   TEXT,
  enriched_at    TIMESTAMP        -- set once enrichment has run (idempotency marker)
);

-- One row per Google Maps review; structured_qa holds the review's questions JSON.
CREATE TABLE reviews (
  review_id     INTEGER PRIMARY KEY,
  place_key     TEXT NOT NULL REFERENCES places(place_key),
  rating        INTEGER,
  text          TEXT,
  reviewed_at   TIMESTAMP,
  structured_qa TEXT
);

-- One row per geotagged photo sidecar with usable EXIF coordinates.
CREATE TABLE photos (
  photo_id   INTEGER PRIMARY KEY,
  place_key  TEXT REFERENCES places(place_key),
  taken_at   TIMESTAMP NOT NULL,
  lat REAL, lng REAL,
  media_type TEXT
);

-- Generic visit signal (currently from questions; session_id is forward-compat).
CREATE TABLE visits (
  visit_id    INTEGER PRIMARY KEY,
  place_key   TEXT NOT NULL REFERENCES places(place_key),
  occurred_at TIMESTAMP,
  source      TEXT NOT NULL,
  session_id  TEXT
);
CREATE INDEX visits_place ON visits(place_key);

-- Directed travel edge between two places with a travel mode (from commute routes).
CREATE TABLE transitions (
  from_place_key TEXT REFERENCES places(place_key),
  to_place_key   TEXT REFERENCES places(place_key),
  travel_mode    TEXT,
  PRIMARY KEY (from_place_key, to_place_key, travel_mode)
);

-- Detected trips (spatiotemporal clusters of visits). Materialized by `querencia trips`.
CREATE TABLE trips (
  trip_id       INTEGER PRIMARY KEY,
  started_at    TIMESTAMP,
  ended_at      TIMESTAMP,
  country_code  TEXT,
  lead_category TEXT,
  place_count   INTEGER,
  lat REAL, lng REAL
);
CREATE TABLE trip_places (
  trip_id   INTEGER REFERENCES trips(trip_id) ON DELETE CASCADE,
  place_key TEXT REFERENCES places(place_key),
  PRIMARY KEY (trip_id, place_key)
);

-- Per-category user preference vector (pickled np.ndarray). Cache for recommend.
CREATE TABLE pref_vectors (
  category    TEXT PRIMARY KEY,
  vector      BLOB,
  n_reviews   INTEGER,
  computed_at TIMESTAMP
);

-- Candidate places fetched from external sources (Google Places) for a city+category.
CREATE TABLE candidate_cache (
  city       TEXT,
  category   TEXT,
  payload    TEXT,
  fetched_at TIMESTAMP,
  PRIMARY KEY (city, category)
);

-- Full-text index over the rendered text of each place (keyword recall).
CREATE VIRTUAL TABLE place_fts USING fts5(place_key UNINDEXED, rendered_text);

-- 384-dim embedding per place (semantic recall via sqlite-vec).
CREATE VIRTUAL TABLE place_vec USING vec0(place_key TEXT PRIMARY KEY, embedding FLOAT[384]);
```
