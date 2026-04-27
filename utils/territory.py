import json
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, LineString
from shapely.ops import unary_union

BUFFER_DEGREES = 0.0004  # roughly 40-45 meters depending on latitude

def create_polygon_from_route(route_geojson_str):
    \"\"\"Converts a GeoJSON LineString route into a buffered Polygon.\"\"\"
    if not route_geojson_str:
        return None
        
    try:
        route_data = json.loads(route_geojson_str)
        geom = shape(route_data.get('geometry', route_data))
        
        if geom.is_empty:
            return None
            
        # Buffer the line to create a polygon (area)
        poly = geom.buffer(BUFFER_DEGREES, resolution=4)
        return poly
    except Exception as e:
        print(f"Error creating polygon from route: {e}")
        return None

def merge_territories(poly1, poly2):
    \"\"\"Unions two polygons.\"\"\"
    if not poly1: return poly2
    if not poly2: return poly1
    try:
        merged = unary_union([poly1, poly2])
        return merged
    except Exception as e:
        print(f"Error merging territories: {e}")
        return poly1

def subtract_territory(base_poly, subtract_poly):
    \"\"\"Subtracts subtract_poly from base_poly.\"\"\"
    if not base_poly or not subtract_poly:
        return base_poly
    try:
        diff = base_poly.difference(subtract_poly)
        return diff
    except Exception as e:
        print(f"Error subtracting territory: {e}")
        return base_poly

def geojson_to_shapely(geojson_str):
    \"\"\"Parses a GeoJSON string into a Shapely geometry.\"\"\"
    if not geojson_str:
        return None
    try:
        data = json.loads(geojson_str)
        if 'geometry' in data:
            return shape(data['geometry'])
        return shape(data)
    except Exception as e:
        print(f"Error parsing geojson to shapely: {e}")
        return None

def shapely_to_geojson(geom):
    \"\"\"Converts a Shapely geometry back to a GeoJSON string.\"\"\"
    if not geom or geom.is_empty:
        return None
    try:
        # Simplify slightly to save space and remove microscopic artifacts
        geom = geom.simplify(0.00005, preserve_topology=True)
        feature = {
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {}
        }
        return json.dumps(feature)
    except Exception as e:
        print(f"Error converting shapely to geojson: {e}")
        return None

def calculate_area(geom):
    \"\"\"Rough estimate of area in square degrees. Good enough for ranking.\"\"\"
    if not geom or geom.is_empty:
        return 0.0
    return geom.area
