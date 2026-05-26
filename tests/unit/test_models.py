from querencia.models import Place, Review, Photo, Visit, Transition


def test_place_defaults():
    p = Place(place_key="geo:40.74,-74.05", lat=40.74, lng=-74.05)
    assert p.canonical_name is None
    assert p.enriched_at is None
    assert p.source_flags == set()


def test_review_holds_text_and_rating():
    r = Review(place_key="pid:abc", rating=5, text="great", reviewed_at="2024-09-11T17:44:39Z")
    assert r.rating == 5
    assert r.text == "great"
