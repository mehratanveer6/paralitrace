#!/bin/bash
# EC2 launch script for ParaliTrace (Ubuntu 24.04, t3.micro or larger).
# Paste the whole file into "Advanced details -> User data" when launching the instance.
# It installs everything, serves the live app on port 80 and refreshes NASA fires every hour.
# The assistant runs on Amazon Bedrock (Amazon Nova) through the instance's IAM role.
# Progress log on the instance: /var/log/cloud-init-output.log

# ---- optional: paste keys between the quotes ----------------------------------------
GEMINI_API_KEY=""   # fallback for the assistant if Bedrock is unavailable on the account
FIRMS_MAP_KEY=""    # NASA FIRMS key; without it live fires come from NASA's public files
# ----------------------------------------------------------------------------------

set -euxo pipefail
REPO=https://github.com/mehratanveer6/paralitrace.git
APP=/opt/paralitrace
BEDROCK_REGION=us-east-1   # Amazon Nova cross-region inference profiles (us.amazon.nova-*)

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

cat > .env <<EOF
PT_MODEL=bedrock
AWS_REGION=$BEDROCK_REGION
GEMINI_API_KEY=$GEMINI_API_KEY
FIRMS_MAP_KEY=$FIRMS_MAP_KEY
EOF

# Proof tab: the 2025 season backtest that ships with the repo
mkdir -p output
cp frontend/public/demo/backtest.json output/backtest.json

# First forecast: live NASA fires, or demo data if the live sources are unreachable
.venv/bin/python -m paralitrace.pipeline --mode live || .venv/bin/python -m paralitrace.pipeline

cat > /etc/systemd/system/paralitrace.service <<EOF
[Unit]
Description=ParaliTrace web app
After=network-online.target

[Service]
WorkingDirectory=$APP
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
