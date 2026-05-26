import json
from pathlib import Path
from querencia.db import connect, init_schema
from querencia.ingest.photos import ingest_photo_sidecar

FIX = Path(__file__).parent.parent / "fixtures" / "photo_sidecar.json"


def test_photo_sidecar_creates_geo_place_and_photo(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ok = ingest_photo_sidecar(conn, json.loads(FIX.read_text()), "x.jpg")
    assert ok is True
    photo = conn.execute("SELECT place_key, media_type, taken_at FROM photos").fetchone()
    assert photo[0] == "geo:40.74357,-74.05123"
    assert photo[1] == "jpg"
    assert photo[2].startswith("2026-01-11")


def test_photo_without_geo_is_skipped(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ok = ingest_photo_sidecar(conn, {"creationTime": {"timestamp": "1768151101"}}, "y.jpg")
    assert ok is False
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 0
