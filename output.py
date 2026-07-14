"""Write generated GPX and link files to disk, with safe filenames."""

import re
from pathlib import Path


def slugify(name: str) -> str:
    """Turn a route name into a filesystem-safe slug."""
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
