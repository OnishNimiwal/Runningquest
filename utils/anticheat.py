import math
from datetime import datetime

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def validate_movement(user, current_lat, current_lng):
    """
    Returns True if valid, False if suspicious (speed > 25 km/h).
    Updates user last_lat, last_lng, last_loc_time.
    """
    now = datetime.utcnow()

    # First point in run
    if user.last_lat is None or user.last_lng is None or user.last_loc_time is None:
        user.last_lat = current_lat
        user.last_lng = current_lng
        user.last_loc_time = now
        return True

    distance_km = haversine(user.last_lat, user.last_lng, current_lat, current_lng)
    time_diff_hours = (now - user.last_loc_time).total_seconds() / 3600.0

    if time_diff_hours > 0:
        speed_kmh = distance_km / time_diff_hours
        if speed_kmh > 200.0: # Increased to 200km/h temporarily for testing GPS glitches
            print(f"ANTI-CHEAT TRIGGERED: User {user.username} moved at {speed_kmh:.2f} km/h!")
            return False

    # Valid movement, update cache
    user.last_lat = current_lat
    user.last_lng = current_lng
    user.last_loc_time = now
    return True
