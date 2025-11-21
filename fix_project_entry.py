from app import create_app, db
from app.models import Project

app = create_app()

with app.app_context():
    # Find the project
    # We'll look for the one on port 5002 or by name if we knew it for sure (likely 'drawly' based on logs)
    project = Project.query.filter_by(port=5002).first()
    
    if project:
        print(f"Found project: {project.name}")
        print(f"Current entry point: {project.entry_point}")
        print(f"Current path: {project.path}")
        
        # Update entry point
        project.entry_point = 'run:app'
        db.session.commit()
        
        print(f"Updated entry point to: {project.entry_point}")
    else:
        print("Project on port 5002 not found.")
