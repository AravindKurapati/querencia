from locus.ingest._util import geo_key, upsert_place
from locus.db import connect, init_schema


def test_geo_key_rounds_to_5dp():
    assert geo_key(40.7435693, -74.0512251) == "geo:40.74357,-74.05123"


def test_upsert_place_merges_source_flags(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", lat=1.0, lng=2.0, name="X", source="review")
    upsert_place(conn, "pid:a", source="photo")
    row = conn.execute(
        "SELECT canonical_name, source_flags FROM places WHERE place_key='pid:a'"
    ).fetchone()
    assert row[0] == "X"
    assert set(row[1].split(",")) == {"review", "photo"}
