# FEATURE: locus — Personal Place Knowledge Graph

> **Working name:** `locus`. Final name TBD before first commit.
> **Date:** 2026-05-19
> **Author:** Aravind Kurapati
> **Status:** Design approved (revised after data verification), pending implementation plan

---

## 0. Important context — why this is a "Place" graph, not a "Timeline" graph

The original design assumed a rich Google Timeline location history. **Verification of the actual Takeout export proved that history is gone** — Google's Dec 2024 on-device migration wiped this account's server-side Timeline. The export's `Timeline/Timeline Edits.json` contains only two ~5-day slivers (Jul + Aug 2025) of raw activity signals, not a usable history.

However, the same export contains a **curated 8-year personal-place dataset** in the Maps contributions, which is arguably a *better* foundation for the narrative + recall use cases. This spec is built on the data that actually exists. See §2 for the verified inventory.

---

## 1. Summary

A local-first **personal place knowledge graph** built from your Google Maps *contributions* (reviews, geotagged photos, labeled places, commute routes) rather than Timeline visits. Ingests the relevant slices of a Google Takeout export, builds a SQLite-backed KG with semantic embeddings, and exposes it through a Python library, a CLI, and an MCP server.

**Headline capability:** generating coherent written narratives grounded in *your own words* — "tell me the story of my food year," "what kind of places do I love?"

**Secondary capability:** semantic recall over places — "my go-to South Indian spots in NJ," "the rooftop place I loved in Athens."

**Distinctive agentic move:** "given my review patterns, predict what I'd love in a new city" — taste extrapolation grounded in real preference data.

Architecturally mirrors `session-sidekick`: `local-ingest → SQLite + FTS5 + sqlite-vec → MCP/CLI surfaces`. Different domain, same engineering muscle.

---

## 2. Verified data inventory (ground truth from the actual export)

Source: `takeout-20260519T205538Z-3-001.zip` (5.81 GB total).

| Source file | Volume | Fields we use | Role |
|---|---|---|---|
| `Maps (your places)/Reviews.json` | **80 reviews, 2017-12 → 2026-01, 7 countries** (IN 26, US 23, BE 4, GR 4, SE 3, HU 2, FR 2) | coords, address, place name, star rating, written text, date, structured Q&A (meal type, price) | **Primary entity + narrative source** |
| `Maps/Photos and videos/*.json` | **1,057 sidecars** (873 jpg, 182 mp4, 2 png) | `creationTime` (unix + formatted), `geoDataExif` lat/lng | **Visit-time signal** (geo+time points; spatial-join to places) |
| `Maps/Answers to automated questions/*.json` | **241 entries** | `placeUrl` (cid form), `question`, `selectedChoice` | Place associations + preference signal (no reliable timestamp) |
| `Maps/My labeled places/*.json` | Home, Work, … | GeoJSON coords + name + address | Anchor places |
| `Maps/Commute routes/*.json` | trips | `place_visit` lat/lng pairs, `transition.travel_mode` | Route/commute structure |
| `Timeline/Timeline Edits.json` | 9 days, summer 2025 | activity types, position, wifiScan | Minor — activity-type demo only, not narrative |

**Not usable:** the bulk of the 5.7 GB is photo binaries and `Answers to automated questions` chatter. We read only the JSON listed above.

---

## 3. Goals & non-goals

### Goals
- Single-user, local-first. Zero data leaves the machine except one-time place enrichment.
- Ship in 3–4 days of focused work.
- Reinforce existing portfolio thesis (`agent-flight-recorder`, `session-sidekick`, `claude-burnrate`): local-first agentic tooling, MCP/hooks, semantic recall over personal data.
- Public README demos via bundled synthetic data so hiring managers can poke it without uploading their own export.

### Non-goals (v1)
- Multi-user hosted product. (Rejected — legal/operational burden of hosting location PII.)
- Real-time tracking.
- Live integration with `agent-flight-recorder` / `session-sidekick`. Schema is forward-compatible via `visits.session_id` but the join is deferred.
- Property graph DB (Kuzu/Neo4j). Relational `transitions` covers all v1 graph queries.
- Prospective location collection (OwnTracks/GPSLogger). Possible v2; out of scope now.

