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

class SubRoute(db.Model):
    """
    Sub-route mounting: allows mounting another project on a specific path of a host project.
    Example: Host project has domain example.com, mounted project runs on /api path
    -> example.com/api/* proxies to mounted project's port
    """
    id = db.Column(db.Integer, primary_key=True)
    host_project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    mounted_project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    route_path = db.Column(db.String(256), nullable=False)  # e.g., /api, /admin, /blog
    strip_prefix = db.Column(db.Boolean, default=True)  # Strip the prefix before forwarding
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    host_project = db.relationship('Project', foreign_keys=[host_project_id], backref='sub_routes')
    mounted_project = db.relationship('Project', foreign_keys=[mounted_project_id], backref='mounted_on')
    
    def __repr__(self):
        return f'<SubRoute {self.route_path} -> Project#{self.mounted_project_id}>'


class FileManifest(db.Model):
    """
    Dosya manifest kaydı - her dosyanın hash'ini tutar (git benzeri)
    Deployment sırasında sadece değişen dosyaları göndermek için kullanılır
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)  # Relative path from project root
    file_hash = db.Column(db.String(64), nullable=False)  # SHA256 hash
    file_size = db.Column(db.Integer, default=0)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: one entry per file per project
    __table_args__ = (db.UniqueConstraint('project_id', 'file_path', name='uix_project_file'),)
    
    project = db.relationship('Project', backref=db.backref('file_manifests', lazy='dynamic', cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<FileManifest {self.file_path}>'


class AppState(db.Model):
    """
    Uygulama durumu - server restart sonrası hangi uygulamaların çalışması gerektiğini tutar
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, unique=True)
    should_run = db.Column(db.Boolean, default=False)  # Restart sonrası çalışmalı mı?
    last_started_at = db.Column(db.DateTime)
    last_stopped_at = db.Column(db.DateTime)
    auto_restart = db.Column(db.Boolean, default=True)  # Crash durumunda otomatik yeniden başlat
    
    project = db.relationship('Project', backref=db.backref('app_state', uselist=False, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<AppState {self.project_id} should_run={self.should_run}>'


class DeploymentLog(db.Model):
    """
    Deployment geçmişi - kim, ne zaman, hangi dosyaları deploy etti
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    deployed_at = db.Column(db.DateTime, default=datetime.utcnow)
    files_changed = db.Column(db.Integer, default=0)
    files_added = db.Column(db.Integer, default=0)
    files_deleted = db.Column(db.Integer, default=0)
    total_size = db.Column(db.Integer, default=0)  # bytes
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='success')  # success, failed, partial
    
    project = db.relationship('Project', backref=db.backref('deployment_logs', lazy='dynamic', cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<DeploymentLog {self.project_id} @ {self.deployed_at}>'
