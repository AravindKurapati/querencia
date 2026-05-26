from querencia.db import connect, init_schema
from querencia.ingest.labels import ingest_labels
from querencia.ingest.commutes import ingest_commutes

LABELS = {"features": [
    {"geometry": {"coordinates": [77.6529267, 12.914492], "type": "Point"},
     "properties": {"address": "HSR Layout, Bengaluru", "name": "Home"}}]}

COMMUTES = {"trips": [
    {"id": "T1",
     "place_visit": [
        {"id": "SOURCE_ID"},
        {"id": "DESTINATION_ID",
         "place": {"lat_lng": {"latitude": 12.9067, "longitude": 77.5463}}}],
     "transition": [
        {"route": {"travel_mode": "DRIVE"},
         "origin": {"visit_id": "SOURCE_ID"},
         "destination": {"visit_id": "DESTINATION_ID"}}]}]}


def test_labels_create_named_places(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    n = ingest_labels(conn, LABELS)
    assert n == 1
    row = conn.execute("SELECT canonical_name FROM places").fetchone()
    assert row[0] == "Home"


def test_commutes_create_transition_with_mode(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ingest_commutes(conn, COMMUTES)
    row = conn.execute("SELECT travel_mode FROM transitions").fetchone()
    assert row[0] == "DRIVE"
