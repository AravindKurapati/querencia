# querencia: agent recipes

How to use querencia's MCP tools from Claude Code. The MCP server exposes six tools — the
recipes below show how Claude composes them to answer multi-step questions without you
stitching CLI calls together.

## Setup once

```bash
claude mcp add querencia -- python -m querencia.mcp_server
export QUERENCIA_DB=/path/to/your/querencia.db
```

Tools available:
- `querencia_narrative(theme, year, trip_id)` — grounded structured summary.
- `querencia_recall(question, k)` — semantic recall (FTS + vector).
- `querencia_patterns(kind)` — aggregates over places.
- `querencia_taste(city)` — preference profile.
- `querencia_trips(rebuild)` — detected spatiotemporal trips.
- `querencia_recommend(city, top)` — ranked picks in a city.

## Recipe 1 — "Tell me about my trips"

User asks Claude: *"Walk me through every trip I've taken, year by year."*

Claude's tool plan:
1. `querencia_trips()` → list of trips with country, dates, place_count.
2. For each trip with ≥ 3 places, `querencia_narrative(trip_id=N)` → structured summary
   of what you ate / saw / rated.
3. Synthesize prose, grouping by year.

This turns a row-per-review database into a year-by-year travelogue without any
hand-written prompts.

## Recipe 2 — "Plan a weekend in <city> for me"

User asks: *"I'm going to Lisbon next month — what should I do?"*

Claude's tool plan:
1. `querencia_taste("Lisbon")` → top categories + average rating profile.
2. `querencia_recommend("Lisbon", top=5)` → ranked candidate places scored against the
   user's preference vector.
3. (optional) `querencia_recall("seaside walks", k=5)` → past favorites that match the
   target city's vibe, for "because you liked…" justifications.
4. Synthesize a half-day-by-half-day plan.

The grounded retrieval means Claude is never inventing places — every recommendation has
a `place_key` traceable in your local DB or the candidate cache.

## Recipe 3 — "Remind me of restaurants I'd forgotten I liked"

User asks: *"Find me places I rated highly more than two years ago but haven't been back to."*

Claude's tool plan:
1. `querencia_patterns(kind="categories")` → grounds the response in real category counts.
2. `querencia_recall("favorite restaurants", k=20)` with `hops=1` (via the underlying
   `recall` function's graph-hop parameter) → semantic top matches plus their graph
   neighbors.
3. Filter by review date in the synthesized prose.

This recipe is the canonical use case for the derived-edges PR: hop expansion turns up
places you visited *with* a favorite, not just textually similar.

## Why this is the agentic surface

The CLI is for one-shot questions; the MCP server is for *flows*. Every tool returns
JSON-safe grounded data — no LLM inside the tools themselves — so Claude can chain them
freely and the synthesis stays auditable.
