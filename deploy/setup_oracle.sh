#!/usr/bin/env bash
# deploy/setup_oracle.sh — Oracle Cloud ARM (Ubuntu 22.04) setup script
# Run once on a fresh VM: bash setup_oracle.sh

set -euo pipefail
echo "=== YouTube Automation — Oracle ARM Setup ==="

# ── System packages ────────────────────────────────────────────────────────────
sudo apt-get update -qq
sudo apt-get install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    ffmpeg imagemagick \
    espeak-ng espeak-ng-data \
    nginx certbot python3-certbot-nginx \
    git curl unzip build-essential

echo "✓ System packages installed"

# ── App directory ──────────────────────────────────────────────────────────────
APP_DIR="/opt/youtube-automation"
sudo mkdir -p "$APP_DIR"
sudo chown "$USER:$USER" "$APP_DIR"

# ── Python virtual environment ─────────────────────────────────────────────────
python3.11 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip wheel
pip install -r requirements.txt

echo "✓ Python environment ready"

# ── App directories ────────────────────────────────────────────────────────────
mkdir -p "$APP_DIR"/{output,cache,music,data,logs}
echo "✓ App directories created"

# ── Systemd service: FastAPI ───────────────────────────────────────────────────
sudo tee /etc/systemd/system/yt-api.service > /dev/null <<EOF
[Unit]
Description=YouTube Automation FastAPI
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/logs/api.log
StandardError=append:$APP_DIR/logs/api.log

[Install]
WantedBy=multi-user.target
EOF

# ── Systemd service: Streamlit UI ─────────────────────────────────────────────
sudo tee /etc/systemd/system/yt-ui.service > /dev/null <<EOF
[Unit]
Description=YouTube Automation Streamlit UI
After=network.target yt-api.service

[Service]
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/logs/ui.log
StandardError=append:$APP_DIR/logs/ui.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable yt-api yt-ui
echo "✓ Systemd services registered"

# ── Nginx config (copy and enable) ────────────────────────────────────────────
sudo cp deploy/nginx.conf /etc/nginx/sites-available/yt-automation
sudo ln -sf /etc/nginx/sites-available/yt-automation /etc/nginx/sites-enabled/yt-automation
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo ""
echo "==================================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy your .env file:  cp .env.example $APP_DIR/.env && nano $APP_DIR/.env"
echo "  2. Set up SSL:           sudo certbot --nginx -d yourdomain.com"
echo "  3. Start services:       sudo systemctl start yt-api yt-ui"
echo "  4. OAuth YouTube:        $APP_DIR/venv/bin/python -c 'from app.pipeline.uploader import _get_credentials; _get_credentials()'"
echo "==================================================="
