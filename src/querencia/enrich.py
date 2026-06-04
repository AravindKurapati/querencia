import sqlite3
from datetime import datetime, timezone


class GoogleClient:
    """Thin wrapper over googlemaps; only used in production, never in tests."""

    def __init__(self, api_key: str | None = None):
        from ._keys import require_env_key
        key = require_env_key("GOOGLE_PLACES_API_KEY", api_key)
        import googlemaps
        self._gm = googlemaps.Client(key=key)

    def reverse_geocode(self, lat: float, lng: float) -> dict | None:
        res = self._gm.reverse_geocode((lat, lng))
        if not res:
            return None
        top = res[0]
        types = top.get("types", [])
        return {
            "name": top.get("formatted_address", "").split(",")[0],
            "category": types[0] if types else None,
            "address": top.get("formatted_address"),
        }


def enrich_places(conn: sqlite3.Connection, client, max_calls: int | None = None) -> int:
    rows = conn.execute(
        "SELECT place_key, lat, lng FROM places "
        "WHERE enriched_at IS NULL AND lat IS NOT NULL AND lng IS NOT NULL"
    ).fetchall()
    calls = 0
    for key, lat, lng in rows:
        if max_calls is not None and calls >= max_calls:
            break
        info = client.reverse_geocode(lat, lng)
        calls += 1
        now = datetime.now(timezone.utc).isoformat()
        if info:
            conn.execute(
                "UPDATE places SET canonical_name=COALESCE(canonical_name,?), "
                "category=COALESCE(category,?), address=COALESCE(address,?), "
                "enriched_at=? WHERE place_key=?",
                (info.get("name"), info.get("category"), info.get("address"), now, key),
            )
        else:
            conn.execute("UPDATE places SET enriched_at=? WHERE place_key=?", (now, key))
    conn.commit()
    return calls
