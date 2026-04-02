import io
import os
from flask import Blueprint, jsonify, request, current_app, g, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import database
import auth
import pdf_generator

# This Blueprint will hold every route in our app
main_bp = Blueprint('main_bp', __name__)


# --- NOTIFICATION HELPER ---

def _notify(roles, shipment_id, notif_type, message, extra_user_ids=None):
    """Fan out a notification to all users with the given roles, plus any specific user_ids."""
    user_ids = set(database.get_user_ids_by_roles(roles))
    if extra_user_ids:
        user_ids.update(extra_user_ids)
    if user_ids:
        database.create_notifications(list(user_ids), shipment_id, notif_type, message)


# --- AUTH ROUTES ---

@main_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'Driver')

    if not email or not password:
        return jsonify({'error': 'EMAIL_AND_PASSWORD_REQUIRED'}), 400

    if role not in ('Admin', 'Driver', 'Client', 'QA Inspector'):
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
        qa_filter = g.current_user['user_id'] if g.current_user['role'] == 'QA Inspector' else None
        shipments = database.get_all_shipments(assigned_qa_id=qa_filter)
        if shipments is None:
            return jsonify({"error": "Database is currently unavailable"}), 503
        return jsonify(shipments), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- EVENT ROUTES ---

@main_bp.route("/api/events", methods=["POST"])
@auth.require_auth
@auth.require_role('Admin', 'Driver', 'QA Inspector')
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
        shipment = database.get_shipment_simple(str(shipment_id))
        bol = shipment['bol_number'] if shipment else str(shipment_id)
        _notify(
            ['Admin', 'Client', 'Driver'], str(shipment_id),
            'status_changed',
            f"Shipment BOL#{bol} status updated to {new_status}"
        )
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
@auth.require_role('Admin', 'Driver', 'QA Inspector')
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


# --- PDF REPORT ROUTE ---

@main_bp.route('/api/shipments/<uuid:shipment_id>/report', methods=['GET'])
@auth.require_auth
def download_report(shipment_id):
    """Generates and returns a PDF chain-of-custody report for a shipment."""
    try:
        shipment_data = database.get_shipment_with_history(str(shipment_id))
        if not shipment_data:
            return jsonify({'error': 'Shipment not found'}), 404

        inspection_data = database.get_inspection_by_shipment(str(shipment_id))

        pdf_bytes = pdf_generator.generate_report(shipment_data, inspection_data)

        bol = shipment_data['shipment'].get('bol_number', str(shipment_id))
        filename = f"serverseal_{bol}_report.pdf".replace(' ', '_')

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- QR CODE ROUTE ---

@main_bp.route('/api/shipments/<uuid:shipment_id>/qr', methods=['GET'])
@auth.require_auth
def get_shipment_qr(shipment_id):
    """Returns a QR code PNG encoding the shipment's URL."""
    app_url = os.environ.get('APP_URL', 'http://localhost:5173')
    url = f"{app_url}/shipments/{shipment_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype='image/png',
        headers={'Cache-Control': 'public, max-age=3600'}
    )


# --- QA ROUTES ---

