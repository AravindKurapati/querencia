import sqlite3

from ._util import geo_key, upsert_place


def ingest_commutes(conn: sqlite3.Connection, data: dict) -> int:
    count = 0
    for trip in data.get("trips", []):
        keys: dict[str, str] = {}
        for pv in trip.get("place_visit", []):
            place = pv.get("place") or {}
            ll = place.get("lat_lng") or {}
            lat, lng = ll.get("latitude"), ll.get("longitude")
            if lat is not None and lng is not None:
                k = geo_key(lat, lng)
                upsert_place(conn, k, lat=lat, lng=lng, source="commute")
            else:
                k = f"visit:{pv['id']}"
                upsert_place(conn, k, source="commute")
            keys[pv["id"]] = k
        for tr in trip.get("transition", []):
            o = (tr.get("origin") or {}).get("visit_id")
            d = (tr.get("destination") or {}).get("visit_id")
            mode = (tr.get("route") or {}).get("travel_mode", "UNKNOWN")
            if o in keys and d in keys:
                conn.execute(
                    "INSERT OR IGNORE INTO transitions"
                    "(from_place_key, to_place_key, travel_mode) VALUES (?,?,?)",
                    (keys[o], keys[d], mode),
                )
                count += 1
    conn.commit()
    return count
