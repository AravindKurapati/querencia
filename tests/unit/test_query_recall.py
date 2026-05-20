from querencia.db import connect, init_schema
from querencia.embed import build_index
from querencia.ingest._util import upsert_place
from querencia.query import recall


class FakeEmbedder:
    dim = 384
    def encode(self, text):
        # "dosa" places get vector A, others vector B
        return [1.0]*384 if "dosa" in text.lower() else [0.0]*384


def _seed(conn):
    upsert_place(conn, "pid:a", name="Balaji Bhavan", source="review")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:a',5,'best dosa')")
    upsert_place(conn, "pid:b", name="Pizza Place", source="review")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:b',4,'good pizza')")
    build_index(conn, FakeEmbedder())


def test_recall_ranks_semantic_match_first(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    results = recall(conn, "dosa", FakeEmbedder(), k=2)
    assert results[0]["place_key"] == "pid:a"
    assert results[0]["name"] == "Balaji Bhavan"
