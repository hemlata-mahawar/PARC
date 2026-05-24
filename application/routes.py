# from flask import current_app as app, jsonify, render_template, request, send_from_directory
from flask import jsonify, render_template, request, send_from_directory
from flask_security import auth_required, login_user, logout_user, current_user, roles_required, roles_accepted, hash_password, verify_password
from datetime import datetime
from sqlalchemy import func
from celery.result import AsyncResult

from .database import db
from .models import *
from .utils import *
from .tasks import csv_report, monthly_report
from cache import cache
from .resources import get_user_data
from app import app


@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def user_login():
    body = request.get_json()
    email = body['email']
    password = body['password']
    
    if not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    user = app.security.datastore.find_user(email=email)
    if user: 
        if verify_password(password, user.password):
            login_user(user)
            return jsonify({"message": "Login successful",
                            "roles": roles_list(user.roles), 
                            "user_id": user.id,
                            "auth-token": user.get_auth_token()}), 200
        else:
            return jsonify({"error": "Invalid password"}), 401

    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/api/user_details', methods=['GET'])
@auth_required('token')  
@roles_accepted('admin','user')
def get_user_details():    
    roles = [role.name for role in current_user.roles]
    return jsonify({
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": roles[0]
    }), 200

@app.route('/api/register', methods=['POST'])
def register_user():
    credentials = request.get_json()
    email = credentials['email']
    username = credentials['username']
    password = credentials['password']
    confirm_password = credentials['confirm_password']
    if not email or not username or not password or not confirm_password:
        return jsonify({"error": "please fill all the fields"}), 401
    
    if password != confirm_password:
        return jsonify({"error": "password do not match"}), 400
    
    if not app.security.datastore.find_user(email=credentials['email']):
        app.security.datastore.create_user(
            email=credentials['email'],
            username=credentials['username'],
            password=hash_password(credentials['password']),
            roles = ['user']
        )
        db.session.commit()
        cache.delete_memoized(get_user_data)
        return jsonify({"message": "User created successfully"}), 201
    else:
        return jsonify({"error": "User already exists"}), 409


@app.route('/api/lots/<int:lot_id>/spots', methods=['GET'])
@auth_required('token')  
@roles_required('admin')
def get_spots_by_lot(lot_id):
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    if spots:
        spots = [{"spot_id": spot.id, "lot_id": spot.lot_id, "status": spot.status} for spot in spots]
        available_spots = 0
        occupied_spots = 0
        for spot in spots:
            if spot["status"] == "available":
                available_spots += 1
            elif spot["status"] == "occupied": 
                occupied_spots += 1

        return jsonify(spots, occupied_spots, available_spots)
    else:
        return jsonify({"error": "No spots found for this lot"}), 404

# GET a specific spot in a lot
@app.route('/api/lots/<int:lot_id>/spots/<int:spot_id>', methods=['GET'])
@auth_required('token')  
@roles_required('admin')
def get_spot_by_id(lot_id, spot_id):
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, id=spot_id).first()
    if spot.status == "available":
        return jsonify({"spot_id": spot.id, "lot_id": spot.lot_id, "status": spot.status}), 200
    elif spot.status == "occupied":
        reserved_spot = Reservation.query.filter_by(spot_id=spot_id).first()
        if reserved_spot:
            return jsonify({"spot_id": reserved_spot.spot_id, "user_id": reserved_spot.user_id, "vrn": reserved_spot.vrn, "parking_timestamp": reserved_spot.parking_timestamp, "parking_cost": reserved_spot.parking_cost}), 200
        else:
            return jsonify({"error": "Spot not found"}), 404
    else:
        return jsonify({"error": "Spot not found"}), 404

@app.route("/api/search")
@auth_required('token')  
@roles_required('user')
def user_search():
    search_query = request.args.get('query', '')

    results = ParkingLot.query.filter(
        db.or_(
            ParkingLot.pl_name.ilike(f"%{search_query}%"),
            ParkingLot.address.ilike(f"%{search_query}%"),
            db.cast(ParkingLot.pincode, db.String).ilike(f"%{search_query}%")
        )
    ).all()
    if results:
        results = [{"lot_id": lot.id, "pl_name": lot.pl_name, "address": lot.address, "pincode": lot.pincode, "price": lot.price, "spots_count": lot.spots_count, "availability": (lot.spots_count - get_reserved_spots_count(lot.id)) } for lot in results]
        return jsonify(results), 200
    else:
        return jsonify({"error": "No results found"}), 404

@app.route('/api/<int:lot_id>/book', methods=['GET'])
@auth_required('token')  
@roles_required('user')
def book_spot( lot_id):
    user_id = current_user.id
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status="available").first()
    if spot:
        return jsonify({"spot_id": spot.id, "lot_id": lot_id, "user_id": user_id, "pl_name": spot.lot.pl_name, "address": spot.lot.address}), 200
    else:
        return jsonify({"error": "No available spots found in this lot"}), 404

