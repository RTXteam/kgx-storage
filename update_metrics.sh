#!/bin/bash
# Update KGX Storage metrics and reload web server workers
# Run hourly via cron to keep folder statistics fresh

cd /home/ubuntu/kgx-storage-webserver

# Compute new metrics
/home/ubuntu/kgx-storage-webserver/.venv/bin/python compute_metrics.py >> /var/log/kgx-storage/metrics.log 2>&1

# Reload gunicorn workers gracefully (HUP signal)
pkill -HUP -f "gunicorn.*web_server:app" 2>&1 | logger -t kgx-metrics

echo "[$(date)] Metrics updated and workers reloaded" >> /var/log/kgx-storage/metrics.log
