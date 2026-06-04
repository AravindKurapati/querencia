import io, json, zipfile
from pathlib import Path
from querencia.db import connect, init_schema
from querencia.ingest import run_all

FIX = Path(__file__).parent.parent / "fixtures"


def _make_zip(tmp_path):
    zpath = tmp_path / "takeout.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Takeout/Maps (your places)/Reviews.json",
                   (FIX / "reviews.json").read_text(encoding="utf-8"))
        z.writestr("Takeout/Maps/Photos and videos/2026-01-11-x.jpg.json",
                   (FIX / "photo_sidecar.json").read_text())
    return zpath


def test_run_all_populates_db(tmp_path):
    zpath = _make_zip(tmp_path)
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    summary = run_all(conn, zpath)
    assert summary["reviews"] == 2
    assert summary["photos"] == 1
    assert conn.execute("SELECT COUNT(*) FROM places").fetchone()[0] >= 2


def _make_full_zip(tmp_path):
    """A Takeout zip exercising every source-type prefix `run_all` routes on,
    including multiple files per directory (photos/questions/labels/commutes)."""
    zpath = tmp_path / "full.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Takeout/Maps (your places)/Reviews.json",
                   (FIX / "reviews.json").read_text(encoding="utf-8"))
        z.writestr("Takeout/Maps/Photos and videos/2026-01-11-x.jpg.json",
                   (FIX / "photo_sidecar.json").read_text())
        # Two answered questions (one resolvable CID, one without -> skipped).
        z.writestr("Takeout/Maps/Answers to automated questions/q1.json",
                   json.dumps({"placeUrl": "https://www.google.com/maps?cid=0x0:0x1a2b"}))
        z.writestr("Takeout/Maps/Answers to automated questions/q2.json",
                   json.dumps({"placeUrl": "https://www.google.com/maps?q=no-cid"}))
        # Labeled places.
        z.writestr("Takeout/Maps/My labeled places/Labeled places.json",
                   json.dumps({"features": [
                       {"geometry": {"coordinates": [-9.139, 38.722]},
                        "properties": {"name": "Home", "address": "Rua A, Lisbon"}},
                   ]}))
        # Commute route with a single transition.
        z.writestr("Takeout/Maps/Commute routes/routes.json",
                   json.dumps({"trips": [{
                       "place_visit": [
                           {"id": "v1", "place": {"lat_lng": {"latitude": 38.7, "longitude": -9.1}}},
                           {"id": "v2", "place": {"lat_lng": {"latitude": 38.8, "longitude": -9.2}}},
                       ],
                       "transition": [{"origin": {"visit_id": "v1"},
                                       "destination": {"visit_id": "v2"},
                                       "route": {"travel_mode": "DRIVE"}}],
                   }]}))
    return zpath


def test_run_all_routes_every_source_type(tmp_path):
    zpath = _make_full_zip(tmp_path)
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    summary = run_all(conn, zpath)

    assert summary == {
        "reviews": 2, "photos": 1, "questions": 1, "labels": 1, "commutes": 1,
    }
    # Each source materialized its own rows.
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM transitions").fetchone()[0] == 1
    assert conn.execute(
        "SELECT travel_mode FROM transitions"
    ).fetchone()[0] == "DRIVE"
    # The labeled place carried its name through.
    assert conn.execute(
        "SELECT canonical_name FROM places WHERE place_key='geo:38.72200,-9.13900'"
    ).fetchone()[0] == "Home"
    # The CID-bearing question created a cid: place; the no-CID one did not.
    cid_places = conn.execute(
        "SELECT COUNT(*) FROM places WHERE place_key LIKE 'cid:%'"
    ).fetchone()[0]
    assert cid_places == 1


def test_run_all_tolerates_missing_optional_sources(tmp_path):
    # Only a Reviews.json present -> other routes are simply skipped, no crash.
    zpath = tmp_path / "reviews_only.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Takeout/Maps (your places)/Reviews.json",
                   (FIX / "reviews.json").read_text(encoding="utf-8"))
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    summary = run_all(conn, zpath)
    assert summary == {
        "reviews": 2, "photos": 0, "questions": 0, "labels": 0, "commutes": 0,
    }