@app.route('/api/reservation/<int:reserve_id>/get', methods=['GET'])
@auth_required('token')  
@roles_required('user')
def get_reservation(reserve_id):
    reservation = Reservation.query.get(reserve_id)
    duration = (datetime.now() - reservation.parking_timestamp).total_seconds() / 3600
    if reservation:
        return jsonify({
            "reservation_id": reservation.id,
            "lot_id": reservation.spot.lot_id,
            "price": reservation.spot.lot.price,
             "spot_id": reservation.spot_id, 
             "user_id": reservation.user_id, 
             "vrn": reservation.vrn, 
             "parking_timestamp": reservation.parking_timestamp,
             "leaving_timestamp": datetime.now(),
             "duration": duration, 
             "status": reservation.status, 
             "pl_name": reservation.spot.lot.pl_name, 
             "parking_cost": (reservation.spot.lot.price* duration)}), 200
    else:
        return jsonify({"error": "Reservation not found"}), 404

@app.route('/api/<int:user_id>/history', methods=['GET'])
@auth_required('token')  
@roles_required('user')
def get_user_history(user_id):
    reservations = Reservation.query.filter(Reservation.user_id==user_id, Reservation.status == "unpaid").all()
    
    if reservations:
        reservations = [{"reservation_id": reservation.id, "lot_id": reservation.spot.lot_id, "spot_id": reservation.spot_id, "vrn": reservation.vrn, "parking_timestamp": reservation.parking_timestamp, "address": reservation.spot.lot.address} for reservation in reservations]
        return jsonify(reservations), 200
    else:
        return jsonify({"error": "No reservations found for this user"}), 404

@app.route('/api/reservation/<int:reserve_id>/release')
@auth_required('token')  
@roles_required('user')
def release_spot(reserve_id):
    reservation = Reservation.query.get(reserve_id)
    if reservation:
        duration = (datetime.now() - reservation.parking_timestamp).total_seconds() / 3600
        reservation.spot.status = "available"
        reservation.status = "paid"
        reservation.duration = duration
        reservation.leaving_timestamp = datetime.now()
        reservation.parking_cost = int(reservation.spot.lot.price * duration)
        db.session.commit()
        return jsonify({"message": "Spot released successfully"}), 200
    else:
        return jsonify({"error": "Reservation not found"}), 404

@app.route('/api/user/<int:user_id>/summary/summary_data', methods=['GET'])
@auth_required('token')  
@roles_required('user')
def user_spot_usage(user_id):
    data = db.session.query(
        ParkingLot.id.label('lot_id'),
        ParkingLot.pl_name.label('lot_name'),
        func.count(Reservation.id).label('times_used')
    ).join(ParkingSpot, ParkingSpot.id == Reservation.spot_id
    ).join(ParkingLot, ParkingLot.id == ParkingSpot.lot_id
    ).filter(Reservation.user_id == user_id
    ).group_by(ParkingLot.id, ParkingLot.pl_name
    ).all()

    result = [
        {'lot_id': lot_id, 'lot_name': lot_name, 'times_used': times_used}
        for lot_id, lot_name, times_used in data
    ]

    return jsonify(result), 200

@app.route('/api/user/<int:user_id>/summary/duration_data', methods=['GET'])
@auth_required('token')  
@roles_required('user')
def user_spot_duration(user_id):
    duration_data = Reservation.query.filter_by(user_id = user_id).all()
    if duration_data:
        result = [{
            "id": r.id, 
            "pl_name": r.spot.lot.pl_name, 
            "parking_timestamp": r.parking_timestamp, 
            "leaving_timestamp": r.leaving_timestamp, 
            "duration": r.duration, 
            "date": r.parking_timestamp.strftime('%d-%m-%Y'), 
            "address": r.spot.lot.address, 
            "pincode" : r.spot.lot.pincode, 
            "cost": r.parking_cost} for r in duration_data]
    return jsonify(result), 200


@app.route('/api/admin/summary/revenue', methods=['GET'])
@auth_required('token')  
@roles_required('admin')
def get_parking_lot_revenue():
    results = db.session.query(
        ParkingLot.id,
        ParkingLot.pl_name,
        func.sum(Reservation.parking_cost).label('total_revenue')
    ).join(ParkingSpot, ParkingLot.id == ParkingSpot.lot_id
    ).join(Reservation, ParkingSpot.id == Reservation.spot_id
    ).group_by(ParkingLot.id).all()

    response = [{
        'lot_id': lot_id,
        'pl_name': name,
        'total_revenue': revenue or 0
    } for lot_id, name, revenue in results]

    return jsonify(response), 200

