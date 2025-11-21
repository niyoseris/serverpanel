#!/bin/bash

# Deploy Adaptive Auto-Setup Feature

SERVER_USER="root"
SERVER_IP="YOUR_SERVER_IP"
SERVER_PATH="/opt/vdspanel"

echo "=== Deploying Adaptive Auto-Setup Feature ==="
echo ""

# Upload updated files
echo "Uploading files..."
scp app/routes.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/
scp app/utils/system.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/utils/

# Restart service
echo ""
echo "Restarting VDS Panel..."
ssh ${SERVER_USER}@${SERVER_IP} "systemctl restart vdspanel && sleep 2 && systemctl status vdspanel --no-pager | head -15"

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "🎉 Adaptive Auto-Setup is now ACTIVE!"
echo ""
echo "Features:"
echo "  ✓ Automatic venv creation"
echo "  ✓ Automatic dependency installation"
echo "  ✓ Automatic gunicorn installation"
echo "  ✓ Smart requirements.txt detection"
echo "  ✓ Fallback to basic Flask setup"
echo "  ✓ Works on both upload and start"
echo ""
echo "Panel will now automatically fix project issues!"
echo "Just upload your project or click Start - it handles the rest!"
