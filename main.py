import os
import logging
from datetime import datetime, timedelta
from app import app
from models import db, User, ParkingSpace, Vehicle

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def add_sample_data():
    """Add sample parking data"""
    try:
        if not Vehicle.query.first():  # Only add if no vehicles exist
            logger.info("Adding sample vehicle data...")

            # Sample active vehicles
            active_vehicles = [
                {
                    'plate_number': 'T123ABC',
                    'vehicle_type': 'car',
                    'vehicle_model': 'Toyota Corolla',
                    'vehicle_color': 'Silver',
                    'driver_name': 'John Doe',
                    'driver_id_type': 'national_id',
                    'driver_id_number': 'ID123456',
                    'driver_phone': '+255700123456',
                    'driver_residence': 'Upanga',
                    'check_in_time': datetime.utcnow() - timedelta(hours=2),
                    'status': 'active'
                },
                {
                    'plate_number': 'MC789XY',
                    'vehicle_type': 'motorcycle',
                    'vehicle_model': 'Honda CB150R',
                    'vehicle_color': 'Red',
                    'driver_name': 'Sarah Smith',
                    'driver_id_type': 'drivers_license',
                    'driver_id_number': 'DL789012',
                    'driver_phone': '+255700789012',
                    'driver_residence': 'Kariakoo',
                    'check_in_time': datetime.utcnow() - timedelta(hours=1),
                    'status': 'active'
                },
                {
                    'plate_number': 'BJ456PQ',
                    'vehicle_type': 'bajaj',
                    'vehicle_model': 'Bajaj RE',
                    'vehicle_color': 'Yellow',
                    'driver_name': 'Michael Johnson',
                    'driver_id_type': 'voters_id',
                    'driver_id_number': 'VID345678',
                    'driver_phone': '+255700345678',
                    'driver_residence': 'Kinondoni',
                    'check_in_time': datetime.utcnow() - timedelta(minutes=30),
                    'status': 'active'
                }
            ]

            # Sample completed parkings
            completed_vehicles = [
                {
                    'plate_number': 'T789XYZ',
                    'vehicle_type': 'car',
                    'vehicle_model': 'Nissan X-Trail',
                    'vehicle_color': 'Black',
                    'driver_name': 'Alice Brown',
                    'driver_id_type': 'passport',
                    'driver_id_number': 'PP123789',
                    'driver_phone': '+255700123789',
                    'driver_residence': 'Masaki',
                    'check_in_time': datetime.utcnow() - timedelta(hours=5),
                    'check_out_time': datetime.utcnow() - timedelta(hours=2),
                    'status': 'completed'
                },
                {
                    'plate_number': 'MC456AB',
                    'vehicle_type': 'motorcycle',
                    'vehicle_model': 'Yamaha YBR',
                    'vehicle_color': 'Blue',
                    'driver_name': 'David Wilson',
                    'driver_id_type': 'national_id',
                    'driver_id_number': 'ID987654',
                    'driver_phone': '+255700987654',
                    'driver_residence': 'Ilala',
                    'check_in_time': datetime.utcnow() - timedelta(hours=3),
                    'check_out_time': datetime.utcnow() - timedelta(hours=1),
                    'status': 'completed'
                }
            ]

            # Get admin user for foreign key
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                logger.error("Admin user not found, cannot add sample data")
                return

            # Add active vehicles and update space counts
            for vehicle_data in active_vehicles:
                vehicle = Vehicle(**vehicle_data, user_id=admin_user.id)
                db.session.add(vehicle)
                space = ParkingSpace.query.filter_by(vehicle_type=vehicle_data['vehicle_type']).first()
                if space:
                    space.occupied_spaces += 1

            # Add completed vehicles
            for vehicle_data in completed_vehicles:
                vehicle = Vehicle(**vehicle_data, user_id=admin_user.id)
                db.session.add(vehicle)

            db.session.commit()
            logger.info("Sample vehicle data added successfully")

    except Exception as e:
        logger.error(f"Error adding sample data: {str(e)}")
        db.session.rollback()

def initialize_database():
    """Initialize database with default data"""
    try:
        # Create tables if they don't exist
        db.create_all()

        # Initialize default spaces if none exist
        if not ParkingSpace.query.first():
            logger.info("Initializing default parking spaces...")
            default_spaces = [
                ParkingSpace(vehicle_type='motorcycle', total_spaces=50, occupied_spaces=0),
                ParkingSpace(vehicle_type='bajaj', total_spaces=30, occupied_spaces=0),
                ParkingSpace(vehicle_type='car', total_spaces=20, occupied_spaces=0)
            ]
            for space in default_spaces:
                db.session.add(space)
            db.session.commit()
            logger.info("Default parking spaces created successfully")

        # Create default admin account if none exists
        if not User.query.filter_by(username='admin').first():
            logger.info("Creating default admin account...")
            admin = User(
                username='admin',
                email='admin@chinopark.com',
                is_admin=True,
                is_approved=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin account created successfully")

        # Add sample data after admin user is created
        add_sample_data()

    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        db.session.rollback()

# Initialize database when running the app
if __name__ == "__main__":
    with app.app_context():
        initialize_database()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)