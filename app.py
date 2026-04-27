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
    from models import TerritoryEventLog, User, Territory, Run
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from utils.decay import process_user_decay

    # Step 8: Check and process territory decay
    process_user_decay(current_user)

    # Count of territories this user currently owns (for warning state)
    user_territories = Territory.query.filter_by(user_id=current_user.id).count()

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

    # Leaderboard: rank all users by total territory cells currently owned
    leaderboard_query = db.session.query(
        User.username,
        User.color,
        func.count(Territory.id).label('area')
    ).join(
        Territory, User.id == Territory.user_id
    ).group_by(
        User.id
    ).order_by(
        func.count(Territory.id).desc()
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
    
    from models import Run, Territory, TerritoryEventLog
    from datetime import datetime
    
    route_str = data.get('route_data', '{}')
    new_run = Run(
        user_id=current_user.id,
        distance=data.get('distance', 0.0),
        duration=data.get('duration', 0),
        route_data=route_str
    )
    db.session.add(new_run)
    
    # Robust fallback: Calculate and grant Grid Cells at the end of the run
    from utils.grid import route_to_cells
    cells = route_to_cells(route_str)
    
    captured_count = 0
    if not current_user.is_suspicious_run:
        for cell_id in cells:
            t = Territory.query.filter_by(cell_id=cell_id).first()
            if not t:
                t = Territory(cell_id=cell_id, user_id=current_user.id)
                db.session.add(t)
                event = TerritoryEventLog(cell_id=cell_id, captured_by_user_id=current_user.id)
                db.session.add(event)
                current_user.score += 1
                captured_count += 1
            elif t.user_id != current_user.id:
                prev_owner = t.user_id
                t.user_id = current_user.id
                t.date_captured = datetime.utcnow()
                event = TerritoryEventLog(cell_id=cell_id, captured_by_user_id=current_user.id, previous_owner_id=prev_owner)
                db.session.add(event)
                current_user.score += 1
                captured_count += 1
        
        if captured_count > 0:
            current_user.last_active = datetime.utcnow()

    db.session.commit()
    
    return jsonify({'success': True, 'run_id': new_run.id, 'cells_calculated': cells, 'captured_count': captured_count}), 201

@app.route('/api/capture_cell', methods=['POST'])
@login_required
def capture_cell():
    data = request.get_json()
    cell_id = data.get('cell_id')
    lat = data.get('lat')
    lng = data.get('lng')

    if not cell_id or lat is None or lng is None:
        return jsonify({'error': 'Missing cell data or coordinates'}), 400

    if current_user.is_suspicious_run:
        return jsonify({'status': 'suspicious', 'message': 'Anti-cheat triggered: Run permanently marked suspicious.'}), 200

    from utils.anticheat import validate_movement
    is_valid = validate_movement(current_user, float(lat), float(lng))
    
    if not is_valid:
        current_user.is_suspicious_run = True
        db.session.commit()
        return jsonify({'status': 'suspicious', 'message': 'Anti-cheat triggered: Impossible speed detected.'}), 200

    from models import Territory, TerritoryEventLog
    from datetime import datetime
    
    # Check if territory exists
    territory = Territory.query.filter_by(cell_id=cell_id).first()
    prev_owner_id = None
    
    if territory:
        if territory.user_id == current_user.id:
            return jsonify({'status': 'already_owned'}), 200
        prev_owner_id = territory.user_id
        territory.user_id = current_user.id
        territory.date_captured = datetime.utcnow()
    else:
        territory = Territory(cell_id=cell_id, user_id=current_user.id)
        db.session.add(territory)

    # Log the event
    event = TerritoryEventLog(
        cell_id=cell_id,
        captured_by_user_id=current_user.id,
        previous_owner_id=prev_owner_id
    )
    db.session.add(event)

    # Update user score
    current_user.score += 1
    current_user.last_active = datetime.utcnow()

    db.session.commit()

    return jsonify({'status': 'captured', 'color': current_user.color}), 200

@app.route('/api/territories', methods=['GET'])
@login_required
def get_territories():
    from models import Territory, User
    territories = db.session.query(Territory, User).join(User, Territory.user_id == User.id).all()
    
    result = []
    for t, u in territories:
        result.append({
            'cell_id': t.cell_id,
            'color': u.color,
            'owner': u.username
        })
    return jsonify(result), 200

@app.route('/api/user_map_data', methods=['GET'])
@login_required
def user_map_data():
    from models import Territory, Run, User
    import json

    # Get all territories globally to show turf war
    territories = db.session.query(Territory, User).join(User, Territory.user_id == User.id).all()
    cells_data = []
    for t, u in territories:
        cells_data.append({
            'cell_id': t.cell_id,
            'color': u.color,
            'owner': u.username
        })

    # Get ALL runs from all users to draw intersecting public paths
    runs_data = db.session.query(Run, User).join(User, Run.user_id == User.id).all()
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
        'cells': cells_data,
        'routes': routes
    }), 200

@app.route('/api/fix_territories')
def fix_territories():
    from models import Run, Territory, TerritoryEventLog, User
    from utils.grid import route_to_cells
    from datetime import datetime
    
    runs = Run.query.all()
    count = 0
    for run in runs:
        if not run.route_data: continue
        try:
            cells = route_to_cells(run.route_data)
            for cell_id in cells:
                t = Territory.query.filter_by(cell_id=cell_id).first()
                if not t:
                    t = Territory(cell_id=cell_id, user_id=run.user_id)
                    db.session.add(t)
                    event = TerritoryEventLog(cell_id=cell_id, captured_by_user_id=run.user_id)
                    db.session.add(event)
                    user = User.query.get(run.user_id)
                    if user:
                        user.score += 1
                    count += 1
                elif t.user_id != run.user_id:
                    prev_owner = t.user_id
                    t.user_id = run.user_id
                    t.date_captured = datetime.utcnow()
                    event = TerritoryEventLog(cell_id=cell_id, captured_by_user_id=run.user_id, previous_owner_id=prev_owner)
                    db.session.add(event)
                    user = User.query.get(run.user_id)
                    if user:
                        user.score += 1
                    count += 1
        except Exception as e:
            pass
    db.session.commit()
    return f"Successfully processed existing runs and retroactively granted {count} territories to the database!"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
