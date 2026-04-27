import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from models import db, User
from forms import LoginForm, RegistrationForm

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-12345'

# Database Configuration
db_url = os.environ.get('DATABASE_URL')

if db_url:
    # Vercel/Heroku provide URLs starting with postgres:// but SQLAlchemy requires postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    # Fallback to local SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'runningquest.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Ensure tables are created when Vercel boots up the app
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Warning: Database initialization failed. Check your DATABASE_URL: {e}")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    from models import User, Territory, Run
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from utils.decay import process_user_decay

    # Step 8: Check and process territory decay
    process_user_decay(current_user)

    # Count of territories this user currently owns (for warning state)
    user_territories = Territory.query.filter_by(user_id=current_user.id).count()


    # Auto-seed logic has been moved to /api/fix_territories
    if user_territories == 0:
        pass
    # Calculate Total Distance
    total_dist_query = db.session.query(func.sum(Run.distance)).filter_by(user_id=current_user.id).scalar()
    total_distance = total_dist_query if total_dist_query else 0.0

    # Calculate Current Streak + streak-aware warning state
    runs = Run.query.filter_by(user_id=current_user.id).order_by(Run.date.desc()).all()
    current_streak = 0
    run_dates = set(r.date.date() for r in runs)
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    if runs:
        last_run_date = runs[0].date.date()
        days_since_last_run = (today - last_run_date).days
        if days_since_last_run <= 1:
            current_streak = 1
            check_date = last_run_date - timedelta(days=1)
            while check_date in run_dates:
                current_streak += 1
                check_date -= timedelta(days=1)
    else:
        days_since_last_run = 999

    # Warning state logic — synced with streak and decay:
    # 'safe'    → ran today, no warning
    # 'warning' → last run was yesterday (streak alive but today not run yet)
    # 'danger'  → streak broken (2+ days ago), decay is starting / active
    if user_territories == 0:
        warning_state = 'none'          # new user, no territories to lose
    elif today in run_dates:
        warning_state = 'safe'          # already ran today
    elif yesterday in run_dates:
        warning_state = 'warning'       # haven't run today — streak at risk
    else:
        warning_state = 'danger'        # streak broken, decay active

    # Leaderboard: rank all users by total territory area
    leaderboard_query = db.session.query(
        User.username,
        User.color,
        Territory.area_sqkm.label('area')
    ).join(
        Territory, User.id == Territory.user_id
    ).filter(
        Territory.area_sqkm > 0
    ).order_by(
        Territory.area_sqkm.desc()
    ).limit(10).all()

    return render_template('dashboard.html', title='Dashboard',
                           leaderboard=leaderboard_query,
                           warning_state=warning_state,
                           total_distance=total_distance,
                           current_streak=current_streak)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        import random
        rand_color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        user = User(username=form.username.data, email=form.email.data, color=rand_color)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

from flask import jsonify

@app.route('/run')
@login_required
def run_tracker():
    current_user.is_suspicious_run = False
    current_user.last_lat = None
    current_user.last_lng = None
    current_user.last_loc_time = None
    db.session.commit()
    return render_template('run.html', title='Live Run Tracking')

@app.route('/api/save_run', methods=['POST'])
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
