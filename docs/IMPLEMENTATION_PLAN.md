# locus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first personal place knowledge graph from Google Maps contributions (reviews, geotagged photos, labeled places, commute routes), queryable for narrative, semantic recall, and taste-extrapolation via a Python library, CLI, and MCP server.

**Architecture:** One ingester per Takeout source normalizes into a SQLite schema centered on a `places` table (unified by `place_key`). Enrichment fills categories/canonical names (Google Places API, idempotent). Embedding renders each place to text and stores a 384-dim vector in sqlite-vec. A pure-Python, LLM-free `query` module backs both surfaces: a `click` CLI (uses Anthropic API for prose) and an MCP server (Claude Code does prose for free).

**Tech Stack:** Python 3.11+, `sqlite3` (stdlib) + `sqlite-vec`, `sentence-transformers` (BAAI/bge-small-en-v1.5, 384-dim), `googlemaps`, `anthropic`, `click`, `mcp`, `pytest`.

---

## File Structure

```
locus/
├── pyproject.toml
├── README.md
├── SCHEMA.md
├── .gitignore
├── src/locus/
│   ├── __init__.py
│   ├── db.py                 # connection + schema DDL + sqlite-vec loading
│   ├── models.py             # dataclasses: Place, Review, Photo, Visit, Transition
│   ├── ingest/
│   │   ├── __init__.py        # orchestrator: run_all(zip_or_dir, conn)
│   │   ├── _util.py           # geo_key(), open_takeout(), safe_json()
│   │   ├── reviews.py
│   │   ├── photos.py
│   │   ├── questions.py
│   │   ├── labels.py
│   │   └── commutes.py
│   ├── enrich.py             # Places client wrapper + spatial join
│   ├── embed.py              # render_place() + Embedder + index build
│   ├── query.py              # LLM-free: recall(), narrative(), taste(), patterns()
│   ├── synth_llm.py          # Anthropic rendering for CLI (prose)
│   ├── cli.py                # click CLI
│   └── mcp_server.py         # FastMCP server
├── examples/synthetic/       # generated fake data + builder script
├── data/raw/                 # gitignored: extracted real Takeout slices
└── tests/
    ├── fixtures/             # tiny real-shaped JSON
    ├── unit/
    ├── integration/
    └── MANUAL.md
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/locus/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/
data/raw/
*.db
.env
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "locus"
version = "0.1.0"
description = "Local-first personal place knowledge graph from Google Maps contributions"
requires-python = ">=3.11"
dependencies = [
    "sqlite-vec>=0.1.3",
    "sentence-transformers>=2.7.0",
    "googlemaps>=4.10.0",
    "anthropic>=0.39.0",
    "click>=8.1.0",
    "mcp>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-mock>=3.12.0"]

[project.scripts]
locus = "locus.cli:cli"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `src/locus/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create venv and install**

Run: `python -m venv .venv && .venv\Scripts\pip install -e ".[dev]"`
Expected: installs without error; `locus` script registered.

- [ ] **Step 5: Commit**

```bash
git init
git add .gitignore pyproject.toml src/locus/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Data models

**Files:**
- Create: `src/locus/models.py`
- Test: `tests/unit/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models.py
from locus.models import Place, Review, Photo, Visit, Transition

def test_place_defaults():
    p = Place(place_key="geo:40.74,-74.05", lat=40.74, lng=-74.05)
    assert p.canonical_name is None
    assert p.enriched_at is None
    assert p.source_flags == set()

def test_review_holds_text_and_rating():
    r = Review(place_key="pid:abc", rating=5, text="great", reviewed_at="2024-09-11T17:44:39Z")
    assert r.rating == 5
    assert r.text == "great"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'locus.models'`

- [ ] **Step 3: Write `src/locus/models.py`**

```python
from dataclasses import dataclass, field


@dataclass
class Place:
    place_key: str
    lat: float | None = None
    lng: float | None = None
    canonical_name: str | None = None
    category: str | None = None
    address: str | None = None
    country_code: str | None = None
    source_flags: set[str] = field(default_factory=set)
    enriched_at: str | None = None


@dataclass
class Review:
    place_key: str
    rating: int | None = None
    text: str | None = None
    reviewed_at: str | None = None
    structured_qa: str | None = None  # JSON string


@dataclass
class Photo:
    place_key: str | None
    taken_at: str
    lat: float
    lng: float
    media_type: str


@dataclass
class Visit:
    place_key: str
    occurred_at: str | None
    source: str  # "photo" | "question" | "commute"
    session_id: str | None = None


@dataclass
class Transition:
    from_place_key: str
    to_place_key: str
    travel_mode: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/models.py tests/unit/test_models.py
git commit -m "feat: data models"
```

---

## Task 3: Database schema

**Files:**
- Create: `src/locus/db.py`
- Test: `tests/unit/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_db.py
from locus.db import connect, init_schema

def test_schema_creates_all_tables(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )}
    assert {"places", "reviews", "photos", "visits", "transitions"} <= names

