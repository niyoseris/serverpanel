from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(project)"))
            columns = [row[1] for row in result]
            if 'pid' not in columns:
                print("Adding pid column...")
                conn.execute(text("ALTER TABLE project ADD COLUMN pid INTEGER"))
                conn.commit()
                print("Column added.")
            else:
                print("Column already exists.")
        except Exception as e:
            print(f"Error: {e}")
