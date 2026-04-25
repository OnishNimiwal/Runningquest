from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    color = db.Column(db.String(7), default='#3b82f6')
    score = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    last_lat = db.Column(db.Float, nullable=True)
    last_lng = db.Column(db.Float, nullable=True)
    last_loc_time = db.Column(db.DateTime, nullable=True)
    is_suspicious_run = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

from datetime import datetime

class Run(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    distance = db.Column(db.Float, default=0.0)
    duration = db.Column(db.Integer, default=0) # in seconds
    route_data = db.Column(db.Text, nullable=True) # GeoJSON string
    date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('runs', lazy=True))

    def __repr__(self):
        return f'<Run {self.id} User {self.user_id}>'

class Territory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.String(12), unique=True, index=True, nullable=False) # Geohash string
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Who captured it
    date_captured = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('User', backref=db.backref('territories', lazy=True))

    def __repr__(self):
        return f'<Territory {self.cell_id} Owner {self.user_id}>'

class TerritoryEventLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.String(12), nullable=False)
    captured_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    previous_owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    captor = db.relationship('User', foreign_keys=[captured_by_user_id])
    previous_owner = db.relationship('User', foreign_keys=[previous_owner_id])

class TerritoryDecayLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.String(12), nullable=False)
    lost_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    loser = db.relationship('User', backref=db.backref('decay_logs', lazy=True))