def test_vec_table_accepts_embedding(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    conn.execute("INSERT INTO places(place_key) VALUES ('pid:x')")
    vec = ",".join(["0.1"] * 384)
    conn.execute(
        "INSERT INTO place_vec(place_key, embedding) VALUES ('pid:x', vec_f32(?))",
        (f"[{vec}]",),
    )
    rows = list(conn.execute("SELECT place_key FROM place_vec"))
    assert rows[0][0] == "pid:x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'locus.db'`

- [ ] **Step 3: Write `src/locus/db.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_db.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/db.py tests/unit/test_db.py
git commit -m "feat: sqlite schema with sqlite-vec"
```

---

## Task 4: Ingest utilities

**Files:**
- Create: `src/locus/ingest/__init__.py` (empty stub for now), `src/locus/ingest/_util.py`
- Test: `tests/unit/test_ingest_util.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ingest_util.py
from locus.ingest._util import geo_key, upsert_place
from locus.db import connect, init_schema

def test_geo_key_rounds_to_5dp():
    assert geo_key(40.7435693, -74.0512251) == "geo:40.74357,-74.05123"

def test_upsert_place_merges_source_flags(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", lat=1.0, lng=2.0, name="X", source="review")
    upsert_place(conn, "pid:a", source="photo")
    row = conn.execute(
        "SELECT canonical_name, source_flags FROM places WHERE place_key='pid:a'"
    ).fetchone()
    assert row[0] == "X"
    assert set(row[1].split(",")) == {"review", "photo"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_util.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'locus.ingest._util'`

- [ ] **Step 3: Write the files**

```python
# src/locus/ingest/__init__.py
```

```python
# src/locus/ingest/_util.py
import sqlite3


def geo_key(lat: float, lng: float) -> str:
    return f"geo:{lat:.5f},{lng:.5f}"


def upsert_place(
    conn: sqlite3.Connection,
    place_key: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    name: str | None = None,
    address: str | None = None,
    country_code: str | None = None,
    source: str | None = None,
) -> None:
    row = conn.execute(
        "SELECT source_flags FROM places WHERE place_key=?", (place_key,)
    ).fetchone()
    if row is None:
        flags = {source} if source else set()
        conn.execute(
            "INSERT INTO places(place_key, lat, lng, canonical_name, address, "
            "country_code, source_flags) VALUES (?,?,?,?,?,?,?)",
            (place_key, lat, lng, name, address, country_code,
             ",".join(sorted(flags))),
        )
    else:
        flags = set(filter(None, (row[0] or "").split(",")))
        if source:
            flags.add(source)
        conn.execute(
            "UPDATE places SET "
            "lat=COALESCE(lat,?), lng=COALESCE(lng,?), "
            "canonical_name=COALESCE(canonical_name,?), "
            "address=COALESCE(address,?), country_code=COALESCE(country_code,?), "
            "source_flags=? WHERE place_key=?",
            (lat, lng, name, address, country_code,
             ",".join(sorted(flags)), place_key),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_util.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/ingest/__init__.py src/locus/ingest/_util.py tests/unit/test_ingest_util.py
git commit -m "feat: ingest utilities (geo_key, upsert_place)"
```

---

## Task 5: Reviews ingester

**Files:**
- Create: `src/locus/ingest/reviews.py`, `tests/fixtures/reviews.json`
- Test: `tests/unit/test_ingest_reviews.py`

- [ ] **Step 1: Create the fixture** `tests/fixtures/reviews.json`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "geometry": {"coordinates": [-74.0512857, 40.7435999], "type": "Point"},
      "properties": {
        "date": "2026-01-11T17:05:01.966536Z",
        "five_star_rating_published": 5,
        "google_maps_url": "https://www.google.com/maps/place//data=!1s0x0:0x49c924ef18940842",
        "location": {"address": "249 Central Ave, Jersey City, NJ 07307, United States",
                     "country_code": "US",
                     "name": "Balaji Bhavan"},
        "review_text_published": "Great dosa",
        "questions": [{"question": "Meal type", "selected_option": "Breakfast"}]
      }
    },
    {
      "geometry": {"coordinates": [0, 0], "type": "Point"},
      "properties": {
        "date": "2020-01-01T00:00:00Z",
        "five_star_rating_published": 3,
        "google_maps_url": "https://www.google.com/maps/place//data=!1s0x0:0xNOLOC",
        "Comment": "No location information is available for this review"
      }
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_ingest_reviews.py
import json
from pathlib import Path
from locus.db import connect, init_schema
from locus.ingest.reviews import ingest_reviews

FIX = Path(__file__).parent.parent / "fixtures" / "reviews.json"

def test_ingest_reviews_creates_place_and_review(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    n = ingest_reviews(conn, json.loads(FIX.read_text(encoding="utf-8")))
    assert n == 2
    places = conn.execute("SELECT place_key, canonical_name FROM places").fetchall()
    keys = {p[0] for p in places}
    assert any(k.startswith("pid:") for k in keys)
    r = conn.execute("SELECT rating, text FROM reviews WHERE text='Great dosa'").fetchone()
    assert r == (5, "Great dosa")

def test_locationless_review_uses_url_id_key(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ingest_reviews(conn, json.loads(FIX.read_text(encoding="utf-8")))
    noloc = conn.execute("SELECT rating FROM reviews WHERE rating=3").fetchone()
    assert noloc[0] == 3
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_reviews.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'locus.ingest.reviews'`

- [ ] **Step 4: Write `src/locus/ingest/reviews.py`**

```python
import json
import re
import sqlite3

from ._util import geo_key, upsert_place

_HEX_ID = re.compile(r"!1s0x0:0x([0-9a-fA-F]+)")


def _place_key(props: dict, geom: dict) -> str:
    m = _HEX_ID.search(props.get("google_maps_url", ""))
    if m:
        return f"pid:{m.group(1)}"
    coords = (geom or {}).get("coordinates") or []
    if len(coords) == 2 and (coords[0] or coords[1]):
        return geo_key(coords[1], coords[0])  # GeoJSON is [lng, lat]
    return f"url:{props.get('google_maps_url', 'unknown')}"


def ingest_reviews(conn: sqlite3.Connection, data: dict) -> int:
    count = 0
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        loc = props.get("location") or {}
        coords = geom.get("coordinates") or [None, None]
        lat = coords[1] if len(coords) == 2 else None
        lng = coords[0] if len(coords) == 2 else None
        key = _place_key(props, geom)
        upsert_place(
            conn, key,
            lat=lat if lat else None, lng=lng if lng else None,
            name=loc.get("name"), address=loc.get("address"),
            country_code=loc.get("country_code"), source="review",
        )
        qa = props.get("questions")
        conn.execute(
            "INSERT INTO reviews(place_key, rating, text, reviewed_at, structured_qa) "
            "VALUES (?,?,?,?,?)",
            (key, props.get("five_star_rating_published"),
             props.get("review_text_published"), props.get("date"),
             json.dumps(qa) if qa else None),
        )
        count += 1
    conn.commit()
    return count
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_reviews.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/locus/ingest/reviews.py tests/fixtures/reviews.json tests/unit/test_ingest_reviews.py
git commit -m "feat: reviews ingester"
```

---

## Task 6: Photos ingester

**Files:**
- Create: `src/locus/ingest/photos.py`, `tests/fixtures/photo_sidecar.json`
- Test: `tests/unit/test_ingest_photos.py`

- [ ] **Step 1: Create fixture** `tests/fixtures/photo_sidecar.json`

```json
{
  "title": "2026-01-11-x.jpg",
  "creationTime": {"timestamp": "1768151101", "formatted": "Jan 11, 2026"},
  "geoDataExif": {"latitude": 40.7435693, "longitude": -74.0512251, "altitude": 0.0}
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_ingest_photos.py
import json
from pathlib import Path
from locus.db import connect, init_schema
from locus.ingest.photos import ingest_photo_sidecar

FIX = Path(__file__).parent.parent / "fixtures" / "photo_sidecar.json"

def test_photo_sidecar_creates_geo_place_and_photo(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ok = ingest_photo_sidecar(conn, json.loads(FIX.read_text()), "x.jpg")
    assert ok is True
    photo = conn.execute("SELECT place_key, media_type, taken_at FROM photos").fetchone()
    assert photo[0] == "geo:40.74357,-74.05123"
    assert photo[1] == "jpg"
    assert photo[2].startswith("2026-01-11")

def test_photo_without_geo_is_skipped(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ok = ingest_photo_sidecar(conn, {"creationTime": {"timestamp": "1768151101"}}, "y.jpg")
    assert ok is False
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_photos.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write `src/locus/ingest/photos.py`**

```python
import sqlite3
from datetime import datetime, timezone

from ._util import geo_key, upsert_place


def _media_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in {"jpg", "jpeg", "mp4", "png"} else "other"


def ingest_photo_sidecar(conn: sqlite3.Connection, data: dict, filename: str) -> bool:
    geo = data.get("geoDataExif") or {}
    lat, lng = geo.get("latitude"), geo.get("longitude")
    if not lat or not lng:  # (0,0) and missing both count as no-geo
        return False
    ts = (data.get("creationTime") or {}).get("timestamp")
    if not ts:
        return False
    taken_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    key = geo_key(lat, lng)
    upsert_place(conn, key, lat=lat, lng=lng, source="photo")
    conn.execute(
        "INSERT INTO photos(place_key, taken_at, lat, lng, media_type) VALUES (?,?,?,?,?)",
        (key, taken_at, lat, lng, _media_type(filename)),
    )
    conn.commit()
    return True
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_photos.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/locus/ingest/photos.py tests/fixtures/photo_sidecar.json tests/unit/test_ingest_photos.py
git commit -m "feat: photos ingester"
```

---

## Task 7: Labels & commutes ingesters

**Files:**
- Create: `src/locus/ingest/labels.py`, `src/locus/ingest/commutes.py`
- Test: `tests/unit/test_ingest_labels_commutes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ingest_labels_commutes.py
from locus.db import connect, init_schema
from locus.ingest.labels import ingest_labels
from locus.ingest.commutes import ingest_commutes

LABELS = {"features": [
    {"geometry": {"coordinates": [77.6529267, 12.914492], "type": "Point"},
     "properties": {"address": "HSR Layout, Bengaluru", "name": "Home"}}]}

COMMUTES = {"trips": [
    {"id": "T1",
     "place_visit": [
        {"id": "SOURCE_ID"},
        {"id": "DESTINATION_ID",
         "place": {"lat_lng": {"latitude": 12.9067, "longitude": 77.5463}}}],
     "transition": [
        {"route": {"travel_mode": "DRIVE"},
         "origin": {"visit_id": "SOURCE_ID"},
         "destination": {"visit_id": "DESTINATION_ID"}}]}]}

def test_labels_create_named_places(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    n = ingest_labels(conn, LABELS)
    assert n == 1
    row = conn.execute("SELECT canonical_name FROM places").fetchone()
    assert row[0] == "Home"

def test_commutes_create_transition_with_mode(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ingest_commutes(conn, COMMUTES)
    row = conn.execute("SELECT travel_mode FROM transitions").fetchone()
    assert row[0] == "DRIVE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_labels_commutes.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/ingest/labels.py`**

```python
import sqlite3

from ._util import geo_key, upsert_place


def ingest_labels(conn: sqlite3.Connection, data: dict) -> int:
    count = 0
    for feat in data.get("features", []):
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        if len(coords) != 2:
            continue
        props = feat.get("properties", {})
        key = geo_key(coords[1], coords[0])
        upsert_place(conn, key, lat=coords[1], lng=coords[0],
                     name=props.get("name"), address=props.get("address"),
                     source="label")
        count += 1
    conn.commit()
    return count
```

- [ ] **Step 4: Write `src/locus/ingest/commutes.py`**

```python
import sqlite3

from ._util import geo_key, upsert_place


def ingest_commutes(conn: sqlite3.Connection, data: dict) -> int:
    count = 0
    for trip in data.get("trips", []):
        keys: dict[str, str] = {}
        for pv in trip.get("place_visit", []):
            place = pv.get("place") or {}
            ll = place.get("lat_lng") or {}
            lat, lng = ll.get("latitude"), ll.get("longitude")
            if lat is not None and lng is not None:
                k = geo_key(lat, lng)
                upsert_place(conn, k, lat=lat, lng=lng, source="commute")
                keys[pv["id"]] = k
        for tr in trip.get("transition", []):
            o = tr.get("origin", {}).get("visit_id")
            d = tr.get("destination", {}).get("visit_id")
            mode = (tr.get("route") or {}).get("travel_mode", "UNKNOWN")
            if o in keys and d in keys:
                conn.execute(
                    "INSERT OR IGNORE INTO transitions"
                    "(from_place_key, to_place_key, travel_mode) VALUES (?,?,?)",
                    (keys[o], keys[d], mode),
                )
                count += 1
    conn.commit()
    return count
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_labels_commutes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/locus/ingest/labels.py src/locus/ingest/commutes.py tests/unit/test_ingest_labels_commutes.py
git commit -m "feat: labels and commutes ingesters"
```

---

## Task 8: Questions ingester

**Files:**
- Create: `src/locus/ingest/questions.py`
- Test: `tests/unit/test_ingest_questions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ingest_questions.py
from locus.db import connect, init_schema
from locus.ingest.questions import ingest_question

QA = {"placeUrl": "https://google.com/maps/?cid=0x3bae16a82da08f99:0x3ce7be42251d9745",
      "selectedChoice": "Yes", "question": "Is this dish shown? Sujuk"}

def test_question_creates_cid_place_and_visit(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ingest_question(conn, QA)
    place = conn.execute("SELECT place_key FROM places").fetchone()
    assert place[0].startswith("cid:")
    visit = conn.execute("SELECT source, occurred_at FROM visits").fetchone()
    assert visit[0] == "question"
    assert visit[1] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_questions.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/ingest/questions.py`**

```python
import re
import sqlite3

from ._util import upsert_place

_CID = re.compile(r"cid=0x[0-9a-fA-F]+:0x([0-9a-fA-F]+)")


def ingest_question(conn: sqlite3.Connection, data: dict) -> bool:
    m = _CID.search(data.get("placeUrl", ""))
    if not m:
        return False
    key = f"cid:{m.group(1)}"
    upsert_place(conn, key, source="question")
    conn.execute(
        "INSERT INTO visits(place_key, occurred_at, source) VALUES (?,?,?)",
        (key, None, "question"),
    )
    conn.commit()
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_ingest_questions.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/ingest/questions.py tests/unit/test_ingest_questions.py
git commit -m "feat: questions ingester"
```

---

## Task 9: Ingest orchestrator

**Files:**
- Create: `src/locus/ingest/_util.py` (add `open_takeout`), modify `src/locus/ingest/__init__.py`
- Test: `tests/integration/test_ingest_all.py`

- [ ] **Step 1: Add `open_takeout` to `src/locus/ingest/_util.py`** (append)

```python
import json as _json
import zipfile
from pathlib import Path


def read_zip_json(zf: zipfile.ZipFile, name: str) -> dict | None:
    try:
        with zf.open(name) as f:
            return _json.loads(f.read().decode("utf-8"))
    except KeyError:
        return None


def iter_zip_jsons(zf: zipfile.ZipFile, prefix: str):
    for info in zf.infolist():
        if info.filename.startswith(prefix) and info.filename.endswith(".json"):
            with zf.open(info) as f:
                yield info.filename, _json.loads(f.read().decode("utf-8"))
```

- [ ] **Step 2: Write the failing integration test**

```python
# tests/integration/test_ingest_all.py
import io, json, zipfile
from pathlib import Path
from locus.db import connect, init_schema
from locus.ingest import run_all

FIX = Path(__file__).parent.parent / "fixtures"

def _make_zip(tmp_path):
    zpath = tmp_path / "takeout.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Takeout/Maps (your places)/Reviews.json",
                   (FIX / "reviews.json").read_text(encoding="utf-8"))
        z.writestr("Takeout/Maps/Photos and videos/2026-01-11-x.jpg.json",
                   (FIX / "photo_sidecar.json").read_text())
    return zpath

def test_run_all_populates_db(tmp_path):
    zpath = _make_zip(tmp_path)
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    summary = run_all(conn, zpath)
    assert summary["reviews"] == 2
    assert summary["photos"] == 1
    assert conn.execute("SELECT COUNT(*) FROM places").fetchone()[0] >= 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/integration/test_ingest_all.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_all'`

- [ ] **Step 4: Write `src/locus/ingest/__init__.py`**

```python
import sqlite3
import zipfile
from pathlib import Path

from . import commutes, labels, photos, questions, reviews
from ._util import iter_zip_jsons, read_zip_json

R_PREFIX = "Takeout/Maps (your places)/Reviews.json"
PHOTO_PREFIX = "Takeout/Maps/Photos and videos/"
Q_PREFIX = "Takeout/Maps/Answers to automated questions/"
LABEL_PREFIX = "Takeout/Maps/My labeled places/"
COMMUTE_PREFIX = "Takeout/Maps/Commute routes/"


def run_all(conn: sqlite3.Connection, zip_path: str | Path) -> dict:
    summary = {"reviews": 0, "photos": 0, "questions": 0, "labels": 0, "commutes": 0}
    with zipfile.ZipFile(zip_path) as z:
        rdata = read_zip_json(z, R_PREFIX)
        if rdata:
            summary["reviews"] = reviews.ingest_reviews(conn, rdata)
        for name, data in iter_zip_jsons(z, PHOTO_PREFIX):
            fname = name.rsplit("/", 1)[-1].removesuffix(".json")
            if photos.ingest_photo_sidecar(conn, data, fname):
                summary["photos"] += 1
        for _, data in iter_zip_jsons(z, Q_PREFIX):
            if questions.ingest_question(conn, data):
                summary["questions"] += 1
        for _, data in iter_zip_jsons(z, LABEL_PREFIX):
            summary["labels"] += labels.ingest_labels(conn, data)
        for _, data in iter_zip_jsons(z, COMMUTE_PREFIX):
            summary["commutes"] += commutes.ingest_commutes(conn, data)
    return summary
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/integration/test_ingest_all.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add src/locus/ingest/_util.py src/locus/ingest/__init__.py tests/integration/test_ingest_all.py
git commit -m "feat: ingest orchestrator over takeout zip"
```

---

## Task 10: Enrichment

**Files:**
- Create: `src/locus/enrich.py`
- Test: `tests/unit/test_enrich.py`

**Note:** enrichment does two things — (a) reverse-geocode `geo:`/`cid:` places to a name+category, (b) spatial-join photo `geo:` places to nearby reviewed `pid:` places. The Places client is injected so tests use a fake.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_enrich.py
from locus.db import connect, init_schema
from locus.enrich import enrich_places
from locus.ingest._util import upsert_place

class FakeClient:
    def reverse_geocode(self, lat, lng):
        return {"name": "Found Cafe", "category": "cafe", "address": "1 St"}

def test_enrich_fills_unenriched_geo_place(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "geo:40.74357,-74.05123", lat=40.74357, lng=-74.05123, source="photo")
    n = enrich_places(conn, FakeClient())
    assert n == 1
    row = conn.execute(
        "SELECT canonical_name, category, enriched_at FROM places"
    ).fetchone()
    assert row[0] == "Found Cafe"
    assert row[1] == "cafe"
    assert row[2] is not None

def test_enrich_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "geo:1.0,2.0", lat=1.0, lng=2.0, source="photo")
    enrich_places(conn, FakeClient())
    assert enrich_places(conn, FakeClient()) == 0  # already enriched

def test_enrich_respects_max_calls(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "geo:1.0,2.0", lat=1.0, lng=2.0, source="photo")
    upsert_place(conn, "geo:3.0,4.0", lat=3.0, lng=4.0, source="photo")
    assert enrich_places(conn, FakeClient(), max_calls=1) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_enrich.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/enrich.py`**

```python
import os
import sqlite3
from datetime import datetime, timezone


class GoogleClient:
    """Thin wrapper over googlemaps; only used in production, never in tests."""

    def __init__(self, api_key: str | None = None):
        import googlemaps
        self._gm = googlemaps.Client(key=api_key or os.environ["GOOGLE_PLACES_API_KEY"])

    def reverse_geocode(self, lat: float, lng: float) -> dict | None:
        res = self._gm.reverse_geocode((lat, lng))
        if not res:
            return None
        top = res[0]
        types = top.get("types", [])
        return {
            "name": top.get("formatted_address", "").split(",")[0],
            "category": types[0] if types else None,
            "address": top.get("formatted_address"),
        }


def enrich_places(conn: sqlite3.Connection, client, max_calls: int | None = None) -> int:
    rows = conn.execute(
        "SELECT place_key, lat, lng FROM places "
        "WHERE enriched_at IS NULL AND lat IS NOT NULL AND lng IS NOT NULL"
    ).fetchall()
    calls = 0
    for key, lat, lng in rows:
        if max_calls is not None and calls >= max_calls:
            break
        info = client.reverse_geocode(lat, lng)
        calls += 1
        now = datetime.now(timezone.utc).isoformat()
        if info:
            conn.execute(
                "UPDATE places SET canonical_name=COALESCE(canonical_name,?), "
                "category=COALESCE(category,?), address=COALESCE(address,?), "
                "enriched_at=? WHERE place_key=?",
                (info.get("name"), info.get("category"), info.get("address"), now, key),
            )
        else:
            conn.execute("UPDATE places SET enriched_at=? WHERE place_key=?", (now, key))
    conn.commit()
    return calls
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_enrich.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/enrich.py tests/unit/test_enrich.py
git commit -m "feat: place enrichment with injectable client"
```

---

## Task 11: Embedding & indexing

**Files:**
- Create: `src/locus/embed.py`
- Test: `tests/unit/test_embed.py`

**Note:** `render_place()` (pure string builder) is tested directly. The `Embedder` wraps sentence-transformers and is injected so tests use a deterministic fake.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_embed.py
from locus.db import connect, init_schema
from locus.embed import render_place, build_index
from locus.ingest._util import upsert_place

class FakeEmbedder:
    dim = 384
    def encode(self, text: str) -> list[float]:
        return [float(len(text) % 7)] * 384

def test_render_place_includes_name_and_reviews(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Balaji Bhavan", source="review")
    conn.execute("UPDATE places SET category='restaurant' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key, rating, text) VALUES ('pid:a',5,'Great dosa')")
    text = render_place(conn, "pid:a")
    assert "Balaji Bhavan" in text
    assert "Great dosa" in text
    assert "restaurant" in text

def test_build_index_populates_fts_and_vec(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="X", source="review")
    n = build_index(conn, FakeEmbedder())
    assert n == 1
    assert conn.execute("SELECT COUNT(*) FROM place_fts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM place_vec").fetchone()[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_embed.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/embed.py`**

```python
import sqlite3


class Embedder:
    """Wraps sentence-transformers; only used in production, never in tests."""

    dim = 384

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)

    def encode(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()


def render_place(conn: sqlite3.Connection, place_key: str) -> str:
    p = conn.execute(
        "SELECT canonical_name, category, address, country_code "
        "FROM places WHERE place_key=?", (place_key,)
    ).fetchone()
    name, category, address, cc = p or (None, None, None, None)
    parts = [name or "Unknown place"]
    if category:
        parts.append(f"({category})")
    if address:
        parts.append(address)
    for rating, text in conn.execute(
        "SELECT rating, text FROM reviews WHERE place_key=?", (place_key,)
    ):
        bit = f"rated {rating}/5" if rating else "reviewed"
        if text:
            bit += f": {text}"
        parts.append(bit)
    return " | ".join(parts)


def build_index(conn: sqlite3.Connection, embedder) -> int:
    keys = [r[0] for r in conn.execute("SELECT place_key FROM places")]
    conn.execute("DELETE FROM place_fts")
    conn.execute("DELETE FROM place_vec")
    for key in keys:
        text = render_place(conn, key)
        conn.execute(
            "INSERT INTO place_fts(place_key, rendered_text) VALUES (?,?)", (key, text)
        )
        vec = embedder.encode(text)
        conn.execute(
            "INSERT INTO place_vec(place_key, embedding) VALUES (?, vec_f32(?))",
            (key, f"[{','.join(str(x) for x in vec)}]"),
        )
    conn.commit()
    return len(keys)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_embed.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/embed.py tests/unit/test_embed.py
git commit -m "feat: place rendering + FTS/vec index build"
```

---

## Task 12: Query — recall

**Files:**
- Create: `src/locus/query.py`
- Test: `tests/unit/test_query_recall.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_query_recall.py
from locus.db import connect, init_schema
from locus.embed import build_index
from locus.ingest._util import upsert_place
from locus.query import recall

class FakeEmbedder:
    dim = 384
    def encode(self, text):
        # "dosa" places get vector A, others vector B
        return [1.0]*384 if "dosa" in text.lower() else [0.0]*384

def _seed(conn):
    upsert_place(conn, "pid:a", name="Balaji Bhavan", source="review")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:a',5,'best dosa')")
    upsert_place(conn, "pid:b", name="Pizza Place", source="review")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:b',4,'good pizza')")
    build_index(conn, FakeEmbedder())

def test_recall_ranks_semantic_match_first(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    results = recall(conn, "dosa", FakeEmbedder(), k=2)
    assert results[0]["place_key"] == "pid:a"
    assert results[0]["name"] == "Balaji Bhavan"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_query_recall.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/query.py`**

```python
import sqlite3


def recall(conn: sqlite3.Connection, question: str, embedder, k: int = 10) -> list[dict]:
    qvec = embedder.encode(question)
    rows = conn.execute(
        "SELECT v.place_key, distance, p.canonical_name, p.category, p.country_code "
        "FROM place_vec v JOIN places p ON p.place_key = v.place_key "
        "WHERE v.embedding MATCH vec_f32(?) AND k = ? "
        "ORDER BY distance",
        (f"[{','.join(str(x) for x in qvec)}]", k),
    ).fetchall()
    out = []
    for key, dist, name, category, cc in rows:
        reviews = [
            {"rating": r[0], "text": r[1]}
            for r in conn.execute(
                "SELECT rating, text FROM reviews WHERE place_key=?", (key,)
            )
        ]
        out.append({
            "place_key": key, "name": name, "category": category,
            "country_code": cc, "distance": dist, "reviews": reviews,
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_query_recall.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/query.py tests/unit/test_query_recall.py
git commit -m "feat: semantic recall query"
```

---

## Task 13: Query — narrative, patterns, taste

**Files:**
- Modify: `src/locus/query.py` (append functions)
- Test: `tests/unit/test_query_narrative.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_query_narrative.py
from locus.db import connect, init_schema
from locus.ingest._util import upsert_place
from locus.query import narrative, patterns, taste

def _seed(conn):
    for k, name, cat, cc, rating in [
        ("pid:a", "Balaji Bhavan", "restaurant", "US", 5),
        ("pid:b", "Athens Rooftop", "restaurant", "GR", 5),
        ("pid:c", "City Park", "park", "US", 4),
    ]:
        upsert_place(conn, k, name=name, source="review")
        conn.execute("UPDATE places SET category=?, country_code=? WHERE place_key=?",
                     (cat, cc, k))
        conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                     "VALUES (?,?,?,?)", (k, rating, "good", "2024-06-01T00:00:00Z"))

def test_narrative_returns_grounded_structure(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    data = narrative(conn, theme="food")
    assert data["place_count"] == 2          # only restaurants
    assert "US" in data["countries"]
    assert any(p["name"] == "Balaji Bhavan" for p in data["top_rated"])

def test_patterns_categories_counts(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    cats = patterns(conn, kind="categories")
    assert cats["restaurant"] == 2
    assert cats["park"] == 1

def test_taste_returns_preferred_categories(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    profile = taste(conn, city="Lisbon")
    assert profile["city"] == "Lisbon"
    assert profile["top_categories"][0] == "restaurant"
    assert profile["avg_rating"] >= 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_query_narrative.py -v`
Expected: FAIL — `ImportError: cannot import name 'narrative'`

- [ ] **Step 3: Append to `src/locus/query.py`**

```python
FOOD_CATEGORIES = ("restaurant", "cafe", "bar", "bakery", "food")


def narrative(conn: sqlite3.Connection, theme: str | None = None,
              year: int | None = None) -> dict:
    where, params = [], []
    if theme == "food":
        where.append("p.category IN (%s)" % ",".join("?" * len(FOOD_CATEGORIES)))
        params.extend(FOOD_CATEGORIES)
    if year:
        where.append("strftime('%Y', r.reviewed_at) = ?")
        params.append(str(year))
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT p.place_key, p.canonical_name, p.category, p.country_code, "
        f"r.rating, r.text, r.reviewed_at "
        f"FROM places p JOIN reviews r ON r.place_key = p.place_key {clause} "
        f"ORDER BY r.rating DESC, r.reviewed_at DESC",
        params,
    ).fetchall()
    countries = sorted({r[3] for r in rows if r[3]})
    top_rated = [
        {"name": r[1], "category": r[2], "country": r[3], "rating": r[4], "text": r[5]}
        for r in rows[:10]
    ]
    return {
        "theme": theme, "year": year,
        "place_count": len({r[0] for r in rows}),
        "countries": countries,
        "top_rated": top_rated,
    }


def patterns(conn: sqlite3.Connection, kind: str = "categories") -> dict:
    if kind == "categories":
        return {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT COALESCE(category,'unknown'), COUNT(*) FROM places "
                "WHERE place_key IN (SELECT place_key FROM reviews) "
                "GROUP BY category ORDER BY COUNT(*) DESC"
            )
        }
    raise ValueError(f"unknown pattern kind: {kind}")


def taste(conn: sqlite3.Connection, city: str) -> dict:
    cats = conn.execute(
        "SELECT p.category, COUNT(*) c, AVG(r.rating) a "
        "FROM places p JOIN reviews r ON r.place_key=p.place_key "
        "WHERE p.category IS NOT NULL GROUP BY p.category ORDER BY c DESC"
    ).fetchall()
    avg = conn.execute("SELECT AVG(rating) FROM reviews").fetchone()[0] or 0
    return {
        "city": city,
        "top_categories": [c[0] for c in cats],
        "avg_rating": round(avg, 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_query_narrative.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/query.py tests/unit/test_query_narrative.py
git commit -m "feat: narrative, patterns, taste queries"
```

---

## Task 14: LLM synthesis layer (CLI prose)

**Files:**
- Create: `src/locus/synth_llm.py`
- Test: `tests/unit/test_synth_llm.py`

**Note:** the Anthropic client is injected. Tests use a fake. This layer turns a structured dict into prose; it is only used by the CLI, never the MCP server.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_synth_llm.py
from locus.synth_llm import render_prose

class FakeAnthropic:
    def __init__(self):
        self.messages = self
    def create(self, **kwargs):
        class R:
            content = [type("B", (), {"text": "A lovely food year."})()]
        self.last_kwargs = kwargs
        return R()

def test_render_prose_calls_model_with_payload():
    client = FakeAnthropic()
    out = render_prose(client, "Summarize my food year", {"place_count": 2})
    assert out == "A lovely food year."
    assert "place_count" in str(client.last_kwargs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_synth_llm.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/synth_llm.py`**

```python
import json
import os

MODEL = "claude-sonnet-4-6"


def make_client(api_key: str | None = None):
    import anthropic
    return anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])


def render_prose(client, instruction: str, payload: dict) -> str:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                f"{instruction}\n\nGround your answer ONLY in this data; "
                f"do not invent places or facts:\n{json.dumps(payload, indent=2)}"
            ),
        }],
    )
    return msg.content[0].text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_synth_llm.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/synth_llm.py tests/unit/test_synth_llm.py
