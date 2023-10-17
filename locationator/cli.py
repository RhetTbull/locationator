"""CLI for Locationator to get reverse geolocation for a lat/lon pair."""

from __future__ import annotations

import json
import pathlib
import plistlib
from typing import Any

import click
import httpx
from exiftool import ExifTool, get_exiftool_path

# Do not update __version__ manually. Use bump2version.
__version__ = "0.0.6"


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
    """Lookup the reverse geolocation for a lat/lon pair.

    Note: if you need to pass a negative latitude or longitude, you must use the -- flag to
    prevent the command line parser from interpreting the value as an option.
    This is the standard behavior for most command line tools.

    For example:

    locationator lookup -- 33.953636 -118.33895

    """
    port = get_port(ctx)
    indent = get_indent(indent, no_indent)

    results = reverse_geocode(latitude, longitude, port)
    if results:
        click.echo(json.dumps(results, indent=indent))
    else:
        click.echo("Error: Could not get reverse geolocation", err=True)
        raise click.Abort()


@cli.command(name="from-exif")
@click.option("--indent", "-i", type=int, help="Indentation level for JSON output")
@click.option("--no-indent", "-I", is_flag=True, help="Do not indent JSON output")
@click.argument("filename", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def from_exif(ctx: click.Context, indent: int, no_indent: bool, filename: str):
    """Lookup the reverse geolocation for an image/video file using the
    latitude/longitude from the file's metadata.

    Requires exiftool (https://exiftool.org/) be installed and on your PATH.

    """

    try:
        get_exiftool_path()
    except FileNotFoundError as e:
        click.echo(e, err=True)
        raise click.Abort()

    port = get_port(ctx)
    indent = get_indent(indent, no_indent)

    exiftool = ExifTool(filename)
    metadata = exiftool.asdict()

    latitude = metadata.get("Composite:GPSLatitude")
    longitude = metadata.get("Composite:GPSLongitude")

    if latitude is None or longitude is None:
        click.echo("Error: Could not find GPS latitude/longitude in metadata", err=True)
        raise click.Abort()

    latitude = float(latitude)
    longitude = float(longitude)

    results = reverse_geocode(latitude, longitude, port)
    if results:
        click.echo(json.dumps(results, indent=indent))
    else:
        click.echo("Error: Could not get reverse geolocation", err=True)
        raise click.Abort()


@cli.command(name="write-xmp")
@click.option("--indent", "-i", type=int, help="Indentation level for JSON output")
@click.option("--no-indent", "-I", is_flag=True, help="Do not indent JSON output")
@click.argument("filename", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def write_xmp(ctx: click.Context, indent: int, no_indent: bool, filename: str):
    """Write the reverse geocode results to the file's XMP metadata after performing
    a lookup with the latitude/longitude found in the file's metadata with exiftool.

    Requires exiftool (https://exiftool.org/) be installed and on your PATH.

    The following XMP fields are written (parentheses indicate the corresponding
    reverse geocode result field):

    \b
    - XMP:CountryCode (ISOcountryCode)
    - XMP:Country (country)
    - XMP:State (administrativeArea)
    - XMP:City (locality)
    - XMP:Location (name)

    """

    try:
        get_exiftool_path()
    except FileNotFoundError as e:
        click.echo(e, err=True)
        raise click.Abort("Error: Could not find exiftool")

    port = get_port(ctx)
    indent = get_indent(indent, no_indent)

    exiftool = ExifTool(filename)
    metadata = exiftool.asdict()

    latitude = metadata.get("Composite:GPSLatitude")
    longitude = metadata.get("Composite:GPSLongitude")

    if latitude is None or longitude is None:
        click.echo("Error: Could not find GPS latitude/longitude in metadata", err=True)
        raise click.Abort()

    latitude = float(latitude)
    longitude = float(longitude)

    results = reverse_geocode(latitude, longitude, port)
    if not results:
        click.echo("Error: Could not get reverse geolocation", err=True)
        raise click.Abort()

    xmp = write_xmp_metadata(filename, results)
    click.echo(f"Wrote the following XMP metadata to {filename}:")
    for key, value in xmp.items():
        click.echo(f"{key}: {value}")


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
                f"Error: Could not connect to server on port {port}. Is Locationator.app running?",
                err=True,
            )
            return {}


def write_xmp_metadata(filename: str, results: dict[str, Any]) -> dict[str, Any]:
    """Write reverse geolocation-related fields to file metadata using exiftool

    Args:
        filename (str): Path to file
        results (dict): Reverse geocode results

    Note: The following XMP fields are written (parentheses indicate the corresponding
    reverse geocode result field):

    - XMP:CountryCode (ISOcountryCode)
    - XMP:Country (country)
    - XMP:State (administrativeArea)
    - XMP:City (locality)
    - XMP:Location (name)
    """

    metadata = {
        "XMP:CountryCode": results["ISOcountryCode"],
        "XMP:Country": results["country"],
        "XMP:State": results["administrativeArea"],
        "XMP:City": results["locality"],
        "XMP:Location": results["name"],
        # "XMP-iptcExt:LocationCreatedSublocation": results["subLocality"],
    }

    with ExifTool(filename) as exiftool:
        for key, value in metadata.items():
            exiftool.setvalue(key, value)

    return metadata


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


def get_port(ctx: click.Context) -> int:
    """Get the port number to connect to from command line or config file"""
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(e, err=True)
        config = {}

    return ctx.obj["PORT"] if ctx.obj["PORT"] else config.get("port", 8000)


def get_indent(indent: int, no_indent: bool) -> int | None:
    """Return value for json indent argument"""
    if no_indent and indent is not None:
        raise click.UsageError("Cannot specify both --indent and --no-indent")

    if no_indent:
        return None

    return indent if indent is not None else 4


if __name__ == "__main__":
    cli(obj={})
