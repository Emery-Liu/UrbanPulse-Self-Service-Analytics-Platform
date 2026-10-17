import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database.db"


def get_connection():
    return sqlite3.connect(str(DATABASE_PATH))


def get_filename_by_id(file_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT filename FROM uploads
            WHERE id = ?
            """,
            (file_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def insert_upload(filename):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO uploads
            (filename, upload_time)
            VALUES (?, datetime('now'))
            """,
            (filename,),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_uploads_older_than(days):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, filename FROM uploads
            WHERE upload_time <= datetime('now', ?)
            """,
            (f"-{days} days",),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def delete_upload(upload_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM uploads WHERE id = ?",
            (upload_id,),
        )
        conn.commit()
    finally:
        conn.close()


def init_database():
    conn = get_connection()
    try:
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
    finally:
        conn.close()
