#!/bin/bash

# VDS Panel - Nginx Setup Script
# This script sets up Nginx for reverse proxy

SERVER_IP="YOUR_SERVER_IP"
SERVER_USER="root"
SERVER_PATH="/opt/vdspanel"

echo "=== Nginx Setup for VDS Panel ==="
echo ""

# Check if Nginx is installed
echo "Checking Nginx installation..."
ssh ${SERVER_USER}@${SERVER_IP} "which nginx"

if [ $? -ne 0 ]; then
    echo "Nginx not found. Installing..."
    ssh ${SERVER_USER}@${SERVER_IP} "apt-get update && apt-get install -y nginx"
else
    echo "✓ Nginx is already installed"
fi

# Create sites-available and sites-enabled directories if they don't exist
echo ""
echo "Setting up Nginx directories..."
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled"

# Check if nginx.conf includes sites-enabled
echo ""
echo "Checking Nginx configuration..."
ssh ${SERVER_USER}@${SERVER_IP} "grep -q 'include /etc/nginx/sites-enabled' /etc/nginx/nginx.conf"

if [ $? -ne 0 ]; then
    echo "Adding sites-enabled include to nginx.conf..."
    ssh ${SERVER_USER}@${SERVER_IP} "sed -i '/http {/a \    include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf"
else
    echo "✓ Nginx config already includes sites-enabled"
fi

# Remove default site if it exists
echo ""
echo "Removing default Nginx site..."
ssh ${SERVER_USER}@${SERVER_IP} "rm -f /etc/nginx/sites-enabled/default"

# Create a default catch-all config for VDS Panel
echo ""
echo "Creating VDS Panel default config..."
ssh ${SERVER_USER}@${SERVER_IP} "cat > /etc/nginx/sites-available/vdspanel-default << 'EOF'
server {
    listen 80 default_server;
    server_name _;
    
    location / {
        return 404 'No site configured for this domain';
    }
}
EOF"

# Enable the default config
ssh ${SERVER_USER}@${SERVER_IP} "ln -sf /etc/nginx/sites-available/vdspanel-default /etc/nginx/sites-enabled/vdspanel-default"

# Test Nginx configuration
echo ""
echo "Testing Nginx configuration..."
ssh ${SERVER_USER}@${SERVER_IP} "nginx -t"

if [ $? -eq 0 ]; then
    echo "✓ Nginx configuration is valid"
    
    # Start/restart Nginx
    echo ""
    echo "Restarting Nginx..."
    ssh ${SERVER_USER}@${SERVER_IP} "systemctl enable nginx && systemctl restart nginx"
    
    echo ""
    echo "✓ Nginx setup complete!"
    echo ""
    echo "You can now:"
    echo "  1. Add domains to your projects via VDS Panel"
    echo "  2. Click 'Configure Nginx' to create reverse proxy"
    echo "  3. Access projects via their domains on port 80"
else
    echo "✗ Nginx configuration test failed"
    exit 1
fi

echo ""
echo "Nginx status:"
ssh ${SERVER_USER}@${SERVER_IP} "systemctl status nginx --no-pager | head -15"
