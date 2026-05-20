import json
import re
import sqlite3

from ._util import geo_key, upsert_place

_HEX_ID = re.compile(r"!1s0x0:0x([0-9a-fA-F]+)")


def _place_key(props: dict, geom: dict) -> str:
    m = _HEX_ID.search(props.get("google_maps_url", ""))
    if m:
        return f"pid:{m.group(1)}"
    coords = (geom or {}).get("coordinates") or []
    if len(coords) == 2 and (coords[0] or coords[1]):
        return geo_key(coords[1], coords[0])  # GeoJSON is [lng, lat]
    return f"url:{props.get('google_maps_url', 'unknown')}"


def ingest_reviews(conn: sqlite3.Connection, data: dict) -> int:
    count = 0
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        loc = props.get("location") or {}
        coords = geom.get("coordinates") or [None, None]
        lat = coords[1] if len(coords) == 2 else None
        lng = coords[0] if len(coords) == 2 else None
        key = _place_key(props, geom)
        upsert_place(
            conn, key,
            lat=lat if lat else None, lng=lng if lng else None,
            name=loc.get("name"), category=props.get("category"),
            address=loc.get("address"),
            country_code=loc.get("country_code"), source="review",
        )
        qa = props.get("questions")
        conn.execute(
            "INSERT INTO reviews(place_key, rating, text, reviewed_at, structured_qa) "
            "VALUES (?,?,?,?,?)",
            (key, props.get("five_star_rating_published"),
             props.get("review_text_published"), props.get("date"),
             json.dumps(qa) if qa else None),
        )
        count += 1
    conn.commit()
    return count
