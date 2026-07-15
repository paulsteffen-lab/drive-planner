# Streamlit Route-Entry App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Streamlit web app (`app.py`) where a user types a route name and an ordered list of addresses, clicks Generate, and gets a `resources/routes/<slug>.json` file plus generated `.gpx`/`.txt` outputs and download buttons — deployable for free on Streamlit Community Cloud.

**Architecture:** Extract the existing geocode → GPX → Maps-link pipeline out of `main.run()` into a new `main.generate(route, output_dir, cache_path) -> GenerateResult` function that raises on failure instead of printing to stdout. `main.run()` becomes a thin CLI wrapper around `generate()` (no behavior change — existing tests must keep passing unmodified). `app.py` calls `route.load_route()` and `main.generate()` directly and renders results with Streamlit widgets.

**Tech Stack:** Python 3.13, Streamlit, existing `geopy`/`gpxpy` pipeline, `uv` for dependency management, `pytest` for tests.

Spec: `docs/superpowers/specs/2026-07-15-streamlit-route-app-design.md`

---

### Task 1: Extract `generate()` from `main.run()`

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py` (existing tests must pass unchanged — no edits in this task)

- [ ] **Step 1: Write the failing test for the new `generate()` function**

First, update the imports at the top of `tests/test_main.py` to:

```python
import json

import pytest

import geocode
import main
from route import load_route
```

Then add these test functions (after the existing imports, before the
first test function):

```python
def test_generate_short_route_creates_gpx_and_single_link_file(tmp_path):
    route_path = tmp_path / "route.json"
    route_path.write_text(
        json.dumps({"name": "Short Loop", "stops": ["Addr A", "Addr B", "Addr C"]})
    )
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"
    route = load_route(route_path)

    result = main.generate(route, output_dir=str(output_dir), cache_path=str(cache_path))

    assert result.route_name == "Short Loop"
    assert result.stop_count == 3
    assert result.gpx_path == output_dir / "short_loop.gpx"
    assert result.link_paths == [output_dir / "short_loop_link.txt"]
    assert len(result.links) == 1
    assert result.links[0].startswith("https://www.google.com/maps/dir/?api=1")


def test_generate_long_route_creates_multiple_legs(tmp_path):
    stops = [f"Stop {i}" for i in range(20)]
    route_path = tmp_path / "route.json"
    route_path.write_text(json.dumps({"name": "Long Loop", "stops": stops}))
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"
    route = load_route(route_path)

    result = main.generate(route, output_dir=str(output_dir), cache_path=str(cache_path))

    assert len(result.link_paths) == 3
    assert len(result.links) == 3
    assert result.gpx_path.exists()


