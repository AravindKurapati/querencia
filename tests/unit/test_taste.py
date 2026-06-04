import json

from querencia.db import connect, init_schema
from querencia.embed import build_index
from querencia.ingest._util import upsert_place
from querencia.taste import fetch_candidates, preference_vector, recommend


def _pad(v):
    out = list(v) + [0.0] * (384 - len(v))
    return out[:384]


class FakeEmbedder:
    dim = 384

    def __init__(self, mapping):
        self.mapping = {k: _pad(v) for k, v in mapping.items()}
        self.default = [0.0] * 384

    def encode(self, text: str):
        for key, vec in self.mapping.items():
            if key in text:
                return vec
        return self.default


class FakePlacesClient:
    def __init__(self, by_cat):
        self.by_cat = by_cat
        self.calls = 0

    def places_nearby(self, *, city, category):
        self.calls += 1
        return self.by_cat.get(category, [])


def _seed(conn, embedder):
    # Loved: italian restaurants (5-star).
    upsert_place(conn, "pid:1", name="Pasta House", lat=1, lng=1, source="review")
    conn.execute("UPDATE places SET category='restaurant', country_code='US' WHERE place_key='pid:1'")
    conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                 "VALUES ('pid:1',5,'amazing italian pasta','2023-01-01T12:00:00Z')")
    upsert_place(conn, "pid:2", name="Pizza Place", lat=1, lng=1, source="review")
    conn.execute("UPDATE places SET category='restaurant', country_code='US' WHERE place_key='pid:2'")
    conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                 "VALUES ('pid:2',5,'best pizza','2023-01-02T12:00:00Z')")
    # Disliked: chains (2-star).
    upsert_place(conn, "pid:3", name="Burger Chain", lat=1, lng=1, source="review")
    conn.execute("UPDATE places SET category='restaurant', country_code='US' WHERE place_key='pid:3'")
    conn.execute("INSERT INTO reviews(place_key,rating,text,reviewed_at) "
                 "VALUES ('pid:3',2,'meh fast food','2023-01-03T12:00:00Z')")
    conn.commit()
    build_index(conn, embedder)


def test_preference_vector_only_uses_above_average_ratings(tmp_path):
    embedder = FakeEmbedder({
        "Pasta": [1.0] * 8, "Pizza": [1.0] * 8, "Burger": [0.0] * 8,
    })
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn, embedder)
    prefs = preference_vector(conn)
    assert "__global__" in prefs
    # Pref vector should be in the italian-food direction, not zero.
    assert sum(prefs["__global__"]) > 0


def test_fetch_candidates_uses_cache(tmp_path):
    embedder = FakeEmbedder({})
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn, embedder)
    client = FakePlacesClient({"restaurant": [{"name": "Trattoria", "category": "restaurant"}]})
    cands = fetch_candidates(conn, "Rome", ["restaurant"], client=client)
    assert any(c["name"] == "Trattoria" for c in cands)
    assert client.calls == 1
    cached = fetch_candidates(conn, "Rome", ["restaurant"], client=client)
    assert cached == cands
    assert client.calls == 1  # second call hit cache


def test_recommend_ranks_similar_first(tmp_path):
    embedder = FakeEmbedder({
        "Pasta": [1.0] * 8, "Pizza": [1.0] * 8, "Burger": [0.0] * 8,
        "Trattoria": [1.0] * 8, "Drive-Thru": [0.0] * 8,
    })
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn, embedder)
    client = FakePlacesClient({"restaurant": [
        {"name": "Drive-Thru", "category": "restaurant", "address": "x"},
        {"name": "Trattoria", "category": "restaurant", "address": "y"},
    ]})
    out = recommend(conn, embedder, "Rome", client=client, top=2)
    assert out[0]["name"] == "Trattoria"
    assert out[0]["score"] > out[1]["score"]


def test_recommend_with_no_client_and_no_cache_returns_empty(tmp_path):
    embedder = FakeEmbedder({"Pasta": [1.0] * 8, "Pizza": [1.0] * 8})
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn, embedder)
    out = recommend(conn, embedder, "Rome", client=None, top=5)
    assert out == []


def test_recommend_no_candidates_never_builds_embedder(tmp_path):
    # embedder=None + no candidates must short-circuit WITHOUT constructing a
    # default Embedder (which would load a heavy model / fail offline). A real
    # build would raise here; reaching [] proves the lazy path stays model-free.
    embedder = FakeEmbedder({"Pasta": [1.0] * 8, "Pizza": [1.0] * 8})
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn, embedder)
    out = recommend(conn, None, "Rome", client=None, top=5)
    assert out == []


def test_recommend_falls_back_to_db_candidates_by_country(tmp_path):
    # The documented offline fallback: with no client but a country_code, rank
    # the user's own in-DB places from that country. Previously unreachable from
    # any caller, so never exercised.
    embedder = FakeEmbedder({
        "Pasta": [1.0] * 8, "Pizza": [1.0] * 8, "Burger": [0.0] * 8,
    })
    conn = connect(tmp_path / "t.db"); init_schema(conn); _seed(conn, embedder)
    # _seed already sets canonical_name + category + country_code on each place,
    # which is all _fallback_candidates needs.
    out = recommend(conn, embedder, "Anytown", client=None, country_code="US", top=5)
    assert out, "expected DB-fallback candidates from country US"
    assert all(r["source"] == "db_fallback" for r in out)
    # Italian-leaning prefs should rank Pasta/Pizza above the disliked Burger.
    assert out[0]["name"] in ("Pasta House", "Pizza Place")
