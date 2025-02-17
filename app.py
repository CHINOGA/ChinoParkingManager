import os
import logging
import io
import csv
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template, request, flash, redirect, url_for, send_file, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import aliased
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
                is_approved=True,
                is_active=True #added is_active field
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin account created successfully")

    except Exception as e:
        logger.error(f"Error during data initialization: {str(e)}")
        db.session.rollback()
        raise

# Initialize database and default data
with app.app_context():
    create_tables()
    initialize_default_data()

# Authentication routes
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    spaces = {space.vehicle_type: {"total": space.total_spaces, "occupied": space.occupied_spaces}
             for space in ParkingSpace.query.all()}
    return render_template('index.html', spaces=spaces)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

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
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

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
            is_approved=False,  # Users need admin approval by default
            is_active=True #added is_active field
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
        return redirect(url_for('dashboard'))

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
        return redirect(url_for('dashboard'))

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
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)
    # Instead of deleting, we could also add a rejected status
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} has been rejected.', 'success')
    return redirect(url_for('manage_users'))

# Add these new routes after the existing user management routes
@app.route('/admin/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
def deactivate_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot deactivate admin users.', 'error')
    else:
        user.is_active = False
        db.session.commit()
        flash(f'User {user.username} has been deactivated.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
@login_required
def activate_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    flash(f'User {user.username} has been activated.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot delete admin users.', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} has been deleted.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        # Check if username already exists for different user
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != user_id:
            flash('Username already exists.', 'error')
            return redirect(url_for('edit_user', user_id=user_id))

        # Check if email already exists for different user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != user_id:
            flash('Email already registered.', 'error')
            return redirect(url_for('edit_user', user_id=user_id))

        user.username = username
        user.email = email
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash('User details updated successfully.', 'success')
        return redirect(url_for('manage_users'))

    return render_template('admin/edit_user.html', user=user)

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
        return redirect(url_for('dashboard'))

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
        return redirect(url_for('dashboard'))

    spaces = ParkingSpace.query.all()
    return render_template('admin/spaces.html', spaces=spaces)

@app.route('/admin/spaces/update', methods=['POST'])
@login_required
def update_spaces():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('admin_spaces'))

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

# Add these new routes after the existing admin routes
@app.route('/admin/reports')
@login_required
def admin_reports():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Get filter parameters
        date_range = request.args.get('date_range', 'today')
        vehicle_type = request.args.get('vehicle_type', 'all')
        status = request.args.get('status', 'all')
        handover_status = request.args.get('handover_status', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Calculate date range
        today = datetime.utcnow().date()
        if date_range == 'today':
            start_date = today
            end_date = today + timedelta(days=1)
        elif date_range == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = today
        elif date_range == 'this_week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=7)
        elif date_range == 'last_week':
            start_date = today - timedelta(days=today.weekday() + 7)
            end_date = start_date + timedelta(days=7)
        elif date_range == 'this_month':
            start_date = today.replace(day=1)
            end_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        elif date_range == 'custom':
            if not start_date or not end_date:
                flash('Please select both start and end dates for custom range', 'warning')
                return redirect(url_for('admin_reports'))
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date() + timedelta(days=1)

        # Build query filters
        filters = [
            Vehicle.check_in_time >= start_date,
            Vehicle.check_in_time < end_date
        ]

        if vehicle_type != 'all':
            filters.append(Vehicle.vehicle_type == vehicle_type)
        if status != 'all':
            filters.append(Vehicle.status == status)
        if handover_status != 'all':
            if handover_status == 'handed_over':
                filters.append(Vehicle.handler_id.isnot(None))
            elif handover_status == 'not_handed_over':
                filters.append(Vehicle.handler_id.is_(None))

        # Create aliases for User joins
        RecordedByUser = aliased(User)
        HandlerUser = aliased(User)

        # Query vehicles with proper aliasing
        vehicles = (Vehicle.query
                   .join(RecordedByUser, Vehicle.user_id == RecordedByUser.id)
                   .outerjoin(HandlerUser, Vehicle.handler_id == HandlerUser.id)
                   .filter(and_(*filters))
                   .order_by(Vehicle.check_in_time.desc())
                   .all())

        # Calculate metrics
        metrics = calculate_metrics(vehicles, start_date, end_date)

        # Add handover metrics
        total_handovers = sum(1 for v in vehicles if v.handler_id is not None)
        active_handovers = sum(1 for v in vehicles if v.handler_id is not None and v.status == 'active')
        metrics.update({
            'total_handovers': total_handovers,
            'active_handovers': active_handovers
        })

        vehicle_distribution = calculate_vehicle_distribution(vehicles)
        checkins_trend = calculate_checkins_trend(start_date, end_date)

        return render_template(
            'admin/reports.html',
            vehicles=vehicles,
            metrics=metrics,
            vehicle_distribution=vehicle_distribution,
            checkins_trend=checkins_trend,
            date_range=date_range,
            vehicle_type=vehicle_type,
            status=status,
            handover_status=handover_status,
            start_date=start_date.strftime('%Y-%m-%d') if isinstance(start_date, datetime) else start_date,
            end_date=(end_date - timedelta(days=1)).strftime('%Y-%m-%d') if isinstance(end_date, datetime) else end_date,
            now=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error generating admin report: {str(e)}")
        flash('Error generating report', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/reports/export')
@login_required
def export_report():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Get the same filters as the report
        date_range = request.args.get('date_range', 'today')
        vehicle_type = request.args.get('vehicle_type', 'all')
        status = request.args.get('status', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Use the same date range logic as in admin_reports
        today = datetime.utcnow().date()
        if date_range == 'today':
            start_date = today
            end_date = today + timedelta(days=1)
        elif date_range == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = today
        elif date_range == 'this_week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=7)
        elif date_range == 'last_week':
            start_date = today - timedelta(days=today.weekday() + 7)
            end_date = start_date + timedelta(days=7)
        elif date_range == 'this_month':
            start_date = today.replace(day=1)
            end_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        elif date_range == 'custom':
            if not start_date or not end_date:
                flash('Please select both start and end dates for custom range', 'warning')
                return redirect(url_for('admin_reports'))
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date() + timedelta(days=1)

        # Build query filters
        filters = [
            Vehicle.check_in_time >= start_date,
            Vehicle.check_in_time < end_date
        ]

        if vehicle_type != 'all':
            filters.append(Vehicle.vehicle_type == vehicle_type)
        if status != 'all':
            filters.append(Vehicle.status == status)

        # Query vehicles with filters
        vehicles = (Vehicle.query
                   .join(User)
                   .options(db.joinedload(Vehicle.recorded_by))
                   .filter(and_(*filters))
                   .order_by(Vehicle.check_in_time.desc())
                   .all())

        # Create CSV file
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow([
            'Recorded By', 'Email', 'Vehicle Type', 'Plate Number',
            'Vehicle Model', 'Vehicle Color', 'Driver Name', 'Driver ID Type',
            'Driver ID Number', 'Driver Phone', 'Driver Residence',
            'Check-in Time (EAT)', 'Check-out Time (EAT)', 'Duration (Hours)',
            'Status'
        ])

        # Write data
        for vehicle in vehicles:
            if vehicle.status == 'completed':
                duration = (vehicle.check_out_time - vehicle.check_in_time).total_seconds() / 3600
            else:
                duration = (datetime.utcnow() - vehicle.check_in_time).total_seconds() / 3600

            writer.writerow([
                vehicle.recorded_by.username,
                vehicle.recorded_by.email,
                vehicle.vehicle_type,
                vehicle.plate_number,
                vehicle.vehicle_model,
                vehicle.vehicle_color,
                vehicle.driver_name,
                vehicle.driver_id_type,
                vehicle.driver_id_number,
                vehicle.driver_phone,
                vehicle.driver_residence,
                vehicle.formatted_check_in_time(),
                vehicle.formatted_check_out_time() or 'N/A',
                f"{duration:.1f}",
                vehicle.status
            ])

        # Prepare the response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'parking_report_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
        )

    except Exception as e:
        logger.error(f"Error exporting report: {str(e)}")
        flash('Error exporting report', 'error')
        return redirect(url_for('admin_reports'))


# Add these new routes after the existing admin routes
@app.route('/admin/reports/api')
@login_required
def admin_reports_api():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Get filter parameters
        date_range = request.args.get('date_range', 'today')
        vehicle_type = request.args.get('vehicle_type', 'all')
        status = request.args.get('status', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Calculate date range
        today = datetime.utcnow().date()
        if date_range == 'today':
            start_date = today
            end_date = today + timedelta(days=1)
        elif date_range == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = today
        elif date_range == 'this_week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=7)
        elif date_range == 'last_week':
            start_date = today - timedelta(days=today.weekday() + 7)
            end_date = start_date + timedelta(days=7)
        elif date_range == 'this_month':
            start_date = today.replace(day=1)
            end_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        elif date_range == 'custom':
            if not start_date or not end_date:
                return jsonify({'error': 'Invalid date range'}), 400
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date() + timedelta(days=1)

        # Build query filters
        filters = [
            Vehicle.check_in_time >= start_date,
            Vehicle.check_in_time < end_date
        ]

        if vehicle_type != 'all':
            filters.append(Vehicle.vehicle_type == vehicle_type)
        if status != 'all':
            filters.append(Vehicle.status == status)

        # Query vehicles with filters
        vehicles = (Vehicle.query
                   .join(User)
                   .options(db.joinedload(Vehicle.recorded_by))
                   .filter(and_(*filters))
                   .order_by(Vehicle.check_in_time.desc())
                   .all())

        # Calculate metrics
        metrics = calculate_metrics(vehicles, start_date, end_date)
        vehicle_distribution = calculate_vehicle_distribution(vehicles)
        checkins_trend = calculate_checkins_trend(start_date, end_date)

        # Format vehicle data
        vehicle_data = []
        for vehicle in vehicles:
            if vehicle.status == 'completed':
                duration = (vehicle.check_out_time - vehicle.check_in_time).total_seconds() / 3600
            else:
                duration = (datetime.utcnow() - vehicle.check_in_time).total_seconds() / 3600

            vehicle_data.append({
                'recorded_by': {
                    'username': vehicle.recorded_by.username,
                    'email': vehicle.recorded_by.email
                },
                'vehicle_type': vehicle.vehicle_type,
                'plate_number': vehicle.plate_number,
                'vehicle_model': vehicle.vehicle_model,
                'vehicle_color': vehicle.vehicle_color,
                'driver_name': vehicle.driver_name,
                'driver_id_type': vehicle.driver_id_type,
                'driver_id_number': vehicle.driver_id_number,
                'driver_phone': vehicle.driver_phone,
                'driver_residence': vehicle.driver_residence,
                'check_in_time': vehicle.formatted_check_in_time(),
                'check_out_time': vehicle.formatted_check_out_time() or '-',
                'duration': f"{duration:.1f}",
                'status': vehicle.status
            })

        return jsonify({
            'vehicles': vehicle_data,
            'metrics': metrics,
            'vehicle_distribution': vehicle_distribution,
            'checkins_trend': checkins_trend
        })

    except Exception as e:
        logger.error(f"Error generating API report: {str(e)}")
        return jsonify({'error': 'Error generating report'}), 500

# Protected routes for regular users
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
            return redirect(url_for('dashboard'))

        # Check if vehicle already exists and is active
        existing_vehicle = Vehicle.query.filter_by(
            plate_number=plate_number, 
            status='active'
        ).first()

        if existing_vehicle:
            flash('Vehicle is already parked!', 'error')
            return redirect(url_for('dashboard'))

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

    return redirect(url_for('dashboard'))

@app.route('/check-out', methods=['POST'])
@login_required
def check_out():
    try:
        plate_number = request.form.get('plate_number')
                # Modified query to check both user_id and handler_id
        vehicle = Vehicle.query.filter(
            Vehicle.plate_number == plate_number,
            Vehicle.status == 'active'
        ).filter(
            (Vehicle.user_id == current_user.id) | 
            (Vehicle.handler_id == current_user.id)
        ).first()

        if not vehicle:
            flash('Vehicle not found or already checked out!', 'error')
            return redirect(url_for('dashboard'))

        space = ParkingSpace.query.filter_by(vehicle_type=vehicle.vehicle_type).first()
        if space:
            space.occupied_spaces = max(0, space.occupied_spaces - 1)

        vehicle.status = 'completed'
        vehicle.check_out_time = datetime.utcnow()
        vehicle.handler_id = None  # Clear handler when checking out
        db.session.commit()
        flash('Vehicle checked out successfully!', 'success')
    except Exception as e:
        logger.error(f"Error during check-out: {str(e)}")
        flash('An error occurred during check-out!', 'error')
        db.session.rollback()

    return redirect(url_for('dashboard'))

# Fix the typo in the report route
@app.route('/report')
@login_required
def report():
    try:
        # Get vehicles based on user role
        if current_user.is_admin:
            # Admin sees all vehicles with user information
            vehicles = (Vehicle.query
                       .join(User, Vehicle.user_id == User.id)
                       .options(db.joinedload(Vehicle.recorded_by))
                       .order_by(Vehicle.check_in_time.desc())
                       .all())
            logger.info(f"Admin report: Found {len(vehicles)} vehicles")
        else:
            # Regular users only see their vehicles
            vehicles = (Vehicle.query
                       .filter_by(user_id=current_user.id)  # Fixed userid to user_id
                       .order_by(Vehicle.check_in_time.desc())
                       .all())
            logger.info(f"User report: Found {len(vehicles)} vehicles for user {current_user.username}")

        return render_template('report.html',
                           vehicles=vehicles,
                           now=datetime.utcnow(),
                           is_admin=current_user.is_admin)

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        flash('Error loading report data', 'error')
        return redirect(url_for('dashboard'))

# Add helper functions for metrics calculation
def calculate_metrics(vehicles, start_date, end_date):
    """Calculate various metrics for the report"""
    try:
        total_vehicles = len(vehicles)

        # Calculate average duration
        durations = []
        for vehicle in vehicles:
            if vehicle.status == 'completed':
                duration = (vehicle.check_out_time - vehicle.check_in_time).total_seconds() / 3600
            else:
                duration = (datetime.utcnow() - vehicle.check_in_time).total_seconds() / 3600
            durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else 0

        # Find peak hour
        hour_counts = defaultdict(int)
        for vehicle in vehicles:
            hour = vehicle.check_in_time.replace(minute=0, second=0, microsecond=0)
            hour_counts[hour] += 1

        peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
        peak_hour_str = peak_hour.strftime('%H:00') if peak_hour else 'N/A'

        # Calculate space utilization
        total_spaces = sum(space.total_spaces for space in ParkingSpace.query.all())
        avg_occupied = db.session.query(func.avg(ParkingSpace.occupied_spaces)).scalar() or 0
        utilization = (avg_occupied / total_spaces * 100) if total_spaces > 0 else 0

        return {
            'total_vehicles': total_vehicles,
            'avg_duration': avg_duration,
            'peak_hour': peak_hour_str,
            'utilization': utilization
        }
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        return {
            'total_vehicles': 0,
            'avg_duration': 0,
            'peak_hour': 'N/A',
            'utilization': 0
        }

def calculate_vehicle_distribution(vehicles):
    """Calculate vehicle type distribution for pie chart"""
    try:
        distribution = defaultdict(int)
        for vehicle in vehicles:
            distribution[vehicle.vehicle_type.title()] += 1

        return {
            'labels': list(distribution.keys()),
            'data': list(distribution.values())
        }
    except Exception as e:
        logger.error(f"Error calculating vehicle distribution: {str(e)}")
        return {'labels': [], 'data': []}

def calculate_checkins_trend(start_date, end_date):
    """Calculate daily check-ins trend"""
    try:
        dates = []
        counts = []
        current_date = start_date

        while current_date < end_date:
            next_date = current_date + timedelta(days=1)
            count = Vehicle.query.filter(
                Vehicle.check_in_time >= current_date,
                Vehicle.check_in_time < next_date
            ).count()

            dates.append(current_date.strftime('%Y-%m-%d'))
            counts.append(count)
            current_date = next_date

        return {
            'labels': dates,
            'data': counts
        }
    except Exception as e:
        logger.error(f"Error calculating check-ins trend: {str(e)}")
        return {'labels': [], 'data': []}

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
        return redirect(url_for('dashboard'))

# Add these new routes after the existing vehicle management routes
@app.route('/handover/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def handover_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    # Check if user has permission to handover this vehicle
    if vehicle.user_id != current_user.id and vehicle.handler_id != current_user.id:
        flash('You do not have permission to handover this vehicle.', 'error')
        return redirect(url_for('dashboard'))

    if vehicle.status != 'active':
        flash('Only active vehicles can be handed over.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        handler_username = request.form.get('handler_username')
        handover_notes = request.form.get('handover_notes')

        handler = User.query.filter_by(username=handler_username).first()
        if not handler:
            flash('User not found.', 'error')
            return redirect(url_for('handover_vehicle', vehicle_id=vehicle_id))

        if not handler.is_active or not handler.is_approved:
            flash('Selected user cannot receive vehicle handovers.', 'error')
            return redirect(url_for('handover_vehicle', vehicle_id=vehicle_id))

        vehicle.handler_id = handler.id
        vehicle.handover_time = datetime.utcnow()
        vehicle.handover_notes = handover_notes
        db.session.commit()

        flash(f'Vehicle handed over to {handler.username} successfully.', 'success')
        return redirect(url_for('dashboard'))

    users = User.query.filter(
        User.is_active == True,
        User.is_approved == True,
        User.id != current_user.id
    ).all()

    return render_template('handover.html', vehicle=vehicle, users=users)

@app.route('/my-handovers')
@login_required
def my_handovers():
    # Get vehicles handed over to current user
    received_handovers = Vehicle.query.filter(
        Vehicle.handler_id == current_user.id,
        Vehicle.status == 'active'
    ).all()

    # Get vehicles user has handed over to others
    sent_handovers = Vehicle.query.filter(
        Vehicle.user_id == current_user.id,
        Vehicle.handler_id.isnot(None),
        Vehicle.status == 'active'
    ).all()

    return render_template('my_handovers.html',
                       received_handovers=received_handovers,
                       sent_handovers=sent_handovers)

@app.route('/cancel-handover/<int:vehicle_id>', methods=['POST'])
@login_required
def cancel_handover(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    # Only the original recorder can cancel a handover
    if vehicle.user_id != current_user.id:
        flash('You do not have permission to cancel this handover.', 'error')
        return redirect(url_for('my_handovers'))

    if vehicle.status != 'active':
        flash('Only active handovers can be cancelled.', 'error')
        return redirect(url_for('my_handovers'))

    vehicle.handler_id = None
    vehicle.handover_time = None
    vehicle.handover_notes = None
    db.session.commit()

    flash('Handover cancelled successfully.', 'success')
    return redirect(url_for('my_handovers'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)