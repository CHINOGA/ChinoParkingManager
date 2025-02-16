import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key")

PARKING_DATA_FILE = "data/parking.json"

# Initialize parking spaces
PARKING_SPACES = {
    "motorcycle": {"total": 50, "occupied": 0},
    "bajaj": {"total": 30, "occupied": 0},
    "car": {"total": 20, "occupied": 0}
}

def load_parking_data():
    if os.path.exists(PARKING_DATA_FILE):
        with open(PARKING_DATA_FILE, 'r') as f:
            return json.load(f)
    return {"vehicles": [], "spaces": PARKING_SPACES}

def save_parking_data(data):
    os.makedirs(os.path.dirname(PARKING_DATA_FILE), exist_ok=True)
    with open(PARKING_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    parking_data = load_parking_data()
    return render_template('index.html', spaces=parking_data["spaces"])

@app.route('/check-in', methods=['POST'])
def check_in():
    vehicle_type = request.form.get('vehicle_type')
    plate_number = request.form.get('plate_number')
    
    parking_data = load_parking_data()
    
    if parking_data["spaces"][vehicle_type]["occupied"] >= parking_data["spaces"][vehicle_type]["total"]:
        flash('No available spaces for this vehicle type!', 'error')
        return redirect(url_for('index'))
    
    vehicle = {
        "type": vehicle_type,
        "plate_number": plate_number,
        "check_in_time": datetime.now().isoformat(),
        "status": "active"
    }
    
    parking_data["vehicles"].append(vehicle)
    parking_data["spaces"][vehicle_type]["occupied"] += 1
    save_parking_data(parking_data)
    
    flash('Vehicle checked in successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/check-out', methods=['POST'])
def check_out():
    plate_number = request.form.get('plate_number')
    
    parking_data = load_parking_data()
    
    for vehicle in parking_data["vehicles"]:
        if vehicle["plate_number"] == plate_number and vehicle["status"] == "active":
            vehicle["status"] = "completed"
            vehicle["check_out_time"] = datetime.now().isoformat()
            parking_data["spaces"][vehicle["type"]]["occupied"] -= 1
            save_parking_data(parking_data)
            flash('Vehicle checked out successfully!', 'success')
            return redirect(url_for('index'))
    
    flash('Vehicle not found or already checked out!', 'error')
    return redirect(url_for('index'))

@app.route('/report')
def report():
    parking_data = load_parking_data()
    active_vehicles = [v for v in parking_data["vehicles"] if v["status"] == "active"]
    return render_template('report.html', vehicles=active_vehicles, spaces=parking_data["spaces"])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
