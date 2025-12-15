#!/usr/bin/env python3
"""
Deployment tabloları için migration script
Yeni tabloları mevcut veritabanına ekler
"""

import os
import sys

project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

from app import create_app, db
from app.models import FileManifest, AppState, DeploymentLog

def migrate():
    print("Deployment tabloları oluşturuluyor...")
    
    app = create_app()
    
    with app.app_context():
        # Yeni tabloları oluştur (varsa atla)
        db.create_all()
        print("✓ Tablolar oluşturuldu/güncellendi")
        
        # Mevcut projelere app_state ekle
        from app.models import Project
        projects = Project.query.all()
        
        for project in projects:
            # AppState yoksa oluştur
            if not project.app_state:
                state = AppState(
                    project_id=project.id,
                    should_run=project.status == 'running',  # Çalışıyorsa should_run=True
                    auto_restart=True
                )
                db.session.add(state)
                print(f"  + AppState oluşturuldu: {project.name} (should_run={state.should_run})")
        
        db.session.commit()
        print("\n✓ Migration tamamlandı!")

if __name__ == '__main__':
    migrate()
