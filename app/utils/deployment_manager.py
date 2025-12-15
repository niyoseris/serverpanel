"""
Deployment Manager - SSH gerektirmeyen, HTTP tabanlı deployment sistemi
Git benzeri dosya değişiklik takibi ile sadece değişen dosyaları deploy eder
"""

import os
import hashlib
import json
import base64
from datetime import datetime
from app import db
from app.models import Project, FileManifest, AppState, DeploymentLog


# Yoksayılacak dosya/dizin kalıpları
IGNORE_PATTERNS = {
    '__pycache__', '.git', '.svn', '.hg',
    'venv', '.venv', 'env', '.env',
    'node_modules', '.idea', '.vscode',
    '*.pyc', '*.pyo', '*.pyd',
    '*.so', '*.dll', '*.dylib',
    '*.log', '*.tmp', '*.temp',
    '.DS_Store', 'Thumbs.db',
    '*.sqlite', '*.db',
    '.coverage', 'htmlcov',
    'dist', 'build', '*.egg-info'
}


def should_ignore(path, name):
    """Dosya/dizinin yoksayılıp yoksayılmayacağını kontrol et"""
    # Exact matches
    if name in IGNORE_PATTERNS:
        return True
    
    # Pattern matches
    for pattern in IGNORE_PATTERNS:
        if pattern.startswith('*') and name.endswith(pattern[1:]):
            return True
    
    return False


