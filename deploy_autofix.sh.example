#!/bin/bash

# Deploy Auto-Fix Entry Point Feature

SERVER_USER="root"
SERVER_IP="YOUR_SERVER_IP"
SERVER_PATH="/opt/vdspanel"

echo "=== Deploying Auto-Fix Entry Point Feature ==="
echo ""

echo "Uploading files..."
scp app/utils/auto_fix.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/utils/
scp app/routes.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/

echo ""
echo "Restarting VDS Panel..."
ssh ${SERVER_USER}@${SERVER_IP} "systemctl restart vdspanel && sleep 2 && systemctl status vdspanel --no-pager | head -15"

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "🤖 Auto-Fix Entry Point is now ACTIVE!"
echo ""
echo "How it works:"
echo "  1. Project fails to start with entry point error"
echo "  2. Panel detects ModuleNotFoundError or ImportError"
echo "  3. Scans project for all Python files (app.py, run.py, etc.)"
echo "  4. Tests each possible entry point combination"
echo "  5. Finds working entry point"
echo "  6. Updates database"
echo "  7. Restarts project automatically"
echo ""
echo "Supported errors:"
echo "  ✓ ModuleNotFoundError: No module named 'app'"
echo "  ✓ ImportError: cannot import name 'app'"
echo "  ✓ Worker failed to boot"
echo ""
echo "Your project will now self-heal entry point issues!"
