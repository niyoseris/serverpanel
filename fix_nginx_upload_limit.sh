#!/bin/bash

# Fix Nginx Upload Limit for VDS Panel
# This script increases the upload size limit to allow large project uploads

SERVER_USER="root"
SERVER_IP="45.132.181.253"

echo "=== Fixing Nginx Upload Limit ==="
echo ""

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
set -e

echo "Configuring Nginx to allow large file uploads..."

# Backup current nginx config
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%s)

# Add or update client_max_body_size in http block
if grep -q "client_max_body_size" /etc/nginx/nginx.conf; then
    echo "Updating existing client_max_body_size..."
    sed -i 's/client_max_body_size.*/client_max_body_size 1000M;/' /etc/nginx/nginx.conf
else
    echo "Adding client_max_body_size to nginx.conf..."
    sed -i '/http {/a \    client_max_body_size 1000M;' /etc/nginx/nginx.conf
fi

# Also add to vdspanel nginx config if it exists
if [ -f /etc/nginx/sites-available/vdspanel ]; then
    if ! grep -q "client_max_body_size" /etc/nginx/sites-available/vdspanel; then
        sed -i '/server {/a \    client_max_body_size 1000M;' /etc/nginx/sites-available/vdspanel
    fi
fi

# Test nginx configuration
echo ""
echo "Testing Nginx configuration..."
nginx -t

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Configuration valid. Reloading Nginx..."
    systemctl reload nginx
    echo "✓ Nginx reloaded successfully"
    echo ""
    echo "Upload limit is now set to 1000MB (1GB)"
else
    echo ""
    echo "✗ Configuration test failed. Restoring backup..."
    cp /etc/nginx/nginx.conf.backup.* /etc/nginx/nginx.conf
    echo "Backup restored. Please check the configuration manually."
fi

# Show current configuration
echo ""
echo "Current Nginx upload limit:"
grep -A 1 "client_max_body_size" /etc/nginx/nginx.conf

ENDSSH

echo ""
echo "=== Done! ==="
echo ""
echo "You can now upload projects up to 1GB in size."
echo "Try uploading your folder again."
