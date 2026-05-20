import json
import random

CITIES = [
    ("New York", "US", 40.71, -74.00), ("Athens", "GR", 37.98, 23.72),
    ("Bengaluru", "IN", 12.97, 77.59), ("Stockholm", "SE", 59.33, 18.07),
    ("Paris", "FR", 48.85, 2.35),
]
NAMES = ["Bistro", "Cafe", "Diner", "Garden", "Rooftop", "Corner", "Market", "Kitchen"]
CATS = ["restaurant", "cafe", "bar", "park", "bakery"]


def build_synthetic_reviews(n: int = 40, seed: int = 0) -> dict:
    rng = random.Random(seed)
    feats = []
    for i in range(n):
        city, cc, lat, lng = rng.choice(CITIES)
        name = f"{rng.choice(NAMES)} {i}"
        category = rng.choice(CATS)
        feats.append({
            "geometry": {"coordinates": [lng + rng.uniform(-.05, .05),
                                         lat + rng.uniform(-.05, .05)], "type": "Point"},
            "properties": {
                "date": f"202{rng.randint(0,5)}-0{rng.randint(1,9)}-15T12:00:00Z",
                "five_star_rating_published": rng.randint(3, 5),
                "google_maps_url": f"https://www.google.com/maps/place//data=!1s0x0:0x{i:x}",
                "category": category,
                "location": {"address": f"{i} Main St, {city}",
                             "country_code": cc, "name": name},
                "review_text_published": f"Loved the vibe at {name}.",
            },
        })
    return {"type": "FeatureCollection", "features": feats}


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).parent / "synthetic"
    out.mkdir(exist_ok=True)
    (out / "Reviews.json").write_text(json.dumps(build_synthetic_reviews(40, 7), indent=2))
    print(f"wrote {out / 'Reviews.json'}")
