import json

from querencia.db import connect, init_schema
from querencia.export import build_snapshot, export_to_file
from querencia.ingest._util import upsert_place


def _seed(conn):
    for k, name, cat, cc, addr, lat, lng, rating, ts in [
        ("pid:a", "A", "cafe", "PT", "X, Lisbon, Portugal", 38.7, -9.1, 5, "2025-01-01T00:00:00Z"),
        ("pid:b", "B", "restaurant", "US", "Y, Brooklyn, USA", 40.7, -74.0, 4, "2025-02-01T00:00:00Z"),
        ("pid:c", "C", "cafe", "PT", "Z, Lisbon, Portugal", 38.71, -9.12, 5, "2025-03-01T00:00:00Z"),
    ]:
        upsert_place(conn, k, name=name, source="review")
        conn.execute("UPDATE places SET category=?, country_code=?, address=?, lat=?, lng=? "
                     "WHERE place_key=?", (cat, cc, addr, lat, lng, k))
        conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) VALUES (?,?,?,?)",
                     (k, rating, "great", ts))


def test_build_snapshot_shape(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn)
    snap = build_snapshot(conn)
    for key in ("generated_at", "summary", "places", "by_country", "by_category",
                "by_city", "rating_dist", "reviews_over_time", "taste_sentence"):
        assert key in snap
    assert snap["summary"]["place_count"] == 3
    assert sum(r["count"] for r in snap["by_country"]) == 3
    assert sum(snap["rating_dist"].values()) == 3


def test_export_to_file_writes_valid_json(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn)
    out = tmp_path / "out" / "data.json"
    export_to_file(conn, out)
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["summary"]["review_count"] == 3
    assert len(snap["places"]) == 3
