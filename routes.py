from flask import Blueprint, jsonify, request
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