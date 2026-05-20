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