def calculate_file_hash(file_path):
    """Dosyanın SHA256 hash'ini hesapla"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return None


def scan_project_files(project_path):
    """
    Proje dizinindeki tüm dosyaları tarar ve hash'lerini hesaplar
    
    Returns:
        dict: {relative_path: {'hash': str, 'size': int, 'mtime': float}}
    """
    files = {}
    
    if not os.path.exists(project_path):
        return files
    
    for root, dirs, filenames in os.walk(project_path):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if not should_ignore(root, d)]
        
        for filename in filenames:
            if should_ignore(root, filename):
                continue
            
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, project_path)
            
            try:
                stat = os.stat(full_path)
                file_hash = calculate_file_hash(full_path)
                
                if file_hash:
                    files[relative_path] = {
                        'hash': file_hash,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    }
            except (OSError, IOError):
                continue
    
    return files


def get_project_manifest(project_id):
    """
    Veritabanından projenin mevcut manifest'ini getir
    
    Returns:
        dict: {relative_path: hash}
    """
    manifests = FileManifest.query.filter_by(project_id=project_id).all()
    return {m.file_path: m.file_hash for m in manifests}


def update_project_manifest(project_id, files_dict):
    """
    Projenin manifest'ini güncelle
    
    Args:
        project_id: Proje ID'si
        files_dict: {relative_path: {'hash': str, 'size': int}}
    """
    # Mevcut manifest kayıtlarını sil
    FileManifest.query.filter_by(project_id=project_id).delete()
    
    # Yeni kayıtları ekle
    for file_path, info in files_dict.items():
        manifest = FileManifest(
            project_id=project_id,
            file_path=file_path,
            file_hash=info['hash'],
            file_size=info.get('size', 0),
            last_modified=datetime.utcnow()
        )
        db.session.add(manifest)
    
    db.session.commit()


def compare_manifests(local_files, remote_manifest):
    """
    Yerel dosyaları uzak manifest ile karşılaştır
    
    Args:
        local_files: Yerel dosya dict'i {path: {'hash': str, 'size': int}}
        remote_manifest: Uzak manifest dict'i {path: hash}
    
    Returns:
        dict: {
            'added': [paths],      # Yeni eklenen dosyalar
            'modified': [paths],   # Değişen dosyalar
            'deleted': [paths],    # Silinen dosyalar
            'unchanged': [paths]   # Değişmeyen dosyalar
        }
    """
    result = {
        'added': [],
        'modified': [],
        'deleted': [],
        'unchanged': []
    }
    
    local_paths = set(local_files.keys())
    remote_paths = set(remote_manifest.keys())
    
    # Yeni eklenen dosyalar
    result['added'] = list(local_paths - remote_paths)
    
    # Silinen dosyalar
    result['deleted'] = list(remote_paths - local_paths)
    
    # Ortak dosyaları karşılaştır
    common_paths = local_paths & remote_paths
    for path in common_paths:
        if local_files[path]['hash'] != remote_manifest[path]:
            result['modified'].append(path)
        else:
            result['unchanged'].append(path)
    
    return result


def prepare_deployment_package(project_path, files_to_deploy):
    """
    Deploy edilecek dosyaları hazırla (base64 encoded)
    
    Args:
        project_path: Proje kök dizini
        files_to_deploy: Deploy edilecek dosya yolları listesi
    
    Returns:
        dict: {path: {'content': base64_string, 'size': int}}
    """
    package = {}
    
    for file_path in files_to_deploy:
        full_path = os.path.join(project_path, file_path)
        
        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            
            package[file_path] = {
                'content': base64.b64encode(content).decode('utf-8'),
                'size': len(content),
                'hash': hashlib.sha256(content).hexdigest()
            }
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            continue
    
    return package


def apply_deployment_package(project_path, package, deleted_files=None):
    """
    Deployment paketini uygula
    
    Args:
        project_path: Hedef proje dizini
        package: {path: {'content': base64_string, 'size': int, 'hash': str}}
        deleted_files: Silinecek dosya yolları listesi
    
    Returns:
        dict: {'success': bool, 'applied': int, 'deleted': int, 'errors': []}
    """
    result = {
        'success': True,
        'applied': 0,
        'deleted': 0,
        'errors': []
    }
    
    # Dosyaları sil
    if deleted_files:
        for file_path in deleted_files:
            full_path = os.path.join(project_path, file_path)
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
                    result['deleted'] += 1
                    
                    # Boş dizinleri temizle
                    dir_path = os.path.dirname(full_path)
                    while dir_path != project_path:
                        if os.path.isdir(dir_path) and not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            dir_path = os.path.dirname(dir_path)
                        else:
                            break
            except Exception as e:
                result['errors'].append(f"Delete error {file_path}: {str(e)}")
    
    # Dosyaları yaz
    for file_path, file_info in package.items():
        full_path = os.path.join(project_path, file_path)
        
        try:
            # Dizin yoksa oluştur
            dir_path = os.path.dirname(full_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            
            # Dosyayı yaz
            content = base64.b64decode(file_info['content'])
            
            # Hash doğrulaması
            if hashlib.sha256(content).hexdigest() != file_info['hash']:
                result['errors'].append(f"Hash mismatch for {file_path}")
                result['success'] = False
                continue
            
            with open(full_path, 'wb') as f:
                f.write(content)
            
            result['applied'] += 1
            
        except Exception as e:
            result['errors'].append(f"Write error {file_path}: {str(e)}")
            result['success'] = False
    
    return result


class DeploymentManager:
    """Ana deployment yönetici sınıfı"""
    
    def __init__(self, project_id=None):
        self.project_id = project_id
        self.project = None
        if project_id:
            self.project = Project.query.get(project_id)
    
    def get_server_manifest(self):
        """Server'daki projenin manifest'ini getir"""
        if not self.project:
            return {}
        return get_project_manifest(self.project_id)
    
    def scan_server_files(self):
        """Server'daki proje dosyalarını tara ve manifest'i güncelle"""
        if not self.project:
            return {}
        
        files = scan_project_files(self.project.path)
        update_project_manifest(self.project_id, files)
        return {path: info['hash'] for path, info in files.items()}
    
    def receive_deployment(self, package, deleted_files=None, description=None):
        """
        Deployment paketini al ve uygula
        
        Args:
            package: Dosya paketi
            deleted_files: Silinecek dosyalar
            description: Deployment açıklaması
        
        Returns:
            dict: Deployment sonucu
        """
        if not self.project:
            return {'success': False, 'error': 'Project not found'}
        
        # Deployment öncesi backup
        from app.utils.version_manager import VersionManager
        vm = VersionManager()
        try:
            vm.create_backup(self.project, description=f"Pre-deployment backup: {description or 'No description'}")
        except Exception as e:
            print(f"Backup failed: {e}")
        
        # Paketi uygula
        result = apply_deployment_package(
            self.project.path,
            package,
            deleted_files
        )
        
        # Manifest'i güncelle
        if result['success'] or result['applied'] > 0:
            self.scan_server_files()
        
        # Log kaydet
        log = DeploymentLog(
            project_id=self.project_id,
            files_changed=result['applied'],
            files_deleted=result.get('deleted', 0),
            total_size=sum(f.get('size', 0) for f in package.values()),
            description=description,
            status='success' if result['success'] else 'partial' if result['applied'] > 0 else 'failed'
        )
        db.session.add(log)
        db.session.commit()
        
        return result
    
    def get_deployment_history(self, limit=20):
        """Deployment geçmişini getir"""
        if not self.project:
            return []
        
        logs = DeploymentLog.query.filter_by(
            project_id=self.project_id
        ).order_by(DeploymentLog.deployed_at.desc()).limit(limit).all()
        
        return [{
            'id': log.id,
            'deployed_at': log.deployed_at.isoformat(),
            'files_changed': log.files_changed,
            'files_deleted': log.files_deleted,
            'total_size': log.total_size,
            'description': log.description,
            'status': log.status
        } for log in logs]


# App State Management
def get_or_create_app_state(project_id):
    """Proje için AppState kaydını getir veya oluştur"""
    state = AppState.query.filter_by(project_id=project_id).first()
    if not state:
        state = AppState(project_id=project_id, should_run=False)
        db.session.add(state)
        db.session.commit()
    return state


def set_app_should_run(project_id, should_run):
    """Projenin restart sonrası çalışma durumunu ayarla"""
    state = get_or_create_app_state(project_id)
    state.should_run = should_run
    if should_run:
        state.last_started_at = datetime.utcnow()
    else:
        state.last_stopped_at = datetime.utcnow()
    db.session.commit()
    return state


def get_apps_to_restore():
    """Restart sonrası başlatılması gereken uygulamaları getir"""
    states = AppState.query.filter_by(should_run=True).all()
    return [state.project for state in states if state.project]


def restore_app_states():
    """
    Server restart sonrası uygulamaları eski durumlarına getir
    should_run=True olan tüm projeleri başlat
    """
    from app.utils.system import generate_supervisor_config
    
    apps_to_restore = get_apps_to_restore()
    results = []
    
    for project in apps_to_restore:
        try:
            # Proje zaten çalışıyor mu kontrol et
            if project.status == 'running' and project.pid:
                from app.utils.system import check_process_status
                if check_process_status(project.pid):
                    results.append({
                        'project': project.name,
                        'status': 'already_running',
                        'pid': project.pid
                    })
                    continue
            
            # Projeyi başlat
            env_vars = json.loads(project.env_vars) if project.env_vars else {}
            pid = generate_supervisor_config(
                project.name,
                project.project_type,
                project.path,
                project.port,
                env_vars=env_vars,
                entry_point=project.entry_point
            )
            
            if pid:
                project.pid = pid
                project.status = 'running'
                db.session.commit()
                results.append({
                    'project': project.name,
                    'status': 'started',
                    'pid': pid
                })
            else:
                results.append({
                    'project': project.name,
                    'status': 'failed',
                    'error': 'Could not start process'
                })
                
        except Exception as e:
            results.append({
                'project': project.name,
                'status': 'error',
                'error': str(e)
            })
    
    return results
