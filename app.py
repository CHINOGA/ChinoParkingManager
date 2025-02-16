import os
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Import models after db initialization
from models import Vehicle, ParkingSpace  # noqa

with app.app_context():
    db.create_all()
    # Initialize default spaces if none exist
    if not ParkingSpace.query.first():
        default_spaces = [
            ParkingSpace(vehicle_type='motorcycle', total_spaces=50, occupied_spaces=0),
            ParkingSpace(vehicle_type='bajaj', total_spaces=30, occupied_spaces=0),
            ParkingSpace(vehicle_type='car', total_spaces=20, occupied_spaces=0)
        ]
        db.session.bulk_save_objects(default_spaces)
        db.session.commit()

@app.route('/')
def index():
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('index.html', spaces=spaces)

@app.route('/check-in', methods=['POST'])
def check_in():
    # Get all form data
    vehicle_type = request.form.get('vehicle_type')
    plate_number = request.form.get('plate_number')
    vehicle_color = request.form.get('vehicle_color')
    driver_name = request.form.get('driver_name')
    driver_id_type = request.form.get('driver_id_type')
    driver_id_number = request.form.get('driver_id_number')
    driver_phone = request.form.get('driver_phone')
    driver_residence = request.form.get('driver_residence')

    # Check for available space
    space = ParkingSpace.query.filter_by(vehicle_type=vehicle_type).first()
    if not space or space.occupied_spaces >= space.total_spaces:
        flash('No available spaces for this vehicle type!', 'error')
        return redirect(url_for('index'))

    # Check if vehicle already exists and is active
    existing_vehicle = Vehicle.query.filter_by(
        plate_number=plate_number, 
        status='active'
    ).first()

    if existing_vehicle:
        flash('Vehicle is already parked!', 'error')
        return redirect(url_for('index'))

    # Create new vehicle record
    vehicle = Vehicle(
        plate_number=plate_number,
        vehicle_type=vehicle_type,
        vehicle_color=vehicle_color,
        driver_name=driver_name,
        driver_id_type=driver_id_type,
        driver_id_number=driver_id_number,
        driver_phone=driver_phone,
        driver_residence=driver_residence,
        check_in_time=datetime.utcnow(),
        status='active'
    )

    space.occupied_spaces += 1
    db.session.add(vehicle)
    db.session.commit()

    flash('Vehicle checked in successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/check-out', methods=['POST'])
def check_out():
    plate_number = request.form.get('plate_number')

    vehicle = Vehicle.query.filter_by(
        plate_number=plate_number, 
        status='active'
    ).first()

    if not vehicle:
        flash('Vehicle not found or already checked out!', 'error')
        return redirect(url_for('index'))

    space = ParkingSpace.query.filter_by(vehicle_type=vehicle.vehicle_type).first()
    if space:
        space.occupied_spaces = max(0, space.occupied_spaces - 1)

    vehicle.status = 'completed'
    vehicle.check_out_time = datetime.utcnow()
    db.session.commit()

    flash('Vehicle checked out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/report')
def report():
    active_vehicles = Vehicle.query.filter_by(status='active').all()
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('report.html', vehicles=active_vehicles, spaces=spaces)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)