git commit -m "feat: anthropic prose synthesis (injectable client)"
```

---

## Task 15: CLI surface

**Files:**
- Create: `src/locus/cli.py`
- Test: `tests/integration/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli.py
import zipfile
from pathlib import Path
from click.testing import CliRunner
from locus.cli import cli

FIX = Path(__file__).parent.parent / "fixtures"

def _zip(tmp_path):
    zp = tmp_path / "t.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("Takeout/Maps (your places)/Reviews.json",
                   (FIX / "reviews.json").read_text(encoding="utf-8"))
    return zp

def test_cli_ingest_then_story_json(tmp_path):
    db = tmp_path / "t.db"
    zp = _zip(tmp_path)
    runner = CliRunner()
    r1 = runner.invoke(cli, ["--db", str(db), "ingest", str(zp)])
    assert r1.exit_code == 0, r1.output
    assert "reviews: 2" in r1.output
    r2 = runner.invoke(cli, ["--db", str(db), "story", "--json"])
    assert r2.exit_code == 0, r2.output
    assert "place_count" in r2.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/integration/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/cli.py`**

```python
import json

import click

from . import query
from .db import connect, init_schema
from .ingest import run_all


@click.group()
@click.option("--db", default="locus.db", help="Path to the SQLite database.")
@click.pass_context
def cli(ctx, db):
    ctx.ensure_object(dict)
    conn = connect(db)
    init_schema(conn)
    ctx.obj["conn"] = conn


