import sqlite3

conn = sqlite3.connect("escrow.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS escrows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    token FLOAT DEFAULT 0,
    fulfillment TEXT NOT NULL,
    condition TEXT NOT NULL,
    offer_sequence INTEGER NOT NULL,
    tx_hash TEXT NOT NULL,
    questioner_address TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    questioner_address TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    answer TEXT NOT NULL,
    responder_address TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id)
)
""")

conn.commit()
conn.close()
