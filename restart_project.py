from app import create_app, db
from app.models import Project
from app.utils.system import generate_supervisor_config
import json

app = create_app()

with app.app_context():
    project = Project.query.filter_by(port=5002).first()
    if project:
        print(f"Restarting project: {project.name}")
        
        env_vars = {}
        if project.env_vars:
            try:
                env_vars = json.loads(project.env_vars)
            except:
                pass
        
        # Start it
        pid = generate_supervisor_config(
            project.name, 
            project.project_type, 
            project.path, 
            project.port, 
            env_vars, 
            project.entry_point
        )
        
        if pid:
            print(f"Project started with PID: {pid}")
            project.pid = pid
            project.status = 'running'
            db.session.commit()
        else:
            print("Failed to start project.")
    else:
        print("Project not found.")
