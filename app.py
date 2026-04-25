import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from models import db, User
from forms import LoginForm, RegistrationForm

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'runningquest.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

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
    return render_template('dashboard.html', title='Dashboard')

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
        flash('Congratulations, you are now a registered user!')
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
            flash('Invalid email or password')
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
    return render_template('run.html', title='Live Run Tracking')

@app.route('/api/save_run', methods=['POST'])
@login_required
def save_run():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    from models import Run
    route_str = data.get('route_data', '{}')
    new_run = Run(
        user_id=current_user.id,
        distance=data.get('distance', 0.0),
        duration=data.get('duration', 0),
        route_data=route_str
    )
    db.session.add(new_run)
    db.session.commit()
    
    # Step 5 Logic: Calculate Grid Cells
    from utils.grid import route_to_cells
    cells = route_to_cells(route_str)
    print(f"DEBUG: Run calculated {len(cells)} unique grid cells: {cells}")
    
    return jsonify({'success': True, 'run_id': new_run.id, 'cells_calculated': cells}), 201

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
