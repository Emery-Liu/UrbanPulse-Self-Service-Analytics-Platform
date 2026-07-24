import sqlite3
print("DATABASE FILE LOADED")
def get_filename_by_id(file_id):
    print("DB:", file_id)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT filename FROM uploads
        WHERE id = ?
        """,
        (file_id,) #notice the comma in line 11
    ) #execute has two parameters seperated by ,
    row = cursor.fetchone()
    conn.close()
    return row

def insert_upload(filename):
    conn = sqlite3.connect("database.db")
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


def delete_uploads_older_than(days):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT filename FROM uploads
        WHERE upload_time <= datetime('now', ?)
        """,
        (f"-{days} days",)
    )
    rows = cursor.fetchall()

    cursor.execute(
        """
        DELETE FROM uploads
        WHERE upload_time <= datetime('now', ?)
        """,
        (f"-{days} days",)
    )
    conn.commit()
    conn.close()

    return [row[0] for row in rows]


def init_database():
    conn = sqlite3.connect("database.db")

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            upload_time TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()