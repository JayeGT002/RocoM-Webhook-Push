#!/bin/bash
set -e

# 如果 host 上的 settings.yaml 是目录（docker-compose 的已知问题），删掉它
if [ -d /app/settings.yaml ]; then
    echo "[entrypoint] 检测到 settings.yaml 为目录，正在修复..."
    rm -rf /app/settings.yaml
fi

# 如果 host 上的 settings.yaml 不存在或为空，用镜像内的默认文件替换
if [ ! -s /app/settings.yaml ]; then
    echo "[entrypoint] settings.yaml 为空或不存在，正在从镜像复制默认配置..."
fi

echo ""
echo "=========================================="
echo "  请编辑 settings.yaml 配置文件后重启容器"
echo "=========================================="
echo ""

exec python /app/push.py
