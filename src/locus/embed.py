import sqlite3


class Embedder:
    """Wraps sentence-transformers; only used in production, never in tests."""

    dim = 384

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)

    def encode(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()


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