def test_generate_raises_geocode_error_and_cleans_up_partial_output(tmp_path, monkeypatch):
    route_path = tmp_path / "route.json"
    route_path.write_text(
        json.dumps({"name": "Short Loop", "stops": ["Addr A", "Addr B", "Addr C"]})
    )
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"
    route = load_route(route_path)

    def failing_write_link_files(links, name_slug, out_dir):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(main, "write_link_files", failing_write_link_files)

    with pytest.raises(OSError, match="simulated disk failure"):
        main.generate(route, output_dir=str(output_dir), cache_path=str(cache_path))

    assert not (output_dir / "short_loop.gpx").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_main.py -v -k test_generate`
Expected: FAIL with `AttributeError: module 'main' has no attribute 'generate'`

- [ ] **Step 3: Implement `generate()` and refactor `run()` to use it**

Replace the full contents of `main.py` with:

```python
"""CLI entrypoint: convert a route JSON file into shareable outputs.

Usage:
    uv run python main.py <route_json_path> [output_dir]
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from geocode import GeocodeError, Geocoder
from gpx import build_gpx
from maps_link import build_links
from output import slugify, write_gpx_file, write_link_files
from route import Route, RouteError, load_route


@dataclass
class GenerateResult:
    route_name: str
    stop_count: int
    gpx_path: Path
    link_paths: list[Path]
    links: list[str]


def generate(
    route: Route,
    output_dir: str = "output",
    cache_path: str = ".geocode_cache.json",
) -> GenerateResult:
    """Run the geocode -> GPX -> Maps-link pipeline for an already-loaded Route.

    Raises GeocodeError if an address cannot be geocoded, or OSError if the
    output files cannot be written. On OSError, any partially-written output
    files for this route are removed before re-raising, so a failed run
    never leaves misleading artifacts behind.
    """
    geocoder = Geocoder(cache_path=cache_path)
    geocoded_stops = geocoder.geocode_all(route.stops)

    name_slug = slugify(route.name)
    output_path = Path(output_dir)

    try:
        gpx_xml = build_gpx(geocoded_stops)
        gpx_path = write_gpx_file(gpx_xml, name_slug, output_path)

        links = build_links(route.stops)
        link_paths = write_link_files(links, name_slug, output_path)
    except OSError:
        for stray in output_path.glob(f"{name_slug}*"):
            stray.unlink(missing_ok=True)
        raise

    return GenerateResult(
        route_name=route.name,
        stop_count=len(route.stops),
        gpx_path=gpx_path,
        link_paths=link_paths,
        links=links,
    )


def run(
    route_path: str,
    output_dir: str = "output",
    cache_path: str = ".geocode_cache.json",
) -> int:
    try:
        route = load_route(route_path)
    except RouteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        result = generate(route, output_dir=output_dir, cache_path=cache_path)
    except GeocodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: Cannot write output files: {exc}", file=sys.stderr)
        return 1

    print(f"Route '{result.route_name}': {result.stop_count} stops")
    print(f"  GPX file: {result.gpx_path}")
    if len(result.link_paths) == 1:
        print(f"  Link file: {result.link_paths[0]}")
    else:
        print(f"  Segmented into {len(result.link_paths)} legs:")
        for path in result.link_paths:
            print(f"    {path}")

    return 0


def main() -> None:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python main.py <route_json_path> [output_dir]", file=sys.stderr)
        sys.exit(1)

    output_dir = sys.argv[2] if len(sys.argv) == 3 else "output"
    sys.exit(run(sys.argv[1], output_dir=output_dir))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all of `tests/test_main.py` to verify everything passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS — all existing tests (`test_run_short_route_creates_gpx_and_single_link_file`,
`test_run_long_route_creates_gpx_and_multiple_leg_files`,
`test_run_returns_nonzero_on_invalid_route_file`,
`test_run_cleans_up_partial_output_on_write_failure`) plus the three new
`test_generate_*` tests, 7 total, PASS.

- [ ] **Step 5: Run the full test suite to make sure nothing else broke**

Run: `uv run pytest tests -v`
Expected: All tests PASS (no regressions in `test_geocode.py`, `test_gpx.py`,
`test_maps_link.py`, `test_output.py`, `test_route.py`).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "refactor: extract main.generate() from main.run()

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Add the `streamlit` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, update the `dependencies` list:

```toml
dependencies = [
    "geopy>=2.4",
    "gpxpy>=1.6",
    "streamlit>=1.38",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: Command completes successfully; `streamlit` appears in `uv.lock`.

- [ ] **Step 3: Verify Streamlit is importable**

Run: `uv run python -c "import streamlit; print(streamlit.__version__)"`
Expected: Prints a version string (e.g. `1.4x.y`), no errors.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add streamlit dependency

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Build the Streamlit app

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write `app.py`**

```python
"""Streamlit UI: enter a route name and ordered addresses, then generate
the route JSON plus shareable GPX/Maps-link files.

Run locally with:
    uv run streamlit run app.py
