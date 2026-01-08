# KGX Storage Web Server

Web interface for browsing and downloading KGX (Knowledge Graph Exchange) files from S3 storage.

**Live Site**: https://kgx-storage.rtx.ai

---

## Overview

This web server provides public HTTP access to Knowledge Graph Exchange (KGX) files produced by the NCATS Biomedical Data Translator project. The service enables the DOGSURF team and other Translator consortium members to browse and download processed knowledge graph outputs stored in Amazon S3.

The system architecture separates data processing from data access: the data processing pipeline resides in the main `translator-ingests` repository, while this repository contains only the web interface layer. This separation of concerns allows independent development and deployment of the pipeline and web interface components.

**Data processing pipeline**: https://github.com/NCATSTranslator/translator-ingests/tree/kgx_storage/src/translator_ingest/util/storage

---

## Features

- **Browse S3 bucket folders and files**: Provides a hierarchical directory interface for navigating the S3 bucket structure. Users can explore folder hierarchies without requiring direct S3 access or AWS credentials.
- **Download files via presigned URLs (1-hour expiration)**: Generates temporary authenticated S3 URLs that enable public downloads without exposing permanent credentials. The 1-hour expiration provides security while allowing sufficient time for downloads.
- **JSON viewer with syntax highlighting for metadata files**: Displays JSON metadata files (such as `graph-metadata.json`) directly in the browser with syntax highlighting and formatting. This eliminates the need to download files just to inspect their contents. Includes a download button for saving the file locally.
- **HTTPS with SSL certificate management via Let's Encrypt**: Provides encrypted connections for data security. Let's Encrypt certificates are free and automatically renewed, eliminating manual certificate management.
- **Public read-only access**: No authentication is required, enabling open access to research data for the Translator consortium and broader scientific community.

---

## Architecture

```
User Browser
    ↓ HTTPS (port 443)
Nginx (reverse proxy + SSL termination)
    ↓ HTTP (localhost:5000)
Flask + Gunicorn Web Server
    ↓ AWS SDK (boto3)
S3 Bucket (translator-ingests)
```

