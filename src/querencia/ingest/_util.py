import json as _json
import sqlite3
import zipfile
from pathlib import Path


def geo_key(lat: float, lng: float) -> str:
    return f"geo:{lat:.5f},{lng:.5f}"


def upsert_place(
    conn: sqlite3.Connection,
    place_key: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    name: str | None = None,
    category: str | None = None,
    address: str | None = None,
    country_code: str | None = None,
    source: str | None = None,
) -> None:
    row = conn.execute(
        "SELECT source_flags FROM places WHERE place_key=?", (place_key,)
    ).fetchone()
    if row is None:
        flags = {source} if source else set()
        conn.execute(
            "INSERT INTO places(place_key, lat, lng, canonical_name, category, address, "
            "country_code, source_flags) VALUES (?,?,?,?,?,?,?,?)",
            (place_key, lat, lng, name, category, address, country_code,
             ",".join(sorted(flags))),
        )
    else:
        flags = set(filter(None, (row[0] or "").split(",")))
        if source:
            flags.add(source)
        conn.execute(
            "UPDATE places SET "
            "lat=COALESCE(lat,?), lng=COALESCE(lng,?), "
            "canonical_name=COALESCE(canonical_name,?), "
            "category=COALESCE(category,?), "
            "address=COALESCE(address,?), country_code=COALESCE(country_code,?), "
            "source_flags=? WHERE place_key=?",
            (lat, lng, name, category, address, country_code,
             ",".join(sorted(flags)), place_key),
        )


def read_zip_json(zf: zipfile.ZipFile, name: str) -> dict | None:
    try:
        with zf.open(name) as f:
            return _json.loads(f.read().decode("utf-8"))
    except KeyError:
        return None


def iter_zip_jsons(zf: zipfile.ZipFile, prefix: str):
    for info in zf.infolist():
        if info.filename.startswith(prefix) and info.filename.endswith(".json"):
            with zf.open(info) as f:
                yield info.filename, _json.loads(f.read().decode("utf-8"))
