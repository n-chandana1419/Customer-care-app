"""
database.py
-----------
Handles all SQLite database operations for CustomerCareHub.
Creates the database file and tables automatically on first run.
"""

import sqlite3
import os
from datetime import datetime

# ---------------------------------------------------------
# Path to the database file (inside the data/ folder)
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "customer_care.db")


def get_connection():
    """
    Create and return a new SQLite connection.
    Enables foreign key support (needed for users <-> complaints relation).
    """
    # Make sure the data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Create tables if they do not exist.
    Called once when the app starts.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # --------------------- USERS TABLE ---------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            phone         TEXT    NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)

    # ------------------ COMPLAINTS TABLE -------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id     TEXT    NOT NULL UNIQUE,
            user_id          INTEGER NOT NULL,
            category         TEXT    NOT NULL,
            subject          TEXT    NOT NULL,
            description      TEXT    NOT NULL,
            priority         TEXT    NOT NULL,
            status           TEXT    NOT NULL DEFAULT 'Submitted',
            support_response TEXT,
            created_at       TEXT    NOT NULL,
            updated_at       TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# USER OPERATIONS
# ---------------------------------------------------------
def create_user(full_name, email, phone, password_hash):
    """
    Insert a new user into the users table.
    Returns (True, user_id) on success or (False, error_message) on failure.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO users (full_name, email, phone, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (full_name, email.lower(), phone, password_hash, created_at))

        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return True, user_id
    except sqlite3.IntegrityError:
        # This happens when email already exists (UNIQUE constraint)
        return False, "An account with this email already exists."
    except sqlite3.Error as e:
        return False, f"Database error: {e}"


def get_user_by_email(email):
    """
    Return a single user row (as dict) matching the email, or None.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    """
    Return a user row (as dict) by ID, or None.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------
# COMPLAINT OPERATIONS
# ---------------------------------------------------------
def generate_complaint_id():
    """
    Generate a unique complaint ID like CCH-20250115-0001.
    Uses current date + count of complaints created today + 1.
    """
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"CCH-{today}-"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM complaints WHERE complaint_id LIKE ?",
        (prefix + "%",)
    )
    count = cursor.fetchone()[0]
    conn.close()

    return f"{prefix}{count + 1:04d}"


def create_complaint(user_id, category, subject, description, priority):
    """
    Insert a new complaint.
    Returns (True, complaint_id) on success or (False, error_message).
    """
    try:
        complaint_id = generate_complaint_id()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO complaints
                (complaint_id, user_id, category, subject, description,
                 priority, status, support_response, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Submitted', NULL, ?, ?)
        """, (complaint_id, user_id, category, subject, description,
              priority, now, now))

        conn.commit()
        conn.close()
        return True, complaint_id
    except sqlite3.Error as e:
        return False, f"Could not save complaint: {e}"


def get_complaints_by_user(user_id):
    """
    Return ALL complaints belonging to a specific user.
    Ordered by newest first.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM complaints
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_complaint_by_complaint_id(complaint_id, user_id):
    """
    Fetch one complaint by its complaint_id, but ONLY if it belongs to user_id.
    This prevents one customer from viewing another customer's complaint.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM complaints
        WHERE complaint_id = ? AND user_id = ?
    """, (complaint_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_complaint_stats(user_id):
    """
    Return counts for dashboard metrics:
    { total, submitted, in_progress, resolved, rejected }
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE user_id = ?", (user_id,))
    total = cursor.fetchone()[0]

    stats = {"total": total, "Submitted": 0, "In Progress": 0,
             "Resolved": 0, "Rejected": 0}

    cursor.execute("""
        SELECT status, COUNT(*) FROM complaints
        WHERE user_id = ? GROUP BY status
    """, (user_id,))
    for status, count in cursor.fetchall():
        if status in stats:
            stats[status] = count

    conn.close()
    return stats