import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Tell python to find and read the .env file 
load_dotenv()

# --- ADD THIS LINE FOR TESTING ---
print(f"DEBUG CHECK: The DB_NAME from .env is: '{os.getenv('DB_NAME')}'")
# ---------------------------------

# Update: Changed dbname to serverseal_db to match your terminal success
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password" : os.getenv("DB_PASSWORD"), 
    "host" : os.getenv("DB_HOST"), 
    "port" : os.getenv("DB_PORT")
}

def get_connection(): 
    try: 
        # Now it uses the .env values automatically 
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e: 
        print(f"Database connection failed: {e}")
        return None

def create_shipment(bol_number, origin, destination): 
    """Inserts a shipment into Postgres and returns the UUID"""
    query = """
        INSERT INTO shipments (bol_number, origin, destination)
        VALUES (%s, %s, %s)
        RETURNING shipment_id;        
    """
    conn = get_connection()
    try: 
        with conn.cursor() as cur: 
            cur.execute(query, (bol_number, origin, destination))
            shipment_id = cur.fetchone()[0]
            conn.commit()
            return shipment_id
    finally:
        conn.close()

def get_all_shipments(): 
    """ Fetches all Shipments as a list of dictionaries"""
    query = "SELECT * FROM shipments ORDER BY created_at DESC;"
    conn = get_connection()
    try: 
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
    finally: 
        conn.close()

# Creating Event 
def create_event(shipment_id, event_type, location, hardware_details, notes, handler_id): 
    query = """
        INSERT INTO events (shipment_id, event_type, location, hardware_details, notes, handler_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING event_id;
    """
    conn = get_connection()
    try: 
        with conn.cursor() as cur: 
            cur.execute(query, (shipment_id, event_type, location, hardware_details, notes, handler_id))
            event_id = cur.fetchone()[0]
            conn.commit()
            return event_id
    finally: 
        conn.close()

# Gets Specific shipment for all created events
def get_shipment_with_events(shipment_id):
    conn = get_connection()
    try: 
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Fetch the master shipment record
            cur.execute("SELECT * FROM shipments WHERE shipment_id = %s", (shipment_id,))
            shipment = cur.fetchone()

            # 2. Fetch all events that "point" to this shipment
            cur.execute("SELECT * FROM events WHERE shipment_id = %s ORDER BY created_at ASC", (shipment_id,))
            events = cur.fetchall()

            return {
                "shipment": shipment, 
                "history": events
            }
    finally: 
        conn.close()

# Updated: Uses file_path to match new schema
def create_media(event_id, media_type, file_path, latitude=None, longitude=None):
    conn = get_connection()
    cur = conn.cursor()
    try: 
        query = """
                INSERT INTO media (event_id, media_type, file_path, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING media_id;
        """
        cur.execute(query, (event_id, media_type, file_path, latitude, longitude))
        media_id = cur.fetchone()[0]
        conn.commit()
        return media_id
    except Exception as e: 
        conn.rollback()
        print(f"Database error: {e}")
        raise e 
    finally: 
        cur.close()
        conn.close()

# Updated: Correctly bundles 'file_path' into JSON response
def get_shipment_with_history(shipment_id):
    conn = get_connection()
    try: 
        with conn.cursor(cursor_factory=RealDictCursor) as cur: 
            # 1. Get the Master Shipment Data
            cur.execute("SELECT * FROM shipments WHERE shipment_id = %s", (shipment_id,))
            shipment = cur.fetchone()

            if not shipment: 
                return None
            
            # 2. Get all Events and their associated Media 
            query = """
                SELECT
                    e.*, 
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'media_id', m.media_id, 
                                'type', m.media_type, 
                                'path', m.file_path,   -- Corrected to file_path
                                'lat', m.latitude, 
                                'lon', m.longitude
                            )
                        ) FILTER (WHERE m.media_id IS NOT NULL), '[]'
                    ) as evidence_photos
                FROM events e
                LEFT JOIN media m ON e.event_id = m.event_id
                WHERE e.shipment_id = %s 
                GROUP BY e.event_id
                ORDER BY e.created_at DESC;
            """
            cur.execute(query, (shipment_id,))
            events = cur.fetchall()

            return {
                "shipment": shipment, 
                "history": events
            }
    finally: 
        conn.close()