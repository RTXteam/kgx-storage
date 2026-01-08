# KGX Storage Web Server

Web interface for browsing and downloading KGX (Knowledge Graph Exchange) files from S3 storage.

**Live Site**: https://kgx-storage.rtx.ai

---

## Overview

Web interface for the KGX Storage Component, serving the NCATS Translator project. Provides public access to processed KGX output files stored in S3 for DOGSURF and other Translator teams.

This repository contains only the Flask web server for browsing and downloading. The core S3 upload logic and data processing pipeline is in the main translator-ingests repository:
https://github.com/NCATSTranslator/translator-ingests/tree/kgx_storage/src/translator_ingest/util/storage

---

## Features

- Browse S3 bucket folders and files
- Download files via presigned URLs (1-hour expiration)
- JSON viewer with syntax highlighting for metadata files
- HTTPS with SSL certificate management via Let's Encrypt
- Public read-only access

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
- **Nginx**: HTTPS, SSL certificates, reverse proxying
- **Flask/Gunicorn**: Web application server
- **S3**: KGX output file storage
- **IAM Role**: EC2 instance read-only S3 access

---

## Requirements

### Infrastructure
- EC2 instance running Ubuntu/Debian (t3.medium)
- IAM role with S3 read permissions (`s3:GetObject`, `s3:ListBucket`)
- Elastic IP allocated and associated
- Domain `kgx-storage.rtx.ai` pointing to Elastic IP
- Security Group allowing ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Software
- Python 3.12.3 (specified in `.python-version`)
- Nginx for reverse proxy
- Certbot for SSL certificates
- Python packages with pinned versions in `requirements.txt`

---

## Installation (Fresh EC2 Setup)

### 1. Clone This Repository

```bash
cd /home/ubuntu
git clone https://github.com/RTXteam/kgx-storage.git kgx-storage-webserver
cd kgx-storage-webserver
```

### 2. Install System Dependencies

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3.12 python3.12-venv python3-pip
```

### 3. Set Up Python Virtual Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set Up the Web Service

```bash
cd /home/ubuntu/kgx-storage-webserver
sudo ./setup-webserver-service.sh
sudo systemctl status kgx-storage-webserver
```

### 5. Configure Nginx

```bash
sudo cp nginx-config /etc/nginx/sites-available/kgx-storage
sudo ln -sf /etc/nginx/sites-available/kgx-storage /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 6. Set Up HTTPS with Let's Encrypt

```bash
sudo certbot --nginx -d kgx-storage.rtx.ai
sudo certbot renew --dry-run
```

### 7. Configure Security Group

Configure EC2 Security Group inbound rules:

| Type  | Protocol | Port | Source    |
|-------|----------|------|-----------|
| SSH   | TCP      | 22   | Your IP   |
| HTTP  | TCP      | 80   | 0.0.0.0/0 |
| HTTPS | TCP      | 443  | 0.0.0.0/0 |

### 8. Verify Setup

Access https://kgx-storage.rtx.ai

---

## File Structure

```
kgx-storage-webserver/
├── web_server.py                      # Flask application
├── requirements.txt                   # Python dependencies with pinned versions
├── .python-version                    # Python version specification (3.12.3)
├── kgx-storage-webserver.service      # Systemd service file
├── setup-webserver-service.sh         # Installation script
├── nginx-config                       # Nginx configuration template
├── .gitignore                         # Git ignore rules
├── public/                            # Static assets
│   └── ncats-banner.png              # NCATS Translator banner
└── README.md                          # This file
```

---

## Service Management

### Systemd Commands

```bash
# Check status
sudo systemctl status kgx-storage-webserver

# Stop/Start/Restart
sudo systemctl stop kgx-storage-webserver
sudo systemctl start kgx-storage-webserver
sudo systemctl restart kgx-storage-webserver

# View logs (real-time)
sudo journalctl -u kgx-storage-webserver -f

# View last 100 lines
sudo journalctl -u kgx-storage-webserver -n 100

# Enable/Disable auto-start on boot
sudo systemctl enable kgx-storage-webserver
sudo systemctl disable kgx-storage-webserver
```

### Nginx Commands

```bash
# Test configuration
sudo nginx -t

# Reload (no downtime)
sudo systemctl reload nginx

# Restart
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx
```

### SSL Certificate Management

```bash
# Check certificate expiry
sudo certbot certificates

# Manually renew certificates
sudo certbot renew

# Test renewal (dry run)
sudo certbot renew --dry-run
```

---

## Log Files

- Application: `/var/log/kgx-storage/access.log`, `/var/log/kgx-storage/error.log`
- Systemd: `journalctl -u kgx-storage-webserver`
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

---

## Updating the Application

```bash
cd /home/ubuntu/kgx-storage-webserver
git pull
sudo systemctl restart kgx-storage-webserver
sudo systemctl status kgx-storage-webserver
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check detailed logs
sudo journalctl -u kgx-storage-webserver -n 50

# Verify port 5000 is available
sudo ss -tulpn | grep 5000

# Check Python dependencies
cd /home/ubuntu/kgx-storage-webserver
source .venv/bin/activate
python -c "import flask, boto3, gunicorn"
```

### 502 Bad Gateway

```bash
sudo systemctl status kgx-storage-webserver
sudo journalctl -u kgx-storage-webserver -n 50
```

### SSL Certificate Issues

```bash
sudo certbot certificates
sudo nginx -t
sudo cat /etc/nginx/sites-available/kgx-storage
```

### JSON Viewer Not Working

```bash
sudo systemctl restart kgx-storage-webserver
```

### S3 Access Denied

```bash
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

---

## IAM Permissions

Required IAM policy for EC2 instance role:

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

---

## Development

```bash
cd /home/ubuntu/kgx-storage-webserver
source .venv/bin/activate
python web_server.py
```

Access at http://localhost:5000

---

## Production

### Web Interface

- Main site: https://kgx-storage.rtx.ai
- Browse folders: `https://kgx-storage.rtx.ai/?path=<folder-path>`
- View JSON: `https://kgx-storage.rtx.ai/view/<s3-key>`
- Download file: `https://kgx-storage.rtx.ai/download/<s3-key>`

### Download Methods

#### Method 1: HTTPS via Web Interface (Recommended for users)

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

- HTTPS via Let's Encrypt SSL
- IAM role authentication (no hardcoded credentials)
- Presigned URLs with 1-hour expiration
- Flask listens on localhost only
- Public read-only access
- No rate limiting

---

## License

Part of the NCATS Biomedical Data Translator project.
