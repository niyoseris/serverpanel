from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(project)"))
            columns = [row[1] for row in result]
            if 'entry_point' not in columns:
                print("Adding entry_point column...")
                conn.execute(text("ALTER TABLE project ADD COLUMN entry_point VARCHAR(64) DEFAULT 'app:app'"))
                conn.commit()
                print("Column added.")
        except Exception as e:
            print(f"Error: {e}")
