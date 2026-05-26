from querencia.db import connect, init_schema
from querencia.embed import render_place, build_index
from querencia.ingest._util import upsert_place


class FakeEmbedder:
    dim = 384
    def encode(self, text: str) -> list[float]:
        return [float(len(text) % 7)] * 384


def test_render_place_includes_name_and_reviews(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="Balaji Bhavan", source="review")
    conn.execute("UPDATE places SET category='restaurant' WHERE place_key='pid:a'")
    conn.execute("INSERT INTO reviews(place_key, rating, text) VALUES ('pid:a',5,'Great dosa')")
    text = render_place(conn, "pid:a")
    assert "Balaji Bhavan" in text
    assert "Great dosa" in text
    assert "restaurant" in text


def test_build_index_populates_fts_and_vec(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    upsert_place(conn, "pid:a", name="X", source="review")
    n = build_index(conn, FakeEmbedder())
    assert n == 1
    assert conn.execute("SELECT COUNT(*) FROM place_fts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM place_vec").fetchone()[0] == 1
