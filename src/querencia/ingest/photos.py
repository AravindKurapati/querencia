import sqlite3
from datetime import datetime, timezone

from ._util import geo_key, upsert_place


def _media_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in {"jpg", "jpeg", "mp4", "png"} else "other"


def ingest_photo_sidecar(conn: sqlite3.Connection, data: dict, filename: str) -> bool:
    geo = data.get("geoDataExif") or {}
    lat, lng = geo.get("latitude"), geo.get("longitude")
    if not lat or not lng:  # (0,0) and missing both count as no-geo
        return False
    ts = (data.get("creationTime") or {}).get("timestamp")
    if not ts:
        return False
    taken_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    key = geo_key(lat, lng)
    upsert_place(conn, key, lat=lat, lng=lng, source="photo")
    conn.execute(
        "INSERT INTO photos(place_key, taken_at, lat, lng, media_type) VALUES (?,?,?,?,?)",
        (key, taken_at, lat, lng, _media_type(filename)),
    )
    conn.commit()
    return True
