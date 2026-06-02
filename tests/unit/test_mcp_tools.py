from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place
from querencia.mcp_server import (
    _narrative_tool, _patterns_tool, _recommend_tool, _trips_tool, mcp,
)


def test_narrative_tool_returns_dict(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:a',5,'nice')")
    out = _narrative_tool(conn, theme="food")
    assert out["place_count"] == 1


def test_narrative_tool_scopes_to_trip(tmp_path):
    # RECIPES.md Recipe 1 calls querencia_narrative(trip_id=N) after querencia_trips;
    # the MCP narrative tool must accept and honor trip_id, not just theme/year.
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    # Two reviewed places; only one belongs to the trip.
    upsert_place(conn, "pid:in", name="On Trip", source="review")
    upsert_place(conn, "pid:out", name="Off Trip", source="review")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:in',5,'a')")
    conn.execute("INSERT INTO reviews(place_key,rating,text) VALUES ('pid:out',5,'b')")
    conn.execute("INSERT INTO trips(trip_id,place_count) VALUES (7,1)")
    conn.execute("INSERT INTO trip_places(trip_id,place_key) VALUES (7,'pid:in')")
    conn.commit()

    scoped = _narrative_tool(conn, trip_id=7)
    assert scoped["trip_id"] == 7
    assert scoped["place_count"] == 1
    assert {p["name"] for p in scoped["top_rated"]} == {"On Trip"}

    # Unscoped still sees both, proving the filter is what narrowed it.
    assert _narrative_tool(conn)["place_count"] == 2


def test_narrative_mcp_tool_exposes_trip_id():
    # The registered MCP tool's schema must advertise trip_id so clients can call it.
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    narrative = next(t for t in tools if t.name == "querencia_narrative")
    assert "trip_id" in narrative.inputSchema.get("properties", {})


def test_patterns_tool_returns_counts(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating) VALUES ('pid:a',5)")
    out = _patterns_tool(conn, kind="categories")
    assert out["cafe"] == 1


def test_trips_tool_materializes_on_first_call(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    for i in range(6):
        upsert_place(conn, f"pid:home{i}", name=f"home{i}",
                     lat=40.71, lng=-74.00, source="review")
        conn.execute("UPDATE places SET country_code='US' WHERE place_key=?",
                     (f"pid:home{i}",))
        conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                     "VALUES (?,5,'x',?)",
                     (f"pid:home{i}", f"2023-01-{i+1:02d}T12:00:00Z"))
    for i, lng in enumerate([23.72, 23.73, 23.74]):
        upsert_place(conn, f"pid:gr{i}", name=f"gr{i}",
                     lat=37.98, lng=lng, source="review")
        conn.execute("UPDATE places SET country_code='GR' WHERE place_key=?",
                     (f"pid:gr{i}",))
        conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                     "VALUES (?,5,'x',?)",
                     (f"pid:gr{i}", f"2023-06-1{i}T12:00:00Z"))
    conn.commit()
    out = _trips_tool(conn)
    assert len(out) == 1
    assert out[0]["country_code"] == "GR"


def test_recommend_tool_returns_list(tmp_path):
    # No API key + no candidates => empty list, no crash.
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Cafe", source="review")
    conn.execute("UPDATE places SET category='cafe' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key,rating) VALUES ('pid:a',5)")
    out = _recommend_tool(conn, "Rome", top=3)
    assert isinstance(out, list)


def test_mcp_registry_contains_new_tools():
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert "querencia_trips" in names
    assert "querencia_recommend" in names
