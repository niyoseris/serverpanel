#!/usr/bin/env python3
"""
App State Restore Script
Server restart sonrası should_run=True olan uygulamaları otomatik başlatır.

Kullanım:
    python restore_apps.py

Bu script'i systemd service olarak veya crontab @reboot ile çalıştırabilirsiniz.
"""

import os
import sys

# Proje dizinini path'e ekle
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

from app import create_app, db
from app.utils.deployment_manager import restore_app_states, get_apps_to_restore

def main():
    print("=" * 50)
    print("VDS Panel - App State Restore")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        # Restore edilecek uygulamaları listele
        apps = get_apps_to_restore()
        
        if not apps:
            print("\n✓ No applications to restore (none marked as should_run=True)")
            return
        
        print(f"\nFound {len(apps)} application(s) to restore:")
        for p in apps:
            print(f"  - {p.name} (port {p.port})")
        
        print("\nStarting applications...")
        print("-" * 50)
        
        results = restore_app_states()
        
        # Sonuçları göster
        started = 0
        failed = 0
        already_running = 0
        
        for result in results:
            status = result['status']
            name = result['project']
            
            if status == 'started':
                print(f"✓ {name}: Started (PID: {result.get('pid', 'N/A')})")
                started += 1
            elif status == 'already_running':
                print(f"○ {name}: Already running (PID: {result.get('pid', 'N/A')})")
                already_running += 1
            elif status == 'failed':
                print(f"✗ {name}: Failed - {result.get('error', 'Unknown error')}")
                failed += 1
            elif status == 'error':
                print(f"✗ {name}: Error - {result.get('error', 'Unknown error')}")
                failed += 1
        
        print("-" * 50)
        print(f"\nSummary:")
        print(f"  Started: {started}")
        print(f"  Already running: {already_running}")
        print(f"  Failed: {failed}")
        print("=" * 50)


if __name__ == '__main__':
    main()
