# querencia — Architecture & End-to-End Guide

This document explains what querencia is, how the pipeline works stage by stage, how the
pieces fit together, and how to run and extend it. For the quickstart see `README.md`; for the
raw table definitions see `SCHEMA.md`; for the product/design rationale see `FEATURE_design.md`.

---

## 1. What it is, in one paragraph

querencia turns the *contributions* you've made to Google Maps over the years — reviews,
ratings, geotagged photos, answered questions, labeled places, and commute routes — into a
local **knowledge graph of places** you can query three ways: semantic **recall** ("that
rooftop with the great vibe"), grounded **narrative** ("the story of my food year"), and
**taste extrapolation** ("what would I enjoy in a city I've never visited"). Everything runs on
your machine against one SQLite file. Nothing is uploaded; the only optional outbound calls are
to the Google Places API (enrichment) and the Anthropic API (prose), and both are opt-in.

The name is the Spanish word *querencia*: the place one is instinctively drawn to.

### Why contributions instead of Timeline

Location History / Timeline was the obvious source, but Google's December 2024 migration moved
Timeline on-device and wiped server-side history for accounts that hadn't opted in — so for many
people the Takeout *Timeline Edits* file is a near-empty sliver. Contributions survived that
migration and are richer anyway: a review carries a rating *and your own words*; a photo carries
a place *and a moment*. querencia is built on that durable, expressive data.

---

## 2. High-level architecture

```
                         ┌─────────────────────────────────────────────┐
   Google Takeout .zip   │                  querencia                   │
   (Maps contributions)  │                                              │
            │            │   ┌──────────┐                               │
            ▼            │   │  INGEST  │  one normalizer per source     │
   ┌──────────────────┐  │   │          │  → unified `places` + facts    │
   │ Reviews.json     │──┼──▶│ reviews  │                               │
   │ Photo sidecars   │  │   │ photos   │           ┌──────────────┐    │
   │ Questions        │  │   │ questions├──────────▶│   SQLite      │   │
   │ Labeled places   │  │   │ labels   │           │ (+ sqlite-vec)│   │
   │ Commute routes   │  │   │ commutes │           │               │   │
   └──────────────────┘  │   └──────────┘           │  places       │   │
                         │                          │  reviews      │   │
                         │   ┌──────────┐           │  photos       │   │
   Google Places API ───┼──▶│  ENRICH  │──────────▶│  visits       │   │
   (optional, your key) │   │          │  names,    │  transitions  │   │
                         │   └──────────┘  categories│  place_fts    │   │
                         │                          │  place_vec    │   │
                         │   ┌──────────┐           └──────┬───────┘    │
   sentence-transformers │   │  EMBED   │──────────────────┘            │
   (BAAI/bge-small)  ────┼──▶│          │  render → vector + FTS        │
                         │   └──────────┘                               │
                         │                                              │
                         │   ┌──────────┐   LLM-free, pure Python        │
                         │   │  QUERY   │   recall / narrative /         │
                         │   │          │   patterns / taste            │
                         │   └────┬─────┘                               │
                         │        │                                     │
                         │   ┌────┴───────────────┬──────────────────┐  │
                         │   ▼                    ▼                  ▼  │
                         │  CLI               MCP server        Library │
                         │  (Anthropic        (Claude does      (import │
                         │   prose, opt.)      prose for free)   directly)│
                         └─────────────────────────────────────────────┘
```

The spine is a single SQLite database. Every stage reads from and writes to it; nothing holds
state in memory between runs. That is what "local-first" means here — the database *is* the
application state, and you can inspect it with any SQLite browser.

---

## 3. The unifying idea: `place_key`

Everything hangs off one table, `places`, keyed by a string `place_key`. Different sources
identify a place differently, so the key encodes which identity scheme was used:

| Prefix      | Source                                   | Example                       |
|-------------|------------------------------------------|-------------------------------|
| `pid:<hex>` | Google place id parsed from a review URL | `pid:49c924ef18940842`        |
| `cid:<hex>` | the `cid=` id in a question's place URL  | `cid:3ce7be42251d9745`        |
| `geo:lat,lng`| a coordinate rounded to 5 decimals      | `geo:40.74357,-74.05123`      |
| `visit:<id>`| a commute leg endpoint with no coords    | `visit:SOURCE_ID`             |

The `pid:` form is preferred because it's stable across photos/reviews of the same place. When
no stable id exists (a photo only has EXIF coordinates), querencia falls back to a `geo:` key
rounded to ~1.1 m precision so repeated visits to the same spot collapse to one node.

**Upsert semantics.** Multiple sources can describe the same place. `ingest._util.upsert_place`
inserts the row the first time and afterwards only *fills gaps* (`COALESCE`) — it never
overwrites a value with `NULL`. It also accumulates a comma-joined `source_flags` set
(`review`, `photo`, `label`, `commute`, `question`) so you can see every source that touched a
place. This is why ingest order doesn't matter and why re-running ingest is safe.

> **Known v1 simplification.** Photo `geo:` places are *not* spatially merged into the matching
> reviewed `pid:` place — enrichment reverse-geocodes them independently. True spatial merging
> is a deliberate follow-up, noted in the plan's self-review.

---

## 4. The pipeline, stage by stage

### Stage 1 — Ingest (`querencia.ingest`)

`run_all(conn, zip_path)` opens the Takeout zip and dispatches each known path prefix to a
dedicated normalizer, returning a count summary. Each normalizer is small and pure: it reads one
JSON shape and writes rows.

| Module        | Reads (Takeout path)                          | Writes                                  |
|---------------|-----------------------------------------------|-----------------------------------------|
| `reviews.py`  | `Maps (your places)/Reviews.json`             | `places` + `reviews` (rating, text, structured Q&A) |
| `photos.py`   | `Maps/Photos and videos/*.json` sidecars      | `places` + `photos` (only if EXIF geo present) |
| `questions.py`| `Maps/Answers to automated questions/*.json`  | `places` (`cid:`) + `visits` (source=question) |
| `labels.py`   | `Maps/My labeled places/*.json`               | `places` (named, e.g. Home/Work)        |
| `commutes.py` | `Maps/Commute routes/*.json`                  | `places` + `transitions` (with travel mode) |

Key parsing details, all verified against real export data:
- Review geometry coordinates are GeoJSON order `[lng, lat]` — querencia swaps them.
- The place id is extracted from the review URL with the regex `!1s0x0:0x([0-9a-fA-F]+)`.
- Reviews without a `location` block (some exports drop it) still ingest; they just won't have
  a name/address until enrichment or stay coordinate-only.
- Photos with missing or `(0,0)` coordinates are skipped (return `False`) rather than creating a
  junk place at null island.
- A commute `place_visit` that has no coordinates still gets a `visit:<id>` placeholder place so
  its `transition` edge can satisfy the foreign key and be recorded.

### Stage 2 — Enrich (`querencia.enrich`)

Coordinate-only places (`geo:`/`cid:`) have no human-readable name or category. `enrich_places`
walks every place where `enriched_at IS NULL` and has coordinates, calls a reverse-geocode
client, and fills `canonical_name`, `category`, `address` (again via `COALESCE`, so existing
review names win). It stamps `enriched_at` so the work is **idempotent** — a second run does
nothing — and accepts `max_calls` to cap spend.

The Google dependency is isolated behind `GoogleClient`, which is injected. In production the CLI
passes a real `GoogleClient` (needs `GOOGLE_PLACES_API_KEY`); in tests a fake client returns
canned data, so the test suite makes zero network calls. This is the central testability pattern
of the codebase (see §7).

### Stage 3 — Embed (`querencia.embed`)

Two parts:
- `render_place(conn, key)` is a pure function that turns a place + its reviews into one text
  line, e.g. `Balaji Bhavan | (restaurant) | 249 Central Ave… | rated 5/5: Great dosa`. This is
  the *only* place that decides what text represents a place, so recall quality lives here.
- `build_index(conn, embedder)` renders every place, writes the text into the `place_fts` FTS5
  table (keyword search) and the embedding vector into the `place_vec` sqlite-vec table
  (semantic search). It clears both tables first, so the index is always a clean rebuild.

The embedder is `BAAI/bge-small-en-v1.5` (384-dim, matching the schema's `FLOAT[384]`), wrapped
in an injectable `Embedder` class — again faked in tests with a deterministic vector.

### Stage 4 — Query (`querencia.query`) — LLM-free core

All analytical logic is plain Python + SQL with **no LLM calls**, so it's fast, deterministic,
and testable. Four functions:

- `recall(conn, question, embedder, k)` — embeds the question, runs a sqlite-vec `MATCH … k`
  nearest-neighbor search over `place_vec`, joins back to `places` and the place's reviews, and
  returns ranked candidates with their distance.
- `narrative(conn, theme, year)` — pulls reviewed places (optionally filtered to food categories
  or a year), and returns a *grounded* structure: place count, countries, and the top-rated
  places. No prose, no invention — just the facts a prose layer may later narrate.
- `patterns(conn, kind)` — aggregates, e.g. category counts across reviewed places.
- `taste(conn, city)` — builds a preference profile (top categories, average rating). The `city`
  argument frames the output ("what you'd like in Lisbon"); the profile is derived from
  everywhere you've actually rated.

Because this layer returns dicts/lists rather than text, both surfaces below share it.

### Stage 5 — Surfaces

querencia exposes the same core three ways, differing only in *who writes the prose*:

1. **Library** — import `querencia.query` etc. directly. Returns structured data. No prose.
2. **CLI** (`querencia.cli`) — wraps the core with `click`. For `story`/`ask` it optionally calls
   the **Anthropic** API (`synth_llm.render_prose`, injectable client) to turn the grounded dict
   into prose, with a strict instruction to use *only* the provided data. If
   `ANTHROPIC_API_KEY` is unset it gracefully prints the JSON instead — so the CLI always works
   offline.
3. **MCP server** (`querencia.mcp_server`) — exposes `querencia_narrative`, `querencia_recall`,
   `querencia_patterns`, `querencia_taste` as MCP tools. Here Claude Code itself does the prose,
   so no Anthropic key is needed and there's no extra cost.

---

## 5. Data model (summary)

Full DDL is in `SCHEMA.md`. The shape:

- **`places`** — the hub. One row per `place_key`; `source_flags`, `enriched_at`, lat/lng,
  name/category/address/country.
- **`reviews`** — rating, text, `reviewed_at`, and `structured_qa` (the review's questions as
  JSON), FK → `places`.
- **`photos`** — geotagged photo events (place, timestamp, media type).
- **`visits`** — generic visit signal (currently from questions); `session_id` is a
  forward-compat column for future session grouping.
- **`transitions`** — directed travel edges between places with a travel mode (from commutes).
- **`place_fts`** — FTS5 virtual table of rendered text (keyword recall).
- **`place_vec`** — sqlite-vec virtual table of 384-dim embeddings (semantic recall).

`connect()` loads the sqlite-vec extension and enables foreign keys; `init_schema()` is
idempotent (`CREATE … IF NOT EXISTS`).

---

## 6. End-to-end walkthroughs

### A. Offline demo (synthetic data, no API keys)

```bash
# 1. generate synthetic reviews (deterministic, seeded)
.venv\Scripts\python examples\build_synthetic.py

# 2. wrap them in the Takeout layout the ingester expects
.venv\Scripts\python -c "import zipfile; z=zipfile.ZipFile('demo.zip','w'); z.write('examples/synthetic/Reviews.json','Takeout/Maps (your places)/Reviews.json'); z.close()"

# 3. run the pipeline
.venv\Scripts\querencia --db demo.db ingest demo.zip          # -> reviews: 40
.venv\Scripts\querencia --db demo.db embed                    # -> indexed: 40
.venv\Scripts\querencia --db demo.db story --theme food --json
.venv\Scripts\querencia --db demo.db taste Lisbon
```

The synthetic generator assigns each review a category, so `story --theme food` and `taste`
produce real output even without the Google enrichment step. With no `ANTHROPIC_API_KEY`,
`story`/`ask` print grounded JSON instead of prose.

### B. Real data (your Takeout)

```bash
querencia --db querencia.db ingest ~/Downloads/takeout-*.zip  # reviews, photos, questions, …
querencia --db querencia.db enrich    # needs GOOGLE_PLACES_API_KEY; fills names/categories
querencia --db querencia.db embed     # downloads bge-small on first run, builds index
querencia --db querencia.db story --theme food
querencia --db querencia.db ask "my favorite South Indian places"
querencia --db querencia.db taste Lisbon
```

`enrich` is the only step that contacts an external service for *your* data, and it's optional —
without it you still get reviewed-place narrative/recall, just with thinner categories on
coordinate-only places. Real review/photo data is gitignored and never committed.
See `tests/MANUAL.md` for the manual acceptance checklist (verify prose is grounded — no
hallucinated places).

### C. As an MCP server in Claude Code

```bash
claude mcp add querencia -- python -m querencia.mcp_server
# point it at your database:
#   set QUERENCIA_DB=C:\path\to\querencia.db   (PowerShell: $env:QUERENCIA_DB=...)
```

Then ask Claude things like "use querencia to tell the story of my food year" — it calls the
tools and writes the prose itself.

---

## 7. Design principles worth knowing

- **Local-first, DB-as-state.** Each command is a pure function of the SQLite file plus its
  input. No hidden caches, no servers. You can delete the `.db` and rebuild from the zip.
- **Injectable external clients.** Every network/paid dependency — Google Places (`GoogleClient`),
  the embedder (`Embedder`), Anthropic (`make_client`) — is passed in, so tests substitute fakes
  and run with no keys and no network. This is why the whole suite runs in seconds.
- **Idempotency everywhere.** `init_schema`, `upsert_place` (gap-fill via `COALESCE`),
  `enrich_places` (`enriched_at` marker), and `build_index` (clear-then-rebuild) are all safe to
  re-run.
- **LLM-free analytics, LLM-only prose.** All the logic that must be correct lives in `query.py`
  with no model in the loop; the model only ever *phrases* already-grounded data, and is
  instructed not to invent. This keeps results trustworthy and the core unit-testable.
- **Graceful degradation.** Missing `ANTHROPIC_API_KEY` → JSON instead of prose; missing
  `GOOGLE_PLACES_API_KEY` → skip enrichment with a message. Nothing hard-fails on absent keys.

---

## 8. Extending it

- **A new Takeout source.** Add `ingest/<source>.py` with an `ingest_<x>(conn, data)` that calls
  `upsert_place` and writes its facts, then wire its path prefix into `ingest.run_all`. Add a
  fixture and a unit test.
- **A new query.** Add a function to `query.py` returning a dict/list, then expose it on the CLI
  (`cli.py`) and/or as an MCP tool (`mcp_server.py`). The structured/prose split means you write
  the logic once.
- **A different embedding model.** Swap the model name in `Embedder` — keep it 384-dim or update
  the `place_vec` schema's `FLOAT[N]` to match.
- **Spatial photo↔review merge.** The deferred v1 simplification: join photo `geo:` places onto
  nearby reviewed `pid:` places before enrichment, so a place you reviewed *and* photographed is
  one node. Would live in `enrich.py` or a new merge pass before `build_index`.

---

## 9. File map

```
src/querencia/
  db.py            connection + schema DDL + sqlite-vec loading
  models.py        dataclasses: Place, Review, Photo, Visit, Transition
  ingest/
    __init__.py    run_all() orchestrator over the Takeout zip
    _util.py       geo_key(), upsert_place(), zip JSON readers
    reviews.py     photos.py  questions.py  labels.py  commutes.py
  enrich.py        GoogleClient (injectable) + idempotent enrich_places()
  embed.py         render_place() + Embedder (injectable) + build_index()
  query.py         LLM-free recall / narrative / patterns / taste
  synth_llm.py     Anthropic prose synthesis (injectable client) — CLI only
  cli.py           click CLI: ingest|enrich|embed|story|ask|taste
  mcp_server.py    FastMCP server exposing the query tools
examples/
  build_synthetic.py   seeded synthetic Reviews.json for offline demos
tests/
  unit/  integration/  fixtures/  MANUAL.md
```
