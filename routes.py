import os
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
import database

# This Blueprint will hold every route in our app
main_bp = Blueprint('main_bp', __name__)

# --- SHIPMENT ROUTES ---


@main_bp.route("/api/shipments", methods=["POST"])
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
def list_shipments():
    try:
        shipments = database.get_all_shipments()
        return jsonify(shipments), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- EVENT ROUTES (Condition Reporting) ---


@main_bp.route("/api/events", methods=["POST"])
def add_events():
    data = request.json
    try:
        new_event_id = database.create_event(
            data['shipment_id'],
            data['event_type'],
            data.get('location'),
            data.get('hardware_details'),
            data.get('notes'),
            data.get('handler_id')
        )
        return jsonify({"event_id": str(new_event_id), "status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -- "Full Story" (History of events) of specific shipment


@main_bp.route("/api/shipments/<uuid:shipment_id>", methods=["GET"])
def get_full_shipment(shipment_id):
    try:
        data = database.get_shipment_with_history(str(shipment_id))
        if not data:
            return jsonify({"error": "Shipment not found"}), 404
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Security Check of file upload


def allowed_file(filename):
    # This looks for a '.' and checks if the text after it is in your ALLOWED_EXTENSIONS
    allowed = current_app.config.get(
        'ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in allowed

# --- MEDIA UPLOAD ROUTE ---


@main_bp.route('/api/media/upload', methods=['POST'])
def add_media():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file and not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Please uplaod png, jpg, jpeg, or gif."}), 400

    event_id = request.form.get('event_id')
    media_type = request.form.get('media_type', 'image')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and event_id:
        filename = secure_filename(file.filename)
        # Using current_app.config to find the 'uploads' folder dynamically
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        file.save(file_path)

        try:
            # Fixed: Changed 'db' to 'database' to match your import
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
