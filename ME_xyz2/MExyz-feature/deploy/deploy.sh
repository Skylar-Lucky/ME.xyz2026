#!/usr/bin/env bash
# ME.xyz 部署脚本 —— 在服务器上以 root/sudo 运行
#
# 前置条件：/opt/mexyz/MExyz-feature 目录已经存在（用 rsync 或 git clone 把代码放过去，
# 见 deploy/README 里的说明），本脚本只负责"从代码到能跑起来"的部分。
#
# 用法：
#   sudo bash deploy.sh                  # 只用 IP 访问，不配域名/HTTPS
#   sudo bash deploy.sh your-domain.com  # 配上域名（仍是 HTTP，HTTPS 见脚本最后打印的 certbot 命令）

set -euo pipefail

APP_ROOT="/opt/mexyz/MExyz-feature"
BACKEND_DIR="$APP_ROOT/backend"
VENV_DIR="/opt/mexyz/.venv"
SERVICE_NAME="mexyz"
DOMAIN="${1:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 或 root 运行本脚本" >&2
  exit 1
fi

if [ ! -d "$BACKEND_DIR" ]; then
  echo "没找到 $BACKEND_DIR，请先把代码同步到服务器（rsync/git clone），再跑本脚本。" >&2
  exit 1
fi

echo "==> 安装系统依赖 (python3-venv, nginx, certbot ...)"
apt-get update -y
apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx

echo "==> 创建运行账号 mexyz（无登录权限，仅用来跑服务，降低风险）"
id -u mexyz >/dev/null 2>&1 || useradd --system --home /opt/mexyz --shell /usr/sbin/nologin mexyz

echo "==> 创建虚拟环境并安装依赖"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

echo "==> 检查 backend/.env"
if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "    已从 .env.example 生成 .env —— 部署完成后请立刻手动编辑："
  echo "    sudo nano $BACKEND_DIR/.env"
  echo "    至少要填 GLM_API_KEY 和 JWT_SECRET，否则 AI 对话和登录都用不了。"
else
  echo "    .env 已存在，跳过生成（不会覆盖你已有的密钥配置）"
fi

echo "==> 准备数据目录并交给 mexyz 用户"
mkdir -p "$BACKEND_DIR/data"
chown -R mexyz:mexyz /opt/mexyz
chmod 600 "$BACKEND_DIR/.env"

echo "==> 安装 systemd 服务"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sed "s#/opt/mexyz/MExyz-feature/.venv#$VENV_DIR#" "$SCRIPT_DIR/mexyz.service" > /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "==> 配置 nginx 反向代理"
SERVER_NAME="${DOMAIN:-_}"
sed "s/__SERVER_NAME__/$SERVER_NAME/" "$SCRIPT_DIR/nginx.conf.template" > /etc/nginx/sites-available/${SERVICE_NAME}
ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/${SERVICE_NAME}
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> 放行防火墙端口（仅在 ufw 已启用时才动它，避免误把自己锁在外面）"
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 'Nginx Full'
else
  echo "    ufw 未启用，跳过 —— 阿里云轻量应用服务器请去控制台的『防火墙』里放行 80、443 端口"
fi

echo ""
echo "======================================================"
echo "部署完成。"
echo "1) 用 IP 直接访问：http://<服务器公网IP>/"
echo "2) systemd 服务状态：systemctl status $SERVICE_NAME"
echo "3) 后端日志：journalctl -u $SERVICE_NAME -f"
if [ -n "$DOMAIN" ]; then
  echo "4) 域名已配置到 nginx（HTTP）。要开 HTTPS，DNS 解析生效后执行："
  echo "   sudo certbot --nginx -d $DOMAIN"
fi
echo "======================================================"
