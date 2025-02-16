import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, desc
from models import db, Vehicle, ParkingSpace, Admin

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure database
logger.info("Configuring database connection...")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = 'Please log in to access the admin panel.'

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

def initialize_database():
    """Initialize database with default data"""
    try:
        # Create all tables
        db.create_all()

        # Initialize default spaces if none exist
        if not ParkingSpace.query.first():
            logger.info("Initializing default parking spaces...")
            default_spaces = [
                ParkingSpace(vehicle_type='motorcycle', total_spaces=50, occupied_spaces=0),
                ParkingSpace(vehicle_type='bajaj', total_spaces=30, occupied_spaces=0),
                ParkingSpace(vehicle_type='car', total_spaces=20, occupied_spaces=0)
            ]
            db.session.bulk_save_objects(default_spaces)

            # Create default admin account if none exists
            if not Admin.query.first():
                logger.info("Creating default admin account...")
                default_admin = Admin(
                    username='admin',
                    email='admin@chinopark.com'
                )
                default_admin.set_password('admin123')
                db.session.add(default_admin)

            db.session.commit()
            logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        db.session.rollback()
        raise

with app.app_context():
    initialize_database()

# Routes
@app.route('/')
def index():
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('index.html', spaces=spaces)

@app.route('/check-in', methods=['POST'])
def check_in():
    try:
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
        # Get space utilization data
        spaces = ParkingSpace.query.all()
        space_labels = [space.vehicle_type.title() for space in spaces]
        space_occupied = [space.occupied_spaces for space in spaces]
        space_total = [space.total_spaces for space in spaces]

        # Get current vehicle distribution
        active_vehicles = db.session.query(
            Vehicle.vehicle_type,
            func.count(Vehicle.id).label('count')
        ).filter(
            Vehicle.status == 'active'
        ).group_by(Vehicle.vehicle_type).all()

        distribution_labels = []
        distribution_data = []
        for v_type, count in active_vehicles:
            distribution_labels.append(v_type.title())
            distribution_data.append(count)

        # Get recent activities (check-ins and check-outs)
        today = datetime.utcnow().date()
        recent_activities = []

        # Recent check-ins
        recent_check_ins = Vehicle.query.filter(
            Vehicle.check_in_time >= today
        ).order_by(desc(Vehicle.check_in_time)).limit(10).all()

        for vehicle in recent_check_ins:
            recent_activities.append({
                'timestamp': vehicle.formatted_check_in_time(),
                'type': 'check_in',
                'vehicle_type': vehicle.vehicle_type,
                'plate_number': vehicle.plate_number
            })

        # Recent check-outs
        recent_check_outs = Vehicle.query.filter(
            Vehicle.check_out_time >= today,
            Vehicle.status == 'completed'
        ).order_by(desc(Vehicle.check_out_time)).limit(10).all()

        for vehicle in recent_check_outs:
            recent_activities.append({
                'timestamp': vehicle.formatted_check_out_time(),
                'type': 'check_out',
                'vehicle_type': vehicle.vehicle_type,
                'plate_number': vehicle.plate_number
            })

        # Sort activities by timestamp
        recent_activities.sort(key=lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M'), reverse=True)
        recent_activities = recent_activities[:10]  # Keep only the 10 most recent

        # Calculate daily statistics
        daily_stats = {
            'check_ins': Vehicle.query.filter(
                Vehicle.check_in_time >= today
            ).count(),
            'check_outs': Vehicle.query.filter(
                Vehicle.check_out_time >= today
            ).count(),
            'avg_stay_time': '-- hours',  # Placeholder
            'peak_hour': '-- : --'  # Placeholder
        }

        # Calculate average stay time for completed parkings today
        completed_today = Vehicle.query.filter(
            Vehicle.status == 'completed',
            Vehicle.check_out_time >= today
        ).all()

        if completed_today:
            total_duration = sum(
                (v.check_out_time - v.check_in_time).total_seconds() / 3600
                for v in completed_today
            )
            avg_hours = round(total_duration / len(completed_today), 1)
            daily_stats['avg_stay_time'] = f"{avg_hours} hours"

        # Find peak hour
        peak_hour_data = db.session.query(
            func.date_trunc('hour', Vehicle.check_in_time).label('hour'),
            func.count(Vehicle.id).label('count')
        ).filter(
            Vehicle.check_in_time >= today
        ).group_by(
            'hour'
        ).order_by(
            desc('count')
        ).first()

        if peak_hour_data and peak_hour_data[0]:
            peak_hour = peak_hour_data[0] + timedelta(hours=3)  # Convert to EAT
            daily_stats['peak_hour'] = peak_hour.strftime('%H:00')

        return render_template(
            'analytics.html',
            space_labels=space_labels,
            space_occupied=space_occupied,
            space_total=space_total,
            distribution_labels=distribution_labels,
            distribution_data=distribution_data,
            recent_activities=recent_activities,
            daily_stats=daily_stats
        )

    except Exception as e:
        logger.error(f"Error in analytics: {str(e)}")
        flash('Error loading analytics data', 'error')
        return redirect(url_for('index'))

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            login_user(admin)
            admin.last_login = datetime.utcnow()
            db.session.commit()
            flash('Logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    total_vehicles = Vehicle.query.count()
    active_vehicles = Vehicle.query.filter_by(status='active').count()
    spaces = ParkingSpace.query.all()

    # Get today's statistics
    today = datetime.utcnow().date()
    today_check_ins = Vehicle.query.filter(
        Vehicle.check_in_time >= today
    ).count()
    today_check_outs = Vehicle.query.filter(
        Vehicle.check_out_time >= today,
        Vehicle.status == 'completed'
    ).count()

    return render_template('admin/dashboard.html',
                         total_vehicles=total_vehicles,
                         active_vehicles=active_vehicles,
                         spaces=spaces,
                         today_check_ins=today_check_ins,
                         today_check_outs=today_check_outs)

@app.route('/admin/spaces')
@login_required
def admin_spaces():
    spaces = ParkingSpace.query.all()
    return render_template('admin/spaces.html', spaces=spaces)

@app.route('/admin/spaces/update', methods=['POST'])
@login_required
def update_spaces():
    try:
        space_id = request.form.get('space_id')
        total_spaces = request.form.get('total_spaces')

        space = ParkingSpace.query.get_or_404(space_id)
        if int(total_spaces) < space.occupied_spaces:
            flash('New total spaces cannot be less than currently occupied spaces.', 'error')
        else:
            space.total_spaces = int(total_spaces)
            db.session.commit()
            flash('Parking spaces updated successfully.', 'success')
    except Exception as e:
        flash('Error updating parking spaces.', 'error')
        logger.error(f"Error updating parking spaces: {str(e)}")

    return redirect(url_for('admin_spaces'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)