"""

import json
from pathlib import Path

import streamlit as st

from geocode import GeocodeError
from main import generate
from output import slugify
from route import load_route

ROUTES_DIR = Path("resources/routes")
OUTPUT_DIR = Path("output")
CACHE_PATH = Path(".geocode_cache.json")

st.title("Drive Planner")
st.write(
    "Enter a route name and the ordered list of stop addresses, then click "
    "Generate to produce a route file, a GPX file, and shareable Google "
    "Maps links."
)

route_name = st.text_input("Route name")
addresses_text = st.text_area(
    "Addresses (one per line, in the order you want to visit them)",
    height=200,
)
st.caption(
    "Generated files are written to this app's local storage, which is not "
    "guaranteed to persist across restarts on Streamlit Community Cloud — "
    "download anything you want to keep."
)

if st.button("Generate"):
    name = route_name.strip()
    stops = [line.strip() for line in addresses_text.splitlines() if line.strip()]

    if not name:
        st.error("Route name cannot be empty.")
    elif len(stops) < 2:
        st.error(f"Enter at least 2 non-empty addresses, got {len(stops)}.")
    else:
        slug = slugify(name)
        route_path = ROUTES_DIR / f"{slug}.json"

        if route_path.exists():
            st.error(
                f"A route named '{name}' already exists "
                f"({route_path}). Choose a different route name."
            )
        else:
            ROUTES_DIR.mkdir(parents=True, exist_ok=True)
            route_path.write_text(json.dumps({"name": name, "stops": stops}, indent=2))

            try:
                route = load_route(route_path)
                result = generate(
                    route, output_dir=str(OUTPUT_DIR), cache_path=str(CACHE_PATH)
                )
            except GeocodeError as exc:
                st.error(str(exc))
            except OSError as exc:
                st.error(f"Cannot write output files: {exc}")
            else:
                st.success(
                    f"Route '{result.route_name}': {result.stop_count} stops generated."
                )

                st.subheader("Google Maps links")
                if len(result.links) == 1:
                    st.markdown(f"[Open in Google Maps]({result.links[0]})")
                else:
                    for i, link in enumerate(result.links, start=1):
                        st.markdown(f"[Leg {i}]({link})")

                st.subheader("Download files")
                st.download_button(
                    "Download route JSON",
                    data=route_path.read_bytes(),
                    file_name=route_path.name,
                    mime="application/json",
                )
                st.download_button(
                    "Download GPX file",
                    data=result.gpx_path.read_bytes(),
                    file_name=result.gpx_path.name,
                    mime="application/gpx+xml",
                )
                for link_path in result.link_paths:
                    st.download_button(
                        f"Download {link_path.name}",
                        data=link_path.read_bytes(),
                        file_name=link_path.name,
                        mime="text/plain",
                    )
```

- [ ] **Step 2: Launch the app locally to smoke-test it**

Run: `uv run streamlit run app.py --server.headless true &` then
`sleep 3 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8501`
Expected: Prints `200`.

Stop the server afterwards (find and kill the `streamlit` process started
above).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit app for interactive route entry

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Update README with Streamlit usage and deployment notes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Streamlit app" section**

In `README.md`, after the existing "## Usage" section and before
"## Testing", add:

```markdown
## Streamlit app

Instead of hand-writing a route JSON file, you can use the interactive
Streamlit app:

```bash
uv run streamlit run app.py
```

Open the printed local URL, enter a route name and the ordered addresses
(one per line), and click **Generate**. This writes
`resources/routes/<name>.json` and the corresponding `.gpx`/`.txt` files
to `output/`, and offers download buttons for each.

### Deploying to Streamlit Community Cloud

1. Push this repository to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at this repo, branch, and `app.py` as the entrypoint.
3. Streamlit Cloud installs dependencies from `pyproject.toml`
   automatically via `uv`.

Note: Streamlit Cloud's filesystem is ephemeral — files written to
`resources/routes/` and `output/` during a session are not guaranteed to
persist across app restarts or redeploys. Use the download buttons to
keep anything you generate.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document Streamlit app usage and deployment

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests -v`
Expected: All tests PASS (no failures, no errors).

- [ ] **Step 2: Confirm `app.py` still starts cleanly**

Run: `uv run streamlit run app.py --server.headless true &` then
`sleep 3 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8501`
Expected: Prints `200`. Kill the background streamlit process afterwards.

- [ ] **Step 3: Confirm `main.py` CLI still works end-to-end**

Run: `uv run python main.py resources/routes/beziers_1.json /tmp/drive_planner_smoke_test`
Expected: Exit code 0, prints a summary, and
`/tmp/drive_planner_smoke_test/b_ziers_loop_1.gpx` plus at least one
`.txt` link file exist. Clean up with
`rm -rf /tmp/drive_planner_smoke_test` afterwards.
