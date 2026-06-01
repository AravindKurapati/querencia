from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place
from querencia.trips import detect_trips, materialize_trips


def _conn(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    return conn


def _place(conn, key, lat, lng, cc="US", cat="restaurant"):
    upsert_place(conn, key, name=key, lat=lat, lng=lng, source="review")
    conn.execute("UPDATE places SET country_code=?, category=? WHERE place_key=?",
                 (cc, cat, key))


def _review(conn, key, when, rating=5):
    conn.execute(
        "INSERT INTO reviews(place_key,rating,text,reviewed_at) VALUES (?,?,?,?)",
        (key, rating, "x", when),
    )


def test_empty_db_returns_no_trips(tmp_path):
    conn = _conn(tmp_path)
    assert detect_trips(conn) == []


def test_three_close_visits_in_foreign_country_form_one_trip(tmp_path):
    conn = _conn(tmp_path)
    # Home: NYC reviews (anchor the home centroid)
    for i in range(6):
        _place(conn, f"pid:home{i}", 40.71, -74.00, cc="US")
        _review(conn, f"pid:home{i}", f"2023-01-{i+1:02d}T12:00:00Z")
    # Trip: 3 places in Athens within 2 days
    for i, lng in enumerate([23.72, 23.73, 23.74]):
        _place(conn, f"pid:gr{i}", 37.98, lng, cc="GR", cat="restaurant")
        _review(conn, f"pid:gr{i}", f"2023-06-1{i}T12:00:00Z")
    conn.commit()
    trips = detect_trips(conn, min_pts=3)
    assert len(trips) == 1
    assert trips[0].country_code == "GR"
    assert trips[0].place_count == 3


def test_same_country_far_apart_in_time_are_separate_trips(tmp_path):
    conn = _conn(tmp_path)
    for i in range(6):
        _place(conn, f"pid:home{i}", 40.71, -74.00, cc="US")
        _review(conn, f"pid:home{i}", f"2023-01-{i+1:02d}T12:00:00Z")
    # Two trips to Athens, months apart
    for i, lng in enumerate([23.72, 23.73, 23.74]):
        _place(conn, f"pid:spring{i}", 37.98, lng, cc="GR")
        _review(conn, f"pid:spring{i}", f"2023-03-1{i}T12:00:00Z")
    for i, lng in enumerate([23.72, 23.73, 23.74]):
        _place(conn, f"pid:fall{i}", 37.98, lng, cc="GR")
        _review(conn, f"pid:fall{i}", f"2023-10-1{i}T12:00:00Z")
    conn.commit()
    trips = detect_trips(conn, min_pts=3)
    assert len(trips) == 2


def test_materialize_writes_to_tables(tmp_path):
    conn = _conn(tmp_path)
    for i in range(6):
        _place(conn, f"pid:home{i}", 40.71, -74.00, cc="US")
        _review(conn, f"pid:home{i}", f"2023-01-{i+1:02d}T12:00:00Z")
    for i, lng in enumerate([23.72, 23.73, 23.74]):
        _place(conn, f"pid:gr{i}", 37.98, lng, cc="GR")
        _review(conn, f"pid:gr{i}", f"2023-06-1{i}T12:00:00Z")
    conn.commit()
    n = materialize_trips(conn, min_pts=3)
    assert n == 1
    row = conn.execute("SELECT country_code, place_count FROM trips").fetchone()
    assert row == ("GR", 3)
    assert conn.execute("SELECT COUNT(*) FROM trip_places").fetchone()[0] == 3
