import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database.db"


def get_connection():
    return sqlite3.connect(str(DATABASE_PATH))


def get_filename_by_id(file_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT filename FROM uploads
        WHERE id = ?
        """,
        (file_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def insert_upload(filename):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO uploads
        (filename, upload_time)
        VALUES (?, datetime('now'))
        """,
        (filename,)
    )
    conn.commit()
    file_id = cursor.lastrowid
    conn.close()
    return file_id


def get_uploads_older_than(days):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, filename FROM uploads
        WHERE upload_time <= datetime('now', ?)
        """,
        (f"-{days} days",)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_upload(upload_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM uploads WHERE id = ?",
        (upload_id,)
    )
    conn.commit()
    conn.close()


def delete_uploads_older_than(days):
    """Delete upload metadata only; file deletion is handled by app.py."""
    rows = get_uploads_older_than(days)
    if not rows:
        return []

    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "DELETE FROM uploads WHERE id = ?",
        [(row[0],) for row in rows]
    )
    conn.commit()
    conn.close()

    return [row[1] for row in rows]


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            upload_time TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()
