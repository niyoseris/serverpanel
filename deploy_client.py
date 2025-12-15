#!/usr/bin/env python3
"""
VDS Panel Deployment Client
SSH gerektirmeyen, HTTP tabanlı deployment aracı

Kullanım:
    python deploy_client.py --server https://your-server.com --project PROJECT_NAME --path /path/to/local/project

Özellikler:
    - Git benzeri dosya karşılaştırması (SHA256 hash)
    - Sadece değişen dosyaları gönderir
    - Otomatik backup ve restart
    - Session-based authentication
"""

import os
import sys
import json
import hashlib
import base64
import argparse
import getpass
import requests
from datetime import datetime

# Yoksayılacak dosya/dizin kalıpları
IGNORE_PATTERNS = {
    '__pycache__', '.git', '.svn', '.hg',
    'venv', '.venv', 'env', '.env',
    'node_modules', '.idea', '.vscode',
    '.pyc', '.pyo', '.pyd',
    '.so', '.dll', '.dylib',
    '.log', '.tmp', '.temp',
    '.DS_Store', 'Thumbs.db',
    '.sqlite', '.db',
    '.coverage', 'htmlcov',
    'dist', 'build', '.egg-info'
}


def should_ignore(path, name):
    """Dosya/dizinin yoksayılıp yoksayılmayacağını kontrol et"""
    if name in IGNORE_PATTERNS:
        return True
    
    for pattern in IGNORE_PATTERNS:
        if pattern.startswith('.') and name.endswith(pattern):
            return True
        if pattern in path.split(os.sep):
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


def scan_local_files(project_path):
    """Yerel proje dosyalarını tara"""
    files = {}
    
    if not os.path.exists(project_path):
        print(f"Hata: Proje dizini bulunamadı: {project_path}")
        return files
    
    print(f"Dosyalar taranıyor: {project_path}")
    
    for root, dirs, filenames in os.walk(project_path):
        # Yoksayılacak dizinleri filtrele
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
                        'full_path': full_path
                    }
            except (OSError, IOError) as e:
                print(f"  Uyarı: {relative_path} okunamadı: {e}")
                continue
    
    print(f"  {len(files)} dosya bulundu")
    return files


class DeploymentClient:
    def __init__(self, server_url, username=None, password=None):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.logged_in = False
    
    def login(self):
        """Panel'e giriş yap"""
        if not self.username:
            self.username = input("Kullanıcı adı: ")
        if not self.password:
            self.password = getpass.getpass("Şifre: ")
        
        print(f"Giriş yapılıyor: {self.server_url}")
        
        try:
            response = self.session.post(
                f"{self.server_url}/login",
                data={'username': self.username, 'password': self.password},
                allow_redirects=False
            )
            
            # Başarılı giriş redirect döner
            if response.status_code in [302, 303]:
                self.logged_in = True
                print("✓ Giriş başarılı")
                return True
            else:
                print("✗ Giriş başarısız")
                return False
        except Exception as e:
            print(f"✗ Bağlantı hatası: {e}")
            return False
    
    def get_projects(self):
        """Projeleri listele"""
        response = self.session.get(f"{self.server_url}/api/deployment/projects")
        data = response.json()
        
        if data.get('success'):
            return data['projects']
        return []
    
    def get_server_manifest(self, project_id):
        """Server manifest'ini al"""
        print("Server manifest alınıyor...")
        response = self.session.get(f"{self.server_url}/api/deployment/{project_id}/manifest")
        data = response.json()
        
        if data.get('success'):
            print(f"  {data['file_count']} dosya bulundu")
            return data['manifest']
        
        print(f"  Hata: {data.get('error', 'Bilinmeyen hata')}")
        return {}
    
    def compare_files(self, project_id, local_files):
        """Dosyaları karşılaştır"""
        print("Dosyalar karşılaştırılıyor...")
        
        # Sadece hash ve size gönder
        files_for_compare = {
            path: {'hash': info['hash'], 'size': info['size']}
            for path, info in local_files.items()
        }
        
        response = self.session.post(
            f"{self.server_url}/api/deployment/{project_id}/compare",
            json={'local_files': files_for_compare}
        )
        data = response.json()
        
        if data.get('success'):
            diff = data['diff']
            print(f"  + {len(diff['added'])} yeni dosya")
            print(f"  ~ {len(diff['modified'])} değişen dosya")
            print(f"  - {len(diff['deleted'])} silinen dosya")
            print(f"  = {diff['unchanged_count']} değişmeyen dosya")
            return diff
        
        print(f"  Hata: {data.get('error', 'Bilinmeyen hata')}")
        return None
    
    def deploy(self, project_id, local_files, diff, description=None, restart_after=True):
        """Dosyaları deploy et"""
        files_to_deploy = diff['added'] + diff['modified']
        
        if not files_to_deploy and not diff['deleted']:
            print("Deploy edilecek değişiklik yok.")
            return True
        
        print(f"\nDeployment hazırlanıyor...")
        print(f"  {len(files_to_deploy)} dosya gönderilecek")
        print(f"  {len(diff['deleted'])} dosya silinecek")
        
        # Dosya paketini hazırla
        package = {}
        total_size = 0
        
        for path in files_to_deploy:
            file_info = local_files.get(path)
            if not file_info:
                print(f"  Uyarı: {path} bulunamadı, atlanıyor")
                continue
            
            try:
                with open(file_info['full_path'], 'rb') as f:
                    content = f.read()
                
                package[path] = {
                    'content': base64.b64encode(content).decode('utf-8'),
                    'size': len(content),
                    'hash': file_info['hash']
                }
                total_size += len(content)
                
            except Exception as e:
                print(f"  Hata: {path} okunamadı: {e}")
                continue
        
        print(f"  Toplam boyut: {total_size / 1024:.1f} KB")
        
        # Deploy et
        print("\nDeploy ediliyor...")
        
        response = self.session.post(
            f"{self.server_url}/api/deployment/{project_id}/deploy",
            json={
                'package': package,
                'deleted_files': diff['deleted'],
                'description': description or f'CLI deployment @ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                'restart_after': restart_after
            }
        )
        
        data = response.json()
        
        if data.get('success'):
            print(f"\n✓ Deployment başarılı!")
            print(f"  - {data.get('applied', 0)} dosya güncellendi")
            print(f"  - {data.get('deleted', 0)} dosya silindi")
            if data.get('restarted'):
                print(f"  - Uygulama yeniden başlatıldı")
            return True
        else:
            print(f"\n✗ Deployment başarısız!")
            errors = data.get('errors', [])
            for error in errors:
                print(f"  - {error}")
            return False


