import os

html_path = 'templates/dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove Turf.js script
content = content.replace('<script src="https://cdn.jsdelivr.net/npm/@turf/turf@6/turf.min.js"></script>', '')

# Replace fetch block
start_marker = "fetch('/api/user_map_data')"
end_marker = "});\n        });"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx) + len(end_marker)

new_fetch_block = """fetch('/api/user_map_data')
                .then(r => {
                    if (!r.ok) throw new Error('API error: ' + r.status);
                    return r.json();
                })
                .then(data => {
                    console.log('[RunQuest] Map data received:', data);
                    let bounds = [];

                    // 1. Draw territories (Actual polygons from backend)
                    if (data.cells && data.cells.length > 0) {
                        data.cells.forEach(t => {
                            if (t.geojson) {
                                try {
                                    const geoJsonLayer = L.geoJSON(t.geojson, {
                                        style: {
                                            color: t.color,
                                            weight: 3,
                                            opacity: 1.0,
                                            fillColor: t.color,
                                            fillOpacity: 0.35
                                        }
                                    }).bindTooltip('Territory of ' + t.owner, { sticky: true }).addTo(map);
                                    
                                    const layerBounds = geoJsonLayer.getBounds();
                                    if (layerBounds.isValid()) {
                                        bounds.push(layerBounds.getSouthWest());
                                        bounds.push(layerBounds.getNorthEast());
                                    }
                                } catch(e) {
                                    console.warn('[RunQuest] Error rendering territory polygon:', e);
                                }
                            }
                        });
                    }

                    // 2. Draw glowing GPS paths on top
                    if (data.routes && data.routes.length > 0) {
                        data.routes.forEach(routeObj => {
                            try {
                                const rg = routeObj.geojson;
                                if (rg && rg.geometry && rg.geometry.coordinates && rg.geometry.coordinates.length > 0) {
                                    const ll = rg.geometry.coordinates.map(c => [c[1], c[0]]);
                                    L.polyline(ll, {
                                        color: routeObj.color, weight: 4, opacity: 1.0,
                                        lineCap: 'round', lineJoin: 'round', className: 'glow-path'
                                    }).bindTooltip('Run by ' + routeObj.owner).addTo(map);
                                    ll.forEach(p => bounds.push(p));
                                }
                            } catch(e) {
                                console.warn('[RunQuest] Route error:', e);
                            }
                        });
                    }

                    if (bounds.length > 0) {
                        map.fitBounds(bounds, { padding: [30, 30] });
                    } else {
                        {% if current_user.last_lat and current_user.last_lng %}
                        map.setView([{{ current_user.last_lat }}, {{ current_user.last_lng }}], 14);
                        {% else %}
                        map.setView([20, 0], 2);
                        {% endif %}
                    }
                })
                .catch(err => {
                    console.error('[RunQuest] Failed to load map data:', err);
                });
        });"""

new_content = content[:start_idx] + new_fetch_block + content[end_idx:]
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("dashboard.html refactored.")
