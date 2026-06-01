from querencia.db import connect, init_schema
from querencia.graph import build_graph, communities, expand_hops, pagerank
from querencia.ingest._util import upsert_place


def _conn(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    return conn


def _edge(conn, src, dst, mode="walk"):
    conn.execute(
        "INSERT OR IGNORE INTO transitions(from_place_key,to_place_key,travel_mode) "
        "VALUES (?,?,?)",
        (src, dst, mode),
    )


def test_empty_db_returns_empty_results(tmp_path):
    conn = _conn(tmp_path)
    assert build_graph(conn).number_of_nodes() == 0
    assert pagerank(conn) == []
    assert communities(conn) == []
    assert expand_hops(conn, ["pid:none"], hops=2) == {"pid:none"}


def test_linear_chain_has_one_community_and_ordered_pagerank(tmp_path):
    conn = _conn(tmp_path)
    for k in ("pid:a", "pid:b", "pid:c"):
        upsert_place(conn, k, name=k, source="commute")
    _edge(conn, "pid:a", "pid:b")
    _edge(conn, "pid:b", "pid:c")
    conn.commit()
    ranks = pagerank(conn, k=3)
    assert {r["place_key"] for r in ranks} == {"pid:a", "pid:b", "pid:c"}
    comms = communities(conn)
    assert len(comms) == 1
    assert set(comms[0]) == {"pid:a", "pid:b", "pid:c"}


def test_two_clusters_split_into_two_communities(tmp_path):
    conn = _conn(tmp_path)
    for k in ("pid:a", "pid:b", "pid:c", "pid:x", "pid:y", "pid:z"):
        upsert_place(conn, k, name=k, source="commute")
    for s, d in [("pid:a", "pid:b"), ("pid:b", "pid:c"), ("pid:c", "pid:a"),
                 ("pid:x", "pid:y"), ("pid:y", "pid:z"), ("pid:z", "pid:x")]:
        _edge(conn, s, d)
    conn.commit()
    comms = communities(conn)
    assert len(comms) == 2
    grouped = sorted([sorted(c) for c in comms])
    assert grouped == [["pid:a", "pid:b", "pid:c"], ["pid:x", "pid:y", "pid:z"]]


def test_expand_hops_respects_cutoff(tmp_path):
    conn = _conn(tmp_path)
    for k in ("pid:a", "pid:b", "pid:c", "pid:d"):
        upsert_place(conn, k, name=k, source="commute")
    _edge(conn, "pid:a", "pid:b")
    _edge(conn, "pid:b", "pid:c")
    _edge(conn, "pid:c", "pid:d")
    conn.commit()
    one_hop = expand_hops(conn, ["pid:a"], hops=1)
    assert one_hop == {"pid:a", "pid:b"}
    two_hop = expand_hops(conn, ["pid:a"], hops=2)
    assert two_hop == {"pid:a", "pid:b", "pid:c"}
