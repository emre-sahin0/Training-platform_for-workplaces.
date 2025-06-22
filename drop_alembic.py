import sqlite3
import os

def force_delete_alembic_table():
    db_file = os.path.join('instance', 'isg.db')
    
    # Check if the database file exists in the instance folder
    if not os.path.exists(db_file):
        print(f"Error: Database file '{db_file}' not found.")
        print(f"Please ensure you are running this script from the project root directory and the database exists.")
        return

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Check if table exists before trying to drop it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cursor.fetchone():
            print(f"'alembic_version' table found in '{db_file}'. Dropping it...")
            cursor.execute("DROP TABLE alembic_version")
            print("'alembic_version' table dropped successfully.")
        else:
            print(f"'alembic_version' table not found in '{db_file}'. No action needed.")

        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    force_delete_alembic_table() 