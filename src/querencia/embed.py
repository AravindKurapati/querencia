import sqlite3


class Embedder:
    """Wraps sentence-transformers; only used in production, never in tests."""

    dim = 384

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)

    def encode(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()


class LazyEmbedder:
    """Defers building the underlying model until the first ``encode`` call.

    Constructing an :class:`Embedder` loads a ~130 MB sentence-transformers
    model (downloading it on first use). Some entry points — notably
    ``recommend`` — wire an embedder in unconditionally but only touch it when
    there are candidates to score; in the common no-API-key / no-candidate path
    they return early without ever encoding. Wrapping construction this way
    keeps that path fast and fully offline while staying a drop-in for
    :class:`Embedder` (same ``dim`` and ``encode`` surface).
    """

    dim = Embedder.dim

    def __init__(self, factory=Embedder):
        self._factory = factory
        self._delegate = None

    @property
    def loaded(self) -> bool:
        """True once the underlying embedder has been constructed."""
        return self._delegate is not None

    def encode(self, text: str) -> list[float]:
        if self._delegate is None:
            self._delegate = self._factory()
        return self._delegate.encode(text)


def render_place(conn: sqlite3.Connection, place_key: str) -> str:
    p = conn.execute(
        "SELECT canonical_name, category, address, country_code "
        "FROM places WHERE place_key=?", (place_key,)
    ).fetchone()
    name, category, address, cc = p or (None, None, None, None)
    parts = [name or "Unknown place"]
    if category:
        parts.append(f"({category})")
    if address:
        parts.append(address)
    for rating, text in conn.execute(
        "SELECT rating, text FROM reviews WHERE place_key=?", (place_key,)
    ):
        bit = f"rated {rating}/5" if rating else "reviewed"
        if text:
            bit += f": {text}"
        parts.append(bit)
    return " | ".join(parts)


def build_index(conn: sqlite3.Connection, embedder) -> int:
    keys = [r[0] for r in conn.execute("SELECT place_key FROM places")]
    conn.execute("DELETE FROM place_fts")
    conn.execute("DELETE FROM place_vec")
    for key in keys:
        text = render_place(conn, key)
        conn.execute(
            "INSERT INTO place_fts(place_key, rendered_text) VALUES (?,?)", (key, text)
        )
        vec = embedder.encode(text)
        conn.execute(
            "INSERT INTO place_vec(place_key, embedding) VALUES (?, vec_f32(?))",
            (key, f"[{','.join(str(x) for x in vec)}]"),
        )
    conn.commit()
    return len(keys)
