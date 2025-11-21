#!/bin/bash

# VDS Panel Setup Script
# Usage: sudo ./setup.sh

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

echo "Updating system..."
apt-get update && apt-get upgrade -y

echo "Installing dependencies..."
apt-get install -y python3 python3-venv python3-pip nginx supervisor certbot python3-certbot-nginx

echo "Creating project directory..."
mkdir -p /opt/vdspanel
cd /opt/vdspanel

# In a real scenario, we would clone the repo here or copy files.
# For this script, we assume files are already here or will be copied.

echo "Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy flask-login gunicorn

echo "Configuring VDS Panel service..."
cat > /etc/systemd/system/vdspanel.service <<EOF
[Unit]
Description=VDS Panel
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/opt/vdspanel
Environment="PATH=/opt/vdspanel/venv/bin"
ExecStart=/opt/vdspanel/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 run:app

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vdspanel
systemctl start vdspanel

echo "VDS Panel installed and started on port 8000!"
