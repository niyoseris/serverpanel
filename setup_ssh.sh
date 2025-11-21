#!/bin/bash

# SSH Key Setup Script
# This script will set up passwordless SSH authentication

SERVER_USER="root"
SERVER_IP="YOUR_SERVER_IP"

echo "=== SSH Key Setup ==="
echo ""
echo "This script will set up passwordless SSH access to your VDS server."
echo "You will be asked for the server password ONE TIME."
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Check if SSH key already exists
if [ -f ~/.ssh/id_rsa ]; then
    echo ""
    echo "SSH key already exists at ~/.ssh/id_rsa"
    read -p "Do you want to use the existing key? (y/n): " use_existing
    
    if [ "$use_existing" != "y" ]; then
        echo ""
        echo "Creating backup of existing key..."
        mv ~/.ssh/id_rsa ~/.ssh/id_rsa.backup.$(date +%s)
        mv ~/.ssh/id_rsa.pub ~/.ssh/id_rsa.pub.backup.$(date +%s)
        
        echo "Generating new SSH key..."
        ssh-keygen -t rsa -b 4096 -C "vdspanel@$(hostname)" -f ~/.ssh/id_rsa -N ""
        echo "✓ New SSH key generated"
    fi
else
    echo "Generating SSH key..."
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
    ssh-keygen -t rsa -b 4096 -C "vdspanel@$(hostname)" -f ~/.ssh/id_rsa -N ""
    echo "✓ SSH key generated"
fi

echo ""
echo "Your public key:"
echo "---"
cat ~/.ssh/id_rsa.pub
echo "---"

echo ""
echo "Installing SSH key on server..."
echo "You will be asked for the root password now."
echo ""

# Copy SSH key to server
ssh-copy-id -i ~/.ssh/id_rsa.pub ${SERVER_USER}@${SERVER_IP}

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SSH key successfully installed!"
    echo ""
    echo "Testing passwordless connection..."
    ssh -o BatchMode=yes ${SERVER_USER}@${SERVER_IP} "echo 'Passwordless SSH works!' && uname -a"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✓✓✓ SUCCESS! ✓✓✓"
        echo ""
        echo "Passwordless SSH authentication is now configured."
        echo "You can now connect without entering a password:"
        echo "  ssh ${SERVER_USER}@${SERVER_IP}"
        echo ""
        echo "Next step: Run deployment script"
        echo "  bash deploy_to_server.sh"
    else
        echo ""
        echo "⚠ Warning: Key was installed but connection test failed."
        echo "You may need to check server SSH configuration."
    fi
else
    echo ""
    echo "✗ Failed to install SSH key"
    echo "Please check:"
    echo "1. Server IP is correct: ${SERVER_IP}"
    echo "2. Root password is correct"
    echo "3. SSH service is running on server"
    echo "4. Port 22 is open"
fi
