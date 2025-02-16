import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func, create_engine
from datetime import datetime, timedelta

# Set up logging with more details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure database
logger.debug("Configuring database connection...")
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    logger.error("DATABASE_URL environment variable is not set")
    raise Exception("Database URL not configured")

try:
    # Test database connection before configuring app
    engine = create_engine(database_url)
    with engine.connect() as conn:
        logger.debug("Successfully connected to database")
except Exception as e:
    logger.error(f"Failed to connect to database: {str(e)}")
    raise

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize Flask-SQLAlchemy
logger.debug("Initializing Flask-SQLAlchemy...")
db.init_app(app)

# Import models after db initialization
from models import Vehicle, ParkingSpace  # noqa

with app.app_context():
    try:
        logger.debug("Creating database tables...")
        db.create_all()

        # Initialize default spaces if none exist
        logger.debug("Checking for default parking spaces...")
        spaces = ParkingSpace.query.all()
        logger.debug(f"Found {len(spaces)} existing parking spaces")

        if not spaces:
            logger.debug("Initializing default parking spaces...")
            default_spaces = [
                ParkingSpace(vehicle_type='motorcycle', total_spaces=50),
                ParkingSpace(vehicle_type='bajaj', total_spaces=30),
                ParkingSpace(vehicle_type='car', total_spaces=20)
            ]
            db.session.bulk_save_objects(default_spaces)
            db.session.commit()
            logger.debug("Default parking spaces initialized successfully")
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}", exc_info=True)
        raise

@app.route('/')
def index():
    try:
        spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
                  for space in ParkingSpace.query.all()}
        return render_template('index.html', spaces=spaces)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}", exc_info=True)
        flash('Error loading parking data', 'error')
        return render_template('index.html', spaces={})

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
        logger.error(f"Error during check-in: {str(e)}", exc_info=True)
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
        logger.error(f"Error during check-out: {str(e)}", exc_info=True)
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

        # Initialize with default values
        current_occupancy = {}
        for space in spaces:
            current_occupancy[space.vehicle_type] = {
                'total': space.total_spaces,
                'occupied': space.occupied_spaces,
                'percentage': (space.occupied_spaces / space.total_spaces * 100) if space.total_spaces > 0 else 0
            }
        logger.debug(f"Current occupancy data: {current_occupancy}")

        # Get vehicle type distribution for active vehicles
        active_vehicles = db.session.query(
            Vehicle.vehicle_type,
            func.count(Vehicle.id)
        ).filter(
            Vehicle.status == 'active'
        ).group_by(Vehicle.vehicle_type).all()

        vehicle_distribution = {}
        for vehicle_type in current_occupancy.keys():
            vehicle_distribution[vehicle_type] = 0
        for v_type, count in active_vehicles:
            if v_type in vehicle_distribution:
                vehicle_distribution[v_type] = count

        logger.debug(f"Vehicle distribution: {vehicle_distribution}")

        # Get hourly check-ins for the past 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_checkins = Vehicle.query.filter(
            Vehicle.check_in_time >= yesterday
        ).order_by(Vehicle.check_in_time).all()

        # Process hourly data
        hourly_data = {}
        for vehicle in recent_checkins:
            if vehicle.check_in_time:
                # Convert UTC to EAT (UTC+3)
                eat_time = vehicle.check_in_time + timedelta(hours=3)
                hour_key = eat_time.strftime('%H:00')
                hourly_data[hour_key] = hourly_data.get(hour_key, 0) + 1

        if not hourly_data:
            current_hour = datetime.utcnow()
            eat_hour = (current_hour + timedelta(hours=3)).strftime('%H:00')
            hourly_data = {eat_hour: 0}

        # Sort hourly data by hour
        hourly_data = dict(sorted(hourly_data.items()))
        logger.debug(f"Processed hourly data: {hourly_data}")

        return render_template(
            'analytics.html',
            current_occupancy=current_occupancy,
            vehicle_distribution=vehicle_distribution,
            hourly_data=hourly_data
        )
    except Exception as e:
        logger.error(f"Error in analytics route: {str(e)}", exc_info=True)
        flash('Error loading analytics data', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    logger.warning("This file should not be run directly. Please use main.py instead.")