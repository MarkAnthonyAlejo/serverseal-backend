import psycopg2
from psycopg2.extras import RealDictCursor

# Update these credentials with your local Postgres info
DB_CONFIG = {
    "dbname": "server_seal",
    "user": "postgres",
    "password" : "your_password", 
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
