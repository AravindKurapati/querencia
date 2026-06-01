from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place
from querencia import query


def _seed(conn):
    rows = [
        ("pid:a", "Balaji Bhavan", "restaurant", "US",
         "100 Main St, Brooklyn, NY, USA", 40.7, -74.0, 5, "2024-06-01T00:00:00Z"),
        ("pid:b", "Athens Rooftop", "restaurant", "GR",
         "5 Plaka, Athens, Greece", 37.97, 23.72, 5, "2024-07-01T00:00:00Z"),
        ("pid:c", "City Park", "park", "US",
         "Park Ave, Brooklyn, NY, USA", 40.71, -74.01, 4, "2025-01-01T00:00:00Z"),
        ("pid:d", "Cafe Pessoa", "cafe", "PT",
         "Rua A, Lisbon, Portugal", 38.71, -9.14, 5, "2025-02-01T00:00:00Z"),
        ("pid:e", "Cafe Doce", "cafe", "PT",
         "Rua B, Lisbon, Portugal", 38.72, -9.13, 5, "2025-03-01T00:00:00Z"),
    ]
    for k, name, cat, cc, addr, lat, lng, rating, ts in rows:
        upsert_place(conn, k, name=name, source="review")
        conn.execute(
            "UPDATE places SET category=?, country_code=?, address=?, lat=?, lng=? "
            "WHERE place_key=?",
            (cat, cc, addr, lat, lng, k),
        )
        conn.execute(
            "INSERT INTO reviews(place_key,rating,text,reviewed_at) VALUES (?,?,?,?)",
            (k, rating, "great", ts),
        )


def _conn(tmp_path):
    c = connect(tmp_path / "t.db"); init_schema(c); _seed(c); return c


def test_summary_totals(tmp_path):
    s = query.summary(_conn(tmp_path))
    assert s["place_count"] == 5
    assert s["review_count"] == 5
    assert s["country_count"] == 3
    assert s["avg_rating"] >= 4.5
    assert s["first_review_at"].startswith("2024-06")


def test_by_country_sums_to_place_count(tmp_path):
    rows = query.by_country(_conn(tmp_path))
    assert sum(r["count"] for r in rows) == 5
    cc = {r["country_code"]: r["count"] for r in rows}
    assert cc["US"] == 2 and cc["PT"] == 2 and cc["GR"] == 1


def test_by_category_orders_by_count(tmp_path):
    rows = query.by_category(_conn(tmp_path))
    assert rows[0]["category"] in ("restaurant", "cafe")
    assert sum(r["count"] for r in rows) == 5


def test_by_city_extracts_cities(tmp_path):
    rows = query.by_city(_conn(tmp_path))
    cities = {r["city"]: r["count"] for r in rows}
    assert cities.get("Lisbon") == 2
    assert cities.get("Athens") == 1


def test_rating_distribution_sums_to_reviews(tmp_path):
    dist = query.rating_distribution(_conn(tmp_path))
    assert set(dist.keys()) == {"1", "2", "3", "4", "5"}
    assert sum(dist.values()) == 5
    assert dist["5"] == 4


def test_reviews_over_time_monthly(tmp_path):
    rows = query.reviews_over_time(_conn(tmp_path))
    assert len(rows) == 5
    assert rows[0]["month"] == "2024-06"


def test_places_for_map_has_coords(tmp_path):
    rows = query.places_for_map(_conn(tmp_path))
    assert len(rows) == 5
    for r in rows:
        assert r["lat"] and r["lng"]
        assert r["review_count"] == 1


def test_taste_sentence_nonempty(tmp_path):
    s = query.taste_sentence(_conn(tmp_path))
    assert s.endswith(".")
    assert len(s) > 20
