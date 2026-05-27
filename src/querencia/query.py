import sqlite3


def recall(conn: sqlite3.Connection, question: str, embedder, k: int = 10) -> list[dict]:
    qvec = embedder.encode(question)
    rows = conn.execute(
        "SELECT v.place_key, distance, p.canonical_name, p.category, p.country_code "
        "FROM place_vec v JOIN places p ON p.place_key = v.place_key "
        "WHERE v.embedding MATCH vec_f32(?) AND k = ? "
        "ORDER BY distance",
        (f"[{','.join(str(x) for x in qvec)}]", k),
    ).fetchall()
    out = []
    for key, dist, name, category, cc in rows:
        reviews = [
            {"rating": r[0], "text": r[1]}
            for r in conn.execute(
                "SELECT rating, text FROM reviews WHERE place_key=?", (key,)
            )
        ]
        out.append({
            "place_key": key, "name": name, "category": category,
            "country_code": cc, "distance": dist, "reviews": reviews,
        })
    return out


FOOD_CATEGORIES = ("restaurant", "cafe", "bar", "bakery", "food")


def narrative(conn: sqlite3.Connection, theme: str | None = None,
              year: int | None = None) -> dict:
    where, params = [], []
    if theme == "food":
        where.append("p.category IN (%s)" % ",".join("?" * len(FOOD_CATEGORIES)))
        params.extend(FOOD_CATEGORIES)
    if year:
        where.append("strftime('%Y', r.reviewed_at) = ?")
        params.append(str(year))
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT p.place_key, p.canonical_name, p.category, p.country_code, "
        f"r.rating, r.text, r.reviewed_at "
        f"FROM places p JOIN reviews r ON r.place_key = p.place_key {clause} "
        f"ORDER BY r.rating DESC, r.reviewed_at DESC",
        params,
    ).fetchall()
    countries = sorted({r[3] for r in rows if r[3]})
    top_rated = [
        {"name": r[1], "category": r[2], "country": r[3], "rating": r[4], "text": r[5]}
        for r in rows[:10]
    ]
    return {
        "theme": theme, "year": year,
        "place_count": len({r[0] for r in rows}),
        "countries": countries,
        "top_rated": top_rated,
    }


def patterns(conn: sqlite3.Connection, kind: str = "categories") -> dict:
    if kind == "categories":
        return {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT COALESCE(category,'unknown'), COUNT(*) FROM places "
                "WHERE place_key IN (SELECT place_key FROM reviews) "
                "GROUP BY category ORDER BY COUNT(*) DESC"
            )
        }
    raise ValueError(f"unknown pattern kind: {kind}")


def taste(conn: sqlite3.Connection, city: str) -> dict:
    cats = conn.execute(
        "SELECT p.category, COUNT(*) c, AVG(r.rating) a "
        "FROM places p JOIN reviews r ON r.place_key=p.place_key "
        "WHERE p.category IS NOT NULL GROUP BY p.category ORDER BY c DESC"
    ).fetchall()
    avg = conn.execute("SELECT AVG(rating) FROM reviews").fetchone()[0] or 0
    return {
        "city": city,
        "top_categories": [c[0] for c in cats],
        "avg_rating": round(avg, 2),
    }


def summary(conn: sqlite3.Connection) -> dict:
    place_count = conn.execute(
        "SELECT COUNT(*) FROM places WHERE place_key IN (SELECT place_key FROM reviews)"
    ).fetchone()[0]
    review_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    photo_count = conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    country_count = conn.execute(
        "SELECT COUNT(DISTINCT country_code) FROM places WHERE country_code IS NOT NULL"
    ).fetchone()[0]
    avg = conn.execute("SELECT AVG(rating) FROM reviews").fetchone()[0] or 0
    first_at, last_at = conn.execute(
        "SELECT MIN(reviewed_at), MAX(reviewed_at) FROM reviews"
    ).fetchone()
    return {
        "place_count": place_count,
        "review_count": review_count,
        "photo_count": photo_count,
        "country_count": country_count,
        "avg_rating": round(avg, 2),
        "first_review_at": first_at,
        "last_review_at": last_at,
    }