---

## 4. Architecture overview

```
Takeout zip
   │  (ingesters, one per source)
   ├──► ingest.reviews   ─┐
   ├──► ingest.photos    ─┤
   ├──► ingest.questions ─┼──► SQLite DB ◄───► locus.query (lib, LLM-free)
   ├──► ingest.labels    ─┤                        │
   ├──► ingest.commutes  ─┘                        │
   │                                               │
   ├──► enrich   (Places API: category/canonical) ─┤
   └──► embed    (render → bge-small → sqlite-vec) ─┘
                                                    ├─► CLI surface  (Anthropic API for prose)
                                                    └─► MCP server   (Claude Code does prose, free)
```

Units, each with one clear job:

| Unit | Input | Job | Output |
|---|---|---|---|
| `ingest.*` (one parser per source) | a slice of the Takeout zip | Parse → normalize → upsert into `places`, plus source-specific tables | populated raw schema |
| `enrich` | `places` rows missing metadata | Reverse-geocode photo-only places; fetch category/canonical name once per place; cache | enriched `places` |
| `embed` | every `place` + `review` | Render to NL string, embed, write to sqlite-vec | `place_vec` |
| `locus.query` | structured args | Pure-Python query functions over the DB; **no LLM** | dicts / lists |
| Surfaces (CLI + MCP) | user input | Thin wrappers over `locus.query`. CLI uses Anthropic API for prose; MCP returns structured data, Claude Code synthesizes (free) | narrative / recall results |

**Deliberate boundary:** `locus.query` is the only unit that touches the DB. CLI/MCP wrap it. The LLM call lives only in the surface layer, so `locus.query` is 100% testable without an LLM.

---

## 5. Schema

```sql
-- Central entity: a place (from any source, deduped by place_key)
CREATE TABLE places (
  place_key       TEXT PRIMARY KEY,        -- placeId if known, else "geo:<rlat>,<rlng>"
  canonical_name  TEXT,
  category        TEXT,                     -- enriched: "restaurant", "park", ...
  address         TEXT,
  country_code    TEXT,
  lat REAL, lng REAL,
  source_flags    TEXT,                     -- which sources referenced it: "review,photo,label"
  enriched_at     TIMESTAMP                 -- NULL = enrichment pending
);

-- Reviews: your own words about a place
CREATE TABLE reviews (
  review_id     INTEGER PRIMARY KEY,
  place_key     TEXT NOT NULL REFERENCES places(place_key),
  rating        INTEGER,                    -- 1..5
  text          TEXT,
  reviewed_at   TIMESTAMP,
  structured_qa TEXT                        -- JSON: meal type, price, etc.
);

-- Photos: geotagged, timestamped contributions
CREATE TABLE photos (
  photo_id     INTEGER PRIMARY KEY,
  place_key    TEXT REFERENCES places(place_key),  -- spatial-joined; nullable
  taken_at     TIMESTAMP NOT NULL,
  lat REAL, lng REAL,
  media_type   TEXT                          -- jpg / mp4 / png
);

-- Sparse visits: derived signals (photo clusters, question answers, commute endpoints)
CREATE TABLE visits (
  visit_id     INTEGER PRIMARY KEY,
  place_key    TEXT NOT NULL REFERENCES places(place_key),
  occurred_at  TIMESTAMP,                    -- nullable for sourceless associations
  source       TEXT NOT NULL,                -- "photo" | "question" | "commute"
  session_id   TEXT                          -- forward-compat hook for AFR/sidekick (v2)
);
CREATE INDEX visits_place ON visits(place_key);

-- Transitions: commute-route edges (the "graph")
CREATE TABLE transitions (
  from_place_key TEXT REFERENCES places(place_key),
  to_place_key   TEXT REFERENCES places(place_key),
  travel_mode    TEXT,                        -- DRIVE / WALK / ...
  PRIMARY KEY (from_place_key, to_place_key, travel_mode)
);

-- FTS5 keyword index over review text + place name
CREATE VIRTUAL TABLE place_fts USING fts5(place_key UNINDEXED, rendered_text, content='');

-- sqlite-vec semantic index (one row per place, embedding its reviews + name + category)
CREATE VIRTUAL TABLE place_vec USING vec0(
  place_key TEXT PRIMARY KEY,
  embedding FLOAT[384]                        -- bge-small-en-v1.5
);
```

