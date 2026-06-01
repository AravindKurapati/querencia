# querencia

A local-first **personal place knowledge graph** built from your Google Maps *contributions* —
reviews, geotagged photos, labeled places, answered questions, and commute routes. It turns
years of scattered map activity into something you can narrate, search semantically, and
extrapolate from ("what would I like in a city I've never visited?").

Everything runs on your machine against a single SQLite file. Your real data never leaves it.

## Why contributions, not Timeline

Location History / Timeline is the obvious source — but for many accounts it's gone. Google's
December 2024 migration moved Timeline on-device and, for accounts that hadn't opted in, the
server-side history was wiped. (Verified for this project's account: Takeout's *Timeline Edits*
held only a useless 9-day sliver.) **Contributions survive** that migration and are richer
anyway: a review carries a rating and your own words; a photo carries a place and a moment.
See `FEATURE_design.md` §0 for the full data-source story.

## Install

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"   # Windows; use .venv/bin on macOS/Linux
```

## Quickstart (no real data, no API keys)

```bash
# 1. generate synthetic reviews
.venv\Scripts\python examples\build_synthetic.py

# 2. wrap them in the Takeout layout the ingester expects
.venv\Scripts\python -c "import zipfile; z=zipfile.ZipFile('demo.zip','w'); z.write('examples/synthetic/Reviews.json','Takeout/Maps (your places)/Reviews.json'); z.close()"

# 3. ingest -> embed -> query
.venv\Scripts\querencia --db demo.db ingest demo.zip
.venv\Scripts\querencia --db demo.db embed
.venv\Scripts\querencia --db demo.db story --theme food --json
.venv\Scripts\querencia --db demo.db taste Lisbon
```

Without `ANTHROPIC_API_KEY` set, `story`/`ask` fall back to printing the grounded JSON instead
of prose — so the whole pipeline works offline.

## Real data

Export *Maps* from [Google Takeout](https://takeout.google.com), then:

```bash
querencia --db querencia.db ingest ~/Downloads/takeout-*.zip
querencia --db querencia.db enrich      # needs your own GOOGLE_PLACES_API_KEY
querencia --db querencia.db embed
querencia --db querencia.db story --theme food
```

`enrich` reverse-geocodes photo/commute points into named places and categories via the Google
Places API — it requires `GOOGLE_PLACES_API_KEY` in your environment and is the only step that
calls an external service. Real review/photo data is gitignored and never committed.

## Hero demo: `querencia recommend <city>`

```bash
querencia --db querencia.db recommend Lisbon
```

Builds a per-category preference vector (weighted by `rating - avg`) from your reviews,
fetches candidate places in the target city (Google Places, cached), and ranks them by
cosine similarity. Falls back to in-DB candidates from the same country when no API key
is set.

`querencia taste <city>` still emits the preference profile alone (top categories,
average rating) if you just want the summary.

## Trips

```bash
querencia --db querencia.db trips --rebuild   # detect spatiotemporal clusters
querencia --db querencia.db story --trip 3    # narrative scoped to one trip
```

Spatiotemporal clustering (connected components on lat/lng × time) groups your reviews,
photos, and visits into trips and excludes your home cluster automatically. See
`FEATURE_trips.md` for design.

## Graph analytics + visualization

Treats `places` + `transitions` as a property graph and runs NetworkX on top — no extra infra.

```bash
querencia --db querencia.db graph                  # JSON: node/edge counts, top PageRank, communities
querencia --db querencia.db graph --viz graph.html # standalone interactive HTML (pyvis)
querencia --db querencia.db ask "rooftop bars" --hops 1  # GraphRAG-style: expand vector hits 1 hop
```

`--hops` expands the vector top-k by N graph hops over `transitions` before returning, so
recall pulls in places you went *to* from a match even if their text didn't embed close.
Synthetic Reviews-only demos have no `transitions`, so PageRank degenerates to a flat list
there — communities and hop-expansion light up once commute or photo data lands. See
`FEATURE_graph_analytics.md` for design.

## MCP server

Expose the query tools to Claude Code so it does the prose for free:

```bash
claude mcp add querencia -- python -m querencia.mcp_server
```

Set `QUERENCIA_DB` to point the server at your database. Tools: `querencia_narrative`,
`querencia_recall`, `querencia_patterns`, `querencia_taste`, `querencia_trips`,
`querencia_recommend`. See `RECIPES.md` for canonical multi-turn flows.

## Surfaces

- **Python library** — `querencia.ingest`, `querencia.query`, `querencia.embed`, `querencia.enrich`.
- **CLI** — `querencia ingest|enrich|embed|story|ask|taste|graph|trips|recommend`.
- **MCP server** — `querencia.mcp_server`.

See `ARCHITECTURE.md` for the full end-to-end pipeline and design, `SCHEMA.md` for the database
design, and `tests/MANUAL.md` for the manual verification script.
