import zipfile
from pathlib import Path
from click.testing import CliRunner
from querencia.cli import cli

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


def test_cli_story_prose_falls_back_to_json_when_key_blank(tmp_path, monkeypatch):
    # The prose path (no --json) builds an Anthropic client. A blank
    # ANTHROPIC_API_KEY (the common .env / CI footgun) must degrade to the
    # grounded JSON, exactly as an unset key does -- not crash.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    db = tmp_path / "t.db"
    zp = _zip(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["--db", str(db), "ingest", str(zp)]).exit_code == 0
    r = runner.invoke(cli, ["--db", str(db), "story"])  # prose path, no --json
    assert r.exit_code == 0, r.output
    assert "place_count" in r.output  # fell back to grounded JSON, no crash
