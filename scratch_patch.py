import os

html_path = 'templates/dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "fetch('/api/user_map_data')"
end_marker = "});\n        });"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx) + len(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found!")
else:
    new_fetch_block = """fetch('/api/user_map_data')
                .then(r => {
                    if (!r.ok) throw new Error('API error: ' + r.status);
                    return r.json();
                })
                .then(data => {
                    console.log('[RunQuest] Map data received:', data);
                    let bounds = [];

                    // Group valid routes by user color
                    const userRoutes = {};
                    if (data.routes && data.routes.length > 0) {
                        data.routes.forEach(routeObj => {
                            const rg = routeObj.geojson;
                            if (rg && rg.geometry && rg.geometry.coordinates && rg.geometry.coordinates.length > 1) {
                                if (!userRoutes[routeObj.color]) {
                                    userRoutes[routeObj.color] = { color: routeObj.color, owner: routeObj.owner, features: [] };
                                }
                                userRoutes[routeObj.color].features.push(rg);
                            }
                        });
                    }

                    // INTVL-style: buffer each route + union all for same user = smooth organic polygon
                    Object.values(userRoutes).forEach(ud => {
                        let poly = null;
                        ud.features.forEach(line => {
                            try {
                                const buf = turf.buffer(line, 0.04, { units: 'kilometers' });
                                poly = poly ? turf.union(poly, buf) : buf;
                            } catch(e) {
                                console.warn('[RunQuest] Buffer error:', e);
                            }
                        });
                        if (poly) {
                            L.geoJSON(poly, {
                                style: {
                                    color: ud.color,
                                    weight: 3,
                                    opacity: 1.0,
                                    fillColor: ud.color,
                                    fillOpacity: 0.35
                                }
                            }).bindTooltip('Territory of ' + ud.owner, { sticky: true }).addTo(map);

                            const bb = turf.bbox(poly);
                            bounds.push([bb[1], bb[0]]);
                            bounds.push([bb[3], bb[2]]);
                        }
                    });

                    // Draw glowing GPS paths on top
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
    print("Successfully replaced fetch block with INTVL-style Turf.js logic.")
