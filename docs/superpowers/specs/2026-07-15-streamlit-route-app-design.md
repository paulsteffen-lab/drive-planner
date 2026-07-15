# Streamlit route-entry app — design

## Purpose

Let a user interactively enter a route name and an ordered list of stop
addresses in a browser (deployable for free on Streamlit Community Cloud),
and on clicking "Generate":

1. Write `resources/routes/<slug>.json` in the existing route format.
2. Run the existing geocode → GPX → Maps-link pipeline to produce
   `output/<slug>.gpx` and the `output/<slug>_link.txt` (or
   `_leg1.txt`, `_leg2.txt`, ...) files.
3. Show a summary and let the user download the generated files.

## Non-goals

- No route optimization or stop suggestion — the user supplies the final,
  ordered address list, same as today's CLI.
- No editing/loading of previously saved routes from the UI (out of scope
  for this iteration).
- No persistent multi-user storage guarantees — Streamlit Cloud's
  filesystem is ephemeral per deployment; files written during a session
  may be lost on redeploy/restart. The UI will note this and offer
  downloads.

## Architecture

Add a new `app.py` Streamlit entrypoint at the repo root. It reuses the
existing pipeline modules (`route`, `geocode`, `gpx`, `output`,
`maps_link`) rather than duplicating logic.

To avoid parsing `main.run()`'s stdout output, refactor `main.py` to
extract the core pipeline into a new function:

```python
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
    """Run geocode -> GPX -> Maps-link pipeline for an already-loaded Route.

    Raises GeocodeError or OSError on failure. On OSError, cleans up any
    partially-written output files before re-raising, same as today.
    """
```

`main.run()` becomes a thin CLI wrapper: `load_route()`, call `generate()`,
catch `RouteError`/`GeocodeError`/`OSError`, print the existing
human-readable messages, return the existing exit codes. Its behavior and
existing tests (`tests/test_main.py`) are unaffected — same inputs, same
files written, same messages.

`app.py` calls `load_route()` (after writing the JSON file) and
`generate()` directly, and renders results/errors with `st.error` /
`st.success` instead of stdout.

## UI flow

Single page, top to bottom:

1. `st.text_input("Route name")`
2. `st.text_area("Addresses (one per line, in order)")`
3. `st.caption` note: generated files are written to the app's local
   storage, which is not guaranteed to persist across restarts on
   Streamlit Cloud — download anything you want to keep.
4. `st.button("Generate")`

On click:

1. **Validate input**: route name must be non-empty after stripping;
   addresses are split on newlines, blank lines dropped, and there must
   be ≥2 remaining. Otherwise `st.error` and stop (mirrors
   `RouteError` conditions in `route.load_route`).
2. **Compute slug**: `output.slugify(route_name)`.
3. **Check for existing route file**: if
   `resources/routes/<slug>.json` already exists, `st.error` telling the
   user to choose a different route name, and stop (no overwrite).
4. **Write route JSON**: `{"name": route_name, "stops": [...]}` to
   `resources/routes/<slug>.json`.
5. **Run pipeline**: `route.load_route(...)` then `main.generate(...)`.
   - On `GeocodeError` or `OSError`: `st.error` with the message. The
     route JSON file written in step 4 is left in place (only the
     generated output artifacts are cleaned up by `generate()`, matching
     current CLI behavior) so the user doesn't lose their input.
   - On success: `st.success` summary — route name, stop count — then:
     - The list of Google Maps links (rendered as clickable markdown
       links, labeled "Leg 1", "Leg 2", ... if more than one).
     - `st.download_button` for the route JSON, the GPX file, and each
       link/leg `.txt` file (reading bytes from disk).

## Error handling

Reuses existing exception types (`RouteError`, `GeocodeError`, `OSError`)
and existing cleanup behavior in `generate()` (formerly in `run()`). The
app never lets an unhandled exception surface — all three are caught and
shown via `st.error`.

## Files touched

- `main.py`: extract `generate()` out of `run()` (refactor, no behavior
  change for the CLI).
- `app.py` (new): Streamlit UI described above.
- `pyproject.toml`: add `streamlit` dependency.
- `README.md`: add a short "Streamlit app" usage section and Streamlit
  Cloud deployment note.
- `tests/test_main.py`: no changes needed (behavior preserved); optionally
  add a direct test for `main.generate()` if useful during implementation.

## Testing

- Existing `tests/test_main.py` must continue to pass unchanged, proving
  the refactor preserves CLI behavior.
- Add unit tests for `main.generate()` covering the short-route and
  long-route (multi-leg) cases, reusing the fake-geocoder fixture pattern
  already in `tests/test_main.py`.
- Streamlit UI interactions (`app.py`) are not unit-tested (no existing
  Streamlit-testing setup in this repo); manual verification via
  `streamlit run app.py` is sufficient for this iteration.
