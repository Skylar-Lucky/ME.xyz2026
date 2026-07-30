#!/usr/bin/env bash
# 一键部署脚本（Docker 版）——在服务器上运行
#
# 用法：
#   bash deploy/docker-deploy.sh
#
# 作用：拉最新代码 -> 用新代码重新构建镜像 -> 平滑重启容器 -> 健康检查
# 数据库在 docker volume 里，不受重建容器影响。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "==> 拉取最新代码"
git pull

echo "==> 用新代码重新构建并启动容器"
docker compose up -d --build

echo "==> 等待服务启动"
sleep 2

echo "==> 健康检查"
if curl -sf http://127.0.0.1:8010/health > /dev/null; then
  echo "✅ 部署成功"
else
  echo "❌ 健康检查失败，运行 'docker compose logs --tail=50' 查看原因"
  exit 1
fi
