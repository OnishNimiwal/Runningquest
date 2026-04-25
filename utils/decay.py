from app import db
from models import Territory, TerritoryDecayLog
from datetime import datetime
import math

def process_user_decay(user):
    """
    Calculates and executes inactivity-based territory decay.
    Rule:
    - 0-3 days inactive: no loss
    - > 3 days inactive: starts quadratic loss.
    - Loss cycle k = floor((days_inactive - 3) / 2) + 1
    - Total cells lost = k * (k + 1) / 2
    """
    if not user.last_active:
        return

    now = datetime.utcnow()
    delta = now - user.last_active
    days_inactive = delta.total_seconds() / 86400.0

    if days_inactive <= 3:
        return

    # Calculate Cycle K
    # Days 3-5 -> K=1
    # Days 5-7 -> K=2
    cycle_k = math.floor((days_inactive - 3) / 2) + 1
    if cycle_k < 1:
        return

    # Total cells that SHOULD have decayed since last_active
    target_total_loss = int((cycle_k * (cycle_k + 1)) / 2)

    # How many have actually decayed since last_active?
    already_lost_count = TerritoryDecayLog.query.filter(
        TerritoryDecayLog.lost_by_user_id == user.id,
        TerritoryDecayLog.timestamp >= user.last_active
    ).count()

    cells_to_lose = target_total_loss - already_lost_count

    if cells_to_lose > 0:
        # Find oldest owned territories
        oldest_territories = Territory.query.filter_by(user_id=user.id)\
            .order_by(Territory.date_captured.asc())\
            .limit(cells_to_lose)\
            .all()

        for t in oldest_territories:
            # 1. Log the decay
            log = TerritoryDecayLog(
                cell_id=t.cell_id,
                lost_by_user_id=user.id,
                timestamp=datetime.utcnow()
            )
            db.session.add(log)
            
            # 2. Set to Neutral
            t.user_id = None
            t.date_captured = None

        db.session.commit()