**Components:**
- **Nginx**: Handles incoming HTTPS connections on port 443, performs SSL/TLS termination (decryption), and forwards requests to the Flask application on localhost:5000. This separation allows Nginx to efficiently handle connection management, static file serving, and SSL processing while Flask focuses on application logic.
- **Flask/Gunicorn**: Flask provides the web application framework for routing and S3 integration. Gunicorn serves as the WSGI (Web Server Gateway Interface) server that runs multiple Flask worker processes for concurrent request handling. Gunicorn is production-grade and more robust than Flask's development server.
- **S3**: Amazon S3 bucket (`translator-ingests`) stores the KGX output files. Files are accessed via presigned URLs with 1-hour expiration, which provide temporary authenticated access without exposing permanent credentials.
- **IAM Role**: EC2 instance-attached IAM role provides credentials for S3 API calls via the instance metadata service (http://169.254.169.254). This eliminates the need for hardcoded credentials and follows AWS security best practices.

---

## Requirements

### Infrastructure
- **EC2 instance running Ubuntu/Debian (t3.medium)**: The web server requires a Linux environment with systemd for process management. The t3.medium instance type (2 vCPU, 4 GB RAM) provides sufficient resources for the Flask application and Nginx while remaining cost-effective. Ubuntu/Debian distributions include the required package repositories for Nginx, Certbot, and Python 3.12.
- **IAM role with S3 read permissions**: The EC2 instance requires an attached IAM role with `s3:GetObject` (read individual files) and `s3:ListBucket` (list directory contents) permissions for the `translator-ingests` bucket. This enables boto3 to authenticate via the instance metadata service without requiring hardcoded credentials.
- **Elastic IP allocated and associated**: An Elastic IP provides a static public IP address that persists across instance restarts. This is necessary for DNS configuration and SSL certificate validation.
- **Domain `kgx-storage.rtx.ai` pointing to Elastic IP**: DNS A record mapping the domain to the Elastic IP enables HTTPS certificate issuance via Let's Encrypt, which requires domain validation.
- **Security Group allowing ports 22 (SSH), 80 (HTTP), 443 (HTTPS)**: AWS Security Group acts as a virtual firewall. Port 22 enables remote administration, port 80 is required for Let's Encrypt certificate challenges and HTTP-to-HTTPS redirection, and port 443 is the standard HTTPS port for public access.

### Software
- **Python 3.12.3** (specified in `.python-version`): The exact Python version is pinned to ensure consistent behavior across deployments. All dependencies in `requirements.txt` have been tested with this version.
- **Nginx**: Reverse proxy server for SSL termination, connection management, and static file serving. Nginx is more efficient than Python-based web servers for these tasks.
- **Certbot**: ACME client for automated SSL certificate provisioning and renewal from Let's Encrypt Certificate Authority. Certificates are free and automatically renewed before expiration.
- **Python packages with pinned versions** (in `requirements.txt`): All dependencies use exact version pinning (`==` operator) to ensure reproducible deployments and prevent unexpected breakage from dependency updates.

---

## Installation (Fresh EC2 Setup)

### 1. Clone This Repository

```bash
cd /home/ubuntu
git clone https://github.com/RTXteam/kgx-storage.git kgx-storage-webserver
cd kgx-storage-webserver
```

**Purpose**: Download the web server source code to the EC2 instance. The repository is cloned into `/home/ubuntu/kgx-storage-webserver` to establish a consistent deployment path that is referenced by the systemd service configuration.

### 2. Install System Dependencies

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3.12 python3.12-venv python3-pip
```

**Purpose**: Install required system-level packages that cannot be provided through Python's package manager.
- `nginx`: Reverse proxy server that handles HTTPS termination and forwards requests to the Flask application
- `certbot` and `python3-certbot-nginx`: Automated SSL certificate provisioning and renewal from Let's Encrypt Certificate Authority
- `python3.12`: Specific Python interpreter version required for dependency compatibility (pinned version ensures reproducibility)
- `python3.12-venv`: Virtual environment module for isolated Python dependency management
- `python3-pip`: Python package installer

### 3. Set Up Python Virtual Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Purpose**: Create an isolated Python environment to prevent dependency conflicts with system packages.
- `python3.12 -m venv .venv`: Creates a virtual environment using the exact Python version specified in `.python-version`
- `source .venv/bin/activate`: Activates the environment so subsequent pip installations are isolated
- `pip install --upgrade pip`: Updates pip to the latest version for improved dependency resolution
- `pip install -r requirements.txt`: Installs all Python dependencies with pinned versions (== operator) to ensure exact reproducibility across deployments

### 4. Set Up the Web Service

```bash
cd /home/ubuntu/kgx-storage-webserver
sudo ./setup-webserver-service.sh
sudo systemctl status kgx-storage-webserver
```

**Purpose**: Configure the Flask application as a systemd service for automatic startup and process management.
- The setup script installs `kgx-storage-webserver.service` to `/etc/systemd/system/`, enabling the web server to start automatically on system boot and restart on failure
- Systemd provides process supervision, logging via journald, and standardized service management commands
- `systemctl status` verifies the service is active and running without errors

### 5. Configure Nginx

```bash
sudo cp nginx-config /etc/nginx/sites-available/kgx-storage
sudo ln -sf /etc/nginx/sites-available/kgx-storage /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

**Purpose**: Configure Nginx as a reverse proxy to handle external HTTPS traffic and forward requests to the Flask application.
- Nginx provides SSL termination, static file serving, and connection handling that are more efficient than pure Python implementations
- The sites-available/sites-enabled pattern is a Debian convention that separates configuration storage from active configurations
- Removing the default site prevents port conflicts on port 80
- `nginx -t` validates the configuration syntax before applying changes
- `systemctl enable` ensures Nginx starts automatically on system boot

### 6. Set Up HTTPS with Let's Encrypt

```bash
sudo certbot --nginx -d kgx-storage.rtx.ai
sudo certbot renew --dry-run
```

**Purpose**: Provision and configure SSL/TLS certificates for encrypted HTTPS communication.
- Certbot automatically obtains free certificates from Let's Encrypt and modifies the Nginx configuration to use them
- The `--nginx` flag integrates with the existing Nginx configuration
- Let's Encrypt certificates expire after 90 days; Certbot installs a systemd timer for automatic renewal
- `--dry-run` verifies the renewal process works correctly without actually renewing the certificate

### 7. Configure Security Group

Configure EC2 Security Group inbound rules in the AWS Console:

| Type  | Protocol | Port | Source    | Purpose                          |
|-------|----------|------|-----------|----------------------------------|
| SSH   | TCP      | 22   | Your IP   | Remote administration access     |
| HTTP  | TCP      | 80   | 0.0.0.0/0 | HTTP to HTTPS redirect (Certbot) |
| HTTPS | TCP      | 443  | 0.0.0.0/0 | Public web access                |

**Purpose**: Configure AWS firewall rules to control network access to the EC2 instance.
- Port 22 should be restricted to your administrative IP for security
- Port 80 is required for Certbot's HTTP-01 challenge during certificate issuance and for automatic HTTPS redirection
- Port 443 is the standard HTTPS port for public web access

### 8. Verify Setup

```bash
curl -I https://kgx-storage.rtx.ai
```

**Purpose**: Confirm the web server is accessible over HTTPS and returning valid responses. A successful response (HTTP 200 or 302) indicates that Nginx, SSL certificates, Flask application, and S3 connectivity are all functioning correctly.

---

## File Structure

Repository structure and purpose of each file:

```
kgx-storage-webserver/
├── web_server.py                      # Flask application with S3 integration and routing logic
├── requirements.txt                   # Python dependencies with exact version pinning (==)
├── .python-version                    # Python version specification (3.12.3) for reproducibility
├── kgx-storage-webserver.service      # Systemd unit file for service management
├── setup-webserver-service.sh         # Shell script to install and enable the systemd service
├── nginx-config                       # Nginx reverse proxy configuration template
├── .gitignore                         # Git exclusion rules (virtual env, cache files, etc.)
├── public/                            # Static assets served by Nginx
│   └── ncats-banner.png              # NCATS Translator project banner image
└── README.md                          # Documentation (this file)
```

---

## Service Management

### Systemd Commands

Systemd manages the Flask application as a background service with automatic restarts and logging.

```bash
# Check status - shows if service is running, recent log entries, and PID
sudo systemctl status kgx-storage-webserver

# Stop/Start/Restart
sudo systemctl stop kgx-storage-webserver      # Stop the service
sudo systemctl start kgx-storage-webserver     # Start the service
sudo systemctl restart kgx-storage-webserver   # Restart (use after code changes)

# View logs (real-time) - continuously displays new log entries as they occur
sudo journalctl -u kgx-storage-webserver -f

# View last 100 lines - displays recent log history for debugging
sudo journalctl -u kgx-storage-webserver -n 100

# Enable/Disable auto-start on boot
sudo systemctl enable kgx-storage-webserver    # Start automatically after system boot
sudo systemctl disable kgx-storage-webserver   # Prevent automatic startup
```

### Nginx Commands

Nginx configuration changes require validation and reloading to take effect.

```bash
# Test configuration - validates syntax before applying changes
# Always run this before restarting Nginx to prevent configuration errors
sudo nginx -t

# Reload (no downtime) - applies configuration changes without dropping connections
# Preferred method for configuration updates
sudo systemctl reload nginx

# Restart - full stop and start cycle (brief downtime)
# Use only when reload is insufficient
sudo systemctl restart nginx

# Check status - shows if Nginx is running and listening on ports 80/443
sudo systemctl status nginx
```

### SSL Certificate Management

Let's Encrypt certificates expire after 90 days. Certbot installs a systemd timer that automatically renews certificates when they have 30 days or less remaining.

```bash
# Check certificate expiry - displays certificate validity dates
# Renewal is recommended when less than 30 days remain
sudo certbot certificates

# Manually renew certificates - forces immediate renewal
# Normally not needed due to automatic renewal
sudo certbot renew

# Test renewal (dry run) - validates the renewal process without actually renewing
# Useful for verifying automatic renewal will work
sudo certbot renew --dry-run
```

---

## Log Files

Logs are stored in multiple locations for different system components:

- **Application logs**: `/var/log/kgx-storage/access.log` (HTTP request log), `/var/log/kgx-storage/error.log` (Python exceptions and errors)
  - Created by Gunicorn for application-level logging
- **Systemd logs**: `journalctl -u kgx-storage-webserver`
  - Systemd journal contains service startup/shutdown events and stdout/stderr from the application
  - Persists across service restarts and system reboots
- **Nginx logs**: `/var/log/nginx/access.log` (all incoming HTTPS requests), `/var/log/nginx/error.log` (Nginx-level errors)
  - Useful for diagnosing SSL issues, connection problems, and reverse proxy errors

---

## Updating the Application

To deploy code changes from the Git repository to the running service:

```bash
cd /home/ubuntu/kgx-storage-webserver
git pull                                      # Download latest code from GitHub
sudo systemctl restart kgx-storage-webserver # Restart service to load new code
sudo systemctl status kgx-storage-webserver  # Verify service restarted successfully
```

**Note**: Changes to Python code require a service restart. Changes to Nginx configuration require `sudo nginx -t && sudo systemctl reload nginx`.

---

## Troubleshooting

### Service Won't Start

**Symptoms**: The web server fails to start or crashes immediately after starting.

**Diagnostic steps**:
```bash
# Check detailed logs - displays the last 50 log entries from the systemd journal
# Look for Python exceptions, port conflicts, or missing dependencies
sudo journalctl -u kgx-storage-webserver -n 50

# Verify port 5000 is available - checks if another process is using port 5000
# If another process is listed, you'll need to stop it or change Flask's port
sudo ss -tulpn | grep 5000

# Check Python dependencies - attempts to import required modules
# If import fails, a module is missing or incompatible; reinstall from requirements.txt
cd /home/ubuntu/kgx-storage-webserver
source .venv/bin/activate
python -c "import flask, boto3, gunicorn"
```

### 502 Bad Gateway

**Symptoms**: Nginx returns "502 Bad Gateway" error when accessing the site.

**Cause**: Nginx cannot connect to the Flask application on localhost:5000, typically because the Flask service is not running or crashed.

**Diagnostic steps**:
```bash
# Check if the Flask service is running
sudo systemctl status kgx-storage-webserver

# View recent error logs to identify why the service stopped
sudo journalctl -u kgx-storage-webserver -n 50
```

### SSL Certificate Issues

**Symptoms**: Browser shows SSL certificate errors, or HTTPS is not working.

**Diagnostic steps**:
```bash
# Check certificate validity and expiration date
# Certificates should auto-renew; if expired, run 'sudo certbot renew'
sudo certbot certificates

# Test Nginx configuration syntax - identifies configuration errors before applying
sudo nginx -t

# Review Nginx SSL configuration - verify certificate paths are correct
sudo cat /etc/nginx/sites-available/kgx-storage
```

### JSON Viewer Not Working

**Symptoms**: JSON files download instead of displaying in the browser viewer.

**Cause**: The Flask application may need to reload the updated routing logic.

**Solution**:
```bash
# Restart the Flask service to reload code changes
sudo systemctl restart kgx-storage-webserver
```

### S3 Access Denied

**Symptoms**: Application returns "Access Denied" errors when trying to list or download files.

**Cause**: The EC2 instance IAM role is missing or lacks required S3 permissions.

**Diagnostic steps**:
```bash
# Check if IAM role is attached to the instance
# This should return a role name; if empty, no IAM role is attached
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/

# If a role name appears, you can retrieve temporary credentials (verify they exist):
ROLE_NAME=$(curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/)
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE_NAME
```

**Solution**: Verify the IAM role attached to the EC2 instance includes the policy documented in the IAM Permissions section.

---

## IAM Permissions

The EC2 instance requires an IAM role with the following policy attached. This policy grants the minimum permissions necessary for the web server to function (principle of least privilege).

**Required IAM policy for EC2 instance role:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::translator-ingests",
        "arn:aws:s3:::translator-ingests/*"
      ]
    }
  ]
}
```

**Permission breakdown:**
- `s3:GetObject` on `arn:aws:s3:::translator-ingests/*`: Allows reading individual file objects from the bucket. Required for generating presigned download URLs and viewing JSON files.
- `s3:ListBucket` on `arn:aws:s3:::translator-ingests`: Allows listing directory contents (objects with common prefixes). Required for displaying folder contents in the web interface.

**Security considerations:**
- No write permissions (`s3:PutObject`, `s3:DeleteObject`) are granted, enforcing read-only access
- Permissions are scoped exclusively to the `translator-ingests` bucket
- Credentials are provided via the instance metadata service (http://169.254.169.254), not hardcoded in the application

---

## Development

For local development and testing, you can run Flask's development server directly without systemd or Nginx. The development server includes automatic code reloading and detailed error pages.

```bash
cd /home/ubuntu/kgx-storage-webserver
source .venv/bin/activate       # Activate the virtual environment
python web_server.py             # Run Flask development server
```

Access the development server at http://localhost:5000

**Important**: The development server is single-threaded and not suitable for production use. It lacks Gunicorn's process management and Nginx's SSL termination. Use this mode only for testing code changes before deploying to production.

---

## Production

This section documents the production deployment at https://kgx-storage.rtx.ai, including URL patterns and download methods for accessing KGX files.

### Web Interface

The web interface provides multiple URL endpoints for different operations:

- **Main site**: https://kgx-storage.rtx.ai (root directory listing)
- **Browse folders**: `https://kgx-storage.rtx.ai/?path=<folder-path>` (navigate to subdirectories)
- **View JSON**: `https://kgx-storage.rtx.ai/view/<s3-key>` (display JSON files with syntax highlighting)
- **Download file**: `https://kgx-storage.rtx.ai/download/<s3-key>` (generate presigned S3 URL and download)

### Download Methods

Three download methods are available, each suited for different use cases:

#### Method 1: HTTPS via Web Interface (Recommended for users without AWS credentials)

This method uses presigned S3 URLs generated by the web server. No AWS credentials are required, making it suitable for public access. The URLs expire after 1 hour for security.

Download individual files using curl:
```bash
# Download a single file
curl -O https://kgx-storage.rtx.ai/download/releases/alliance/latest/alliance-nodes.tsv.gz

# Download with custom filename
curl -o myfile.tar.zst https://kgx-storage.rtx.ai/download/releases/alliance/latest/alliance.tar.zst

# Download with progress bar
curl -# -O https://kgx-storage.rtx.ai/download/releases/alliance/latest/alliance-edges.tsv.gz
```

Download using wget:
```bash
# Download a single file
wget https://kgx-storage.rtx.ai/download/releases/alliance/latest/alliance-nodes.tsv.gz

# Download with custom filename
wget -O myfile.json https://kgx-storage.rtx.ai/download/releases/alliance/latest/graph-metadata.json
```

#### Method 2: Direct S3 Access (Requires AWS credentials)

This method bypasses the web server and accesses S3 directly. Requires AWS credentials with `s3:GetObject` and `s3:ListBucket` permissions for the `translator-ingests` bucket. This method is more efficient for downloading multiple files or entire directories, and supports advanced features like filtering and synchronization.

Using AWS CLI with read permissions:
```bash
# Download single file
aws s3 cp s3://translator-ingests/releases/alliance/latest/alliance-nodes.tsv.gz .

# Download entire folder
aws s3 cp s3://translator-ingests/releases/alliance/latest/ . --recursive

# Download with include/exclude filters
aws s3 cp s3://translator-ingests/releases/alliance/latest/ . --recursive --exclude "*" --include "*.json"

# Sync folder (only downloads new/changed files)
aws s3 sync s3://translator-ingests/releases/alliance/latest/ ./local-folder/
```

#### Method 3: Programmatic Access via Python

This method enables automated downloads within Python scripts or applications. The HTTPS approach works without credentials, while the boto3 approach requires AWS credentials but provides more control and efficiency for bulk operations.

```python
import requests

# Download via HTTPS
url = "https://kgx-storage.rtx.ai/download/releases/alliance/latest/graph-metadata.json"
response = requests.get(url)
with open("graph-metadata.json", "wb") as f:
    f.write(response.content)

# Download via boto3 (requires AWS credentials)
import boto3
s3 = boto3.client("s3")
s3.download_file(
    "translator-ingests",
    "releases/alliance/latest/graph-metadata.json",
    "graph-metadata.json"
)
```

### Example File Paths

```
releases/alliance/latest/alliance-nodes.tsv.gz
releases/alliance/latest/alliance-edges.tsv.gz
releases/alliance/latest/alliance.tar.zst
releases/alliance/latest/graph-metadata.json
releases/reactome/latest/reactome-nodes.tsv.gz
releases/reactome/latest/reactome-edges.tsv.gz
```

---

## Related Repositories

Main implementation: https://github.com/NCATSTranslator/translator-ingests/tree/kgx_storage

Contains S3 upload logic, EBS cleanup, and pipeline orchestration.

---

## Security

This deployment implements multiple layers of security controls:

- **HTTPS via Let's Encrypt SSL**: All traffic is encrypted using TLS 1.2/1.3 with certificates from Let's Encrypt Certificate Authority. This prevents eavesdropping and man-in-the-middle attacks.
- **IAM role authentication (no hardcoded credentials)**: AWS credentials are provided via the EC2 instance metadata service rather than stored in configuration files or code. This prevents credential leakage and follows AWS security best practices.
- **Presigned URLs with 1-hour expiration**: Download URLs include cryptographic signatures that expire after 1 hour, limiting the window for URL sharing or abuse while maintaining public accessibility.
- **Flask listens on localhost only**: The Flask application binds to 127.0.0.1:5000, making it inaccessible from external networks. Only Nginx can forward requests to it, reducing the attack surface.
- **Public read-only access**: The service is intentionally designed for public data dissemination. All S3 permissions are read-only, preventing data modification or deletion.
- **No rate limiting**: Currently not implemented. The public nature of the data and the 1-hour URL expiration provide basic abuse prevention. Rate limiting can be added via Nginx if needed.

---

## License

Part of the NCATS Biomedical Data Translator project.
