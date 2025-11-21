from app import create_app, db
from app.models import Project

app = create_app()

with app.app_context():
    projects = Project.query.all()
    for p in projects:
        if p.status == 'running' and p.pid is None:
            print(f"Resetting status for {p.name} (ID: {p.id}) to stopped.")
            p.status = 'stopped'
    db.session.commit()
