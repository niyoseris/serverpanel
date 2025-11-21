#!/bin/bash

# Quick Update - Updated files only

SERVER_USER="root"
SERVER_IP="YOUR_SERVER_IP"
SERVER_PATH="/opt/vdspanel"

echo "=== Quick Update ==="

# Upload updated files
echo "Uploading files..."
scp app/routes.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/
scp app/utils/system.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/utils/

# Restart
echo ""
echo "Restarting service..."
ssh ${SERVER_USER}@${SERVER_IP} "systemctl restart vdspanel && sleep 2 && systemctl status vdspanel --no-pager | head -15"

echo ""
echo "=== Update Complete ==="
echo ""
echo "Fixed:"
echo "  ✓ Log files now read from correct location"
echo "  ✓ Better venv checking and error messages"
echo "  ✓ Detailed startup failure messages"