@cli.command()
@click.argument("takeout_zip")
@click.pass_context
def ingest(ctx, takeout_zip):
    summary = run_all(ctx.obj["conn"], takeout_zip)
    for k, v in summary.items():
        click.echo(f"{k}: {v}")


@cli.command()
@click.pass_context
def enrich(ctx):
    from .enrich import GoogleClient, enrich_places
    try:
        n = enrich_places(ctx.obj["conn"], GoogleClient())
        click.echo(f"enriched: {n}")
    except KeyError:
        click.echo("GOOGLE_PLACES_API_KEY not set; skipping enrichment.")


@cli.command()
@click.pass_context
def embed(ctx):
    from .embed import Embedder, build_index
    n = build_index(ctx.obj["conn"], Embedder())
    click.echo(f"indexed: {n}")


@cli.command()
@click.option("--theme", default=None)
@click.option("--year", default=None, type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def story(ctx, theme, year, as_json):
    data = query.narrative(ctx.obj["conn"], theme=theme, year=year)
    if as_json:
        click.echo(json.dumps(data, indent=2))
        return
    from .synth_llm import make_client, render_prose
    try:
        client = make_client()
    except KeyError:
        click.echo(json.dumps(data, indent=2))
        return
    click.echo(render_prose(client, f"Tell the story of my {theme or 'places'}", data))


@cli.command()
@click.argument("question")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def ask(ctx, question, as_json):
    from .embed import Embedder
    results = query.recall(ctx.obj["conn"], question, Embedder(), k=10)
    if as_json:
        click.echo(json.dumps(results, indent=2))
        return
    from .synth_llm import make_client, render_prose
    try:
        client = make_client()
    except KeyError:
        click.echo(json.dumps(results, indent=2))
        return
    click.echo(render_prose(client, question, {"candidates": results}))


@cli.command()
@click.argument("city")
@click.pass_context
def taste(ctx, city):
    click.echo(json.dumps(query.taste(ctx.obj["conn"], city), indent=2))


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/integration/test_cli.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/cli.py tests/integration/test_cli.py
git commit -m "feat: click CLI surface"
```

---

## Task 16: MCP server

**Files:**
- Create: `src/locus/mcp_server.py`
- Test: `tests/unit/test_mcp_tools.py`

**Note:** test the underlying tool functions directly (not the transport). The server wires them to FastMCP.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_tools.py
from locus.db import connect, init_schema
from locus.ingest._util import upsert_place
from locus.mcp_server import _narrative_tool, _patterns_tool

def test_narrative_tool_returns_dict(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:a',5,'nice')")
    out = _narrative_tool(conn, theme="food")
    assert out["place_count"] == 1

def test_patterns_tool_returns_counts(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating) VALUES ('pid:a',5)")
    out = _patterns_tool(conn, kind="categories")
    assert out["cafe"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/unit/test_mcp_tools.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/locus/mcp_server.py`**

```python
import os
import sqlite3

from mcp.server.fastmcp import FastMCP

from . import query
from .db import connect, init_schema

DB_PATH = os.environ.get("LOCUS_DB", "locus.db")


def _get_conn() -> sqlite3.Connection:
    conn = connect(DB_PATH)
    init_schema(conn)
    return conn


def _narrative_tool(conn, theme=None, year=None) -> dict:
    return query.narrative(conn, theme=theme, year=year)


def _patterns_tool(conn, kind="categories") -> dict:
    return query.patterns(conn, kind=kind)


def _recall_tool(conn, question, k=10) -> list[dict]:
    from .embed import Embedder
    return query.recall(conn, question, Embedder(), k=k)


def _taste_tool(conn, city) -> dict:
    return query.taste(conn, city)


mcp = FastMCP("locus")


@mcp.tool()
def locus_narrative(theme: str | None = None, year: int | None = None) -> dict:
    """Structured summary of reviewed places, optionally filtered by theme/year."""
    return _narrative_tool(_get_conn(), theme=theme, year=year)


@mcp.tool()
def locus_recall(question: str, k: int = 10) -> list[dict]:
    """Semantic recall of places matching a natural-language question."""
    return _recall_tool(_get_conn(), question, k=k)


@mcp.tool()
def locus_patterns(kind: str = "categories") -> dict:
    """Aggregate patterns over reviewed places (e.g. category counts)."""
    return _patterns_tool(_get_conn(), kind=kind)


@mcp.tool()
def locus_taste(city: str) -> dict:
    """Preference profile for predicting what the user would like in a new city."""
    return _taste_tool(_get_conn(), city)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/unit/test_mcp_tools.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/locus/mcp_server.py tests/unit/test_mcp_tools.py
git commit -m "feat: MCP server exposing query tools"
```

---

## Task 17: Synthetic data generator (public demo)

**Files:**
- Create: `examples/build_synthetic.py`
- Test: `tests/integration/test_synthetic.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_synthetic.py
from examples.build_synthetic import build_synthetic_reviews

def test_synthetic_reviews_shape():
    data = build_synthetic_reviews(n=40, seed=1)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 40
    f = data["features"][0]["properties"]
    assert "five_star_rating_published" in f
    assert "location" in f
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/integration/test_synthetic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'examples'`

- [ ] **Step 3: Create `examples/__init__.py` (empty) and `examples/build_synthetic.py`**

```python
# examples/build_synthetic.py
import json
import random

CITIES = [
    ("New York", "US", 40.71, -74.00), ("Athens", "GR", 37.98, 23.72),
    ("Bengaluru", "IN", 12.97, 77.59), ("Stockholm", "SE", 59.33, 18.07),
    ("Paris", "FR", 48.85, 2.35),
]
NAMES = ["Bistro", "Cafe", "Diner", "Garden", "Rooftop", "Corner", "Market", "Kitchen"]
CATS = ["restaurant", "cafe", "bar", "park", "bakery"]


def build_synthetic_reviews(n: int = 40, seed: int = 0) -> dict:
    rng = random.Random(seed)
    feats = []
    for i in range(n):
        city, cc, lat, lng = rng.choice(CITIES)
        name = f"{rng.choice(NAMES)} {i}"
        feats.append({
            "geometry": {"coordinates": [lng + rng.uniform(-.05, .05),
                                         lat + rng.uniform(-.05, .05)], "type": "Point"},
            "properties": {
                "date": f"202{rng.randint(0,5)}-0{rng.randint(1,9)}-15T12:00:00Z",
                "five_star_rating_published": rng.randint(3, 5),
                "google_maps_url": f"https://www.google.com/maps/place//data=!1s0x0:0x{i:x}",
                "location": {"address": f"{i} Main St, {city}",
                             "country_code": cc, "name": name},
                "review_text_published": f"Loved the vibe at {name}.",
            },
        })
    return {"type": "FeatureCollection", "features": feats}


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).parent / "synthetic"
    out.mkdir(exist_ok=True)
    (out / "Reviews.json").write_text(json.dumps(build_synthetic_reviews(40, 7), indent=2))
    print(f"wrote {out / 'Reviews.json'}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/integration/test_synthetic.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Generate the bundle and commit**

```bash
.venv\Scripts\python examples/build_synthetic.py
git add examples/__init__.py examples/build_synthetic.py examples/synthetic/Reviews.json tests/integration/test_synthetic.py
git commit -m "feat: synthetic demo data generator"
```

---

## Task 18: README, SCHEMA.md, manual verification

**Files:**
- Create: `README.md`, `SCHEMA.md`, `tests/MANUAL.md`

- [ ] **Step 1: Write `SCHEMA.md`** — copy the DDL from `src/locus/db.py` verbatim with a one-line purpose per table.

- [ ] **Step 2: Write `tests/MANUAL.md`**

```markdown
# Manual demo verification

Prereq: real Takeout extracted, GOOGLE_PLACES_API_KEY and ANTHROPIC_API_KEY set (optional).

1. `locus --db locus.db ingest ~/Downloads/takeout-*.zip` → expect reviews: 80, photos: ~1000
2. `locus --db locus.db enrich` → expect "enriched: N" (N ~80-250)
3. `locus --db locus.db embed` → expect "indexed: N"
4. `locus --db locus.db story --food` → read prose; verify every named place is a place you actually reviewed (no hallucinations)
5. `locus --db locus.db ask "my favorite South Indian places"` → top result should be a real high-rated review
6. `locus --db locus.db taste Lisbon` → categories should reflect your real preferences

PASS if steps 4-5 produce grounded, non-hallucinated output.
```

- [ ] **Step 3: Write `README.md`** — sections: what it is, the data-source story (Timeline gone → contributions KG, see FEATURE_design.md §0), install, quickstart with synthetic data (`python examples/build_synthetic.py` → zip → ingest → embed → story), MCP setup (`claude mcp add locus -- python -m locus.mcp_server`), the `locus taste` hero demo, and a clear note that real Takeout enrichment needs the user's own `GOOGLE_PLACES_API_KEY`.

- [ ] **Step 4: Run full test suite**

Run: `.venv\Scripts\pytest -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add README.md SCHEMA.md tests/MANUAL.md
git commit -m "docs: README, schema, manual verification"
```

---

## Task 19: End-to-end demo on synthetic data

**Files:** none (verification only)

- [ ] **Step 1: Build a synthetic zip**

```bash
.venv\Scripts\python examples/build_synthetic.py
```

Then zip it to the expected layout:

```bash
.venv\Scripts\python -c "import zipfile,pathlib; z=zipfile.ZipFile('demo.zip','w'); z.write('examples/synthetic/Reviews.json','Takeout/Maps (your places)/Reviews.json'); z.close()"
```

- [ ] **Step 2: Run the full pipeline (no API keys → JSON fallback)**

```bash
.venv\Scripts\locus --db demo.db ingest demo.zip
.venv\Scripts\locus --db demo.db embed
.venv\Scripts\locus --db demo.db story --food --json
.venv\Scripts\locus --db demo.db taste Lisbon
```

Expected: `ingest` reports `reviews: 40`; `embed` reports `indexed: 40`; `story --food --json` prints a dict with `place_count` > 0 and real synthetic place names; `taste` prints category profile. Confirms the whole chain works end-to-end without external services.

- [ ] **Step 3: Clean up demo artifacts (do not commit)**

```bash
del demo.db demo.zip
```

---

## Self-Review Notes (completed by plan author)

**Spec coverage:** Reviews/photos/questions/labels/commutes ingest → Tasks 5–9. Enrichment §6 → Task 10. Embedding §5 → Task 11. Recall/narrative/taste/patterns §7 → Tasks 12–13. CLI §7 → Task 15. MCP §7 → Task 16. Synthetic demo §12 → Task 17. Cost-graceful degradation (no keys) → Tasks 10/15 fallbacks + Task 19. Schema §5 → Task 3. `session_id` forward-compat column → present in Task 3 DDL.

**Type consistency:** `place_key` used uniformly; `upsert_place` signature consistent across ingesters; `Embedder.encode → list[float]` and `recall(conn, question, embedder, k)` consistent between Tasks 11/12/15/16; `narrative(conn, theme, year)` signature identical in query, CLI, MCP.

**Known deferred (non-blocking):** photo→review spatial-join (geo:→pid: merge) is described in spec §6 but implemented minimally (enrichment reverse-geocodes geo: places independently rather than merging into pid: places). If exact-place merging is wanted, add a follow-up task; not required for v1 demos.
