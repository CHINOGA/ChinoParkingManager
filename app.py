import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, desc
from models import db, Vehicle, ParkingSpace, User

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
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access the parking system.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_tables():
    """Create database tables"""
    try:
        logger.info("Creating database tables...")
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        raise

def add_sample_data():
    """Add sample parking data"""
    try:
        logger.info("Checking for existing vehicles...")
        if Vehicle.query.first():
            logger.info("Sample data already exists, skipping...")
            return

        logger.info("Getting admin user for sample data...")
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            logger.error("Admin user not found, cannot add sample data")
            return

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

        # Add active vehicles and update space counts
        for vehicle_data in active_vehicles:
            vehicle = Vehicle(**vehicle_data, user_id=admin_user.id)
            db.session.add(vehicle)
            space = ParkingSpace.query.filter_by(vehicle_type=vehicle_data['vehicle_type']).first()
            if space:
                space.occupied_spaces += 1

        # Sample completed vehicles
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

        # Add completed vehicles
        for vehicle_data in completed_vehicles:
            vehicle = Vehicle(**vehicle_data, user_id=admin_user.id)
            db.session.add(vehicle)

        logger.info("Committing sample data to database...")
        db.session.commit()
        logger.info("Sample vehicle data added successfully")

    except Exception as e:
        logger.error(f"Error adding sample data: {str(e)}")
        db.session.rollback()
        raise

def initialize_default_data():
    """Initialize default spaces and admin user"""
    try:
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
        admin = User.query.filter_by(username='admin').first()
        if not admin:
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

        # Add sample data after ensuring admin exists
        add_sample_data()

    except Exception as e:
        logger.error(f"Error during data initialization: {str(e)}")
        db.session.rollback()
        raise

# Initialize database and default data
with app.app_context():
    create_tables()
    initialize_default_data()

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_approved and not user.is_admin:
                flash('Your account is pending approval.', 'warning')
                return redirect(url_for('login'))

            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Logged in successfully.', 'success')

            # Redirect admin users to admin dashboard
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))

        flash('Invalid username or password.', 'error')

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))

        user = User(
            username=username,
            email=email,
            is_admin=False,  # Regular users are not admins by default
            is_approved=False  # Users need admin approval by default
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful. Please wait for admin approval.', 'success')
        return redirect(url_for('login'))

    return render_template('auth/register.html')

# Add these new routes for user management
@app.route('/admin/users')
@login_required
def manage_users():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    pending_users = User.query.filter_by(is_approved=False, is_admin=False).all()
    all_users = User.query.all()

    return render_template('admin/users.html', 
                         pending_users=pending_users,
                         all_users=all_users)

@app.route('/admin/users/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'User {user.username} has been approved.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/reject', methods=['POST'])
@login_required
def reject_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)
    # Instead of deleting, we could also add a rejected status
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} has been rejected.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# Admin routes
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

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
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    spaces = ParkingSpace.query.all()
    return render_template('admin/spaces.html', spaces=spaces)

@app.route('/admin/spaces/update', methods=['POST'])
@login_required
def update_spaces():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

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

# Protected routes for regular users
@app.route('/')
@login_required
def index():
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('index.html', spaces=spaces)

@app.route('/check-in', methods=['POST'])
@login_required
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
            status='active',
            user_id=current_user.id
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
@login_required
def check_out():
    try:
        plate_number = request.form.get('plate_number')
        vehicle = Vehicle.query.filter_by(
            plate_number=plate_number, 
            status='active',
            user_id=current_user.id
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
@login_required
def report():
    # Get both active and completed vehicles for the current user
    vehicles = Vehicle.query.filter_by(user_id=current_user.id).order_by(
        Vehicle.check_in_time.desc()
    ).all()

    # Pass current time for duration calculations of active parkings
    now = datetime.utcnow()

    return render_template('report.html', 
                         vehicles=vehicles,
                         now=now)

@app.route('/analytics')
@login_required
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
            Vehicle.status == 'active',
            Vehicle.user_id == current_user.id
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
            Vehicle.check_in_time >= today,
            Vehicle.user_id == current_user.id
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
            Vehicle.status == 'completed',
            Vehicle.user_id == current_user.id
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
                Vehicle.check_in_time >= today,
                Vehicle.user_id == current_user.id
            ).count(),
            'check_outs': Vehicle.query.filter(
                Vehicle.check_out_time >= today,
                Vehicle.user_id == current_user.id
            ).count(),
            'avg_stay_time': '-- hours',  # Placeholder
            'peak_hour': '-- : --'  # Placeholder
        }

        # Calculate average stay time for completed parkings today
        completed_today = Vehicle.query.filter(
            Vehicle.status == 'completed',
            Vehicle.check_out_time >= today,
            Vehicle.user_id == current_user.id
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
            Vehicle.check_in_time >= today,
            Vehicle.user_id == current_user.id
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)