**Deliberate calls:**
1. **`place_key` unifies sources.** A real `placeId` when we have one (reviews, questions); a rounded `geo:lat,lng` key otherwise (photos), so a photo near a reviewed place can spatial-join to it during enrichment.
2. **`visits` is sparse and source-tagged**, not the spine. Reflects that we have *associations*, not a continuous history.
3. **`session_id` present from day one**, NULL by default — zero-cost option value for the future AFR/sidekick join.
4. **`places.enriched_at IS NULL`** drives idempotent, resumable enrichment.
5. A `SCHEMA.md` at project root will be created at implementation start and kept in sync per project CLAUDE.md.

---

## 6. Data flow

### Ingest (one-time per export)
```
Takeout zip
  ├─► ingest.reviews    → places (placeId) + reviews
  ├─► ingest.photos     → photos + places (geo: keys)
  ├─► ingest.questions  → places + sparse visits (source=question)
  ├─► ingest.labels     → places (Home/Work anchors)
  ├─► ingest.commutes   → transitions
  ├─► enrich            → fills category/canonical; spatial-joins geo: keys to placeIds
  └─► embed             → place_vec + place_fts
```
Each stage independent, idempotent, resumable.

### Query — narrative (`locus story --food` / MCP `locus_narrative`)
```
scope (theme/period/place-set)
  → SQL + spatial aggregation (places, reviews, ratings, countries, timeline of photos)
  → structured dict (grounded on real review text)
  → [CLI] Anthropic API renders prose   |   [MCP] Claude Code renders prose (free)
```

### Query — recall (`locus ask "..."` / MCP `locus_recall`)
```
question → embed → sqlite-vec ANN over place_vec (+ FTS5 keyword) → top-k places
        → join reviews/photos for full context
        → [CLI] Anthropic API answers   |   [MCP] Claude Code answers
```

**Invariant:** the LLM never sees raw DB rows — always pre-shaped by `locus.query`.

---

## 7. Surfaces

### CLI (`locus`)
```
locus ingest <takeout-zip-or-dir>     # runs all ingesters
locus enrich [--max-calls N]          # idempotent; resumable
locus embed                           # idempotent; resumable

locus story --food                    # narrative themes
locus story --travel
locus story --year 2024
locus ask "my go-to South Indian places in NJ"
locus taste <city>                    # predict what you'd love in a new city
locus patterns categories             # what kinds of places you favor
```
`story`, `ask`, `taste` use the Anthropic API by default; `--json` returns raw structured data and skips the LLM. CLI never hard-requires `ANTHROPIC_API_KEY`.

### MCP server
- `locus_narrative(scope) → structured dict`
- `locus_recall(query, k=10) → list[place_with_context]`
- `locus_taste(city) → ranked prediction inputs`
- `locus_patterns(kind) → structured result`

Claude Code calls these and synthesizes. Zero per-query LLM cost (covered by existing subscription).

---

## 8. Error handling & failure modes

| Failure | Strategy |
|---|---|
| Source file missing / renamed in a future export | Each ingester is independent and optional. Missing source → that ingester no-ops with a log line; others proceed. |
| Photo with no `geoDataExif` | Skip geo-join; still record `taken_at` if present, else skip the photo. |
| Question `placeUrl` cid not resolvable | Store the place with a `cid:` key; enrichment attempts resolution; unresolved stays as a stub. |
| Places API rate-limit / cost ceiling | `enrich` idempotent (`enriched_at IS NULL`), `--max-calls N` cap, resumable. |
| No `GOOGLE_PLACES_API_KEY` | Enrichment skipped; categories blank; narratives read flatter. Never hard-fails. |
| No `ANTHROPIC_API_KEY` (CLI) | `story`/`ask`/`taste` return structured dicts instead of prose. MCP unaffected. |
| Embedding model unavailable | Auto-download on first `embed` with a single log line. |

