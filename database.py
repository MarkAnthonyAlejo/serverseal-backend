import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Tell python to find and read the .env file
load_dotenv()


# Update: Changed dbname to serverseal_db to match your terminal success
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shipments (bol_number, origin, destination) VALUES (%s, %s, %s) RETURNING shipment_id;",
                (bol_number, origin, destination)
            )
            shipment_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO status_history (shipment_id, status) VALUES (%s, 'Pending');",
                (shipment_id,)
            )
            conn.commit()
            return shipment_id
    finally:
        conn.close()


def get_all_shipments(assigned_qa_id=None):
    """ Fetches all Shipments as a list of dictionaries. Filters by assigned_qa_id for QA Inspectors."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if assigned_qa_id:
                cur.execute(
                    "SELECT * FROM shipments WHERE assigned_qa_id = %s ORDER BY created_at DESC;",
                    (assigned_qa_id,)
                )
            else:
                cur.execute("SELECT * FROM shipments ORDER BY created_at DESC;")
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
            cur.execute(query, (shipment_id, event_type, location,
                        hardware_details, notes, handler_id))
            event_id = cur.fetchone()[0]
            conn.commit()
            return event_id
    finally:
        conn.close()


def update_shipment_status(shipment_id, new_status):
    valid_statuses = {
        'Pending', 'Pending Inspection', 'Under Inspection',
        'QA Hold', 'QA Approved', 'Sealed', 'In Transit', 'Delivered'
    }
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}")
    query = """
        UPDATE shipments
        SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE shipment_id = %s
        RETURNING shipment_id, status;
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (new_status, shipment_id))
            result = cur.fetchone()
            cur.execute(
                "INSERT INTO status_history (shipment_id, status) VALUES (%s, %s);",
                (shipment_id, new_status)
            )
            conn.commit()
            return result
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
        cur.execute(query, (event_id, media_type,
                    file_path, latitude, longitude))
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


def get_active_shipments():
    """Returns In Transit shipments with last event info bundled in."""
    query = """
        SELECT
            s.*,
            COUNT(e.event_id) AS event_count,
            MAX(e.created_at) AS last_event_at,
            (
                SELECT event_type FROM events
                WHERE shipment_id = s.shipment_id
                ORDER BY created_at DESC LIMIT 1
            ) AS last_event_type
        FROM shipments s
        LEFT JOIN events e ON s.shipment_id = e.shipment_id
        WHERE s.status = 'In Transit'
        GROUP BY s.shipment_id
        ORDER BY s.updated_at DESC;
    """
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()


def get_shipment_by_bol(bol_number):
    """Finds a shipment by its BOL number. Used by the cargo scanner."""
    query = "SELECT * FROM shipments WHERE bol_number = %s;"
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (bol_number,))
            return cur.fetchone()
    finally:
        conn.close()


# --- USER FUNCTIONS ---

def get_user_count():
    """Returns total number of users — used for bootstrap check."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            return cur.fetchone()[0]
    finally:
        conn.close()


def create_user(email, password_hash, role):
    """Inserts a new user and returns the UUID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) RETURNING user_id;",
                (email, password_hash, role)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            return user_id
    finally:
        conn.close()


def get_user_by_email(email):
    """Finds a user by email. Used for login."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            return cur.fetchone()
    finally:
        conn.close()


def get_all_users():
    """Returns all users (excluding password hashes) for the admin user list."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT user_id, email, role, created_at FROM users ORDER BY created_at ASC;"
            )
            return cur.fetchall()
    finally:
        conn.close()


def delete_user(user_id):
    """Deletes a user by ID. Returns True if deleted, False if not found."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE user_id = %s RETURNING user_id;", (user_id,))
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Fetches a user by ID, excluding the password hash."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT user_id, email, role, created_at FROM users WHERE user_id = %s;",
                (user_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()


# --- QA FUNCTIONS ---

def get_qa_users():
    """Returns all QA Inspector users for the assignment dropdown."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT user_id, email FROM users WHERE role = 'QA Inspector' ORDER BY email ASC;"
            )
            return cur.fetchall()
    finally:
        conn.close()


def assign_qa_to_shipment(shipment_id, qa_user_id, created_by):
    """Creates a QA inspection record and moves shipment to Pending Inspection."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO qa_inspections (shipment_id, assigned_qa_id, created_by)
                   VALUES (%s, %s, %s) RETURNING inspection_id;""",
                (shipment_id, qa_user_id, created_by)
            )
            inspection_id = cur.fetchone()['inspection_id']
            cur.execute(
                """UPDATE shipments SET assigned_qa_id = %s, status = 'Pending Inspection',
                   updated_at = CURRENT_TIMESTAMP WHERE shipment_id = %s;""",
                (qa_user_id, shipment_id)
            )
            cur.execute(
                "INSERT INTO status_history (shipment_id, status) VALUES (%s, 'Pending Inspection');",
                (shipment_id,)
            )
            conn.commit()
            return str(inspection_id)
    finally:
        conn.close()


