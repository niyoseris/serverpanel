from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Check if column exists
    with db.engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(project)"))
            columns = [row[1] for row in result]
            if 'project_type' not in columns:
                print("Adding project_type column...")
                conn.execute(text("ALTER TABLE project ADD COLUMN project_type VARCHAR(20) DEFAULT 'flask'"))
                conn.commit()
                print("Column added.")
            else:
                print("Column already exists.")
        except Exception as e:
            print(f"Error: {e}")
