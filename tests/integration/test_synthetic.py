from examples.build_synthetic import build_synthetic_reviews


def test_synthetic_reviews_shape():
    data = build_synthetic_reviews(n=40, seed=1)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 40
    f = data["features"][0]["properties"]
    assert "five_star_rating_published" in f
    assert "location" in f
