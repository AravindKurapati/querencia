"""Trip detection: spatiotemporal clusters of visits/reviews/photos.

Pure-Python connected-components clustering — no sklearn dependency.
Two events join the same trip iff haversine distance <= r_km AND time gap <= t_days.
The user's home cluster (largest contiguous concentration) is excluded.
"""
from __future__ import annotations

import math
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable


@dataclass
class Trip:
    started_at: datetime
    ended_at: datetime
    country_code: str | None
    lead_category: str | None
    place_keys: list[str]
    lat: float
    lng: float
    place_count: int = field(init=False)

    def __post_init__(self):
        self.place_count = len(self.place_keys)


def _haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _events(conn: sqlite3.Connection) -> list[dict]:
    """Unified event stream: (place_key, when, lat, lng, country, category)."""
    rows = conn.execute(
        """
        SELECT p.place_key, r.reviewed_at AS t, p.lat, p.lng, p.country_code, p.category
        FROM reviews r JOIN places p ON p.place_key = r.place_key
        WHERE r.reviewed_at IS NOT NULL AND p.lat IS NOT NULL
        UNION ALL
        SELECT p.place_key, ph.taken_at, p.lat, p.lng, p.country_code, p.category
        FROM photos ph JOIN places p ON p.place_key = ph.place_key
        WHERE ph.taken_at IS NOT NULL AND p.lat IS NOT NULL
        UNION ALL
        SELECT p.place_key, v.occurred_at, p.lat, p.lng, p.country_code, p.category
        FROM visits v JOIN places p ON p.place_key = v.place_key
        WHERE v.occurred_at IS NOT NULL AND p.lat IS NOT NULL
        """
    ).fetchall()
    out = []
    for key, t, lat, lng, cc, cat in rows:
        if not t:
            continue
        try:
            when = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append({
            "key": key, "when": when, "lat": lat, "lng": lng,
            "country": cc, "category": cat,
        })
    out.sort(key=lambda e: e["when"])
    return out


def _home_centroid(events: list[dict]) -> tuple[float, float] | None:
    if not events:
        return None
    cells: Counter[tuple[float, float]] = Counter()
    for e in events:
        cells[(round(e["lat"], 1), round(e["lng"], 1))] += 1
    (lat, lng), _ = cells.most_common(1)[0]
    return lat, lng


def detect_trips(
    conn: sqlite3.Connection,
    *,
    r_km: float = 50.0,
    t_days: float = 3.0,
    min_pts: int = 3,
    home_radius_km: float = 30.0,
) -> list[Trip]:
    events = _events(conn)
    if not events:
        return []
    home = _home_centroid(events)
    if home is not None:
        events = [
            e for e in events
            if _haversine_km(e["lat"], e["lng"], home[0], home[1]) > home_radius_km
        ]
    if not events:
        return []

    # Connected-components: each event becomes its own component, then merge with
    # any prior event within r_km and t_days.
    parents = list(range(len(events)))

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parents[ri] = rj

    t_seconds = t_days * 86400
    for i, e in enumerate(events):
        # Look back: events are sorted by time, so only earlier ones can be within window.
        for j in range(i - 1, -1, -1):
            gap = (e["when"] - events[j]["when"]).total_seconds()
            if gap > t_seconds:
                break
            if _haversine_km(e["lat"], e["lng"], events[j]["lat"], events[j]["lng"]) <= r_km:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(len(events)):
        clusters.setdefault(find(i), []).append(i)

    trips: list[Trip] = []
    for idxs in clusters.values():
        members = [events[i] for i in idxs]
        keys = sorted({m["key"] for m in members})
        if len(keys) < min_pts:
            continue
        cats = Counter(m["category"] for m in members if m["category"])
        countries = Counter(m["country"] for m in members if m["country"])
        trips.append(Trip(
            started_at=min(m["when"] for m in members),
            ended_at=max(m["when"] for m in members),
            country_code=countries.most_common(1)[0][0] if countries else None,
            lead_category=cats.most_common(1)[0][0] if cats else None,
            place_keys=keys,
            lat=sum(m["lat"] for m in members) / len(members),
            lng=sum(m["lng"] for m in members) / len(members),
        ))
    trips.sort(key=lambda t: t.started_at)
    return trips


def materialize_trips(conn: sqlite3.Connection, **kwargs) -> int:
    """Detect trips and write them to the trips/trip_places tables. Idempotent."""
    conn.execute("DELETE FROM trip_places")
    conn.execute("DELETE FROM trips")
    trips = detect_trips(conn, **kwargs)
    for t in trips:
        cur = conn.execute(
            "INSERT INTO trips(started_at, ended_at, country_code, lead_category, "
            "place_count, lat, lng) VALUES (?,?,?,?,?,?,?)",
            (t.started_at.isoformat(), t.ended_at.isoformat(), t.country_code,
             t.lead_category, t.place_count, t.lat, t.lng),
        )
        tid = cur.lastrowid
        conn.executemany(
            "INSERT INTO trip_places(trip_id, place_key) VALUES (?,?)",
            [(tid, k) for k in t.place_keys],
        )
    conn.commit()
    return len(trips)


def list_trips(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT trip_id, started_at, ended_at, country_code, lead_category, place_count, "
        "lat, lng FROM trips ORDER BY started_at"
    ).fetchall()
    out = []
    for tid, start, end, cc, cat, n, lat, lng in rows:
        keys = [
            r[0] for r in conn.execute(
                "SELECT place_key FROM trip_places WHERE trip_id=? ORDER BY place_key",
                (tid,),
            )
        ]
        out.append({
            "trip_id": tid, "started_at": start, "ended_at": end,
            "country_code": cc, "lead_category": cat, "place_count": n,
            "lat": lat, "lng": lng, "place_keys": keys,
        })
    return out


def trip_places(conn: sqlite3.Connection, trip_id: int) -> list[str]:
    return [
        r[0] for r in conn.execute(
            "SELECT place_key FROM trip_places WHERE trip_id=?", (trip_id,)
        )
    ]
