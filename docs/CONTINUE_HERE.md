# locus — Session Handoff (continue here)

**Last updated:** 2026-05-19. Previous session ran out of budget right before implementation.

## What this project is
`locus` — a local-first **personal place knowledge graph** built from Google Maps *contributions* (reviews, geotagged photos, labeled places, commute routes). NOT Timeline — that was wiped server-side by Google's Dec 2024 migration for this account (verified). Portfolio piece; same architecture as `session-sidekick`. Surfaces: Python lib core + `click` CLI + MCP server. Hero demos: `locus story --food`, `locus ask "..."`, `locus taste <city>`.

## Current state
- **Design spec:** `FEATURE_design.md` — DONE & approved by user.
- **Implementation plan:** `IMPLEMENTATION_PLAN.md` — DONE & self-reviewed. 19 TDD tasks with complete code.
- **Memory written:** `project_locus.md`, `feedback_verify_data_before_committing.md` (in user memory dir).
- **CODE: none written yet.** Project dir contains only the 3 markdown files above. No git repo, no venv, no package.

## Immediate next step
User was choosing execution mode when session ended. **Ask: Subagent-Driven (recommended) vs Inline Execution?** Then execute `IMPLEMENTATION_PLAN.md` task-by-task via `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

Before Task 1 work: `git init` in `D:\Aru\NYU\locus` (not yet a repo), then run Task 1 (scaffold + `python -m venv .venv && .venv\Scripts\pip install -e ".[dev]"`).

## Critical context for the new session
- **Platform:** Windows 11, PowerShell. Use `.venv\Scripts\pytest` / `.venv\Scripts\python` / `.venv\Scripts\locus` (backslash paths). Bash tool also available.
- **Real data:** `~/Downloads/takeout-20260519T205538Z-3-001.zip` (5.81 GB). Verified contents: `Reviews.json` (80 reviews, 2017–2026, 7 countries), 1,057 photo sidecars (geo+time), 241 question answers, labeled places (Home/Work), commute routes. Timeline Edits = useless 9-day sliver.
- **NEVER commit real review/photo data.** `.gitignore` (Task 1) excludes `data/raw/` and `*.db`. Demos use synthetic data (Task 17).
- **Exact field shapes are baked into the plan's parser code** — verified live from the zip. Reviews geometry coords are `[lng, lat]` (GeoJSON order). 5/80 reviews have no `location`; 45/80 have `review_text_published`. Place key = hex id from `google_maps_url` (`!1s0x0:0x<hex>`) → `pid:<hex>`, else `geo:lat,lng`.
- **Injectable external clients:** enrichment (Google Places) and embeddings (sentence-transformers) and Anthropic are all injected so tests use fakes — no network/API keys in tests.
- **Deferred (non-blocking) v1 simplification:** photo `geo:` places are NOT merged into matching reviewed `pid:` places; enrichment reverse-geocodes them independently. Flagged in plan self-review. Add a follow-up task only if user wants true spatial merge.

## User working preferences (from this session)
- Verify real data/assumptions before locking design; pivot honestly with numbers when reality differs (this earned explicit praise).
- Concise responses, comfortable with technical depth.
- Uses Exa MCP for search (not built-in web search).
- Global rules in CLAUDE.md: write spec before non-trivial features; ask before destructive actions; never touch `.env`.

## Open items (from plan §12, decide during impl)
- Project name: `locus` is a working name — verify PyPI/GitHub availability before first publish.
- Embedding model: default `BAAI/bge-small-en-v1.5` (384-dim, matches schema).
- Question `cid` → placeId resolution reliability (treat as preference-only if unreliable).
