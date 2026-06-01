import sqlite3


def recall(
    conn: sqlite3.Connection,
    question: str,
    embedder,
    k: int = 10,
    expand_hops: int = 0,
) -> list[dict]:
    qvec = embedder.encode(question)
    rows = conn.execute(
        "SELECT v.place_key, distance, p.canonical_name, p.category, p.country_code "
        "FROM place_vec v JOIN places p ON p.place_key = v.place_key "
        "WHERE v.embedding MATCH vec_f32(?) AND k = ? "
        "ORDER BY distance",
        (f"[{','.join(str(x) for x in qvec)}]", k),
    ).fetchall()
    out = []
    seen: set[str] = set()
    for key, dist, name, category, cc in rows:
        seen.add(key)
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
    if expand_hops > 0 and seen:
        from .graph import expand_hops as _expand
        neighbors = _expand(conn, seen, hops=expand_hops) - seen
        for key in neighbors:
            row = conn.execute(
                "SELECT canonical_name, category, country_code FROM places WHERE place_key=?",
                (key,),
            ).fetchone()
            if not row:
                continue
            name, category, cc = row
            reviews = [
                {"rating": r[0], "text": r[1]}
                for r in conn.execute(
                    "SELECT rating, text FROM reviews WHERE place_key=?", (key,)
                )
            ]
            out.append({
                "place_key": key, "name": name, "category": category,
                "country_code": cc, "distance": None, "reviews": reviews,
                "via": "graph_hop",
            })
    return out


FOOD_CATEGORIES = ("restaurant", "cafe", "bar", "bakery", "food")


def narrative(conn: sqlite3.Connection, theme: str | None = None,
              year: int | None = None, trip_id: int | None = None) -> dict:
    where, params = [], []
    if theme == "food":
        where.append("p.category IN (%s)" % ",".join("?" * len(FOOD_CATEGORIES)))
        params.extend(FOOD_CATEGORIES)
    if year:
        where.append("strftime('%Y', r.reviewed_at) = ?")
        params.append(str(year))
    if trip_id is not None:
        where.append("p.place_key IN (SELECT place_key FROM trip_places WHERE trip_id=?)")
        params.append(trip_id)
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
        "theme": theme, "year": year, "trip_id": trip_id,
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
