# KGX Storage Web Server

Web interface for browsing and downloading KGX (Knowledge Graph Exchange) files from S3 storage.

**Live Site**: https://kgx-storage.rtx.ai

---

## Overview

This repository contains the **web interface** for the KGX Storage Component, which serves the NCATS Translator project by providing:
- Long-term storage for processed KGX output files in S3
- Public web interface for browsing and downloading files
- Support for DOGSURF and other Translator teams

**Main Implementation**: The core S3 upload logic and data processing pipeline is located in the main translator-ingests repository:
https://github.com/NCATSTranslator/translator-ingests/tree/kgx_storage

This repository only contains the Flask web server that provides the browsing interface. The actual data upload, storage management, and pipeline orchestration code lives in the translator-ingests repo.

---

## Features

- **Browse S3 bucket** folders and files with a clean web interface
- **Download files** directly from S3 via presigned URLs (1-hour expiration)
- **JSON viewer** with syntax highlighting for metadata files
- **Folder statistics** showing size, file count, and last modified date
- **HTTPS** with automatic SSL certificate management via Let's Encrypt
- **Responsive design** for mobile and desktop
- **Read-only public access** - no authentication required

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
- **Nginx**: Handles HTTPS, SSL certificates, and reverse proxying
- **Flask/Gunicorn**: Python web application serving the UI
- **S3**: Stores all KGX output files uploaded by the main pipeline
- **IAM Role**: EC2 instance has read-only S3 access (no credentials needed)

---

## Requirements

### Infrastructure
- **EC2 instance** running Ubuntu/Debian (currently: t3.micro)
- **IAM role** attached to EC2 with S3 read permissions (`s3:GetObject`, `s3:ListBucket`)
- **Elastic IP** allocated and associated (prevents IP changes on restart)
- **Domain**: `kgx-storage.rtx.ai` pointing to Elastic IP
- **Security Group**: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Software
- **Python 3.8+** with pip or uv
- **Nginx** for reverse proxy
- **Certbot** for SSL certificates
- **translator-ingests** repository installed at `/home/ubuntu/translator-ingests`

---

## Installation (Fresh EC2 Setup)

### 1. Clone This Repository

```bash
cd /home/ubuntu
git clone <repository-url> kgx-storage-webserver
cd kgx-storage-webserver
```

### 2. Install System Dependencies

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3-pip python3-venv
```

### 3. Install Python Dependencies

The web server uses the virtual environment from translator-ingests:

```bash
cd /home/ubuntu/translator-ingests
uv pip install flask gunicorn boto3
```

### 4. Set Up the Web Service

```bash
cd /home/ubuntu/kgx-storage-webserver
sudo ./setup-webserver-service.sh
```

This script will:
- Copy systemd service file to `/etc/systemd/system/kgx-storage-webserver.service`
- Create log directory at `/var/log/kgx-storage/`
- Enable and start the service

Verify it's running:
```bash
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
```

Certbot will:
- Obtain a free SSL certificate
- Modify nginx config for HTTPS
- Set up automatic renewal (every 90 days)
- Configure HTTP → HTTPS redirection

Test auto-renewal:
```bash
sudo certbot renew --dry-run
```

### 7. Configure Security Group

In AWS Console → EC2 → Security Groups:

| Type  | Protocol | Port | Source    | Description           |
|-------|----------|------|-----------|-----------------------|
| SSH   | TCP      | 22   | Your IP   | SSH access            |
| HTTP  | TCP      | 80   | 0.0.0.0/0 | HTTP (cert renewal)   |
| HTTPS | TCP      | 443  | 0.0.0.0/0 | HTTPS traffic         |

**Note**: Port 80 is required for Let's Encrypt certificate renewal.

### 8. Verify Setup

Access the site:
- **https://kgx-storage.rtx.ai** (primary, secure)
- **http://kgx-storage.rtx.ai** (redirects to HTTPS)

Click on any `.json` file to test the JSON viewer.

---

## File Structure

```
kgx-storage-webserver/
├── web_server.py                      # Flask application
├── kgx-storage-webserver.service      # Systemd service file
├── setup-webserver-service.sh         # Installation script
├── nginx-config                       # Nginx configuration template
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

- **Application access**: `/var/log/kgx-storage/access.log`
- **Application errors**: `/var/log/kgx-storage/error.log`
- **Systemd logs**: `journalctl -u kgx-storage-webserver`
- **Nginx access**: `/var/log/nginx/access.log`
- **Nginx errors**: `/var/log/nginx/error.log`

---

## Updating the Application

When you make changes to `web_server.py`:

```bash
cd /home/ubuntu/kgx-storage-webserver
git pull
sudo systemctl restart kgx-storage-webserver
sudo systemctl status kgx-storage-webserver
```

No nginx restart needed unless you change nginx configuration.

---

## Troubleshooting

### Service Won't Start

```bash
# Check detailed logs
sudo journalctl -u kgx-storage-webserver -n 50

# Verify port 5000 is available
sudo ss -tulpn | grep 5000

# Check Python dependencies
cd /home/ubuntu/translator-ingests
source .venv/bin/activate
python -c "import flask, boto3, gunicorn"
```

### 502 Bad Gateway

This usually means the Flask app isn't running:
```bash
sudo systemctl status kgx-storage-webserver
sudo journalctl -u kgx-storage-webserver -n 50
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Verify nginx SSL config
sudo nginx -t
sudo cat /etc/nginx/sites-available/kgx-storage
```

### JSON Viewer Not Working

Ensure you restarted after updating `web_server.py`:
```bash
sudo systemctl restart kgx-storage-webserver
```

### S3 Access Denied

Verify IAM role is attached to EC2 instance:
```bash
# Check instance metadata for IAM role
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

---

## IAM Permissions

The EC2 instance requires an IAM role with this policy:

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

**Security Notes:**
- Uses IAM role, not access keys (more secure)
- Read-only access to S3
- Presigned URLs expire after 1 hour
- No write permissions needed for web server

---

## Development

To run locally for testing:

```bash
cd /home/ubuntu/translator-ingests
source .venv/bin/activate
cd /home/ubuntu/kgx-storage-webserver
python web_server.py
```

Access at http://localhost:5000

**Warning**: Don't use Flask's development server in production. Always use Gunicorn via systemd.

---

## Production URLs

- **Main site**: https://kgx-storage.rtx.ai
- **Example folder**: https://kgx-storage.rtx.ai/browse/releases/alliance/latest/
- **JSON viewer**: https://kgx-storage.rtx.ai/view/releases/alliance/latest/graph-metadata.json
- **Download**: https://kgx-storage.rtx.ai/download/releases/alliance/latest/alliance.tar.zst

---

## Related Repositories

- **Main Implementation**: https://github.com/NCATSTranslator/translator-ingests/tree/kgx_storage
  - Contains S3 upload logic, EBS cleanup, and pipeline orchestration
  - Run `make upload` to push data to S3
  - See `/src/translator_ingest/util/storage/` for implementation details

---

## Security Considerations

- **HTTPS**: All traffic encrypted via Let's Encrypt SSL
- **IAM Role**: No hardcoded credentials, uses EC2 instance role
- **Presigned URLs**: Temporary S3 download URLs (1-hour expiration)
- **Reverse Proxy**: Flask only listens on localhost (not exposed directly)
- **No Authentication**: Public read-only access to S3 bucket contents
- **No Rate Limiting**: Currently no rate limiting implemented

---

## License

Part of the NCATS Biomedical Data Translator project.
