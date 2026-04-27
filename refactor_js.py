import os

js_path = 'static/js/run_tracker.js'
with open(js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove Geohash encoding logic inside watchPosition
if "if (typeof Geohash !== 'undefined') {" in content:
    lines = content.split('\n')
    new_lines = []
    skip = False
    for line in lines:
        if "if (typeof Geohash !== 'undefined') {" in line:
            skip = True
        if skip and line.strip() == "}":
            skip = False
            continue
        if not skip:
            new_lines.append(line)
    content = '\n'.join(new_lines)

# Remove captureTerritory and loadGlobalTerritories entirely and replace with loadGlobalTerritories for polygons
start_idx = content.find("let drawnRectangles = {};")
if start_idx != -1:
    new_tail = """let drawnPolygons = [];

async function loadGlobalTerritories() {
    try {
        const response = await fetch('/api/user_map_data');
        const data = await response.json();
        
        if (data.cells && data.cells.length > 0) {
            data.cells.forEach(t => {
                if (t.geojson) {
                    L.geoJSON(t.geojson, {
                        style: {
                            color: t.color,
                            weight: 2,
                            fillOpacity: 0.35,
                            fillColor: t.color
                        }
                    }).bindTooltip('Territory of ' + t.owner).addTo(map);
                }
            });
        }
    } catch (e) {
        console.error("Failed to load global territories", e);
    }
}

// Load global territories when page loads
loadGlobalTerritories();
"""
    content = content[:start_idx] + new_tail

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("run_tracker.js refactored.")
