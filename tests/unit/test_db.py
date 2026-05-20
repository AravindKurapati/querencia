from locus.db import connect, init_schema


def test_schema_creates_all_tables(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )}
    assert {"places", "reviews", "photos", "visits", "transitions"} <= names


def test_vec_table_accepts_embedding(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    conn.execute("INSERT INTO places(place_key) VALUES ('pid:x')")
    vec = ",".join(["0.1"] * 384)
    conn.execute(
        "INSERT INTO place_vec(place_key, embedding) VALUES ('pid:x', vec_f32(?))",
        (f"[{vec}]",),
    )
    rows = list(conn.execute("SELECT place_key FROM place_vec"))
    assert rows[0][0] == "pid:x"
