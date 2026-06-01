# FEATURE: Trip detection (spatiotemporal episodes)

Group visits/reviews/photos into *trips* — the natural narrative unit of personal place
data. A trip is a contiguous period of activity in a place far from the user's normal
center of mass.

## Why
Today every review is an isolated row. Reality: you go to Athens for 5 days, eat 8 meals,
write 3 reviews. Story/taste/ask all get qualitatively better when they can scope to a
trip. It's also the missing primitive for every downstream feature in this PR series.

## Approach
DBSCAN-style clustering on (lat, lng, time):
- Compute the user's home cluster (largest by point count) and exclude points inside its
  radius from trip candidates.
- For the rest, cluster with `(haversine distance ≤ R_km) AND (time gap ≤ T_days)` — implemented
  as a connected-components pass since real DBSCAN over haversine in sklearn needs ball-tree
  setup that's overkill here.
- A cluster with ≥ MIN_PTS points becomes a trip.

Defaults (overridable): `R_km=50`, `T_days=3`, `MIN_PTS=3`, home radius = 30 km.

## Scope
1. `querencia.trips` module
   - `detect_trips(conn, *, r_km=50, t_days=3, min_pts=3) -> list[Trip]` — pure-Python, no
     sklearn dependency added.
   - `materialize_trips(conn)` — runs detection and writes to the `trips` table.
   - Trip dataclass: `id, start, end, country, lead_category, place_count, place_keys`.

2. Schema additions (SCHEMA.md update required):
   ```sql
   CREATE TABLE trips(
     trip_id INTEGER PRIMARY KEY,
     started_at TIMESTAMP, ended_at TIMESTAMP,
     country_code TEXT, lead_category TEXT,
     place_count INTEGER, lat REAL, lng REAL
   );
   CREATE TABLE trip_places(
     trip_id INTEGER REFERENCES trips(trip_id),
     place_key TEXT REFERENCES places(place_key),
     PRIMARY KEY(trip_id, place_key)
   );
   ```

3. CLI
   - `querencia trips` — JSON list of detected trips.
   - `querencia trips --rebuild` — force re-detection (clears and re-populates).
   - `querencia story --trip N` — narrative scoped to one trip's places.

4. Tests
   - empty DB → no trips.
   - three close-by visits within 2 days in a foreign country → one trip.
   - same country, far apart in time → separate trips.
   - points inside home radius → excluded.

## Out of scope
- Per-trip prose generation (handled by existing `narrative` + `synth_llm` once scoped).
- Cross-trip similarity / "trip taste profile".
- User-named trips.

## Risk
Low. Read-derived → write to dedicated tables. Idempotent via `--rebuild`. No external
calls.
