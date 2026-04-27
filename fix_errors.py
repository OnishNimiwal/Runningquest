import os

# Fix utils/territory.py
t_path = 'utils/territory.py'
with open(t_path, 'r', encoding='utf-8') as f:
    t_content = f.read()

t_content = t_content.replace('\\"\\"\\"', '"""')
t_content = t_content.replace('"""Converts a GeoJSON LineString route into a buffered Polygon."""', '"""Converts a GeoJSON LineString route into a buffered Polygon."""')
t_content = t_content.replace('"""Unions two polygons."""', '"""Unions two polygons."""')
t_content = t_content.replace('"""Subtracts subtract_poly from base_poly."""', '"""Subtracts subtract_poly from base_poly."""')
t_content = t_content.replace('"""Parses a GeoJSON string into a Shapely geometry."""', '"""Parses a GeoJSON string into a Shapely geometry."""')
t_content = t_content.replace('"""Converts a Shapely geometry back to a GeoJSON string."""', '"""Converts a Shapely geometry back to a GeoJSON string."""')

# In case it looks like `"""Converts a GeoJSON LineString route into a buffered Polygon.\"""`
t_content = t_content.replace('\\"""', '"""')

with open(t_path, 'w', encoding='utf-8') as f:
    f.write(t_content)

# Fix app.py dashboard route
app_path = 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    a_content = f.read()

# Replace the dashboard method imports and auto-seed logic which uses TerritoryEventLog and utils.grid
start_marker = "def dashboard():"
end_marker = "user_territories = Territory.query.filter_by(user_id=current_user.id).count()"

start_idx = a_content.find(start_marker)
end_idx = a_content.find(end_marker, start_idx) + len(end_marker)

new_dashboard_top = """def dashboard():
    from models import User, Territory, Run
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from utils.decay import process_user_decay

    # Step 8: Check and process territory decay
    process_user_decay(current_user)

    # Count of territories this user currently owns (for warning state)
    user_territories = Territory.query.filter_by(user_id=current_user.id).count()
"""

if start_idx != -1:
    a_content = a_content[:start_idx] + new_dashboard_top + a_content[end_idx:]

# Remove the old grid auto-seed logic in dashboard
seed_start = "if user_territories == 0:"
seed_end = "db.session.commit()"
seed_start_idx = a_content.find(seed_start)
seed_end_idx = a_content.find(seed_end, seed_start_idx) + len(seed_end)

if seed_start_idx != -1 and "all_runs = Run.query" in a_content[seed_start_idx:seed_end_idx]:
    # Replace it with a simpler check or remove it because /api/fix_territories does this now.
    a_content = a_content[:seed_start_idx] + "if user_territories == 0:\n        pass" + a_content[seed_end_idx:]


with open(app_path, 'w', encoding='utf-8') as f:
    f.write(a_content)

print("Errors fixed.")