Thread: **graceful degradation, never hard failure.** Every external dependency is optional.

---

## 9. Testing

1. **Unit** (`tests/unit/`) — each ingester against a small fixture (real-shaped Reviews/photo-sidecar/labeled-place JSON) + one adversarial garbage case. `locus.query` against a seeded DB (~30 places). No network, no LLM.
2. **Integration** (`tests/integration/`) — full pipeline: ingest fixtures → enrich (mocked Places client) → embed (stubbed embeddings) → query end-to-end. One test per CLI command + per MCP tool.
3. **Manual demo verification** (`tests/MANUAL.md`) — run `locus story --food` on the real 80 reviews, eyeball for hallucination; three known recall queries with known answers. `project-launch-checklist` skill runs before public release.

---

## 10. Cost model

| Component | Cost |
|---|---|
| Ingest, embedding, query, storage | $0 — all local |
| Place enrichment | $0 in practice. Only ~80–250 unique places to enrich/reverse-geocode (not thousands). Well inside Google's $200/month free credit. **Requires a GCP billing account** (card on file), no actual charge. |
| MCP synthesis | $0 extra — existing Claude subscription |
| CLI synthesis | Pennies per call; skippable with `--json` |
| Hosting | $0 |

Smaller place count than the original Timeline design → enrichment is even cheaper.

---

## 11. Alternatives considered and rejected

- **Original Timeline-visit design** — Rejected: the account's Timeline history was wiped server-side by Google's Dec 2024 migration (verified, see §0/§2). Pivoted to contributions.
- **Wait 2–3 weeks, collect prospectively** (OwnTracks/GPSLogger) — Rejected for v1 timing; viable v2.
- **Multi-user hosted product** — Rejected: location-PII custody burden, off-thesis.
- **Browser-only stats tool** — Rejected: drifts into Wrapped-style territory, off-thesis.
- **Property graph DB** — Rejected for time risk; relational `transitions` suffices.
- **Enrichment at query-time via MCP-to-MCP** — Rejected for v1; rich data should be present at query time.

---

## 12. Open items (to nail during implementation)

- **Project name** — leading candidate `locus`; verify PyPI/GitHub availability. Alternatives: `placebook`, `groundtruth`, `wherewise`.
- **Embedding model** — default `bge-small-en-v1.5` (sidekick parity); fallback `all-MiniLM-L6-v2`.
- **Synthetic data bundle** — generate a fake 40-place, 5-country review set + photo sidecars committed to `examples/` so the repo demos with zero setup and no real PII.
- **Question `placeUrl` cid → placeId resolution** — confirm a reliable resolution path during enrichment; if unreliable, treat questions as preference-only signal (no place node).
- **MCP tool naming** — finalize `locus_narrative` / `locus_recall` / `locus_taste` / `locus_patterns`.

---

## 13. Implementation precondition — SATISFIED

Data is already in hand and verified (§2). The export at `~/Downloads/takeout-20260519T205538Z-3-001.zip` contains the sources this spec depends on. No further data acquisition needed before implementation. (Recommend copying the needed JSON slices into `locus/data/raw/` — gitignored — at implementation start; do NOT commit real review/photo data.)

---

## 14. Reference: related projects

- **agent-flight-recorder** (`D:\Aru\NYU\agent-flight-recorder`) — same local-first ingest pattern over Claude/Codex session JSONL.
- **session-sidekick** (`D:\Aru\NYU\projects\session-sidekick`) — same SQLite + FTS5 + semantic recall stack. **Closest analog**; locus is "sidekick for your places."
- **claude-burnrate** (`D:\Aru\NYU\claude-burnrate`) — same local-first CLI pattern, different domain.

Together the four form a coherent portfolio: **local-first agentic tooling over personal data, each composable via MCP.**
