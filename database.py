import sqlite3
import random

DATABASE_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Optional: Access columns by name
    return conn

def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            discord_id TEXT UNIQUE, -- Added UNIQUE constraint
            discord_tag TEXT,
            active_character_id INTEGER, -- New column
            FOREIGN KEY (active_character_id) REFERENCES characters(id) -- Optional: Foreign key
        )'''
    )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT,
            name TEXT,
            class TEXT,
            spellcaster BOOLEAN
            -- Consider adding UNIQUE constraint for (discord_id, name) if character names per user must be unique
            -- UNIQUE(discord_id, name) 
        )'''
    )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            building_type TEXT,
            resource_output TEXT,
            resource_type TEXT,
            resource_frequency TEXT
        )'''
    )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_rolls (
            building_type TEXT UNIQUE,
            channel_id INTEGER,
            last_roll_time INTEGER  -- Unix timestamp of the last roll/collection
        )
    ''')
    conn.commit()
    conn.close()

def calculate_roll_result(resource_output: str) -> int:
    try:
        num, die = map(int, resource_output.lower().split('d'))
        return sum(random.randint(1, die) for _ in range(num))
    except ValueError:
        print(f"Error: Invalid dice format '{resource_output}' in _calculate_roll_result")
        return 0

# Initialize the database when this module is imported
initialize_db()
