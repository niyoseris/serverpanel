#!/bin/bash

# Deployment özelliği güncellemesi

SERVER_USER="root"
SERVER_IP="45.132.181.253"
SERVER_PATH="/opt/vdspanel"

echo "=== Deployment Özelliği Güncellemesi ==="
echo "Server: ${SERVER_USER}@${SERVER_IP}"
echo ""

# Upload updated and new files
echo "Dosyalar yükleniyor..."

# Ana dosyalar
scp app/models.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/
scp app/routes.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/

# Utils
scp app/utils/deployment_manager.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/utils/

# Templates
scp app/templates/base.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/deployment.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/project_deployment.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/

# Scripts
scp migrate_deployment.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/
scp restore_apps.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/
scp deploy_client.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/
scp vdspanel-restore.service ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

echo "✓ Dosyalar yüklendi"

# Run migration and restart
echo ""
echo "Migration çalıştırılıyor ve servis yeniden başlatılıyor..."
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /opt/vdspanel
source venv/bin/activate

# Run migration
echo "Migration çalıştırılıyor..."
python migrate_deployment.py

# Setup restore service
echo ""
echo "Restore servisi kuruluyor..."
cp vdspanel-restore.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable vdspanel-restore.service

# Restart main service
echo ""
echo "VDS Panel yeniden başlatılıyor..."
systemctl restart vdspanel

sleep 3
systemctl status vdspanel --no-pager | head -15
ENDSSH

echo ""
echo "=== Güncelleme Tamamlandı ==="
echo ""
echo "Yeni özellikler:"
echo "  ✓ Deployment Manager (SSH gerektirmez)"
echo "  ✓ App State Persistence (restart sonrası otomatik başlatma)"
echo "  ✓ Deployment UI (sidebar'da Deployment menüsü)"
echo "  ✓ CLI Client (deploy_client.py)"