def main():
    parser = argparse.ArgumentParser(description='VDS Panel Deployment Client')
    parser.add_argument('--server', '-s', required=True, help='Server URL (örn: https://panel.example.com)')
    parser.add_argument('--project', '-p', help='Proje adı')
    parser.add_argument('--path', '-d', help='Yerel proje dizini')
    parser.add_argument('--username', '-u', help='Kullanıcı adı')
    parser.add_argument('--password', '-P', help='Şifre (güvenlik için önerilmez, prompt kullanın)')
    parser.add_argument('--no-restart', action='store_true', help='Deployment sonrası restart yapma')
    parser.add_argument('--description', '-m', help='Deployment açıklaması')
    parser.add_argument('--list', '-l', action='store_true', help='Projeleri listele')
    parser.add_argument('--dry-run', action='store_true', help='Sadece karşılaştır, deploy etme')
    
    args = parser.parse_args()
    
    # Client oluştur
    client = DeploymentClient(args.server, args.username, args.password)
    
    # Giriş yap
    if not client.login():
        sys.exit(1)
    
    # Projeleri listele
    if args.list:
        print("\nProjeler:")
        projects = client.get_projects()
        for p in projects:
            status_icon = "🟢" if p['status'] == 'running' else "🔴"
            print(f"  {status_icon} {p['name']} (ID: {p['id']}, Port: {p['port']})")
        sys.exit(0)
    
    # Proje ve path kontrolü
    if not args.project:
        print("\nHata: --project parametresi gerekli")
        print("Mevcut projeleri görmek için: --list")
        sys.exit(1)
    
    if not args.path:
        print("\nHata: --path parametresi gerekli")
        sys.exit(1)
    
    # Projeyi bul
    projects = client.get_projects()
    project = None
    for p in projects:
        if p['name'] == args.project:
            project = p
            break
    
    if not project:
        print(f"\nHata: '{args.project}' projesi bulunamadı")
        print("Mevcut projeleri görmek için: --list")
        sys.exit(1)
    
    print(f"\nProje: {project['name']} (ID: {project['id']})")
    print(f"Durum: {project['status']}")
    print(f"Path: {project['path']}")
    
    # Yerel dosyaları tara
    print()
    local_files = scan_local_files(os.path.abspath(args.path))
    
    if not local_files:
        print("Hata: Yerel dosya bulunamadı")
        sys.exit(1)
    
    # Karşılaştır
    print()
    diff = client.compare_files(project['id'], local_files)
    
    if not diff:
        sys.exit(1)
    
    total_changes = len(diff['added']) + len(diff['modified']) + len(diff['deleted'])
    
    if total_changes == 0:
        print("\n✓ Değişiklik yok, her şey güncel!")
        sys.exit(0)
    
    # Dry run
    if args.dry_run:
        print("\n[DRY RUN] Deployment yapılmadı")
        if diff['added']:
            print("\nYeni dosyalar:")
            for f in diff['added'][:10]:
                print(f"  + {f}")
            if len(diff['added']) > 10:
                print(f"  ... ve {len(diff['added']) - 10} dosya daha")
        
        if diff['modified']:
            print("\nDeğişen dosyalar:")
            for f in diff['modified'][:10]:
                print(f"  ~ {f}")
            if len(diff['modified']) > 10:
                print(f"  ... ve {len(diff['modified']) - 10} dosya daha")
        
        if diff['deleted']:
            print("\nSilinecek dosyalar:")
            for f in diff['deleted'][:10]:
                print(f"  - {f}")
            if len(diff['deleted']) > 10:
                print(f"  ... ve {len(diff['deleted']) - 10} dosya daha")
        
        sys.exit(0)
    
    # Onay al
    print(f"\n{total_changes} dosya değişikliği deploy edilecek.")
    confirm = input("Devam etmek istiyor musunuz? (y/N): ")
    
    if confirm.lower() != 'y':
        print("İptal edildi.")
        sys.exit(0)
    
    # Deploy et
    success = client.deploy(
        project['id'],
        local_files,
        diff,
        description=args.description,
        restart_after=not args.no_restart
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
