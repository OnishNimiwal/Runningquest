import os

app_path = 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "@app.route('/api/save_run', methods=['POST'])"
end_marker = "def fix_territories():"

start_idx = content.find(start_marker)
end_idx = content.find("if __name__ == '__main__':", start_idx)

new_routes = """@app.route('/api/save_run', methods=['POST'])
@login_required
def save_run():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    from models import Run, Territory, User
    from utils.territory import create_polygon_from_route, merge_territories, subtract_territory, geojson_to_shapely, shapely_to_geojson, calculate_area
    from datetime import datetime
    
    route_str = data.get('route_data', '{}')
    new_run = Run(
        user_id=current_user.id,
        distance=data.get('distance', 0.0),
        duration=data.get('duration', 0),
        route_data=route_str
    )
    db.session.add(new_run)
    
    if current_user.is_suspicious_run:
        db.session.commit()
        return jsonify({'success': True, 'run_id': new_run.id, 'message': 'Run saved but anti-cheat flag active. No territory gained.'}), 201

    # 1. Convert run to Polygon
    new_poly = create_polygon_from_route(route_str)
    if not new_poly:
        db.session.commit()
        return jsonify({'success': True, 'run_id': new_run.id, 'message': 'Run saved but not enough data for territory.'}), 201

    # 2. Get current user's territory and merge
    user_terr = Territory.query.filter_by(user_id=current_user.id).first()
    if user_terr and user_terr.geojson:
        existing_poly = geojson_to_shapely(user_terr.geojson)
        merged_poly = merge_territories(existing_poly, new_poly)
    else:
        merged_poly = new_poly
        if not user_terr:
            user_terr = Territory(user_id=current_user.id)
            db.session.add(user_terr)

    user_terr.geojson = shapely_to_geojson(merged_poly)
    user_terr.area_sqkm = calculate_area(merged_poly)
    user_terr.last_updated = datetime.utcnow()
    current_user.score = int(user_terr.area_sqkm * 100000) # update score based on area

    # 3. Subtract from opponents
    opponents = Territory.query.filter(Territory.user_id != current_user.id).all()
    for opp in opponents:
        if opp.geojson:
            opp_poly = geojson_to_shapely(opp.geojson)
            if opp_poly and merged_poly and opp_poly.intersects(merged_poly):
                diff_poly = subtract_territory(opp_poly, new_poly) # subtract only the new run area
                opp.geojson = shapely_to_geojson(diff_poly)
                opp.area_sqkm = calculate_area(diff_poly)
                
                opp_user = User.query.get(opp.user_id)
                if opp_user:
                    opp_user.score = int(opp.area_sqkm * 100000)

    current_user.last_active = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'run_id': new_run.id, 'area': user_terr.area_sqkm}), 201


@app.route('/api/user_map_data', methods=['GET'])
@login_required
def user_map_data():
    from models import Territory, Run, User
    import json

    # Get all territories globally
    territories = db.session.query(Territory, User).join(User, Territory.user_id == User.id).all()
    cells_data = [] # keeping name for compatibility with frontend mapping
    for t, u in territories:
        if t.geojson:
            try:
                cells_data.append({
                    'geojson': json.loads(t.geojson),
                    'color': u.color,
                    'owner': u.username
                })
            except:
                pass

    # Get recent runs for glowing path
    runs_data = db.session.query(Run, User).join(User, Run.user_id == User.id).order_by(Run.date.desc()).limit(50).all()
    routes = []
    for r, u in runs_data:
        if r.route_data:
            try:
                routes.append({
                    'geojson': json.loads(r.route_data),
                    'color': u.color,
                    'owner': u.username
                })
            except:
                pass

    return jsonify({
        'color': current_user.color,
        'cells': cells_data, # This now contains actual polygon geojson, not cell IDs
        'routes': routes
    }), 200

@app.route('/api/debug_map')
@login_required
def debug_map():
    from models import Territory, Run
    runs = Run.query.filter_by(user_id=current_user.id).all()
    user_terr = Territory.query.filter_by(user_id=current_user.id).first()
    
    return jsonify({
        'username': current_user.username,
        'color': current_user.color,
        'total_runs': len(runs),
        'territory_area': user_terr.area_sqkm if user_terr else 0.0,
        'has_geojson': bool(user_terr and user_terr.geojson)
    }), 200

@app.route('/api/fix_territories')
def fix_territories():
    from models import Run, Territory, User
    from utils.territory import create_polygon_from_route, merge_territories, subtract_territory, geojson_to_shapely, shapely_to_geojson, calculate_area
    from datetime import datetime
    
    # 1. Clear all existing territories
    db.session.query(Territory).delete()
    db.session.commit()
    
    # 2. Re-process all runs sequentially (oldest to newest)
    runs = Run.query.order_by(Run.date.asc()).all()
    processed = 0
    for run in runs:
        if not run.route_data: continue
        
        new_poly = create_polygon_from_route(run.route_data)
        if not new_poly: continue
            
        user_terr = Territory.query.filter_by(user_id=run.user_id).first()
        if user_terr and user_terr.geojson:
            existing_poly = geojson_to_shapely(user_terr.geojson)
            merged_poly = merge_territories(existing_poly, new_poly)
        else:
            merged_poly = new_poly
            if not user_terr:
                user_terr = Territory(user_id=run.user_id)
                db.session.add(user_terr)
                
        user_terr.geojson = shapely_to_geojson(merged_poly)
        user_terr.area_sqkm = calculate_area(merged_poly)
        user_terr.last_updated = datetime.utcnow()
        
        user = User.query.get(run.user_id)
        if user:
            user.score = int(user_terr.area_sqkm * 100000)

        # Subtract from others
        opponents = Territory.query.filter(Territory.user_id != run.user_id).all()
        for opp in opponents:
            if opp.geojson:
                opp_poly = geojson_to_shapely(opp.geojson)
                if opp_poly and merged_poly and opp_poly.intersects(merged_poly):
                    diff_poly = subtract_territory(opp_poly, new_poly)
                    opp.geojson = shapely_to_geojson(diff_poly)
                    opp.area_sqkm = calculate_area(diff_poly)
                    opp_user = User.query.get(opp.user_id)
                    if opp_user:
                        opp_user.score = int(opp.area_sqkm * 100000)
        
        processed += 1
        db.session.commit() # Commit each step to persist state for next run
        
    return f"Successfully wiped and rebuilt {processed} run territories into the new Polygon system!"

"""

new_content = content[:start_idx] + new_routes + content[end_idx:]
with open(app_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("app.py rewritten successfully.")
