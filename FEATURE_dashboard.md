# FEATURE: web dashboard (`web/`)

A static React + Vite dashboard for visually browsing one's querencia. Local-first: reads a JSON snapshot exported by the CLI, no server, no live DB connection. Deployable as static files (GitHub Pages, Vercel, or just `npx serve`).

This adds a **fourth surface** alongside lib / CLI / MCP. Updates `CLAUDE.md` to remove the "no web UI" gotcha.

## Why

Hero demos (`story`, `ask`, `taste`) are powerful but text-only. A visual surface makes the portfolio piece scannable in 10 seconds for a recruiter who won't run a CLI. Map-hero editorial layout chosen (see brainstorm). Keeps local-first ethos: the data is your reviews, on your disk, rendered locally.

## Surfaces unchanged

Python library, click CLI, MCP server — all untouched. The dashboard is purely additive and consumes a JSON file.

## Data flow

```
SQLite -> `querencia export --json` -> web/public/data.json -> React app
```

Re-export when ingest/embed changes. No live connection.

## Database impact

None. No schema changes. Read-only consumer of existing tables.

## New CLI command: `querencia export`

```
querencia [--db PATH] export --out web/public/data.json
```

Produces a single JSON document with the shape below. Pure aggregation over existing query helpers; no new SQL beyond what's already in `query.py` plus a few small additions in `query.py` (see "New query functions").

### JSON shape (`data.json`)

```jsonc
{
  "generated_at": "2026-05-26T12:00:00Z",
  "summary": {
    "place_count": 87,
    "review_count": 92,
    "photo_count": 1043,
    "country_count": 5,
    "avg_rating": 4.21,
    "first_review_at": "2019-03-12",
    "last_review_at": "2026-04-30"
  },
  "places": [
    {
      "place_key": "pid:abc...",
      "name": "...",
      "category": "cafe",
      "country_code": "PT",
      "lat": 38.71, "lng": -9.14,
      "review_count": 2,
      "avg_rating": 4.5,
      "sample_text": "...truncated 240 chars..."
    }
  ],
  "by_country": [{ "country_code": "PT", "count": 22, "avg_rating": 4.3 }],
  "by_category": [{ "category": "cafe", "count": 18, "avg_rating": 4.4 }],
  "by_city":     [{ "city": "Lisbon",  "count": 22, "avg_rating": 4.3 }],
  "rating_dist": { "1": 0, "2": 1, "3": 5, "4": 38, "5": 48 },
  "reviews_over_time": [{ "month": "2025-04", "count": 6 }],
  "taste_sentence": "You rate cafes 0.4 stars higher than restaurants, and your top cuisine across cities is South Indian."
}
```

`taste_sentence` is a deterministic, templated string (no LLM) so the dashboard works offline. If `ANTHROPIC_API_KEY` is set, `export` may overwrite it with a synthesized version (out of scope for v1 of this feature; deterministic only).

### New query functions in `query.py`

- `summary(conn) -> dict` — counts + min/max review dates + avg rating
- `by_country(conn) -> list[dict]`
- `by_city(conn) -> list[dict]` (uses `address` LIKE-based city extraction; tolerated rough)
- `rating_distribution(conn) -> dict[int, int]`
- `reviews_over_time(conn) -> list[dict]` (monthly buckets)
- `places_for_map(conn) -> list[dict]` (lat/lng + agg per place)
- `taste_sentence(conn) -> str` (template)

Existing `patterns(kind="categories")` already covers `by_category` essentially; wrap to add avg rating.

## React app (`web/`)

### Stack

- Vite + React 18 (matches `Port/personal-site/`)
- TypeScript
- Tailwind CSS
- Recharts (rating dist, cuisine bars, timeline)
- MapLibre GL JS + maplibre-react-components for the map (free tiles via Carto/OpenFreeMap, no Mapbox token needed)
- No router for v1 — single page

### Component tree

