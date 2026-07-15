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
    "download anything you want to keep. Generating a route with a name "
    "that already exists overwrites the previous route file."
)

if st.button("Generate"):
    # Clear any previously generated result before attempting a new one, so a
    # failed re-generation doesn't leave a stale success block on screen.
    st.session_state.pop("generated", None)

    name = route_name.strip()
    stops = [line.strip() for line in addresses_text.splitlines() if line.strip()]

    if not name:
        st.error("Route name cannot be empty.")
    elif len(stops) < 2:
        st.error(f"Enter at least 2 non-empty addresses, got {len(stops)}.")
    else:
        slug = slugify(name)
        route_path = ROUTES_DIR / f"{slug}.json"

        # Back up any previously existing route file with this name so it can
        # be restored if generation fails - overwriting should never leave the
        # user worse off than before they clicked Generate.
        previous_route_bytes = (
            route_path.read_bytes() if route_path.exists() else None
        )

        ROUTES_DIR.mkdir(parents=True, exist_ok=True)
        route_path.write_text(json.dumps({"name": name, "stops": stops}, indent=2))

        try:
            route = load_route(route_path)
            result = generate(
                route, output_dir=str(OUTPUT_DIR), cache_path=str(CACHE_PATH)
            )
        except GeocodeError as exc:
            if previous_route_bytes is not None:
                route_path.write_bytes(previous_route_bytes)
            else:
                route_path.unlink(missing_ok=True)
            st.error(str(exc))
        except OSError as exc:
            st.error(f"Cannot write output files: {exc}")
        else:
            # Store the result (and file bytes) in session state so the
            # summary/links/downloads below survive reruns triggered by
            # clicking a download button, letting the user download
            # several files in a row instead of the section disappearing
            # after the first click.
            st.session_state["generated"] = {
                "route_name": result.route_name,
                "stop_count": result.stop_count,
                "links": result.links,
                "route_json": {
                    "file_name": route_path.name,
                    "data": route_path.read_bytes(),
                },
                "gpx": {
                    "file_name": result.gpx_path.name,
                    "data": result.gpx_path.read_bytes(),
                },
                "link_files": [
                    {"file_name": link_path.name, "data": link_path.read_bytes()}
                    for link_path in result.link_paths
                ],
            }

generated = st.session_state.get("generated")
if generated:
    st.success(
        f"Route '{generated['route_name']}': {generated['stop_count']} stops generated."
    )

    st.subheader("Google Maps links")
    links = generated["links"]
    if len(links) == 1:
        st.markdown(f"[Open in Google Maps]({links[0]})")
    else:
        for i, link in enumerate(links, start=1):
            st.markdown(f"[Leg {i}]({link})")

    st.subheader("Download files")
    st.download_button(
        "Download route JSON",
        data=generated["route_json"]["data"],
        file_name=generated["route_json"]["file_name"],
        mime="application/json",
        key="download_route_json",
    )
    st.download_button(
        "Download GPX file",
        data=generated["gpx"]["data"],
        file_name=generated["gpx"]["file_name"],
        mime="application/gpx+xml",
        key="download_gpx",
    )
    for link_file in generated["link_files"]:
        st.download_button(
            f"Download {link_file['file_name']}",
            data=link_file["data"],
            file_name=link_file["file_name"],
            mime="text/plain",
            key=f"download_{link_file['file_name']}",
        )
