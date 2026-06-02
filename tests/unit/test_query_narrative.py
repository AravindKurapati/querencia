import pytest

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


def test_narrative_year_filter_restricts_to_that_year(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)  # three reviews dated 2024-06-01
    upsert_place(conn, "pid:old", name="Old Diner", source="review")
    conn.execute("UPDATE places SET category='restaurant', country_code='US' "
                 "WHERE place_key='pid:old'")
    conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                 "VALUES ('pid:old',5,'good','2023-01-01T00:00:00Z')")

    data_2024 = narrative(conn, year=2024)
    assert data_2024["year"] == 2024
    assert data_2024["place_count"] == 3
    assert all(p["name"] != "Old Diner" for p in data_2024["top_rated"])

    data_2023 = narrative(conn, year=2023)
    assert data_2023["place_count"] == 1
    assert data_2023["top_rated"][0]["name"] == "Old Diner"


def test_narrative_trip_id_filter_scopes_to_trip_places(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    conn.execute(
        "INSERT INTO trips(trip_id, started_at, ended_at, country_code, "
        "lead_category, place_count, lat, lng) "
        "VALUES (1,'2024-06-01T00:00:00Z','2024-06-01T00:00:00Z','GR','restaurant',1,0,0)"
    )
    conn.execute("INSERT INTO trip_places(trip_id, place_key) VALUES (1,'pid:b')")
    conn.commit()

    data = narrative(conn, trip_id=1)
    assert data["trip_id"] == 1
    assert data["place_count"] == 1
    assert data["top_rated"][0]["name"] == "Athens Rooftop"

    # A trip with no member places yields an empty-but-valid narrative.
    empty = narrative(conn, trip_id=999)
    assert empty["place_count"] == 0
    assert empty["top_rated"] == []


def test_patterns_rejects_unknown_kind(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    with pytest.raises(ValueError):
        patterns(conn, kind="not-a-kind")


def test_taste_returns_preferred_categories(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    _seed(conn)
    profile = taste(conn, city="Lisbon")
    assert profile["city"] == "Lisbon"
    assert profile["top_categories"][0] == "restaurant"
    assert profile["avg_rating"] >= 4
