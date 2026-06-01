# FEATURE: Derived graph edges

The `transitions` table is empty for review-only data (it's only populated by Takeout
commute exports). That makes the graph-analytics PR's PageRank/communities degenerate.
Fix by *deriving* edges from data we always have.

## Why
Review-only users see communities = N singletons today. Co-visit and semantic-neighbor
edges turn the graph into something meaningful for the common case.

## Approach
Two derived edge types, computed on demand inside `graph.build_graph`:

1. **Co-visit edges** — two reviews/photos at places within `T_HOURS=24` of each other
   imply a connection. Compute via a single SELF JOIN on the event stream
   (`reviews UNION photos UNION visits`) ordered by time.

2. **Semantic edges** — for each place, its top-`K=3` `place_vec` neighbors become edges
   (undirected, deduped). Computed via the existing vec MATCH query per node — cheap
   because vec index is in-memory.

Both edge types are added with a `kind` attribute (`co_visit`, `semantic`,
`transition`) so callers can filter. PageRank/communities use all kinds by default.

## Scope
1. `querencia.graph.build_graph(conn, *, include_derived=True)` — gains a flag.
2. Helpers in `graph.py`: `_covisit_edges(conn)`, `_semantic_edges(conn, k=3)`.
3. CLI: `querencia graph --no-derived` to fall back to transitions-only behavior.
4. Tests
   - two reviews within 24h at different places → one co-visit edge.
   - two reviews 48h apart → no co-visit edge.
   - three embedded places, k=2 → each has ≤2 semantic neighbors.
   - `include_derived=False` returns the original transitions-only graph.

## Schema impact
**None.** Derived at read time. No new tables.

## Out of scope
- Edge weights from visit frequency.
- Persisted/materialized derived edges (revisit if perf becomes an issue beyond ~5k places).

## Risk
Low. Read-only, additive, gated by a flag.
