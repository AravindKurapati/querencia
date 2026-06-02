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


def test_recall_expand_hops_pulls_in_graph_neighbors(tmp_path):
    # GraphRAG-style expansion (README `--hops`): a single vector hit should
    # pull in places reachable over the transition graph, flagged via graph_hop.
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    # pid:a (the dosa hit) leads to pid:b over a transition edge.
    conn.execute(
        "INSERT INTO transitions(from_place_key,to_place_key,travel_mode) "
        "VALUES ('pid:a','pid:b','walking')"
    )
    conn.commit()

    base = recall(conn, "dosa", FakeEmbedder(), k=1)
    assert [r["place_key"] for r in base] == ["pid:a"]

    expanded = recall(conn, "dosa", FakeEmbedder(), k=1, expand_hops=1)
    keys = {r["place_key"] for r in expanded}
    # Direct hit stays first; the transition neighbor is now included.
    assert expanded[0]["place_key"] == "pid:a"
    assert "pid:b" in keys
    hopped = [r for r in expanded if r["place_key"] == "pid:b"]
    assert hopped and hopped[0]["via"] == "graph_hop"
    assert hopped[0]["distance"] is None


def test_recall_expand_hops_zero_matches_plain_recall(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    conn.execute(
        "INSERT INTO transitions(from_place_key,to_place_key,travel_mode) "
        "VALUES ('pid:a','pid:b','walking')"
    )
    conn.commit()
    plain = recall(conn, "dosa", FakeEmbedder(), k=1)
    zero = recall(conn, "dosa", FakeEmbedder(), k=1, expand_hops=0)
    assert [r["place_key"] for r in plain] == [r["place_key"] for r in zero]
    assert all("via" not in r for r in zero)
