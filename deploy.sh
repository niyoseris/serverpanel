#!/bin/bash

# VDS Panel Deployment Script
# Server: root@45.132.181.253
# Port: 5012

set -e

SERVER_USER="root"
SERVER_IP="45.132.181.253"
SERVER_PATH="/opt/vdspanel"
APP_PORT="5012"

echo "=== VDS Panel Deployment Script ==="
echo ""

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "SSH key not found. Generating new SSH key pair..."
    ssh-keygen -t rsa -b 4096 -C "vdspanel@deployment" -f ~/.ssh/id_rsa -N ""
    echo "✓ SSH key generated"
fi

# Copy SSH key to server (will ask for password once)
echo ""
echo "Setting up passwordless SSH access..."
echo "Note: You will be asked for the root password ONE TIME"
ssh-copy-id -i ~/.ssh/id_rsa.pub ${SERVER_USER}@${SERVER_IP}

echo ""
echo "✓ SSH key installed. Testing connection..."
ssh ${SERVER_USER}@${SERVER_IP} "echo 'SSH connection successful!'"

echo ""
echo "=== Analyzing server environment ==="

# Check existing applications and ports
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
echo ""
echo "Checking for existing Python applications..."
ps aux | grep -E "python|gunicorn|flask" | grep -v grep || echo "No Python apps found"

echo ""
echo "Checking ports in use..."
netstat -tuln | grep LISTEN || ss -tuln | grep LISTEN

echo ""
echo "Checking Nginx configuration..."
if [ -d /etc/nginx/sites-enabled ]; then
    ls -la /etc/nginx/sites-enabled/
    echo ""
    echo "Active Nginx configs:"
    for conf in /etc/nginx/sites-enabled/*; do
        if [ -f "$conf" ]; then
            echo "--- $conf ---"
            grep -E "listen|server_name|proxy_pass" "$conf" || true
        fi
    done
fi

echo ""
echo "Checking Supervisor processes..."
if command -v supervisorctl &> /dev/null; then
    supervisorctl status
else
    echo "Supervisor not installed"
fi

echo ""
echo "Checking systemd services..."
systemctl list-units --type=service --state=running | grep -E "python|gunicorn|flask" || echo "No Python services found"

ENDSSH

echo ""
echo "=== Server analysis complete ==="
echo ""
echo "Next steps:"
echo "1. Review the server analysis above"
echo "2. Ensure port ${APP_PORT} is available"
echo "3. Run deploy_to_server.sh to upload and configure the panel"
