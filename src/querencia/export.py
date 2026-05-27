import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import query


def build_snapshot(conn: sqlite3.Connection) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": query.summary(conn),
        "places": query.places_for_map(conn),
        "by_country": query.by_country(conn),
        "by_category": query.by_category(conn),
        "by_city": query.by_city(conn),
        "rating_dist": query.rating_distribution(conn),
        "reviews_over_time": query.reviews_over_time(conn),
        "taste_sentence": query.taste_sentence(conn),
    }


def export_to_file(conn: sqlite3.Connection, out_path: str | Path) -> dict:
    snap = build_snapshot(conn)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return snap