@app.route('/api/admin/summary/availability', methods=['GET'])
@auth_required('token')  
@roles_required('admin')
def get_parking_lot_availability():
    parking_lots = ParkingLot.query.all()
    
    lot_availability = []

    for lot in parking_lots:
        total_spots = lot.spots_count 
        occupied_spots = get_reserved_spots_count(lot.id)  
        available_spots = total_spots - occupied_spots  
        lot_availability.append({
            "pl_name": lot.pl_name,
            "available_spots": available_spots,
            "occupied_spots": occupied_spots,
            "total_spots": total_spots
        })
    
    return jsonify(lot_availability), 200


@app.route('/api/admin/search', methods=['GET'])
@auth_required('token')  
@roles_required('admin')
def admin_search():
        search_query = request.args.get('query', '')
        table = request.args.get('table', '')
        if table == "users":
            results = User.query.filter(
                db.or_(
                    User.username.ilike(f"%{search_query}%"),
                    User.email.ilike(f"%{search_query}%"),
                    User.active.ilike(f"%{search_query}%"),
                    db.cast(User.id, db.String).ilike(f"%{search_query}%"),

                )
            ).all()
            if results:
                results = [{
                    "user_id": user.id, 
                    "username": user.username, 
                    "email": user.email, 
                    "active": user.active} for user in results]
                return jsonify(results), 200
            else:
                return jsonify({"error": "No results found"}), 404
        elif table == "parkingLot":
            results = ParkingLot.query.filter(
                db.or_(
                    ParkingLot.pl_name.ilike(f"%{search_query}%"),
                    ParkingLot.address.ilike(f"%{search_query}%"),
                    db.cast(ParkingLot.id, db.String).ilike(f"%{search_query}%"),
                    db.cast(ParkingLot.price, db.String).ilike(f"%{search_query}%"),
                    db.cast(ParkingLot.pincode, db.String).ilike(f"%{search_query}%")
                )
            ).all()
            if results:
                results = [{
                    "lot_id": lot.id, 
                    "pl_name": lot.pl_name, 
                    "address": lot.address, 
                    "pincode": lot.pincode, 
                    "price": lot.price, 
                    "spots_count": lot.spots_count,
                    "capacity": lot.capacity} for lot in results]
                return jsonify(results), 200
            else:
                return jsonify({"error": "No results found"}), 404
        elif table == "parkingSpot":
            results = ParkingSpot.query.filter(
                db.or_(
                    ParkingSpot.status.ilike(f"%{search_query}%"),
                    db.cast(ParkingSpot.id, db.String).ilike(f"%{search_query}%"),
                    db.cast(ParkingSpot.lot_id, db.String).ilike(f"%{search_query}%")
                )
            ).all()
            if results:
                results = [{
                    "spot_id": spot.id, 
                    "lot_id": spot.lot_id, 
                    "status": spot.status} for spot in results]
                return jsonify(results), 200
            else:
                return jsonify({"error": "No results found"}), 404
        elif table == "reserveParkingSpot":
            results = Reservation.query.filter(
                db.or_(
                    Reservation.status.ilike(f"%{search_query}%"),
                    db.cast(Reservation.id, db.String).ilike(f"%{search_query}%"),
                    db.cast(Reservation.user_id, db.String).ilike(f"%{search_query}%"),
                    db.cast(Reservation.spot_id, db.String).ilike(f"%{search_query}%")
                )
            ).all()
            
            if results:
                results = [{
                    "reservation_id": reservation.id, 
                    "spot_id": reservation.spot_id, 
                    "user_id": reservation.user_id, 
                    "vrn": reservation.vrn, 
                    "parking_timestamp": reservation.parking_timestamp, 
                    "leaving_timestamp": reservation.leaving_timestamp,
                    "price": reservation.spot.lot.price,
                    "parking_cost": reservation.parking_cost,
                    "status": reservation.status} for reservation in results]
                return jsonify(results), 200
            else:
                return jsonify({"error": "No results found"}), 404
        else:
            return jsonify({"error": "something wrong!"}), 400

@app.route("/api/export/")
@auth_required('token')  
@roles_accepted('admin','user')
def export_csv():
    user = current_user
    roles = roles_list(user.roles)
    if "admin" in roles:
        user_id = None
    elif "user" in roles:
        user_id = user.id      
    result = csv_report.delay(user_id=user_id)
    return jsonify({
        "id" : result.id,
        "result" : result.result,
        }), 200

@app.route('/api/csv_result/<id>')
def csv_result(id):
    result = AsyncResult(id)
    return send_from_directory('static/csv_folder', result.result, as_attachment=True), 200
