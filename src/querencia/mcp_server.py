import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from mcp.server.fastmcp import FastMCP

from . import query
from .db import connect, init_schema

DB_PATH = os.environ.get("QUERENCIA_DB", "querencia.db")


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Open a schema-initialized connection and always close it.

    The server is long-lived and handles one tool call after another, so a
    connection opened per call must be closed per call — otherwise SQLite
    connections (and their file handles) accumulate for the life of the process.
    """
    conn = connect(DB_PATH)
    try:
        init_schema(conn)
        yield conn
    finally:
        conn.close()


def _narrative_tool(conn, theme=None, year=None, trip_id=None) -> dict:
    return query.narrative(conn, theme=theme, year=year, trip_id=trip_id)


def _patterns_tool(conn, kind="categories") -> dict:
    return query.patterns(conn, kind=kind)


def _recall_tool(conn, question, k=10) -> list[dict]:
    from .embed import Embedder
    return query.recall(conn, question, Embedder(), k=k)


def _taste_tool(conn, city) -> dict:
    return query.taste(conn, city)


def _trips_tool(conn, rebuild=False) -> list[dict]:
    from . import trips as t
    has_any = conn.execute("SELECT 1 FROM trips LIMIT 1").fetchone()
    if rebuild or not has_any:
        t.materialize_trips(conn)
    return t.list_trips(conn)


def _recommend_tool(conn, city, top=5) -> list[dict]:
    from .embed import LazyEmbedder
    from .taste import PlacesClient, recommend
    try:
        client = PlacesClient()
    except KeyError:
        client = None
    return recommend(conn, LazyEmbedder(), city, client=client, top=top)


mcp = FastMCP("querencia")


@mcp.tool()
def querencia_narrative(
    theme: str | None = None,
    year: int | None = None,
    trip_id: int | None = None,
) -> dict:
    """Structured summary of reviewed places, optionally filtered by theme/year/trip.

    Pass ``trip_id`` (from ``querencia_trips``) to scope the narrative to a single
    detected trip — see RECIPES.md Recipe 1.
    """
    with _conn() as conn:
        return _narrative_tool(conn, theme=theme, year=year, trip_id=trip_id)


@mcp.tool()
def querencia_recall(question: str, k: int = 10) -> list[dict]:
    """Semantic recall of places matching a natural-language question."""
    with _conn() as conn:
        return _recall_tool(conn, question, k=k)


@mcp.tool()
def querencia_patterns(kind: str = "categories") -> dict:
    """Aggregate patterns over reviewed places (e.g. category counts)."""
    with _conn() as conn:
        return _patterns_tool(conn, kind=kind)


@mcp.tool()
def querencia_taste(city: str) -> dict:
    """Preference profile for predicting what the user would like in a new city."""
    with _conn() as conn:
        return _taste_tool(conn, city)


@mcp.tool()
def querencia_trips(rebuild: bool = False) -> list[dict]:
    """Detected trips (spatiotemporal clusters of visits). Set rebuild=True to re-detect."""
    with _conn() as conn:
        return _trips_tool(conn, rebuild=rebuild)


@mcp.tool()
def querencia_recommend(city: str, top: int = 5) -> list[dict]:
    """Ranked place recommendations in `city` against the user's preference vector."""
    with _conn() as conn:
        return _recommend_tool(conn, city, top=top)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
