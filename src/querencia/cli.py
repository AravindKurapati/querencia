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
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def story(ctx, theme, year, as_json):
    data = query.narrative(ctx.obj["conn"], theme=theme, year=year)
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
@click.pass_context
def ask(ctx, question, as_json):
    from .embed import Embedder
    results = query.recall(ctx.obj["conn"], question, Embedder(), k=10)
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


if __name__ == "__main__":
    cli()
