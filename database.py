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
            discord_id TEXT UNIQUE, 
            discord_tag TEXT,
            active_character_id INTEGER, 
            FOREIGN KEY (active_character_id) REFERENCES characters(id) 
        )'''
    )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT,
            name TEXT,
            class TEXT,
            spellcaster BOOLEAN,
            cp INTEGER DEFAULT 0, 
            sp INTEGER DEFAULT 0, 
            ep INTEGER DEFAULT 0, 
            gp INTEGER DEFAULT 0, 
            pp INTEGER DEFAULT 0  
        )'''
    )
    # Renamed from 'buildings' to 'building_types'
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS building_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, -- e.g., "Small Mine", "Herbalist Hut"
            resource_output TEXT, -- e.g., "1d6"
            resource_type TEXT, -- e.g., "gp", "herbs" (for now, assume currency from economy cog)
            resource_frequency TEXT -- e.g., "daily", "hourly"
        )'''
    )
    # New table to store instances of buildings owned by characters
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS character_buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            building_type_id INTEGER,
            custom_name TEXT, -- Optional: "Bob's Lucky Mine"
            channel_id INTEGER, -- Channel for notifications for this specific building
            last_collection_time INTEGER, -- Unix timestamp
            FOREIGN KEY (character_id) REFERENCES characters(id),
            FOREIGN KEY (building_type_id) REFERENCES building_types(id)
        )'''
    )
    # The old 'active_rolls' table is no longer needed with this structure.
    # cursor.execute('DROP TABLE IF EXISTS active_rolls') # Optional: explicitly drop if it exists

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
