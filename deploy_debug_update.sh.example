#!/bin/bash

# Deploy Debug & Logging Improvements

SERVER_USER="root"
SERVER_IP="YOUR_SERVER_IP"
SERVER_PATH="/opt/vdspanel"

echo "=== Deploying Debug & Logging Improvements ==="
echo ""

echo "Uploading updated system.py with enhanced logging..."
scp app/utils/system.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/app/utils/

echo ""
echo "Restarting VDS Panel..."
ssh ${SERVER_USER}@${SERVER_IP} "systemctl restart vdspanel && sleep 2 && systemctl status vdspanel --no-pager | head -15"

echo ""
echo "=== Update Complete! ==="
echo ""
echo "Enhanced Features:"
echo "  ✓ Detailed startup logging"
echo "  ✓ Error logs always created"
echo "  ✓ Process crash detection (0.5s check)"
echo "  ✓ Executable path validation"
echo "  ✓ Better error messages in logs"
echo ""
echo "Now when a project fails to start, check the Error Log tab."
echo "It will show detailed error information!"