@main_bp.route('/api/users/qa', methods=['GET'])
@auth.require_auth
@auth.require_role('Admin')
def list_qa_users():
    """Returns all QA Inspector users for the assignment dropdown."""
    try:
        users = database.get_qa_users()
        return jsonify([{'user_id': str(u['user_id']), 'email': u['email']} for u in users]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection', methods=['POST'])
@auth.require_auth
@auth.require_role('Admin')
def assign_qa_inspector(shipment_id):
    """Admin assigns a QA Inspector to a shipment."""
    data = request.json or {}
    qa_user_id = data.get('qa_user_id')
    if not qa_user_id:
        return jsonify({'error': 'QA_USER_ID_REQUIRED'}), 400
    try:
        inspection_id = database.assign_qa_to_shipment(
            str(shipment_id), qa_user_id, g.current_user['user_id']
        )
        shipment = database.get_shipment_simple(str(shipment_id))
        bol = shipment['bol_number'] if shipment else str(shipment_id)
        # Notify the assigned QA Inspector directly
        _notify(
            [], str(shipment_id), 'qa_assigned',
            f"You have been assigned to inspect shipment BOL#{bol}",
            extra_user_ids=[qa_user_id]
        )
        # Notify all Admins
        _notify(
            ['Admin'], str(shipment_id), 'qa_assigned',
            f"Shipment BOL#{bol} has been assigned for QA inspection"
        )
        return jsonify({'inspection_id': inspection_id, 'status': 'success'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection', methods=['GET'])
@auth.require_auth
def get_inspection(shipment_id):
    """Returns the QA inspection record and checklist for a shipment."""
    try:
        inspection = database.get_inspection_by_shipment(str(shipment_id))
        if not inspection:
            return jsonify({'error': 'INSPECTION_NOT_FOUND'}), 404
        return jsonify(inspection), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection/start', methods=['PATCH'])
@auth.require_auth
@auth.require_role('QA Inspector')
def start_inspection(shipment_id):
    """QA Inspector starts the inspection."""
    try:
        inspection = database.get_inspection_by_shipment(str(shipment_id))
        if not inspection:
            return jsonify({'error': 'INSPECTION_NOT_FOUND'}), 404
        if inspection['assigned_qa_id'] != g.current_user['user_id']:
            return jsonify({'error': 'FORBIDDEN'}), 403
        database.start_inspection(inspection['inspection_id'], str(shipment_id))
        shipment = database.get_shipment_simple(str(shipment_id))
        bol = shipment['bol_number'] if shipment else str(shipment_id)
        _notify(
            ['Admin'], str(shipment_id), 'inspection_started',
            f"QA inspection started on shipment BOL#{bol}"
        )
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection/items', methods=['POST'])
@auth.require_auth
@auth.require_role('QA Inspector')
def add_inspection_item(shipment_id):
    """QA Inspector adds a hardware unit to the checklist."""
    data = request.json or {}
    try:
        inspection = database.get_inspection_by_shipment(str(shipment_id))
        if not inspection:
            return jsonify({'error': 'INSPECTION_NOT_FOUND'}), 404
        if inspection['assigned_qa_id'] != g.current_user['user_id']:
            return jsonify({'error': 'FORBIDDEN'}), 403
        item_id = database.add_checklist_item(
            inspection['inspection_id'],
            data.get('manufacturer'),
            data.get('model'),
            data.get('serial_number'),
            data.get('quantity', 1),
            data.get('visual_condition'),
            data.get('packaging_condition'),
            data.get('damage_notes'),
            data.get('disposition'),
        )
        return jsonify({'item_id': item_id, 'status': 'success'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection/items/<uuid:item_id>', methods=['DELETE'])
@auth.require_auth
@auth.require_role('QA Inspector')
def delete_inspection_item(shipment_id, item_id):
    """QA Inspector removes a checklist item."""
    try:
        deleted = database.delete_checklist_item(str(item_id))
        if not deleted:
            return jsonify({'error': 'ITEM_NOT_FOUND'}), 404
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection/submit', methods=['PATCH'])
@auth.require_auth
@auth.require_role('QA Inspector')
def submit_inspection(shipment_id):
    """QA Inspector submits the completed inspection."""
    data = request.json or {}
    overall_disposition = data.get('overall_disposition')
    if not overall_disposition:
        return jsonify({'error': 'OVERALL_DISPOSITION_REQUIRED'}), 400
    if overall_disposition not in ('Pass', 'Fail', 'QA Hold', 'Conditional'):
        return jsonify({'error': 'INVALID_DISPOSITION'}), 400
    try:
        inspection = database.get_inspection_by_shipment(str(shipment_id))
        if not inspection:
            return jsonify({'error': 'INSPECTION_NOT_FOUND'}), 404
        if inspection['assigned_qa_id'] != g.current_user['user_id']:
            return jsonify({'error': 'FORBIDDEN'}), 403
        new_status = database.submit_inspection(
            inspection['inspection_id'], str(shipment_id),
            overall_disposition, data.get('notes', '')
        )
        shipment = database.get_shipment_simple(str(shipment_id))
        bol = shipment['bol_number'] if shipment else str(shipment_id)
        _notify(
            ['Admin', 'Client', 'Driver'], str(shipment_id), 'qa_verdict',
            f"QA verdict for shipment BOL#{bol}: {overall_disposition} — status now {new_status}"
        )
        return jsonify({'status': 'success', 'shipment_status': new_status}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/shipments/<uuid:shipment_id>/inspection/resolve', methods=['PATCH'])
@auth.require_auth
@auth.require_role('Admin')
def resolve_qa_hold(shipment_id):
    """Admin resolves a QA Hold — approve override or send back to QA."""
    data = request.json or {}
    action = data.get('action')
    if action not in ('approve', 'reinspect'):
        return jsonify({'error': 'INVALID_ACTION'}), 400
    try:
        inspection = database.get_inspection_by_shipment(str(shipment_id))
        if not inspection:
            return jsonify({'error': 'INSPECTION_NOT_FOUND'}), 404
        new_status = database.resolve_qa_hold(
            inspection['inspection_id'], str(shipment_id), action
        )
        shipment = database.get_shipment_simple(str(shipment_id))
        bol = shipment['bol_number'] if shipment else str(shipment_id)
        action_label = 'approved (override)' if action == 'approve' else 'sent back to QA'
        # Notify the QA Inspector assigned to this shipment
        _notify(
            [], str(shipment_id), 'hold_resolved',
            f"Admin resolved QA Hold on shipment BOL#{bol} — {action_label}",
            extra_user_ids=[inspection['assigned_qa_id']]
        )
        # Notify Admin, Client, Driver
        _notify(
            ['Admin', 'Client', 'Driver'], str(shipment_id), 'hold_resolved',
            f"QA Hold on shipment BOL#{bol} resolved — {action_label} — status now {new_status}"
        )
        return jsonify({'status': 'success', 'shipment_status': new_status}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- NOTIFICATION ROUTES ---

@main_bp.route('/api/notifications', methods=['GET'])
@auth.require_auth
def list_notifications():
    """Returns all notifications for the authenticated user."""
    try:
        notifications = database.get_notifications(g.current_user['user_id'])
        return jsonify([{
            'notification_id': str(n['notification_id']),
            'shipment_id': str(n['shipment_id']) if n['shipment_id'] else None,
            'bol_number': n['bol_number'],
            'type': n['type'],
            'message': n['message'],
            'is_read': n['is_read'],
            'created_at': n['created_at'].isoformat() if n['created_at'] else None,
        } for n in notifications]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/notifications/<uuid:notification_id>/read', methods=['PATCH'])
@auth.require_auth
def mark_notification_read(notification_id):
    """Marks a single notification as read."""
    try:
        updated = database.mark_notification_read(str(notification_id), g.current_user['user_id'])
        if not updated:
            return jsonify({'error': 'NOTIFICATION_NOT_FOUND'}), 404
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/notifications/read-all', methods=['PATCH'])
@auth.require_auth
def mark_all_notifications_read():
    """Marks all notifications for the authenticated user as read."""
    try:
        database.mark_all_notifications_read(g.current_user['user_id'])
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
