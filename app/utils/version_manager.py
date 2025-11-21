import os
import shutil
from datetime import datetime
from app import db
from app.models import Project, ProjectVersion

class VersionManager:
    """Proje versiyon yönetimi ve yedekleme sınıfı"""
    
    def __init__(self, base_backup_dir=None):
        if base_backup_dir is None:
            # uploads klasörünün yanında backups klasörü oluştur
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.base_backup_dir = os.path.join(base_dir, 'backups')
        else:
            self.base_backup_dir = base_backup_dir
            
        if not os.path.exists(self.base_backup_dir):
            os.makedirs(self.base_backup_dir)
    
    def create_backup(self, project, description=None):
        """
        Projenin mevcut durumunu yedekler
        
        Args:
            project: Yedeklenecek Project nesnesi
            description: Yedek açıklaması (opsiyonel)
            
        Returns:
            ProjectVersion: Oluşturulan yedek kaydı
        """
        if not os.path.exists(project.path):
            raise ValueError(f"Proje dizini bulunamadı: {project.path}")
        
        # Son versiyon numarasını bul
        last_version = ProjectVersion.query.filter_by(
            project_id=project.id
        ).order_by(ProjectVersion.version_number.desc()).first()
        
        new_version_number = 1 if not last_version else last_version.version_number + 1
        
        # Yedek dizinini oluştur
        project_backup_dir = os.path.join(self.base_backup_dir, project.name)
        if not os.path.exists(project_backup_dir):
            os.makedirs(project_backup_dir)
        
        # Versiyon dizini adı: v1_20231121_143022 formatında
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        version_dir_name = f"v{new_version_number}_{timestamp}"
        backup_path = os.path.join(project_backup_dir, version_dir_name)
        
        # Projeyi yedekle
        try:
            shutil.copytree(project.path, backup_path, 
                          ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', 
                                                       '.git', 'venv', 'env', 'node_modules',
                                                       '*.log', '.DS_Store'))
            
            # Veritabanına kaydet
            version = ProjectVersion(
                project_id=project.id,
                version_number=new_version_number,
                backup_path=backup_path,
                description=description or f'Auto-backup before update (v{new_version_number})'
            )
            db.session.add(version)
            db.session.commit()
            
            return version
            
        except Exception as e:
            # Hata durumunda yedek dizinini sil
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            raise Exception(f"Yedekleme sırasında hata: {str(e)}")
    
    def restore_version(self, version_id, stop_project=True):
        """
        Belirtilen versiyonu geri yükler
        
        Args:
            version_id: Geri yüklenecek ProjectVersion ID'si
            stop_project: Geri yüklemeden önce projeyi durdur
            
        Returns:
            bool: Başarılı ise True
        """
        version = ProjectVersion.query.get(version_id)
        if not version:
            raise ValueError(f"Versiyon bulunamadı: {version_id}")
        
        project = version.project
        
        if not os.path.exists(version.backup_path):
            raise ValueError(f"Yedek dizini bulunamadı: {version.backup_path}")
        
        # Proje çalışıyorsa durdur
        if stop_project and project.status == 'running':
            from app.routes import stop_project_process
            stop_project_process(project)
        
        # Mevcut durumu yedekle (restore öncesi güvenlik)
        try:
            safety_backup = self.create_backup(
                project, 
                description=f"Safety backup before restoring to v{version.version_number}"
            )
        except Exception as e:
            print(f"Güvenlik yedeği oluşturulamadı: {str(e)}")
            safety_backup = None
        
        # Mevcut proje dizinini sil
        if os.path.exists(project.path):
            shutil.rmtree(project.path)
        
        # Yedekten geri yükle
        try:
            shutil.copytree(version.backup_path, project.path)
            db.session.commit()
            return True
            
        except Exception as e:
            # Hata durumunda güvenlik yedeğini geri yükle
            if safety_backup and os.path.exists(safety_backup.backup_path):
                shutil.copytree(safety_backup.backup_path, project.path)
            raise Exception(f"Geri yükleme sırasında hata: {str(e)}")
    
    def delete_version(self, version_id):
        """
        Bir versiyonu siler
        
        Args:
            version_id: Silinecek ProjectVersion ID'si
            
        Returns:
            bool: Başarılı ise True
        """
        version = ProjectVersion.query.get(version_id)
        if not version:
            raise ValueError(f"Versiyon bulunamadı: {version_id}")
        
        # Yedek dizinini sil
        if os.path.exists(version.backup_path):
            shutil.rmtree(version.backup_path)
        
        # Veritabanından sil
        db.session.delete(version)
        db.session.commit()
        
        return True
    
    def get_project_versions(self, project_id):
        """
        Bir projenin tüm versiyonlarını getirir
        
        Args:
            project_id: Proje ID'si
            
        Returns:
            list: ProjectVersion listesi
        """
        return ProjectVersion.query.filter_by(
            project_id=project_id
        ).order_by(ProjectVersion.created_at.desc()).all()
    
    def get_version_size(self, version_id):
        """
        Bir versiyonun disk boyutunu hesaplar
        
        Args:
            version_id: Versiyon ID'si
            
        Returns:
            int: Boyut (bytes)
        """
        version = ProjectVersion.query.get(version_id)
        if not version or not os.path.exists(version.backup_path):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(version.backup_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        
        return total_size
    
    def cleanup_old_versions(self, project_id, keep_count=5):
        """
        Eski versiyonları temizler, sadece belirtilen sayıda en yeni versiyonu tutar
        
        Args:
            project_id: Proje ID'si
            keep_count: Tutulacak versiyon sayısı
            
        Returns:
            int: Silinen versiyon sayısı
        """
        versions = ProjectVersion.query.filter_by(
            project_id=project_id
        ).order_by(ProjectVersion.created_at.desc()).all()
        
        deleted_count = 0
        if len(versions) > keep_count:
            for version in versions[keep_count:]:
                try:
                    self.delete_version(version.id)
                    deleted_count += 1
                except Exception as e:
                    print(f"Versiyon silinirken hata: {str(e)}")
        
        return deleted_count
