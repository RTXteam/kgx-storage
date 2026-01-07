# KGX Storage Web Server

Web server for browsing and downloading S3 bucket contents via https://kgx-storage.rtx.ai

This is a standalone deployment component that runs on an EC2 instance. It is separate from the main translator-ingests repository.

## Features

- Browse S3 bucket folders and files with a clean web interface
- Download files directly from S3 via presigned URLs
- **JSON viewer** with syntax highlighting for metadata files
- Folder statistics (size, file count, modification date)
- HTTPS with automatic SSL certificate management
- Responsive design for mobile and desktop

## Architecture

```
User Browser
    ↓ HTTPS (port 443)
Nginx (reverse proxy)
    ↓ HTTP (localhost:5000)
Flask/Gunicorn Web Server
    ↓ AWS SDK
S3 Bucket (translator-ingests)
```

## Requirements

- **EC2 instance** (Ubuntu/Debian)
- **IAM role** attached to EC2 with S3 read access (`s3:GetObject`, `s3:ListBucket`)
- **Domain**: `kgx-storage.rtx.ai` DNS pointing to EC2 public IP
- **Python 3.8+** with pip/uv
- translator-ingests repository installed at `/home/ubuntu/translator-ingests`

## Fresh EC2 Setup (Step-by-Step)

### 1. Prerequisites

Clone the repository:
```bash
cd /home/ubuntu
git clone <repository-url> kgx-storage-webserver
cd kgx-storage-webserver
```

Ensure translator-ingests is installed:
```bash
# Should exist at /home/ubuntu/translator-ingests
ls /home/ubuntu/translator-ingests
```

### 2. Install System Dependencies

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3-pip python3-venv
```

### 3. Install Python Dependencies

```bash
# Navigate to translator-ingests and install in its venv
cd /home/ubuntu/translator-ingests
uv pip install flask gunicorn boto3
```

### 4. Set Up the Web Service

```bash
cd /home/ubuntu/kgx-storage-webserver
sudo ./setup-webserver-service.sh
```

This script will:
- Copy systemd service file to `/etc/systemd/system/`
- Create log directory at `/var/log/kgx-storage/`
- Enable and start the service

Verify it's running:
```bash
sudo systemctl status kgx-storage-webserver
```

### 5. Configure Nginx

Copy the nginx configuration:
```bash
sudo cp nginx-config /etc/nginx/sites-available/kgx-storage
sudo ln -sf /etc/nginx/sites-available/kgx-storage /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

Test and reload nginx:
```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 6. Configure HTTPS with Let's Encrypt

Run Certbot to obtain SSL certificate:
```bash
sudo certbot --nginx -d kgx-storage.rtx.ai
```

You'll be prompted for:
- **Email address** (for renewal notifications)
- **Terms of Service** (accept)
- **Redirect HTTP to HTTPS** (choose option 2: Yes)

Certbot will automatically:
- Obtain a free SSL certificate from Let's Encrypt
- Modify your nginx config to enable HTTPS
- Set up automatic certificate renewal (every 90 days)
- Configure HTTP → HTTPS redirection

Verify auto-renewal works:
```bash
sudo certbot renew --dry-run
```

### 7. Configure EC2 Security Group

In AWS Console → EC2 → Security Groups, add these inbound rules:

| Type  | Protocol | Port | Source    | Description           |
|-------|----------|------|-----------|-----------------------|
| HTTP  | TCP      | 80   | 0.0.0.0/0 | HTTP (redirects to HTTPS) |
| HTTPS | TCP      | 443  | 0.0.0.0/0 | HTTPS traffic         |
| SSH   | TCP      | 22   | Your IP   | SSH access            |

**Note**: Port 80 is required for Let's Encrypt certificate renewal.

### 8. Verify Setup

Your site should now be accessible at:
- **https://kgx-storage.rtx.ai** (primary)
- **http://kgx-storage.rtx.ai** (redirects to HTTPS)

Test JSON viewer by clicking on any `.json` file in the browser.

## File Structure

```
kgx-storage-webserver/
├── web_server.py                      # Flask application
├── kgx-storage-webserver.service      # Systemd service file
├── setup-webserver-service.sh         # Installation script
├── nginx-config                       # Nginx configuration template
├── public/                            # Static assets
│   └── ncats-banner.png               # NCATS Translator banner
└── README.md                          # This file
```

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

# Test renewal process (dry run)
sudo certbot renew --dry-run
```

## Log Files

- **Application access logs**: `/var/log/kgx-storage/access.log`
- **Application error logs**: `/var/log/kgx-storage/error.log`
- **Systemd logs**: `journalctl -u kgx-storage-webserver`
- **Nginx access logs**: `/var/log/nginx/access.log`
- **Nginx error logs**: `/var/log/nginx/error.log`

## Updating the Application

When you make changes to `web_server.py`:

```bash
# Pull latest changes
cd /home/ubuntu/kgx-storage-webserver
git pull

# Restart the service
sudo systemctl restart kgx-storage-webserver

# Check if it's running
sudo systemctl status kgx-storage-webserver
```

No nginx restart needed unless you change nginx configuration.

## Troubleshooting

### Service won't start

```bash
# Check detailed logs
sudo journalctl -u kgx-storage-webserver -n 50

# Check if port 5000 is available
sudo ss -tulpn | grep 5000

# Verify Python dependencies
cd /home/ubuntu/translator-ingests
source .venv/bin/activate
python -c "import flask, boto3, gunicorn"
```

### 502 Bad Gateway

Usually means Flask app isn't running:
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

# Check SSL configuration
sudo cat /etc/nginx/sites-available/kgx-storage
```

### Can't access JSON viewer

Ensure you restarted the service after updating `web_server.py`:
```bash
sudo systemctl restart kgx-storage-webserver
```

## IAM Permissions

The EC2 instance needs an IAM role with this policy:

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

## Development

To run locally for testing:

```bash
cd /home/ubuntu/translator-ingests
source .venv/bin/activate
cd /home/ubuntu/kgx-storage-webserver
python web_server.py
```

Access at http://localhost:5000

**Note**: Don't use Flask's development server in production. Always use Gunicorn via systemd.

## Security Considerations

- **S3 Access**: Uses IAM role, not access keys
- **HTTPS**: All traffic encrypted via Let's Encrypt SSL
- **Presigned URLs**: Temporary S3 URLs with 1-hour expiration
- **No Authentication**: Public read-only access to S3 bucket contents
- **Reverse Proxy**: Flask app only listens on localhost

## Production URLs

- **Main site**: https://kgx-storage.rtx.ai
- **Example JSON viewer**: https://kgx-storage.rtx.ai/view/[path-to-json-file]
- **Example download**: https://kgx-storage.rtx.ai/download/[path-to-file]

## License

Part of the NCATS Biomedical Data Translator project.
