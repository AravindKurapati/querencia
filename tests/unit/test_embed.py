from querencia.db import connect, init_schema
from querencia.embed import Embedder, LazyEmbedder, render_place, build_index
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


class _CountingFactory:
    """Stand-in for the Embedder constructor that records how often it runs."""

    def __init__(self):
        self.builds = 0

    def __call__(self):
        self.builds += 1
        return FakeEmbedder()


def test_lazy_embedder_defers_construction_until_encode():
    factory = _CountingFactory()
    emb = LazyEmbedder(factory=factory)
    # Constructing the wrapper must not build the underlying model.
    assert factory.builds == 0
    assert emb.loaded is False

    vec = emb.encode("hello")
    assert emb.loaded is True
    assert factory.builds == 1
    assert vec == FakeEmbedder().encode("hello")


def test_lazy_embedder_builds_underlying_model_only_once():
    factory = _CountingFactory()
    emb = LazyEmbedder(factory=factory)
    emb.encode("a")
    emb.encode("b")
    emb.encode("c")
    assert factory.builds == 1


def test_lazy_embedder_never_constructs_if_unused():
    factory = _CountingFactory()
    LazyEmbedder(factory=factory)
    assert factory.builds == 0


def test_lazy_embedder_is_drop_in_for_embedder():
    # Same advertised surface as the real Embedder, so callers can swap freely.
    assert LazyEmbedder.dim == Embedder.dim


def test_lazy_embedder_propagates_factory_errors():
    def boom():
        raise RuntimeError("model unavailable")

    emb = LazyEmbedder(factory=boom)
    # Failure must surface on first use, not be swallowed.
    try:
        emb.encode("x")
    except RuntimeError as exc:
        assert "model unavailable" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected RuntimeError from factory")
    assert emb.loaded is False
