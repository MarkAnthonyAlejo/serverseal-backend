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
          return jsonify({"error" : str(e)}), 500

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
          return jsonify({"event_id": str(new_event_id), "status" : "success"}), 201 
     except Exception as e: 
        return jsonify({"error": str(e)}), 500

# -- "Full Story"(History of events) of specific shipment
@main_bp.route("/api/shipments/<uuid:shipment_id>", methods=["GET"])
def get_full_shipment(shipment_id):
     try: 
          data = database.get_shipment_with_history(str(shipment_id))

          if not data: 
               return jsonify({"error": "Shipment not found"}), 404
          
          return jsonify(data), 200
     except Exception as e: 
          return jsonify({"error": str(e)}), 500
     
@main_bp.route("/api/media", methods=["POST"])
def add_media():
     
     # Check if the 'file' key exists in the request 
     if 'file' not in request.files:
          return jsonify({"error": "No file part in the request"}), 400 
     
     file = request.files['file']

     # If the user submits without selecting a file 
     if file.filename == '': 
          return jsonify({"error": "No file selected"}), 400
     
     try:
          # Secure the filename and build the path 
          # This saves it as 'uploads/your_image.jpg'
          filename = secure_filename(file.filename)
          file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

          # Physically save the file to your MacBook's disk
          file.save(file_path)

          # Extract other data from 'request.form' (since we aren't using JSON anymore)
          event_id = request.form.get('event_id')
          media_type = request.form.get('media_type','image') # Defaults to image
          lat = request.form.get('latitude')
          lon = request.form.get('longitude')

          # Store the FILE PATH in the database, not the raw image
          new_media_id = database.create_media(
               event_id,
               media_type, 
               file_path, 
               lat, 
               lon
          )

          return jsonify({
               "media_id": str(new_media_id), 
               "status": "success",
               "saved_to": file_path
               }), 201
     
     except Exception as e: 
          return jsonify({"error": str(e)}), 500