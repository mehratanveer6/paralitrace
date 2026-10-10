#!/bin/bash
# EC2 launch script for ParaliTrace (Ubuntu 24.04, t3.micro or larger).
# Paste into "Advanced details -> User data" when launching the instance.
# It installs everything, serves the app on port 80 and refreshes live data every hour.
# Progress log on the instance: /var/log/cloud-init-output.log
set -euxo pipefail

REPO=https://github.com/mehratanveer6/paralitrace.git
APP=/opt/paralitrace
REGION=us-east-1          # where Bedrock runs; must match the region where you enabled model access

# 1 GB of swap so the frontend build fits on a 1 GB instance
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

apt-get update
apt-get install -y python3-venv python3-pip git curl
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

git clone "$REPO" "$APP"
cd "$APP"
python3 -m venv .venv
.venv/bin/pip install --no-cache-dir -r requirements.txt
(cd frontend && npm ci && npm run build)

# First forecast: live data, or demo data if the live sources are unreachable
.venv/bin/python -m paralitrace.pipeline --mode live || .venv/bin/python -m paralitrace.pipeline

cat > /etc/systemd/system/paralitrace.service <<EOF
[Unit]
Description=ParaliTrace web app
After=network-online.target

[Service]
WorkingDirectory=$APP
Environment=PT_MODEL=bedrock
Environment=AWS_REGION=$REGION
ExecStart=$APP/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 80
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now paralitrace

# Fresh fires and winds every hour, at quarter past
echo "15 * * * * root cd $APP && .venv/bin/python -m paralitrace.pipeline --mode live >> /var/log/paralitrace-pipeline.log 2>&1" \
  > /etc/cron.d/paralitrace
