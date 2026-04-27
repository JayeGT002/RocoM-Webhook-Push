#!/bin/bash
set -e

# 确保 settings.yaml 存在且为文件（不是目录）
if [ -d /app/settings.yaml ]; then
    echo "[entrypoint] settings.yaml is a directory, removing and recreating as file"
    rm -rf /app/settings.yaml
    touch /app/settings.yaml
elif [ ! -f /app/settings.yaml ]; then
    echo "[entrypoint] settings.yaml not found, creating default"
    touch /app/settings.yaml
fi

exec python /app/push.py
