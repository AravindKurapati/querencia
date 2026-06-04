"""Edge-case + robustness coverage for the ingest/merge foundation.

Google Takeout exports are messy: features carry explicit `null` (not just
missing keys), reviews lose their geometry, photos sit at (0, 0), and commute
transitions reference visits that never materialized. These tests pin down the
defensive behavior the rest of the pipeline relies on, plus the COALESCE merge
semantics of `upsert_place` (the single function every ingester funnels into).
"""
from querencia.db import connect, init_schema
from querencia.ingest._util import upsert_place
from querencia.ingest.commutes import ingest_commutes
from querencia.ingest.labels import ingest_labels
from querencia.ingest.photos import ingest_photo_sidecar
from querencia.ingest.questions import ingest_question
from querencia.ingest.reviews import ingest_reviews


def _conn(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    return conn


# --------------------------------------------------------------------------- #
# upsert_place — the merge contract every ingester depends on.
# --------------------------------------------------------------------------- #
def test_upsert_place_first_write_wins_for_non_null_fields(tmp_path):
    conn = _conn(tmp_path)
    upsert_place(conn, "pid:a", name="Original", category="cafe",
                 country_code="US", source="review")
    # A later sighting with conflicting metadata must NOT clobber existing values.
    upsert_place(conn, "pid:a", name="Renamed", category="bar",
                 country_code="PT", source="photo")
    row = conn.execute(
        "SELECT canonical_name, category, country_code FROM places WHERE place_key='pid:a'"
    ).fetchone()
    assert row == ("Original", "cafe", "US")


def test_upsert_place_fills_in_previously_null_fields(tmp_path):
    conn = _conn(tmp_path)
    # First seen via a photo: geo only, no name/category.
    upsert_place(conn, "geo:1.0,2.0", lat=1.0, lng=2.0, source="photo")
    # Later seen via a review that knows the name and category.
    upsert_place(conn, "geo:1.0,2.0", name="Beach Bar", category="bar",
                 country_code="PT", source="review")
    row = conn.execute(
        "SELECT canonical_name, category, country_code, lat, lng, source_flags "
        "FROM places WHERE place_key='geo:1.0,2.0'"
    ).fetchone()
    assert row[0] == "Beach Bar"
    assert row[1] == "bar"
    assert row[2] == "PT"
    assert (row[3], row[4]) == (1.0, 2.0)
    assert set(row[5].split(",")) == {"photo", "review"}


def test_upsert_place_idempotent_repeat_keeps_single_row(tmp_path):
    conn = _conn(tmp_path)
    for _ in range(3):
        upsert_place(conn, "pid:a", name="X", source="review")
    assert conn.execute("SELECT COUNT(*) FROM places").fetchone()[0] == 1


# --------------------------------------------------------------------------- #
# reviews — place_key resolution + malformed-feature robustness.
# --------------------------------------------------------------------------- #
def test_review_geo_fallback_key_when_no_hex_id(tmp_path):
    conn = _conn(tmp_path)
    data = {"features": [{
        "geometry": {"coordinates": [-9.139, 38.722], "type": "Point"},
        "properties": {"google_maps_url": "https://maps.google.com/no-id-here",
                       "five_star_rating_published": 4,
                       "review_text_published": "lovely"},
    }]}
    assert ingest_reviews(conn, data) == 1
    key = conn.execute("SELECT place_key FROM reviews").fetchone()[0]
    assert key == "geo:38.72200,-9.13900"  # GeoJSON [lng, lat] -> geo:lat,lng


def test_review_with_null_geometry_does_not_crash(tmp_path):
    conn = _conn(tmp_path)
    data = {"features": [{
        "geometry": None,  # Takeout's shape for a location-less review
        "properties": {"google_maps_url": "x!1s0x0:0xABC",
                       "five_star_rating_published": 5,
                       "review_text_published": "no geo"},
    }]}
    assert ingest_reviews(conn, data) == 1
    key = conn.execute("SELECT place_key FROM reviews").fetchone()[0]
    assert key == "pid:ABC"
    assert conn.execute(
        "SELECT lat FROM places WHERE place_key='pid:ABC'"
    ).fetchone()[0] is None


def test_review_with_null_properties_does_not_crash(tmp_path):
    conn = _conn(tmp_path)
    data = {"features": [{"geometry": {"coordinates": [1.0, 2.0]}, "properties": None}]}
    assert ingest_reviews(conn, data) == 1
    # Falls back to the url-unknown key; no rating/text available.
    row = conn.execute("SELECT rating, text FROM reviews").fetchone()
    assert row == (None, None)


# --------------------------------------------------------------------------- #
# labels — coordinate validation + malformed-feature robustness.
# --------------------------------------------------------------------------- #
def test_label_with_malformed_coords_is_skipped(tmp_path):
    conn = _conn(tmp_path)
    data = {"features": [
        {"geometry": {"coordinates": [1.0]}, "properties": {"name": "Bad"}},      # too short
        {"geometry": None, "properties": {"name": "NullGeom"}},                    # null geometry
        {"geometry": {"coordinates": [-9.1, 38.7]}, "properties": {"name": "Ok"}},
    ]}
    assert ingest_labels(conn, data) == 1
    assert conn.execute("SELECT canonical_name FROM places").fetchone()[0] == "Ok"


def test_label_with_null_properties_does_not_crash(tmp_path):
    conn = _conn(tmp_path)
    data = {"features": [{"geometry": {"coordinates": [-9.1, 38.7]}, "properties": None}]}
    assert ingest_labels(conn, data) == 1
    row = conn.execute(
        "SELECT canonical_name, address FROM places"
    ).fetchone()
    assert row == (None, None)


# --------------------------------------------------------------------------- #
# commutes — coordless visits + dangling transitions.
# --------------------------------------------------------------------------- #
def test_commute_coordless_visit_uses_visit_key(tmp_path):
    conn = _conn(tmp_path)
    data = {"trips": [{
        "place_visit": [
            {"id": "v1", "place": {"lat_lng": {"latitude": 1.0, "longitude": 2.0}}},
            {"id": "v2", "place": {}},  # no coordinates
        ],
        "transition": [
            {"origin": {"visit_id": "v1"}, "destination": {"visit_id": "v2"},
             "route": {"travel_mode": "WALK"}},
        ],
    }]}
    assert ingest_commutes(conn, data) == 1
    keys = {r[0] for r in conn.execute("SELECT place_key FROM places")}
    assert "geo:1.00000,2.00000" in keys
    assert "visit:v2" in keys
    edge = conn.execute(
        "SELECT from_place_key, to_place_key, travel_mode FROM transitions"
    ).fetchone()
    assert edge == ("geo:1.00000,2.00000", "visit:v2", "WALK")


def test_commute_transition_with_unknown_endpoint_is_skipped(tmp_path):
    conn = _conn(tmp_path)
    data = {"trips": [{
        "place_visit": [
            {"id": "v1", "place": {"lat_lng": {"latitude": 1.0, "longitude": 2.0}}},
        ],
        "transition": [
            {"origin": {"visit_id": "v1"}, "destination": {"visit_id": "ghost"}},
            {"origin": None, "destination": {"visit_id": "v1"}},  # null origin
        ],
    }]}
    assert ingest_commutes(conn, data) == 0
    assert conn.execute("SELECT COUNT(*) FROM transitions").fetchone()[0] == 0


def test_commute_missing_travel_mode_defaults_to_unknown(tmp_path):
    conn = _conn(tmp_path)
    data = {"trips": [{
        "place_visit": [
            {"id": "v1", "place": {"lat_lng": {"latitude": 1.0, "longitude": 2.0}}},
            {"id": "v2", "place": {"lat_lng": {"latitude": 3.0, "longitude": 4.0}}},
        ],
        "transition": [{"origin": {"visit_id": "v1"}, "destination": {"visit_id": "v2"}}],
    }]}
    assert ingest_commutes(conn, data) == 1
    assert conn.execute("SELECT travel_mode FROM transitions").fetchone()[0] == "UNKNOWN"


# --------------------------------------------------------------------------- #
# photos — geo/timestamp validation + media-type classification.
# --------------------------------------------------------------------------- #
def test_photo_at_null_island_is_skipped(tmp_path):
    conn = _conn(tmp_path)
    data = {"geoDataExif": {"latitude": 0, "longitude": 0},
            "creationTime": {"timestamp": "1700000000"}}
    assert ingest_photo_sidecar(conn, data, "p.jpg") is False
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 0


def test_photo_without_timestamp_is_skipped(tmp_path):
    conn = _conn(tmp_path)
    data = {"geoDataExif": {"latitude": 40.0, "longitude": -74.0}}
    assert ingest_photo_sidecar(conn, data, "p.jpg") is False
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 0


def test_photo_unknown_extension_maps_to_other(tmp_path):
    conn = _conn(tmp_path)
    data = {"geoDataExif": {"latitude": 40.0, "longitude": -74.0},
            "creationTime": {"timestamp": "1700000000"}}
    assert ingest_photo_sidecar(conn, data, "clip.heic") is True
    assert conn.execute("SELECT media_type FROM photos").fetchone()[0] == "other"


def test_photo_video_extension_classified(tmp_path):
    conn = _conn(tmp_path)
    data = {"geoDataExif": {"latitude": 40.0, "longitude": -74.0},
            "creationTime": {"timestamp": "1700000000"}}
    assert ingest_photo_sidecar(conn, data, "VID_001.MP4") is True
    assert conn.execute("SELECT media_type FROM photos").fetchone()[0] == "mp4"


# --------------------------------------------------------------------------- #
# questions — CID extraction.
# --------------------------------------------------------------------------- #
def test_question_without_cid_is_skipped(tmp_path):
    conn = _conn(tmp_path)
    assert ingest_question(conn, {"placeUrl": "https://maps.google.com/?q=no-cid"}) is False
    assert conn.execute("SELECT COUNT(*) FROM places").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0] == 0


def test_question_missing_place_url_is_skipped(tmp_path):
    conn = _conn(tmp_path)
    assert ingest_question(conn, {}) is False
    assert conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0] == 0
