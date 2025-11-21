from app import create_app, db
from app.models import Project

app = create_app()

with app.app_context():
    projects = Project.query.all()
    for p in projects:
        print(f"ID: {p.id} | Name: {p.name} | Type: {p.project_type} | Port: {p.port} | PID: {p.pid} | Status: {p.status} | Path: {p.path}")
