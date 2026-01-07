import psycopg2
from psycopg2.extras import RealDictCursor

# Update these credentials with your local Postgres info
DB_CONFIG = {
    "dbname": "server_seal",
    "user": "markalejo",
    "password" : "", 
    "host" : "localhost", 
    "port" : "5432"
}

def get_connection(): 
    return psycopg2.connect(**DB_CONFIG)

def create_shipment(bol_number, origin, destination): 
    """Insterts a shipment into Postgres and returns the UUID"""
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
def create_event(shiptment_id, event_type, location, hardware_details, notes, handler_id): 
    query = """
        INSERT INTO events (shipment_id, event_type, location, hardware_details, notes, handler_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING event_id;
    """
    conn = get_connection()
    try: 
        with conn.cursor() as cur: 
            cur.execute(query, (shiptment_id, event_type, location, hardware_details, notes, handler_id))
            event_id = cur.fetchone()[0]
            conn.commit()
            return event_id
    finally: 
        conn.close()
        
# Gets Specific shipment for that event 
def get_shipment_with_events(shipment_id):
    conn = get_connection()
    try: 
        with conn.cursor() as cur:
            # 1. Fetch the master shipment record
            cur.execute("SELECT * FROM shipments WHERE shipment_id = %s", (shipment_id,))
            shipment = cur.fetchone()

            #2. Fetch all events that "point" to this shipment
            cur.execute("SELECT * FROM events WHERE shipment_id = %s ORDER BY created_at ASC", (shipment_id,))
            events = cur.fetchall()

            return {
                "shipment": shipment, 
                "history": events
            }
    finally: 
        conn.close()