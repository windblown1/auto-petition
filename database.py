import sqlite3

DATABASE = "petitions.db"

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS petitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                thread_link TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                vote INTEGER DEFAULT 0
            )
        """) # "vote" can be either 0 = "pending", 1 = "voted on" or 2 = "held back"

def add_petition(type):
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.execute("""
            INSERT INTO petitions (type, thread_link)
            VALUES (?, ?)
        """, (type, None))
        return cur.lastrowid
    
def get_petition(petition_id):
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.execute("""
            SELECT * FROM petitions
            WHERE id = ?
        """, (petition_id,)) # Needs to be a tuple, don't ask me why
        data = cur.fetchone()
        return data

def update_thread_link(petition_id, thread_link):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE petitions
            SET thread_link = ?
            WHERE id = ?
        """, (thread_link, petition_id))

def hold_back(petition_id):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE petitions
            SET vote = 2
            WHERE id = ?
        """, (petition_id,))
        return True
    
def revive(petition_id):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE petitions
            SET vote = 0
            WHERE id = ?
        """, (petition_id,))
        return True

def add_to_voted(petition_id):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE petitions
            SET vote = 1
            WHERE id = ?
        """, (petition_id,))

def get_pending_petitions():
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.execute("""
            SELECT * FROM petitions
            WHERE vote = 0
            ORDER BY created_at ASC
        """)
        return cur.fetchall()

def get_held_back_petitions():
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.execute("""
            SELECT * FROM petitions
            WHERE vote = 2
            ORDER BY created_at ASC
        """)
        return cur.fetchall()
