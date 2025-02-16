import os
import logging
from app import app
from models import db, User, ParkingSpace

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        db.session.rollback()

# Initialize database when running the app
if __name__ == "__main__":
    with app.app_context():
        initialize_database()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)