from locus.db import connect, init_schema
from locus.enrich import enrich_places
from locus.ingest._util import upsert_place


class FakeClient:
    def reverse_geocode(self, lat, lng):
        return {"name": "Found Cafe", "category": "cafe", "address": "1 St"}


def test_enrich_fills_unenriched_geo_place(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "geo:40.74357,-74.05123", lat=40.74357, lng=-74.05123, source="photo")
    n = enrich_places(conn, FakeClient())
    assert n == 1
    row = conn.execute(
        "SELECT canonical_name, category, enriched_at FROM places"
    ).fetchone()
    assert row[0] == "Found Cafe"
    assert row[1] == "cafe"
    assert row[2] is not None


def test_enrich_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "geo:1.0,2.0", lat=1.0, lng=2.0, source="photo")
    enrich_places(conn, FakeClient())
    assert enrich_places(conn, FakeClient()) == 0  # already enriched


def test_enrich_respects_max_calls(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "geo:1.0,2.0", lat=1.0, lng=2.0, source="photo")
    upsert_place(conn, "geo:3.0,4.0", lat=3.0, lng=4.0, source="photo")
    assert enrich_places(conn, FakeClient(), max_calls=1) == 1
