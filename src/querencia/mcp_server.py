import os
import sqlite3

from mcp.server.fastmcp import FastMCP

from . import query
from .db import connect, init_schema

DB_PATH = os.environ.get("QUERENCIA_DB", "querencia.db")


def _get_conn() -> sqlite3.Connection:
    conn = connect(DB_PATH)
    init_schema(conn)
    return conn


def _narrative_tool(conn, theme=None, year=None) -> dict:
    return query.narrative(conn, theme=theme, year=year)


def _patterns_tool(conn, kind="categories") -> dict:
    return query.patterns(conn, kind=kind)


def _recall_tool(conn, question, k=10) -> list[dict]:
    from .embed import Embedder
    return query.recall(conn, question, Embedder(), k=k)


def _taste_tool(conn, city) -> dict:
    return query.taste(conn, city)


mcp = FastMCP("querencia")


@mcp.tool()
def querencia_narrative(theme: str | None = None, year: int | None = None) -> dict:
    """Structured summary of reviewed places, optionally filtered by theme/year."""
    return _narrative_tool(_get_conn(), theme=theme, year=year)


@mcp.tool()
def querencia_recall(question: str, k: int = 10) -> list[dict]:
    """Semantic recall of places matching a natural-language question."""
    return _recall_tool(_get_conn(), question, k=k)


@mcp.tool()
def querencia_patterns(kind: str = "categories") -> dict:
    """Aggregate patterns over reviewed places (e.g. category counts)."""
    return _patterns_tool(_get_conn(), kind=kind)


@mcp.tool()
def querencia_taste(city: str) -> dict:
    """Preference profile for predicting what the user would like in a new city."""
    return _taste_tool(_get_conn(), city)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
