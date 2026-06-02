import json

import click

from . import query
from .db import connect, init_schema
from .ingest import run_all


@click.group()
@click.option("--db", default="querencia.db", help="Path to the SQLite database.")
@click.pass_context
def cli(ctx, db):
    ctx.ensure_object(dict)
    conn = connect(db)
    init_schema(conn)
    ctx.obj["conn"] = conn


@cli.command()
@click.argument("takeout_zip")
@click.pass_context
def ingest(ctx, takeout_zip):
    summary = run_all(ctx.obj["conn"], takeout_zip)
    for k, v in summary.items():
        click.echo(f"{k}: {v}")


@cli.command()
@click.pass_context
def enrich(ctx):
    from .enrich import GoogleClient, enrich_places
    try:
        n = enrich_places(ctx.obj["conn"], GoogleClient())
        click.echo(f"enriched: {n}")
    except KeyError:
        click.echo("GOOGLE_PLACES_API_KEY not set; skipping enrichment.")


@cli.command()
@click.pass_context
def embed(ctx):
    from .embed import Embedder, build_index
    n = build_index(ctx.obj["conn"], Embedder())
    click.echo(f"indexed: {n}")


@cli.command()
@click.option("--theme", default=None)
@click.option("--year", default=None, type=int)
@click.option("--trip", default=None, type=int, help="Scope to a detected trip id.")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def story(ctx, theme, year, trip, as_json):
    data = query.narrative(ctx.obj["conn"], theme=theme, year=year, trip_id=trip)
    if as_json:
        click.echo(json.dumps(data, indent=2))
        return
    from .synth_llm import make_client, render_prose
    try:
        client = make_client()
    except KeyError:
        click.echo(json.dumps(data, indent=2))
        return
    click.echo(render_prose(client, f"Tell the story of my {theme or 'places'}", data))


@cli.command()
@click.argument("question")
@click.option("--json", "as_json", is_flag=True)
@click.option("--hops", default=0, type=int, help="Expand vector hits by N graph hops.")
@click.pass_context
def ask(ctx, question, as_json, hops):
    from .embed import Embedder
    results = query.recall(ctx.obj["conn"], question, Embedder(), k=10, expand_hops=hops)
    if as_json:
        click.echo(json.dumps(results, indent=2))
        return
    from .synth_llm import make_client, render_prose
    try:
        client = make_client()
    except KeyError:
        click.echo(json.dumps(results, indent=2))
        return
    click.echo(render_prose(client, question, {"candidates": results}))


@cli.command()
@click.argument("city")
@click.pass_context
def taste(ctx, city):
    click.echo(json.dumps(query.taste(ctx.obj["conn"], city), indent=2))


@cli.command()
@click.option("--rebuild", is_flag=True, help="Re-detect and replace stored trips.")
@click.pass_context
def trips(ctx, rebuild):
    from . import trips as t
    conn = ctx.obj["conn"]
    if rebuild or not conn.execute("SELECT 1 FROM trips LIMIT 1").fetchone():
        n = t.materialize_trips(conn)
        click.echo(json.dumps({"detected": n, "trips": t.list_trips(conn)}, indent=2))
        return
    click.echo(json.dumps(t.list_trips(conn), indent=2))


@cli.command()
@click.argument("city")
@click.option("--top", default=5, type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def recommend(ctx, city, top, as_json):
    from .embed import LazyEmbedder
    from .taste import recommend as _recommend
    results = _recommend(ctx.obj["conn"], LazyEmbedder(), city, top=top)
    if as_json or not results:
        click.echo(json.dumps(results, indent=2))
        return
    from .synth_llm import make_client, render_prose
    try:
        client = make_client()
    except KeyError:
        click.echo(json.dumps(results, indent=2))
        return
    click.echo(render_prose(client, f"What should I do in {city}?", {"recommendations": results}))


@cli.command()
@click.option("--viz", "viz_path", default=None, help="Write standalone HTML viz to this path.")
@click.option("--top", default=10, type=int, help="Top-N PageRank places to report.")
@click.option("--no-derived", is_flag=True, help="Disable co-visit and semantic edges.")
@click.pass_context
def graph(ctx, viz_path, top, no_derived):
    from . import graph as g
    conn = ctx.obj["conn"]
    if viz_path:
        _write_viz(conn, viz_path, include_derived=not no_derived)
        click.echo(f"wrote: {viz_path}")
        return
    G = g.build_graph(conn, include_derived=not no_derived)
    click.echo(json.dumps({
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "pagerank": g.pagerank(conn, k=top),
        "communities": g.communities(conn),
    }, indent=2))


def _write_viz(conn, path: str, *, include_derived: bool = True) -> None:
    from pyvis.network import Network
    from . import graph as g
    G = g.build_graph(conn, include_derived=include_derived)
    ranks = {r["place_key"]: r["score"] for r in g.pagerank(conn, k=10**6)}
    comms = g.communities(conn)
    comm_of = {key: i for i, c in enumerate(comms) for key in c}
    net = Network(height="800px", width="100%", directed=True, notebook=False)
    net.barnes_hut()
    for key, attrs in G.nodes(data=True):
        label = attrs.get("name") or key
        title = f"{label}\n{attrs.get('category') or ''}\n{attrs.get('country_code') or ''}"
        size = 10 + 200 * ranks.get(key, 0)
        net.add_node(key, label=label, title=title, group=comm_of.get(key, 0), value=size)
    for src, dst, data in G.edges(data=True):
        net.add_edge(src, dst, title=data.get("travel_mode") or "")
    net.write_html(path, notebook=False, open_browser=False)


if __name__ == "__main__":
    cli()
