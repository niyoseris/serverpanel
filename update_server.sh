#!/bin/bash

# Quick Update Script - Updates only changed files on server

SERVER_USER="root"
SERVER_IP="YOUR_SERVER_IP"
SERVER_PATH="/opt/vdspanel"

echo "=== Quick Update - VDS Panel ==="
echo ""

# Upload changed files
echo "Uploading updated files..."

scp requirements.txt ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/
scp config.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/
scp app/routes.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/
scp app/templates/upload_project.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/system_status.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/terminal.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/settings.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/project_details.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/
scp app/templates/base.html ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/templates/

echo "✓ Files uploaded"

# Install new dependencies
echo ""
echo "Installing new dependencies..."
ssh ${SERVER_USER}@${SERVER_IP} "cd ${SERVER_PATH} && source venv/bin/activate && pip install psutil"

# Restart service
echo ""
echo "Restarting vdspanel service..."
ssh ${SERVER_USER}@${SERVER_IP} "systemctl restart vdspanel && sleep 2 && systemctl status vdspanel --no-pager"

echo ""
echo "=== Update Complete! ==="
echo ""
echo "Changes:"
echo "  - Added Nginx Reverse Proxy Management:"
echo "    • Configure Nginx to route domain (port 80) to app port"
echo "    • Auto-generate Nginx config files"
echo "    • Support for @ and www subdomains"
echo "    • One-click configuration and removal"
echo "    • View generated config files"
echo "  - Domain management in project settings"
echo "  - Proper domain routing from port 80"
echo ""
echo "Usage:"
echo "  1. Add domain to project (Settings tab)"
echo "  2. Point A records to YOUR_SERVER_IP"
echo "  3. Click 'Configure Nginx' button"
echo "  4. Access via http://yourdomain.com"
echo ""
echo "Access: http://YOUR_SERVER_IP:5012"
echo "Settings: http://YOUR_SERVER_IP:5012/settings"