def get_inspection_by_shipment(shipment_id):
    """Returns the QA inspection record with checklist items for a shipment."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT i.*, u.email AS assigned_qa_email
                   FROM qa_inspections i
                   JOIN users u ON i.assigned_qa_id = u.user_id
                   WHERE i.shipment_id = %s;""",
                (shipment_id,)
            )
            inspection = cur.fetchone()
            if not inspection:
                return None
            cur.execute(
                "SELECT * FROM qa_checklist_items WHERE inspection_id = %s ORDER BY created_at ASC;",
                (inspection['inspection_id'],)
            )
            items = cur.fetchall()
            result = dict(inspection)
            result['inspection_id'] = str(result['inspection_id'])
            result['shipment_id'] = str(result['shipment_id'])
            result['assigned_qa_id'] = str(result['assigned_qa_id'])
            result['created_by'] = str(result['created_by'])
            result['items'] = [
                {**dict(item), 'item_id': str(item['item_id']), 'inspection_id': str(item['inspection_id'])}
                for item in items
            ]
            return result
    finally:
        conn.close()


def start_inspection(inspection_id, shipment_id):
    """QA Inspector starts the inspection — moves to In Progress / Under Inspection."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE qa_inspections SET status = 'In Progress' WHERE inspection_id = %s;",
                (inspection_id,)
            )
            cur.execute(
                """UPDATE shipments SET status = 'Under Inspection', updated_at = CURRENT_TIMESTAMP
                   WHERE shipment_id = %s;""",
                (shipment_id,)
            )
            cur.execute(
                "INSERT INTO status_history (shipment_id, status) VALUES (%s, 'Under Inspection');",
                (shipment_id,)
            )
            conn.commit()
    finally:
        conn.close()


def add_checklist_item(inspection_id, manufacturer, model, serial_number, quantity,
                       visual_condition, packaging_condition, damage_notes, disposition):
    """Adds a hardware unit to the QA checklist."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO qa_checklist_items
                   (inspection_id, manufacturer, model, serial_number, quantity,
                    visual_condition, packaging_condition, damage_notes, disposition)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING item_id;""",
                (inspection_id, manufacturer, model, serial_number, quantity,
                 visual_condition or None, packaging_condition or None,
                 damage_notes or None, disposition or None)
            )
            item_id = cur.fetchone()['item_id']
            conn.commit()
            return str(item_id)
    finally:
        conn.close()


def delete_checklist_item(item_id):
    """Deletes a checklist item. Returns True if deleted."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM qa_checklist_items WHERE item_id = %s RETURNING item_id;",
                (item_id,)
            )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None
    finally:
        conn.close()


def submit_inspection(inspection_id, shipment_id, overall_disposition, notes):
    """QA submits the inspection. Pass/Conditional → QA Approved; Fail/QA Hold → QA Hold."""
    if overall_disposition in ('Pass', 'Conditional'):
        new_shipment_status = 'QA Approved'
        inspection_status = 'Passed'
    else:
        new_shipment_status = 'QA Hold'
        inspection_status = 'Failed' if overall_disposition == 'Fail' else 'On Hold'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE qa_inspections
                   SET status = %s, overall_disposition = %s, notes = %s,
                       completed_at = CURRENT_TIMESTAMP
                   WHERE inspection_id = %s;""",
                (inspection_status, overall_disposition, notes or None, inspection_id)
            )
            cur.execute(
                """UPDATE shipments SET status = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE shipment_id = %s;""",
                (new_shipment_status, shipment_id)
            )
            cur.execute(
                "INSERT INTO status_history (shipment_id, status) VALUES (%s, %s);",
                (shipment_id, new_shipment_status)
            )
            conn.commit()
            return new_shipment_status
    finally:
        conn.close()


def resolve_qa_hold(inspection_id, shipment_id, action):
    """Admin resolves a QA Hold. action: 'approve' or 'reinspect'."""
    if action == 'approve':
        new_shipment_status = 'QA Approved'
        new_inspection_status = 'Passed'
    else:
        new_shipment_status = 'Under Inspection'
        new_inspection_status = 'In Progress'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE qa_inspections SET status = %s, completed_at = NULL WHERE inspection_id = %s;",
                (new_inspection_status, inspection_id)
            )
            cur.execute(
                """UPDATE shipments SET status = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE shipment_id = %s;""",
                (new_shipment_status, shipment_id)
            )
            cur.execute(
                "INSERT INTO status_history (shipment_id, status) VALUES (%s, %s);",
                (shipment_id, new_shipment_status)
            )
            conn.commit()
            return new_shipment_status
    finally:
        conn.close()


def get_shipment_with_history(shipment_id):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Get the Master Shipment Data
            cur.execute(
                "SELECT * FROM shipments WHERE shipment_id = %s", (shipment_id,))
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
                ORDER BY e.created_at ASC;
            """
            cur.execute(query, (shipment_id,))
            events = cur.fetchall()

            cur.execute(
                "SELECT history_id, shipment_id, status, changed_at FROM status_history WHERE shipment_id = %s ORDER BY changed_at ASC;",
                (shipment_id,)
            )
            status_history = cur.fetchall()

            return {
                "shipment": shipment,
                "history": events,
                "status_history": status_history
            }
    finally:
        conn.close()
