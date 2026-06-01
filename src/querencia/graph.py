"""NetworkX-backed analytics over places + transitions.

Read-only. Builds an in-memory graph from SQLite on each call; cheap at the
sizes querencia targets (hundreds to low thousands of places).
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

import networkx as nx


def build_graph(
    conn: sqlite3.Connection,
    *,
    include_derived: bool = True,
    covisit_hours: float = 24.0,
    semantic_k: int = 3,
) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for row in conn.execute(
        "SELECT place_key, canonical_name, category, country_code, lat, lng FROM places"
    ):
        key, name, category, cc, lat, lng = row
        g.add_node(
            key,
            name=name,
            category=category,
            country_code=cc,
            lat=lat,
            lng=lng,
        )
    for src, dst, mode in conn.execute(
        "SELECT from_place_key, to_place_key, travel_mode FROM transitions "
        "WHERE from_place_key IS NOT NULL AND to_place_key IS NOT NULL"
    ):
        if src in g and dst in g:
            g.add_edge(src, dst, kind="transition", travel_mode=mode)
    if include_derived:
        for src, dst in _covisit_edges(conn, hours=covisit_hours):
            if src in g and dst in g:
                g.add_edge(src, dst, kind="co_visit")
        for src, dst in _semantic_edges(conn, k=semantic_k):
            if src in g and dst in g:
                g.add_edge(src, dst, kind="semantic")
    return g


def _covisit_edges(conn: sqlite3.Connection, *, hours: float) -> list[tuple[str, str]]:
    """Edges between places whose events fall within `hours` of each other."""
    rows = conn.execute(
        """
        SELECT place_key, reviewed_at AS t FROM reviews WHERE reviewed_at IS NOT NULL
        UNION ALL
        SELECT place_key, taken_at FROM photos WHERE taken_at IS NOT NULL
        UNION ALL
        SELECT place_key, occurred_at FROM visits WHERE occurred_at IS NOT NULL
        """
    ).fetchall()
    from datetime import datetime
    events = []
    for key, t in rows:
        try:
            events.append((key, datetime.fromisoformat(str(t).replace("Z", "+00:00"))))
        except (ValueError, TypeError):
            continue
    events.sort(key=lambda e: e[1])
    out: set[tuple[str, str]] = set()
    window = hours * 3600
    for i, (k1, t1) in enumerate(events):
        for j in range(i + 1, len(events)):
            k2, t2 = events[j]
            if (t2 - t1).total_seconds() > window:
                break
            if k1 != k2:
                a, b = sorted([k1, k2])
                out.add((a, b))
    return list(out)


def _semantic_edges(conn: sqlite3.Connection, *, k: int) -> list[tuple[str, str]]:
    """Top-k vector neighbors per place become undirected edges (deduped)."""
    keys = [r[0] for r in conn.execute("SELECT place_key FROM place_vec")]
    if len(keys) < 2:
        return []
    out: set[tuple[str, str]] = set()
    for key in keys:
        vec_row = conn.execute(
            "SELECT embedding FROM place_vec WHERE place_key=?", (key,)
        ).fetchone()
        if not vec_row:
            continue
        neighbors = conn.execute(
            "SELECT place_key FROM place_vec "
            "WHERE embedding MATCH ? AND k=? "
            "ORDER BY distance",
            (vec_row[0], k + 1),
        ).fetchall()
        for (nk,) in neighbors:
            if nk == key:
                continue
            a, b = sorted([key, nk])
            out.add((a, b))
    return list(out)


def pagerank(conn: sqlite3.Connection, k: int = 10) -> list[dict]:
    g = build_graph(conn)
    if g.number_of_nodes() == 0:
        return []
    scores = nx.pagerank(g)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
    out = []
    for key, score in ranked:
        attrs = g.nodes[key]
        out.append({
            "place_key": key,
            "name": attrs.get("name"),
            "category": attrs.get("category"),
            "country_code": attrs.get("country_code"),
            "score": round(score, 6),
        })
    return out


def communities(conn: sqlite3.Connection) -> list[list[str]]:
    g = build_graph(conn)
    if g.number_of_nodes() == 0:
        return []
    undirected = nx.Graph(g)
    if undirected.number_of_edges() == 0:
        return [[n] for n in undirected.nodes()]
    comms = nx.community.greedy_modularity_communities(undirected)
    return [sorted(c) for c in comms]


def expand_hops(
    conn: sqlite3.Connection, seed_keys: Iterable[str], hops: int = 1
) -> set[str]:
    if hops <= 0:
        return set(seed_keys)
    g = build_graph(conn)
    undirected = nx.Graph(g)
    reached: set[str] = set()
    for seed in seed_keys:
        if seed not in undirected:
            reached.add(seed)
            continue
        lengths = nx.single_source_shortest_path_length(
            undirected, seed, cutoff=hops
        )
        reached.update(lengths.keys())
    return reached
