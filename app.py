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