```
App
+- Header        ("querencia", nav links, generated_at)
+- MapHero       (MapLibre map with clustered pins per place)
+- StatStrip     ("87 places . 5 countries . avg 4.2 stars")
+- TasteCard     (taste_sentence + rating-dist + cuisine-bars charts side by side)
+- CountrySection   (per-country mini cards with count and avg)
+- TimelineSection  (reviews-over-time line chart)
+- TopPlacesList    (top 10 by rating, name + category + country + 240-char text)
+- Footer        (built locally, source link)
```

### Layout (map-hero editorial, mockup approved)

```
+---------------------------+
| Header                    |
+---------------------------+
| MapHero (60vh)            |
+---------------------------+
| StatStrip (sticky-ish)    |
+---------------------------+
| TasteCard                 |
+---------------------------+
| CountrySection            |
+---------------------------+
| TimelineSection           |
+---------------------------+
| TopPlacesList             |
+---------------------------+
| Footer                    |
+---------------------------+
```

### Data loading

`data.json` placed in `web/public/`, fetched once at app start, stored in a React context. If missing, show a friendly "run `querencia export` first" empty state with a copyable command.

## File additions

```
web/
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  index.html
  public/
    data.json           (gitignored except a small sample)
    data.sample.json    (checked-in, synthetic, for portfolio viewers)
  src/
    main.tsx
    App.tsx
    types.ts
    data.ts             (loader + types)
    components/
      Header.tsx
      MapHero.tsx
      StatStrip.tsx
      TasteCard.tsx
      CountrySection.tsx
      TimelineSection.tsx
      TopPlacesList.tsx
      Footer.tsx
    charts/
      RatingDistBar.tsx
      CuisineBars.tsx
      TimelineLine.tsx
```

Plus:
- `src/querencia/export.py` (new module — JSON serialization)
- `src/querencia/query.py` (additions listed above)
- `src/querencia/cli.py` (new `export` subcommand)
- `tests/test_export.py` (unit test on synthetic DB)
- `tests/test_query_aggregates.py` (unit tests for new query helpers)

## Gitignore additions

```
web/node_modules
web/dist
web/public/data.json     # real data, never committed
```

`data.sample.json` IS committed — it's synthetic, generated from `examples/build_synthetic.py`.

## CLAUDE.md update

Remove this gotcha:

> **No web UI**: CLI + MCP are the only surfaces by design. Don't scaffold one.

Replace with:

> **Web dashboard**: `web/` is a Vite + React 18 + Tailwind static dashboard reading `web/public/data.json`. Run `querencia export --out web/public/data.json` to refresh. The map uses MapLibre with free Carto tiles (no API key). `data.json` is gitignored; `data.sample.json` (synthetic) is checked in for portfolio viewers.

## Tests

- `test_export.py`: synthetic DB -> `export()` -> assert JSON has all required top-level keys, place_count matches, by_country sums to place_count, rating_dist sums to review_count.
- `test_query_aggregates.py`: one test per new query helper.
- React: no test framework in v1 (matches `Port/personal-site/`). Manual verification only.

## Out of scope for v1 of this feature

- Live filters (city/category toggles) — punt to v2
- Search box wired to `recall` — punt to v2 (would need a server)
- LLM-synthesized `taste_sentence` — deterministic template only in v1
- Per-place detail modal — TopPlacesList shows inline text only

## Deployment

`cd web && npm run build` produces `web/dist/`. Drop into GitHub Pages or Vercel. For portfolio, deploy with `data.sample.json` renamed to `data.json` so visitors see synthetic-but-realistic content.

## Implementation order

1. New `query.py` helpers + tests
2. `export.py` + `cli.py` `export` subcommand + test
3. Run export against synthetic DB, sanity-check JSON
4. Vite scaffold under `web/`, Tailwind config, data loader
5. Build components in order: Header, StatStrip, MapHero, TopPlacesList, TasteCard, charts, CountrySection, TimelineSection, Footer
6. Style pass: editorial typography (serif headline, sans body), generous whitespace
7. `CLAUDE.md` update, `.gitignore` update, `data.sample.json` checked in
8. Manual browser verification
9. PR
