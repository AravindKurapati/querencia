from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place
from querencia.query import narrative, patterns, taste


def _seed(conn):
    for k, name, cat, cc, rating in [
        ("pid:a", "Balaji Bhavan", "restaurant", "US", 5),
        ("pid:b", "Athens Rooftop", "restaurant", "GR", 5),
        ("pid:c", "City Park", "park", "US", 4),
    ]:
        upsert_place(conn, k, name=name, source="review")
        conn.execute("UPDATE places SET category=?, country_code=? WHERE place_key=?",
                     (cat, cc, k))
        conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                     "VALUES (?,?,?,?)", (k, rating, "good", "2024-06-01T00:00:00Z"))


def test_narrative_returns_grounded_structure(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    data = narrative(conn, theme="food")
    assert data["place_count"] == 2          # only restaurants
    assert "US" in data["countries"]
    assert any(p["name"] == "Balaji Bhavan" for p in data["top_rated"])


def test_patterns_categories_counts(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    cats = patterns(conn, kind="categories")
    assert cats["restaurant"] == 2
    assert cats["park"] == 1


def test_taste_returns_preferred_categories(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    profile = taste(conn, city="Lisbon")
    assert profile["city"] == "Lisbon"
    assert profile["top_categories"][0] == "restaurant"
    assert profile["avg_rating"] >= 4
