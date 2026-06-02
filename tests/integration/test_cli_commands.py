"""CLI coverage for the embedder-free commands.

`taste`, `trips`, `graph` (incl. `--viz`) and the no-API-key fallbacks of
`story`/`enrich` need neither a sentence-transformers model nor an external
service, so they can be driven end-to-end offline. The embedder-backed
commands (`embed`, `ask`, `recommend`) are exercised at the library layer
with fakes instead — see test_embed.py / test_taste.py / test_query_recall.py.
"""
import json
from pathlib import Path

from click.testing import CliRunner

from querencia.cli import cli
from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place


def _seed_db(path: Path) -> None:
    """Six home reviews (NYC) plus a three-place foreign trip (Athens)."""
    conn = connect(path)
    init_schema(conn)
    for i in range(6):
        key = f"pid:home{i}"
        upsert_place(conn, key, name=f"Home {i}", lat=40.71, lng=-74.00, source="review")
        conn.execute(
            "UPDATE places SET category='cafe', country_code='US' WHERE place_key=?", (key,)
        )
        conn.execute(
            "INSERT INTO reviews(place_key,rating,text,reviewed_at) VALUES (?,?,?,?)",
            (key, 4, "local spot", f"2023-01-{i + 1:02d}T12:00:00Z"),
        )
    for i, lng in enumerate([23.72, 23.73, 23.74]):
        key = f"pid:gr{i}"
        upsert_place(conn, key, name=f"Athens {i}", lat=37.98, lng=lng, source="review")
        conn.execute(
            "UPDATE places SET category='restaurant', country_code='GR' WHERE place_key=?",
            (key,),
        )
        conn.execute(
            "INSERT INTO reviews(place_key,rating,text,reviewed_at) VALUES (?,?,?,?)",
            (key, 5, "amazing", f"2023-06-1{i}T12:00:00Z"),
        )
    conn.commit()
    conn.close()


def _run(tmp_path, *args):
    db = tmp_path / "t.db"
    if not db.exists():
        _seed_db(db)
    return CliRunner().invoke(cli, ["--db", str(db), *args])


def test_cli_taste_outputs_profile(tmp_path):
    r = _run(tmp_path, "taste", "Lisbon")
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["city"] == "Lisbon"
    assert set(data["top_categories"]) == {"cafe", "restaurant"}
    assert data["avg_rating"] > 0


def test_cli_trips_detects_foreign_cluster(tmp_path):
    r = _run(tmp_path, "trips")
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    # First invocation materializes, so the wrapper reports the detection count.
    assert data["detected"] == 1
    assert data["trips"][0]["country_code"] == "GR"
    assert data["trips"][0]["place_count"] == 3


def test_cli_trips_second_call_reads_stored(tmp_path):
    db = tmp_path / "t.db"
    _seed_db(db)
    runner = CliRunner()
    first = runner.invoke(cli, ["--db", str(db), "trips"])
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli, ["--db", str(db), "trips"])
    assert second.exit_code == 0, second.output
    # Without --rebuild the stored trips are returned as a bare list, not the
    # {"detected": ...} envelope.
    stored = json.loads(second.output)
    assert isinstance(stored, list)
    assert stored[0]["country_code"] == "GR"


def test_cli_graph_reports_nodes_and_edges(tmp_path):
    r = _run(tmp_path, "graph")
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["node_count"] == 9
    # Co-visit derived edges link reviews within 24h, so the graph is non-empty.
    assert data["edge_count"] > 0
    assert {p["place_key"] for p in data["pagerank"]}
    assert isinstance(data["communities"], list)


def test_cli_graph_no_derived_drops_edges(tmp_path):
    # No transitions seeded, so disabling derived edges leaves an edgeless graph.
    r = _run(tmp_path, "graph", "--no-derived")
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["node_count"] == 9
    assert data["edge_count"] == 0


def test_cli_graph_viz_writes_html(tmp_path):
    out = tmp_path / "graph.html"
    r = _run(tmp_path, "graph", "--viz", str(out))
    assert r.exit_code == 0, r.output
    assert f"wrote: {out}" in r.output
    assert out.exists() and out.stat().st_size > 0


def test_cli_story_falls_back_to_json_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = _run(tmp_path, "story", "--theme", "food")
    assert r.exit_code == 0, r.output
    # No key => the prose path raises KeyError and we emit the grounded JSON.
    data = json.loads(r.output)
    assert data["theme"] == "food"
    # Every seeded place is a cafe or restaurant, both of which are food categories.
    assert data["place_count"] == 9


def test_cli_enrich_without_api_key_is_graceful(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    r = _run(tmp_path, "enrich")
    assert r.exit_code == 0, r.output
    assert "GOOGLE_PLACES_API_KEY not set" in r.output
