from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy
db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    vehicles = db.relationship('Vehicle', 
                           foreign_keys='Vehicle.user_id',
                           backref='recorded_by', 
                           lazy='dynamic',
                           cascade='all, delete-orphan')
    # Add relationship for vehicles handed over to this user
    handled_vehicles = db.relationship('Vehicle', 
                                   foreign_keys='Vehicle.handler_id',
                                   backref='current_handler',
                                   lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, role):
        if role == 'admin':
            return self.is_admin
        return False

    def __repr__(self):
        return f'<User {self.username}>'

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Vehicle Information
    plate_number = db.Column(db.String(10), nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)  # motorcycle, bajaj, car
    vehicle_model = db.Column(db.String(100), nullable=False)
    vehicle_color = db.Column(db.String(50), nullable=False)

    # Driver Information
    driver_name = db.Column(db.String(100), nullable=False)
    driver_id_type = db.Column(db.String(50), nullable=False)  # National ID, Voter's ID, Passport, Driver's License
    driver_id_number = db.Column(db.String(50), nullable=False)
    driver_phone = db.Column(db.String(20), nullable=False)
    driver_residence = db.Column(db.String(200), nullable=False)

    # Timing Information
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    check_out_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, completed
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    # Handover Information
    handler_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    handover_time = db.Column(db.DateTime, nullable=True)
    handover_notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Vehicle {self.plate_number}>'

    def get_east_african_time(self, utc_time):
        """Convert UTC time to East African Time (UTC+3)"""
        if utc_time:
            return utc_time + timedelta(hours=3)
        return None

    def formatted_check_in_time(self):
        """Return check-in time in EAT format"""
        eat_time = self.get_east_african_time(self.check_in_time)
        return eat_time.strftime('%Y-%m-%d %H:%M') if eat_time else ''

    def formatted_check_out_time(self):
        """Return check-out time in EAT format"""
        eat_time = self.get_east_african_time(self.check_out_time)
        return eat_time.strftime('%Y-%m-%d %H:%M') if eat_time else ''

    def formatted_handover_time(self):
        """Return handover time in EAT format"""
        eat_time = self.get_east_african_time(self.handover_time)
        return eat_time.strftime('%Y-%m-%d %H:%M') if eat_time else ''

class ParkingSpace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_type = db.Column(db.String(20), nullable=False)
    total_spaces = db.Column(db.Integer, nullable=False)
    occupied_spaces = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ParkingSpace {self.vehicle_type}>'