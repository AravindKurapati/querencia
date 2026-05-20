import json
from pathlib import Path
from querencia.db import connect, init_schema
from querencia.ingest.reviews import ingest_reviews

FIX = Path(__file__).parent.parent / "fixtures" / "reviews.json"


def test_ingest_reviews_creates_place_and_review(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    n = ingest_reviews(conn, json.loads(FIX.read_text(encoding="utf-8")))
    assert n == 2
    places = conn.execute("SELECT place_key, canonical_name FROM places").fetchall()
    keys = {p[0] for p in places}
    assert any(k.startswith("pid:") for k in keys)
    r = conn.execute("SELECT rating, text FROM reviews WHERE text='Great dosa'").fetchone()
    assert r == (5, "Great dosa")


def test_locationless_review_uses_url_id_key(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ingest_reviews(conn, json.loads(FIX.read_text(encoding="utf-8")))
    noloc = conn.execute("SELECT rating FROM reviews WHERE rating=3").fetchone()
    assert noloc[0] == 3
