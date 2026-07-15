# drive-planner

Convert a curated, ordered list of driving-tour stop addresses into formats
that are easy to share and open directly on a smartphone:

- A tappable Google Maps link (or a sequence of links for routes with more
  than ~10 stops, since Google Maps' in-app navigation reliably supports
  only that many)
- A GPX file — a reliable fallback for apps that handle long stop lists
  better (OsmAnd, Organic Maps), and importable into Google Maps too

This tool does not choose or optimize stops — you provide the final,
ordered address list, and it geocodes and packages it for sharing.

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

1. Create a route file in `resources/routes/<name>.json`:

```json
{
  "name": "My route",
  "stops": [
    "14 boulevard de Verdun, 34500 Béziers",
    "Place Jean-Jaurès, 34500 Béziers"
  ]
}
```

2. Run:

```bash
uv run python main.py resources/routes/<name>.json
```

3. Find the outputs in `output/`:
   - `<name>.gpx` — full route, all stops, for GPX-compatible apps
   - `<name>_link.txt` — a single Google Maps link (routes with ≤10 stops)
   - `<name>_leg1.txt`, `_leg2.txt`, ... — sequential Google Maps links
     (routes with more than 10 stops)

Geocoding results are cached in `.geocode_cache.json` (gitignored) to avoid
re-querying the same addresses on repeated runs.

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

## Testing

```bash
uv run pytest tests -v
```
