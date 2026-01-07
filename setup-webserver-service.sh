#!/bin/bash
#
# Setup script for KGX Storage web server systemd service
#
# This script installs and configures the web server to run as a systemd service
# that automatically starts when the EC2 instance boots and stops when it shuts down.
#
# Usage:
#   sudo ./setup-webserver-service.sh
#
# Requirements:
#   - Must be run as root (sudo)
#   - EC2 instance with IAM role for S3 access
#   - uv and Python dependencies already installed
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo_error "Please run as root (sudo ./setup-webserver-service.sh)"
    exit 1
fi

# Configuration
SERVICE_NAME="kgx-storage-webserver"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_DIR="/var/log/kgx-storage"
WEBSERVER_DIR="/home/ubuntu/kgx-storage-webserver"
PROJECT_DIR="/home/ubuntu/translator-ingests"
VENV_DIR="${PROJECT_DIR}/.venv"
UV_BIN="/home/ubuntu/.local/bin/uv"

echo_info "Setting up KGX Storage web server as systemd service..."

# Step 1: Create log directory
echo_info "Creating log directory: ${LOG_DIR}"
mkdir -p "${LOG_DIR}"
chown ubuntu:ubuntu "${LOG_DIR}"
chmod 755 "${LOG_DIR}"

# Step 2: Install gunicorn if not present
echo_info "Checking for gunicorn..."
if [ -f "${VENV_DIR}/bin/gunicorn" ]; then
    echo_info "gunicorn already installed"
else
    echo_info "Installing gunicorn..."
    sudo -u ubuntu bash -c "cd ${PROJECT_DIR} && ${UV_BIN} pip install gunicorn"
fi

# Step 3: Copy service file to systemd directory
echo_info "Installing systemd service file..."
cp "${WEBSERVER_DIR}/kgx-storage-webserver.service" "${SERVICE_FILE}"
chmod 644 "${SERVICE_FILE}"

# Step 4: Reload systemd daemon
echo_info "Reloading systemd daemon..."
systemctl daemon-reload

# Step 5: Enable service to start on boot
echo_info "Enabling service to start on boot..."
systemctl enable "${SERVICE_NAME}"

# Step 6: Start the service
echo_info "Starting the service..."
systemctl start "${SERVICE_NAME}"

# Step 7: Check service status
echo_info "Checking service status..."
sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo_info "Service is running!"
    echo ""
    echo_info "Service status:"
    systemctl status "${SERVICE_NAME}" --no-pager
else
    echo_error "Service failed to start. Checking logs..."
    journalctl -u "${SERVICE_NAME}" --no-pager -n 20
    exit 1
fi

echo ""
echo "=============================================="
echo_info "Setup complete!"
echo "=============================================="
echo ""
echo "The web server is now running as a systemd service."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status ${SERVICE_NAME}    # Check status"
echo "  sudo systemctl stop ${SERVICE_NAME}      # Stop service"
echo "  sudo systemctl start ${SERVICE_NAME}     # Start service"
echo "  sudo systemctl restart ${SERVICE_NAME}   # Restart service"
echo "  sudo journalctl -u ${SERVICE_NAME} -f    # View logs (follow)"
echo ""
echo "Log files:"
echo "  ${LOG_DIR}/access.log    # HTTP access logs"
echo "  ${LOG_DIR}/error.log     # Error logs"
echo ""
echo "Web server URL: http://kgx-storage.rtx.ai"
echo ""
