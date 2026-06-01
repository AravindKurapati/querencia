# FEATURE: MCP agent surface (trips + recommend tools, recipe doc)

Expose the new trip and recommender capabilities through MCP so Claude Code can chain
them into multi-turn flows ("plan me a 3-day Tokyo trip based on my taste").

## Why
The MCP server already exposes narrative/recall/patterns/taste. Adding `trips` and
`recommend` completes the toolkit so Claude can drive a recommendation flow end-to-end
without the human stitching CLI calls together. This is the "agentic" surface of querencia.

## Approach
Pure additive — two new `@mcp.tool` functions and a `RECIPES.md` showing canonical
orchestrations.

## Scope
1. `querencia.mcp_server` additions:
   - `querencia_trips(min_places: int = 3) -> list[dict]` — returns detected trips.
   - `querencia_recommend(city: str, top: int = 5) -> list[dict]` — wraps
     `taste.recommend`; respects the same graceful-degradation path when no API key set.

2. `RECIPES.md` — three worked examples:
   - "Tell me about my trips" → calls `querencia_trips`, then `querencia_narrative`
     per trip.
   - "Plan a weekend in Lisbon for me" → `querencia_recommend("Lisbon")` then prose
     synthesis grounded in the returned candidates.
   - "Remind me of restaurants I'd forgotten I liked" → `querencia_patterns` →
     `querencia_recall("hidden gems")` with `--hops 1`.

3. Tests
   - tool registry includes both new tools.
   - both tools delegate to the underlying functions (mocked) and return JSON-safe payloads.

## Schema impact
**None.** Reuses everything from the trips and taste features.

## Out of scope
- Auto-generated tool descriptions from docstrings.
- A standalone "agent loop" CLI (`querencia chat`) — the agent IS Claude Code; querencia
  provides the tools, not the loop.

## Risk
Low. Additive, no new external calls beyond what `recommend` already does.
