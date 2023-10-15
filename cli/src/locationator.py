"""CLI for Locationator to get reverse geolocation for a lat/lon pair."""

from __future__ import annotations

import json
import pathlib
import plistlib
from typing import Any

import click
import httpx

# Do not update __version__ manually. Use bump2version.
__version__ = "0.0.4"


@click.group()
@click.option("--debug", is_flag=True)
@click.option("--port", default=0, type=int)
@click.pass_context
def cli(ctx: click.Context, debug: bool, port: int):
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    ctx.obj["PORT"] = port


@cli.command()
@click.pass_context
@click.option("--indent", "-i", type=int, help="Indentation level for JSON output")
@click.option("--no-indent", "-I", is_flag=True, help="Do not indent JSON output")
@click.argument("latitude", type=float)
@click.argument("longitude", type=float)
def lookup(
    ctx: click.Context, indent: int, no_indent: bool, latitude: float, longitude: float
):
    """Lookup the reverse geolocation for a lat/lon pair."""
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(e, err=True)
        config = {}

    port = ctx.obj["PORT"] if ctx.obj["PORT"] else config.get("port", 8000)

    if no_indent and indent is not None:
        raise click.UsageError("Cannot specify both --indent and --no-indent")
    if no_indent:
        indent = None
    else:
        indent = indent if indent is not None else 4

    results = reverse_geocode(latitude, longitude, port)
    if results:
        click.echo(json.dumps(results, indent=indent))
    else:
        raise click.Abort("Error: Could not get reverse geolocation")


def reverse_geocode(latitude: float, longitude: float, port: int) -> dict[str, Any]:
    """Perform reverse geocode of latitude/longitude

    Args:
        latitude (float): Latitude
        longitude (float): Longitude
        port (int): Port number to connect to

    Returns: dict: Reverse geocode result
    """
    with httpx.Client() as client:
        try:
            response = client.get(
                f"http://localhost:{port}/reverse_geocode?latitude={latitude}&longitude={longitude}"
            )
            if response.status_code == 200:
                return response.json()
            else:
                click.echo(f"Error: {response.status_code} {response.text}", err=True)
                return {}
        except httpx.ConnectError:
            click.echo(
                f"Error: Could not connect to server on port {port}",
                err=True,
            )
            return {}


def load_config() -> dict[str, Any]:
    """Load config from the Locationator plist file"""
    plist_path = pathlib.Path(
        "~/Library/Application Support/Locationator/Locationator.plist"
    ).expanduser()
    if not plist_path.exists():
        raise FileNotFoundError(
            f"Could not find Locationator plist file at {plist_path}"
        )
    with open(plist_path, "rb") as f:
        return plistlib.load(f)


if __name__ == "__main__":
    cli(obj={})
