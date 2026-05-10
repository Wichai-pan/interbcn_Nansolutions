#!/usr/bin/env bash
# 用法:
#   ./deploy.sh          — rsync 本地文件 + 重启服务
#   ./deploy.sh pull     — 服务器 git pull + 重启服务

set -e
SERVER="frankfurt"
REMOTE="/root/heakathon/Interbcn"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "pull" ]; then
  echo "▶ Pulling from GitHub..."
  ssh $SERVER "cd $REMOTE && git pull origin main"
else
  echo "▶ Syncing local files to ${SERVER}:${REMOTE}..."
  rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv' \
    --exclude 'web_design_proto' \
    --exclude '.DS_Store' \
    --exclude 'deploy.sh' \
    "${LOCAL}/" \
    "${SERVER}:${REMOTE}/"
fi

echo "▶ Restarting service..."
ssh $SERVER "systemctl restart inibsa && sleep 2 && systemctl is-active inibsa"

echo "▶ Health check..."
ssh $SERVER "curl -s http://localhost:8788/api/health"

echo ""
echo "✓ Done. Dashboard: http://$(ssh $SERVER 'curl -s ifconfig.me'):8788"
