from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        try:
            # Check columns
            result = conn.execute(text("PRAGMA table_info(project)"))
            columns = [row[1] for row in result]
            
            if 'env_vars' not in columns:
                print("Adding env_vars column...")
                conn.execute(text("ALTER TABLE project ADD COLUMN env_vars TEXT DEFAULT '{}'"))
            
            if 'ssl_enabled' not in columns:
                print("Adding ssl_enabled column...")
                conn.execute(text("ALTER TABLE project ADD COLUMN ssl_enabled BOOLEAN DEFAULT 0"))
                
            conn.commit()
            print("Schema updated.")
        except Exception as e:
            print(f"Error: {e}")
