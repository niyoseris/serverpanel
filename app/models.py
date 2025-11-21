from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        # In a real app, use werkzeug.security.generate_password_hash
        # For simplicity in this prototype, we might store plain or simple hash, 
        # but let's do it right if we can, or just placeholder for now.
        # We'll use werkzeug if available, else simple.
        try:
            from werkzeug.security import generate_password_hash
            self.password_hash = generate_password_hash(password)
        except ImportError:
            self.password_hash = password

    def check_password(self, password):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(self.password_hash, password)
        except ImportError:
            return self.password_hash == password

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    port = db.Column(db.Integer, unique=True)
    domain = db.Column(db.String(128))
    path = db.Column(db.String(256))
    project_type = db.Column(db.String(20), default='flask') # flask, django, other
    entry_point = db.Column(db.String(64), default='app:app') # e.g. app:app, run:app, config.wsgi:application
    pid = db.Column(db.Integer) # Process ID for local management
    env_vars = db.Column(db.Text, default='{}') # JSON string for environment variables
    ssl_enabled = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='stopped') # stopped, running, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    versions = db.relationship('ProjectVersion', backref='project', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Project {self.name}>'

class ProjectVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    backup_path = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, default='Auto-backup before update')
    
    def __repr__(self):
        return f'<ProjectVersion {self.project_id} v{self.version_number}>'
