import zipfile
from pathlib import Path
from click.testing import CliRunner
from locus.cli import cli

FIX = Path(__file__).parent.parent / "fixtures"


def _zip(tmp_path):
    zp = tmp_path / "t.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("Takeout/Maps (your places)/Reviews.json",
                   (FIX / "reviews.json").read_text(encoding="utf-8"))
    return zp


def test_cli_ingest_then_story_json(tmp_path):
    db = tmp_path / "t.db"
    zp = _zip(tmp_path)
    runner = CliRunner()
    r1 = runner.invoke(cli, ["--db", str(db), "ingest", str(zp)])
    assert r1.exit_code == 0, r1.output
    assert "reviews: 2" in r1.output
    r2 = runner.invoke(cli, ["--db", str(db), "story", "--json"])
    assert r2.exit_code == 0, r2.output
    assert "place_count" in r2.output
