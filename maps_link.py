from urllib.parse import quote


def segment_stops(stops, max_points=10):
    """
    Segment stops into overlapping chunks.
    
    If the number of stops is within max_points, return all stops as a single chunk.
    Otherwise, split into overlapping chunks where each chunk after the first
    starts with the previous chunk's last stop (overlap of 1).
    
    Args:
        stops: List of stop addresses
        max_points: Maximum number of stops per chunk (default 10)
    
    Returns:
        List of chunks (each chunk is a list of stops)
    """
    if len(stops) <= max_points:
        return [stops]
    
    chunks = []
    start = 0
    step = max_points - 1
    
    while start < len(stops):
        end = start + max_points
        chunks.append(stops[start:end])
        start += step
    
    return chunks


def build_link(chunk):
    """
    Build a Google Maps directions link from a chunk of stops.
    
    Args:
        chunk: List of stops where first is origin, last is destination, 
               and middle ones are waypoints
    
    Returns:
        URL string for Google Maps directions
    """
    if len(chunk) < 2:
        raise ValueError("At least origin and destination are required")
    
    origin = quote(chunk[0], safe='')
    destination = quote(chunk[-1], safe='')
    
    url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin}"
        f"&destination={destination}"
        f"&travelmode=driving"
    )
    
    if len(chunk) > 2:
        # Middle stops are waypoints
        waypoints = chunk[1:-1]
        # Join waypoints with | and then URL encode the separator
        # So the final URL has %7C between waypoints
        encoded_waypoints = quote('|', safe='').join(quote(wp, safe='') for wp in waypoints)
        url += f"&waypoints={encoded_waypoints}"
    
    return url


def build_links(stops):
    """
    Build multiple Google Maps directions links for a long route.
    
    Segments the stops into overlapping chunks and builds a link for each chunk.
    
    Args:
        stops: List of stop addresses
    
    Returns:
        List of Google Maps direction URLs
    """
    chunks = segment_stops(stops)
    return [build_link(chunk) for chunk in chunks]
