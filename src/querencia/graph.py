"""NetworkX-backed analytics over places + transitions.

Read-only. Builds an in-memory graph from SQLite on each call; cheap at the
sizes querencia targets (hundreds to low thousands of places).
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

import networkx as nx


def build_graph(conn: sqlite3.Connection) -> nx.MultiDiGraph:
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
            g.add_edge(src, dst, travel_mode=mode)
    return g


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
