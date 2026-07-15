"""Write generated GPX and link files to disk, with safe filenames."""

import re
from pathlib import Path


def slugify(name: str) -> str:
    """Turn a route name into a filesystem-safe slug.

    Non-alphanumeric runs (including accented/non-ASCII characters) are
    collapsed to a single underscore, and the result is lowercased.
    Falls back to "route" if nothing alphanumeric remains.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
    return slug or "route"


def write_gpx_file(gpx_xml: str, name_slug: str, output_dir: Path | str) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name_slug}.gpx"
    path.write_text(gpx_xml)
    return path


def write_link_files(
    links: list[str], name_slug: str, output_dir: Path | str
) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if len(links) == 1:
        path = output_dir / f"{name_slug}_link.txt"
        path.write_text(links[0] + "\n")
        return [path]

    paths = []
    for i, link in enumerate(links, start=1):
        path = output_dir / f"{name_slug}_leg{i}.txt"
        path.write_text(link + "\n")
        paths.append(path)
    return paths


def write_path_link_file(path_link: str, name_slug: str, output_dir: Path | str) -> Path:
    """Write the single all-stops path-format Google Maps link to a file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name_slug}_all_stops_link.txt"
    path.write_text(path_link + "\n")
    return path
