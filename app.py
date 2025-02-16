import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure database
logger.debug("Configuring database connection...")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Import models after db initialization
from models import Vehicle, ParkingSpace  # noqa

with app.app_context():
    logger.debug("Dropping existing database tables...")
    db.drop_all()  # Development only - removes existing tables

    logger.debug("Creating database tables...")
    db.create_all()

    # Initialize default spaces if none exist
    logger.debug("Checking for default parking spaces...")
    if not ParkingSpace.query.first():
        logger.debug("Initializing default parking spaces...")
        default_spaces = [
            ParkingSpace(vehicle_type='motorcycle', total_spaces=50, occupied_spaces=0),
            ParkingSpace(vehicle_type='bajaj', total_spaces=30, occupied_spaces=0),
            ParkingSpace(vehicle_type='car', total_spaces=20, occupied_spaces=0)
        ]
        db.session.bulk_save_objects(default_spaces)
        db.session.commit()
        logger.debug("Default spaces initialized successfully")

@app.route('/')
def index():
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('index.html', spaces=spaces)

@app.route('/check-in', methods=['POST'])
def check_in():
    try:
        # Get all form data
        vehicle_type = request.form.get('vehicle_type')
        plate_number = request.form.get('plate_number')
        vehicle_model = request.form.get('vehicle_model')
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
            vehicle_model=vehicle_model,
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
        logger.debug(f"Vehicle {plate_number} checked in successfully")
        flash('Vehicle checked in successfully!', 'success')
    except Exception as e:
        logger.error(f"Error during check-in: {str(e)}")
        flash('An error occurred during check-in!', 'error')
        db.session.rollback()

    return redirect(url_for('index'))

@app.route('/check-out', methods=['POST'])
def check_out():
    try:
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
        logger.debug(f"Vehicle {plate_number} checked out successfully")
        flash('Vehicle checked out successfully!', 'success')
    except Exception as e:
        logger.error(f"Error during check-out: {str(e)}")
        flash('An error occurred during check-out!', 'error')
        db.session.rollback()

    return redirect(url_for('index'))

@app.route('/report')
def report():
    active_vehicles = Vehicle.query.filter_by(status='active').all()
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('report.html', vehicles=active_vehicles, spaces=spaces)

@app.route('/analytics')
def analytics():
    try:
        # Get current occupancy by vehicle type
        spaces = ParkingSpace.query.all()
        logger.debug(f"Found {len(spaces)} parking spaces")

        current_occupancy = {}
        for space in spaces:
            current_occupancy[space.vehicle_type] = {
                'total': space.total_spaces,
                'occupied': space.occupied_spaces,
                'percentage': (space.occupied_spaces / space.total_spaces * 100) if space.total_spaces > 0 else 0
            }
        logger.debug(f"Current occupancy data: {current_occupancy}")

        # Get vehicle type distribution
        vehicle_counts = db.session.query(
            Vehicle.vehicle_type,
            func.count(Vehicle.id)
        ).group_by(Vehicle.vehicle_type).all()
        logger.debug(f"Vehicle counts: {vehicle_counts}")

        vehicle_distribution = {}
        for vtype, count in vehicle_counts:
            vehicle_distribution[vtype] = count
        logger.debug(f"Vehicle distribution: {vehicle_distribution}")

        # Calculate average parking duration for completed parkings
        completed_parkings = Vehicle.query.filter(
            Vehicle.status == 'completed',
            Vehicle.check_out_time.isnot(None)
        ).all()
        logger.debug(f"Found {len(completed_parkings)} completed parkings")

        avg_duration = timedelta()
        if completed_parkings:
            total_duration = sum((v.check_out_time - v.check_in_time) for v in completed_parkings)
            avg_duration = total_duration / len(completed_parkings)
        logger.debug(f"Average duration: {avg_duration}")

        # Get hourly check-ins for the past 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        hourly_checkins = db.session.query(
            func.date_trunc('hour', Vehicle.check_in_time).label('hour'),
            func.count(Vehicle.id).label('count')
        ).filter(
            Vehicle.check_in_time >= yesterday
        ).group_by(
            'hour'
        ).order_by('hour').all()
        logger.debug(f"Hourly checkins raw data: {hourly_checkins}")

        # Format for the template
        hourly_data = {}
        for hour, count in hourly_checkins:
            if hour:  # Check if hour is not None
                hourly_data[hour.strftime('%Y-%m-%d %H:00')] = count
        logger.debug(f"Formatted hourly data: {hourly_data}")

        if not current_occupancy:
            current_occupancy = {
                'motorcycle': {'total': 50, 'occupied': 0, 'percentage': 0},
                'bajaj': {'total': 30, 'occupied': 0, 'percentage': 0},
                'car': {'total': 20, 'occupied': 0, 'percentage': 0}
            }

        if not vehicle_distribution:
            vehicle_distribution = {'motorcycle': 0, 'bajaj': 0, 'car': 0}

        if not hourly_data:
            current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            hourly_data = {current_hour.strftime('%Y-%m-%d %H:00'): 0}

        return render_template(
            'analytics.html',
            current_occupancy=current_occupancy,
            vehicle_distribution=vehicle_distribution,
            avg_duration=avg_duration,
            hourly_data=hourly_data
        )
    except Exception as e:
        logger.error(f"Error in analytics: {str(e)}")
        flash('Error loading analytics data', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)