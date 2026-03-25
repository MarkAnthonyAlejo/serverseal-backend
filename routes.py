import os
from flask import Blueprint, jsonify, request, current_app, g
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import database
import auth

# This Blueprint will hold every route in our app
main_bp = Blueprint('main_bp', __name__)


# --- AUTH ROUTES ---

@main_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'Driver')

    if not email or not password:
        return jsonify({'error': 'EMAIL_AND_PASSWORD_REQUIRED'}), 400

    if role not in ('Admin', 'Driver', 'Client'):
        return jsonify({'error': 'INVALID_ROLE'}), 400

    # Bootstrap check: if users exist, only an Admin may register new users
    user_count = database.get_user_count()
    if user_count > 0:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'AUTH_REQUIRED'}), 401
        try:
            payload = auth.decode_token(auth_header[7:])
            if payload['role'] != 'Admin':
                return jsonify({'error': 'ADMIN_ONLY'}), 403
        except Exception:
            return jsonify({'error': 'TOKEN_INVALID'}), 401

    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    try:
        user_id = database.create_user(email, password_hash, role)
        return jsonify({'user_id': str(user_id), 'status': 'success'}), 201
    except Exception as e:
        if 'unique' in str(e).lower():
            return jsonify({'error': 'EMAIL_ALREADY_EXISTS'}), 409
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'EMAIL_AND_PASSWORD_REQUIRED'}), 400

    user = database.get_user_by_email(email)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'INVALID_CREDENTIALS'}), 401

    token = auth.create_token(str(user['user_id']), user['role'])
    return jsonify({
        'token': token,
        'user': {
            'user_id': str(user['user_id']),
            'email': user['email'],
            'role': user['role'],
        }
    }), 200


@main_bp.route('/api/auth/me', methods=['GET'])
@auth.require_auth
def get_me():
    user = database.get_user_by_id(g.current_user['user_id'])
    if not user:
        return jsonify({'error': 'USER_NOT_FOUND'}), 404
    return jsonify({
        'user_id': str(user['user_id']),
        'email': user['email'],
        'role': user['role'],
    }), 200


# --- USER MANAGEMENT ROUTES ---

@main_bp.route('/api/users', methods=['GET'])
@auth.require_auth
@auth.require_role('Admin')
def list_users():
    try:
        users = database.get_all_users()
        return jsonify([{
            'user_id': str(u['user_id']),
            'email': u['email'],
            'role': u['role'],
            'created_at': u['created_at'].isoformat() if u['created_at'] else None,
        } for u in users]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/users/<uuid:user_id>', methods=['DELETE'])
@auth.require_auth
@auth.require_role('Admin')
def delete_user(user_id):
    # Prevent Admin from deleting themselves
    if str(user_id) == g.current_user['user_id']:
        return jsonify({'error': 'CANNOT_DELETE_SELF'}), 400
    try:
        deleted = database.delete_user(str(user_id))
        if not deleted:
            return jsonify({'error': 'USER_NOT_FOUND'}), 404
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- SHIPMENT ROUTES ---

@main_bp.route("/api/shipments", methods=["POST"])
@auth.require_auth
@auth.require_role('Admin', 'Driver')
def add_shipment():
    data = request.json
    try:
        new_id = database.create_shipment(
            data['bol_number'],
            data['origin'],
            data['destination']
        )
        return jsonify({"shipment_id": str(new_id), "status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/shipments", methods=["GET"])
@auth.require_auth
def list_shipments():
    try:
        shipments = database.get_all_shipments()
        if shipments is None:
            return jsonify({"error": "Database is currently unavailable"}), 503
        return jsonify(shipments), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- EVENT ROUTES ---

@main_bp.route("/api/events", methods=["POST"])
@auth.require_auth
@auth.require_role('Admin', 'Driver')
def add_events():
    data = request.json
    try:
        new_event_id = database.create_event(
            data['shipment_id'],
            data['event_type'],
            data.get('location'),
            data.get('hardware_details'),
            data.get('notes'),
            # handler_id comes from the authenticated user, not the request body
            g.current_user['user_id'],
        )
        return jsonify({"event_id": str(new_event_id), "status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/shipments/<uuid:shipment_id>/status", methods=["PATCH"])
@auth.require_auth
@auth.require_role('Admin', 'Driver')
def update_status(shipment_id):
    data = request.json
    new_status = data.get('status') if data else None
    if not new_status:
        return jsonify({"error": "Missing 'status' field"}), 400
    try:
        result = database.update_shipment_status(str(shipment_id), new_status)
        if not result:
            return jsonify({"error": "Shipment not found"}), 404
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/shipments/active", methods=["GET"])
@auth.require_auth
def list_active_shipments():
    try:
        shipments = database.get_active_shipments()
        if shipments is None:
            return jsonify({"error": "Database is currently unavailable"}), 503
        return jsonify(shipments), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/shipments/bol/<string:bol_number>", methods=["GET"])
@auth.require_auth
def get_shipment_by_bol(bol_number):
    try:
        shipment = database.get_shipment_by_bol(bol_number)
        if not shipment:
            return jsonify({"error": f"No shipment found for BOL: {bol_number}"}), 404
        return jsonify(shipment), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main_bp.route("/api/shipments/<uuid:shipment_id>", methods=["GET"])
@auth.require_auth
def get_full_shipment(shipment_id):
    try:
        data = database.get_shipment_with_history(str(shipment_id))
        if not data:
            return jsonify({"error": "Shipment not found"}), 404
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- MEDIA UPLOAD ROUTE ---

def allowed_file(filename):
    allowed = current_app.config.get(
        'ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in allowed


@main_bp.route('/api/media/upload', methods=['POST'])
@auth.require_auth
@auth.require_role('Admin', 'Driver')
def add_media():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file and not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Please upload png, jpg, jpeg, or gif."}), 400

    event_id = request.form.get('event_id')
    media_type = request.form.get('media_type', 'image')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and event_id:
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        try:
            media_id = database.create_media(
                event_id=event_id,
                media_type=media_type,
                file_path=file_path,
                latitude=lat,
                longitude=lon
            )
            return jsonify({
                "message": "Media uploaded successfully",
                "media_id": media_id,
                "path": file_path
            }), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Missing event_id"}), 400
