import pygeohash as pgh
import json

def route_to_cells(route_geojson_str, precision=7):
    """
    Parses a GeoJSON LineString and returns a unique set of geohashes
    (grid cells) that the route covers.
    """
    cells = set()
    try:
        route_data = json.loads(route_geojson_str)
        if route_data.get('geometry', {}).get('type') == 'LineString':
            coordinates = route_data['geometry']['coordinates']
            for coord in coordinates:
                lng, lat = coord[0], coord[1]
                # Precision 7 represents approx 153m x 153m
                ghash = pgh.encode(lat, lng, precision=precision)
                cells.add(ghash)
    except Exception as e:
        print(f"Error parsing route to cells: {e}")
    
    return list(cells)
