from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place
from querencia.mcp_server import _narrative_tool, _patterns_tool


def test_narrative_tool_returns_dict(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:a',5,'nice')")
    out = _narrative_tool(conn, theme="food")
    assert out["place_count"] == 1


def test_patterns_tool_returns_counts(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating) VALUES ('pid:a',5)")
    out = _patterns_tool(conn, kind="categories")
    assert out["cafe"] == 1