def by_country(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT p.country_code, COUNT(DISTINCT p.place_key), AVG(r.rating) "
        "FROM places p JOIN reviews r ON r.place_key = p.place_key "
        "WHERE p.country_code IS NOT NULL "
        "GROUP BY p.country_code ORDER BY COUNT(DISTINCT p.place_key) DESC"
    ).fetchall()
    return [
        {"country_code": cc, "count": n, "avg_rating": round(a or 0, 2)}
        for cc, n, a in rows
    ]


def by_category(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT COALESCE(p.category,'unknown'), COUNT(DISTINCT p.place_key), AVG(r.rating) "
        "FROM places p JOIN reviews r ON r.place_key = p.place_key "
        "GROUP BY p.category ORDER BY COUNT(DISTINCT p.place_key) DESC"
    ).fetchall()
    return [
        {"category": c, "count": n, "avg_rating": round(a or 0, 2)}
        for c, n, a in rows
    ]


def _extract_city(address: str | None) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) < 2:
        return None
    return parts[-2] if len(parts) >= 2 else parts[0]


def by_city(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT p.address, p.place_key, r.rating "
        "FROM places p JOIN reviews r ON r.place_key = p.place_key "
        "WHERE p.address IS NOT NULL"
    ).fetchall()
    buckets: dict[str, dict] = {}
    for addr, pk, rating in rows:
        city = _extract_city(addr)
        if not city:
            continue
        b = buckets.setdefault(city, {"places": set(), "ratings": []})
        b["places"].add(pk)
        if rating is not None:
            b["ratings"].append(rating)
    out = [
        {
            "city": city,
            "count": len(b["places"]),
            "avg_rating": round(sum(b["ratings"]) / len(b["ratings"]), 2)
            if b["ratings"] else 0,
        }
        for city, b in buckets.items()
    ]
    out.sort(key=lambda d: d["count"], reverse=True)
    return out


def rating_distribution(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT rating, COUNT(*) FROM reviews WHERE rating IS NOT NULL GROUP BY rating"
    ).fetchall()
    dist = {str(i): 0 for i in range(1, 6)}
    for r, n in rows:
        dist[str(int(r))] = n
    return dist


def reviews_over_time(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT strftime('%Y-%m', reviewed_at) m, COUNT(*) "
        "FROM reviews WHERE reviewed_at IS NOT NULL "
        "GROUP BY m ORDER BY m"
    ).fetchall()
    return [{"month": m, "count": n} for m, n in rows if m]


def places_for_map(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT p.place_key, p.canonical_name, p.category, p.country_code, "
        "p.lat, p.lng, COUNT(r.review_id), AVG(r.rating), MAX(r.text) "
        "FROM places p JOIN reviews r ON r.place_key = p.place_key "
        "WHERE p.lat IS NOT NULL AND p.lng IS NOT NULL "
        "GROUP BY p.place_key"
    ).fetchall()
    out = []
    for pk, name, cat, cc, lat, lng, n, avg, sample in rows:
        text = (sample or "")[:240]
        out.append({
            "place_key": pk, "name": name, "category": cat,
            "country_code": cc, "lat": lat, "lng": lng,
            "review_count": n, "avg_rating": round(avg or 0, 2),
            "sample_text": text,
        })
    return out


def taste_sentence(conn: sqlite3.Connection) -> str:
    cats = by_category(conn)
    if not cats:
        return "Not enough reviews yet for a taste profile."
    top = cats[0]
    pieces = [f"You've reviewed {top['count']} {top['category']} places (avg {top['avg_rating']})"]
    if len(cats) > 1:
        diff = round(top["avg_rating"] - cats[1]["avg_rating"], 2)
        if diff > 0.1:
            pieces.append(
                f"rating them {diff} stars higher than {cats[1]['category']} on average"
            )
    countries = by_country(conn)
    if countries:
        top_c = countries[0]
        pieces.append(f"with {top_c['count']} places in {top_c['country_code']}")
    return ", ".join(pieces) + "."
