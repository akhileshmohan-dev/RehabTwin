import sqlite3
from pathlib import Path
import os
import sys

# Default Database Path from digital_thread.config
db_path_str = os.getenv("REHABTWIN_DB_PATH", "data/rehabtwin_thread.db")
db_path = Path(db_path_str).resolve()

def upgrade_database(db_file: Path):
    if not db_file.exists():
        print(f"Database file does not exist: {db_file}")
        return False

    print(f"Upgrading database: {db_file}")
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check if uniqueness constraint already exists by looking at indexes
    cursor.execute("PRAGMA index_list('results')")
    indexes = cursor.fetchall()
    
    has_unique = False
    for idx in indexes:
        # index format: (seq, name, unique, origin, partial)
        if idx[2] == 1: # if unique
            cursor.execute(f"PRAGMA index_info('{idx[1]}')")
            cols = cursor.fetchall()
            if any(col[2] == 'session_id' for col in cols):
                has_unique = True
                break
                
    if has_unique:
        print("UNIQUE constraint on results.session_id already exists. Skipping migration.")
        conn.close()
        return True
        
    print("Applying UNIQUE constraint to results.session_id...")
    
    try:
        # 1. Turn off foreign keys temporarily for table swap
        cursor.execute("PRAGMA foreign_keys=OFF;")
        
        # 2. Create the new table mirroring models.py exactly
        create_table_sql = """
        CREATE TABLE results_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(64) NOT NULL UNIQUE,
            exercise VARCHAR(128) NOT NULL,
            repetitions INTEGER NOT NULL,
            rom_min FLOAT,
            rom_max FLOAT,
            rom_average FLOAT,
            performance_score FLOAT,
            feedback TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );
        """
        cursor.execute(create_table_sql)
        
        # 3. Insert deduplicated data (keep max id per session)
        insert_sql = """
        INSERT INTO results_new (id, session_id, exercise, repetitions, rom_min, rom_max, rom_average, performance_score, feedback)
        SELECT id, session_id, exercise, repetitions, rom_min, rom_max, rom_average, performance_score, feedback
        FROM results
        WHERE id IN (
            SELECT MAX(id)
            FROM results
            GROUP BY session_id
        );
        """
        cursor.execute(insert_sql)
        
        # 4. Swap tables
        cursor.execute("DROP TABLE results;")
        cursor.execute("ALTER TABLE results_new RENAME TO results;")
        
        # 5. Recreate the index from models.py
        cursor.execute("CREATE UNIQUE INDEX ix_results_session_id ON results (session_id);")
        
        conn.commit()
        
        # Turn foreign keys back on
        cursor.execute("PRAGMA foreign_keys=ON;")
        print("Database upgraded successfully.")
        return True
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else db_path
    success = upgrade_database(target)
    sys.exit(0 if success else 1)
