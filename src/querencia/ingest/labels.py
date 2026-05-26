import sqlite3

from ._util import geo_key, upsert_place


def ingest_labels(conn: sqlite3.Connection, data: dict) -> int:
    count = 0
    for feat in data.get("features", []):
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        if len(coords) != 2:
            continue
        props = feat.get("properties", {})
        key = geo_key(coords[1], coords[0])
        upsert_place(conn, key, lat=coords[1], lng=coords[0],
                     name=props.get("name"), address=props.get("address"),
                     source="label")
        count += 1
    conn.commit()
    return count
