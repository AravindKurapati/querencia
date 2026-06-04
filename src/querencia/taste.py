"""Taste model + cross-city recommender.

Three stages: build a user preference vector from rated reviews; fetch candidate
places for a city (Google Places, or fallback to in-DB places matching country);
score and rank by cosine similarity. All ML-ish steps are LLM-free.
"""
from __future__ import annotations

import json
import math
import pickle
import sqlite3
from collections import Counter
from datetime import datetime, timezone


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def _add(a: list[float], b: list[float], weight: float = 1.0) -> list[float]:
    if not a:
        return [x * weight for x in b]
    return [x + y * weight for x, y in zip(a, b)]


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


def _avg_rating(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT AVG(rating) FROM reviews WHERE rating IS NOT NULL").fetchone()
    return float(row[0]) if row and row[0] is not None else 3.0


def _embedding_for(conn: sqlite3.Connection, key: str) -> list[float] | None:
    row = conn.execute(
        "SELECT vec_to_json(embedding) FROM place_vec WHERE place_key=?", (key,)
    ).fetchone()
    if not row or not row[0]:
        return None
    return json.loads(row[0])


def preference_vector(conn: sqlite3.Connection) -> dict[str, list[float]]:
    """Per-category preference vector + a 'global' vector. Cached in pref_vectors."""
    avg = _avg_rating(conn)
    rows = conn.execute(
        "SELECT r.place_key, r.rating, p.category FROM reviews r "
        "JOIN places p ON p.place_key = r.place_key WHERE r.rating IS NOT NULL"
    ).fetchall()
    accum: dict[str, list[float]] = {}
    counts: Counter[str] = Counter()
    for key, rating, category in rows:
        vec = _embedding_for(conn, key)
        if vec is None:
            continue
        weight = float(rating) - avg
        if weight <= 0:
            continue
        accum["__global__"] = _add(accum.get("__global__", []), vec, weight)
        counts["__global__"] += 1
        if category:
            accum[category] = _add(accum.get(category, []), vec, weight)
            counts[category] += 1
    out = {k: _normalize(v) for k, v in accum.items()}
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM pref_vectors")
    for k, v in out.items():
        conn.execute(
            "INSERT INTO pref_vectors(category, vector, n_reviews, computed_at) "
            "VALUES (?,?,?,?)",
            (k, pickle.dumps(v), counts[k], now),
        )
    conn.commit()
    return out


def _fallback_candidates(conn: sqlite3.Connection, country_code: str, categories: list[str]) -> list[dict]:
    rows = conn.execute(
        "SELECT place_key, canonical_name, category, address FROM places "
        "WHERE country_code = ? AND category IS NOT NULL AND canonical_name IS NOT NULL",
        (country_code,),
    ).fetchall()
    return [
        {"place_key": k, "name": n, "category": c, "address": a, "source": "db_fallback"}
        for k, n, c, a in rows
    ]


def fetch_candidates(
    conn: sqlite3.Connection,
    city: str,
    categories: list[str],
    *,
    client=None,
) -> list[dict]:
    """Fetch candidate places. Uses Google Places client if given; otherwise DB fallback.

    Respects candidate_cache (skips network call when (city, category) cached).
    """
    out: list[dict] = []
    for cat in categories:
        cached = conn.execute(
            "SELECT payload FROM candidate_cache WHERE city=? AND category=?",
            (city, cat),
        ).fetchone()
        if cached:
            out.extend(json.loads(cached[0]))
            continue
        if client is None:
            continue
        try:
            places = client.places_nearby(city=city, category=cat)
        except Exception:
            places = []
        conn.execute(
            "INSERT OR REPLACE INTO candidate_cache(city, category, payload, fetched_at) "
            "VALUES (?,?,?,?)",
            (city, cat, json.dumps(places),
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        out.extend(places)
    return out


def recommend(
    conn: sqlite3.Connection,
    embedder,
    city: str,
    *,
    client=None,
    top: int = 10,
    country_code: str | None = None,
) -> list[dict]:
    """Return ranked candidate places in `city` against the user's preference vector.

    `embedder` may be None: a default `Embedder` is built lazily only when there
    is at least one candidate to score. The no-API-key / no-candidate path thus
    returns [] without loading the (heavy) embedding model.
    """
    prefs = preference_vector(conn)
    if "__global__" not in prefs:
        return []
    top_cats = [
        c for c, _ in conn.execute(
            "SELECT category, COUNT(*) FROM places p JOIN reviews r ON r.place_key=p.place_key "
            "WHERE p.category IS NOT NULL GROUP BY p.category ORDER BY COUNT(*) DESC LIMIT 5"
        ).fetchall()
    ]
    candidates = fetch_candidates(conn, city, top_cats, client=client)
    if not candidates and country_code:
        candidates = _fallback_candidates(conn, country_code, top_cats)
    if not candidates:
        return []
    ranked: list[dict] = []
    for cand in candidates:
        text = " | ".join(filter(None, [
            cand.get("name"), cand.get("category"), cand.get("address"),
        ]))
        if not text:
            continue
        if embedder is None:
            from .embed import Embedder
            embedder = Embedder()
        vec = embedder.encode(text)
        cat = cand.get("category")
        pref = prefs.get(cat) or prefs["__global__"]
        score = _cosine(vec, pref)
        ranked.append({
            "name": cand.get("name"),
            "category": cat,
            "address": cand.get("address"),
            "score": round(score, 4),
            "source": cand.get("source", "places_api"),
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:top]


class PlacesClient:
    """Thin wrapper over googlemaps client for `places_nearby` text search."""

    def __init__(self, api_key: str | None = None):
        from ._keys import require_env_key
        key = require_env_key("GOOGLE_PLACES_API_KEY", api_key)
        import googlemaps
        self._gm = googlemaps.Client(key=key)

    def places_nearby(self, *, city: str, category: str) -> list[dict]:
        res = self._gm.places(query=f"{category} in {city}")
        out = []
        for item in (res.get("results") or [])[:20]:
            out.append({
                "place_key": "pid:" + item.get("place_id", ""),
                "name": item.get("name"),
                "category": category,
                "address": item.get("formatted_address"),
            })
        return out
