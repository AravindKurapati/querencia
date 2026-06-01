# FEATURE: Graph analytics + visualization

Add NetworkX-backed analytics over the existing `places` + `transitions` data, plus a
self-contained HTML visualization. No schema change.

## Why

Today `querencia` treats places as a bag with vector + FTS lookup. The `transitions` table
already encodes the *graph* (from_place → to_place by mode), but nothing reads it
relationally. Industry KGs (Google KG, LinkedIn Economic Graph, Microsoft GraphRAG) layer
graph algorithms on top of the same triple-store substrate. We can do the same locally with
NetworkX over a single SELECT — no new infra.

## Scope

1. `querencia.graph` module
   - `build_graph(conn) -> networkx.MultiDiGraph` — nodes = `places`, edges = `transitions`
     with `travel_mode` attr; node attrs from `places` columns.
   - `pagerank(conn, k=10) -> list[dict]` — hubs of personal travel.
   - `communities(conn) -> list[list[str]]` — greedy modularity on the undirected projection;
     returns sorted lists of place_keys per community.
   - `expand_hops(conn, seed_keys, hops=1) -> set[str]` — GraphRAG-style 1–2 hop neighborhood
     expansion for use by `recall`.

2. `querencia.query.recall` gains an optional `expand_hops: int = 0` parameter. When > 0,
   vector top-k seeds are expanded by N hops over `transitions` and any newly-reached places
   are appended (deduped) below the vector matches.

3. CLI
   - `querencia graph` — prints JSON: `{pagerank: [...], communities: [...], node_count, edge_count}`.
   - `querencia graph --viz <path.html>` — writes a standalone interactive pyvis HTML.
   - `querencia ask <q> --hops N` — passes through to `recall(expand_hops=N)`.

4. Tests (`tests/unit/test_graph.py`)
   - empty DB → empty graph, empty pagerank, empty communities.
   - linear chain A→B→C → pagerank ordering sane, single community.
   - two disjoint clusters → two communities.
   - `expand_hops` includes 1-hop neighbors and excludes 2-hop when `hops=1`.

## Out of scope (deferred)

- Community labels via LLM summarization.
- Force-directed graph view inside the existing `web/` Vite dashboard (current PR ships a
  pyvis HTML; web integration is a follow-up because it pulls in the unmerged dashboard).
- Edge weights from visit frequency (transitions table is currently unweighted).

## Database impact

**None.** This feature is read-only; it consumes existing `places` and `transitions`. No new
tables, no migrations. `SCHEMA.md` does not need updating.

## Dependencies added

- `networkx>=3.2` — core analytics.
- `pyvis>=0.3` — HTML viz; only imported when `--viz` is passed so it stays optional at
  runtime.

## Risk

Low. Pure-Python, in-memory graph build over what is typically a few hundred to a few
thousand places. No external services. If `networkx` isn't installed, the new CLI commands
fail with a clear ImportError; existing commands are unaffected.
