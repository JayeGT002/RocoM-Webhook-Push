#!/bin/bash
set -e

# /app/config 目录（挂载的宿主配置目录）
CONFIG_DIR="/app/config"
SETTINGS_FILE="${CONFIG_DIR}/settings.yaml"

mkdir -p "${CONFIG_DIR}"

# 如果 settings.yaml 不存在或为空，生成模板
if [ ! -s "${SETTINGS_FILE}" ]; then
    echo "[entrypoint] settings.yaml 不存在，正在生成模板..."
    cat > "${SETTINGS_FILE}" << 'TEMPLATE'
# WeGmae API配置
wegame_api_key: ""
base_url: "https://wegame.shallow.ink"

# 推送渠道开关（true 开启，false 关闭）
bark: true
feishu: false
serverchan: false

# Bark配置
bark_key: ""
bark_server: "https://api.day.app"
bark_icon: ""

# 飞书配置
feishu_hook: ""

# Serverchan配置
serverchan_uid: ""
serverchan_key: ""
TEMPLATE
    echo "[entrypoint] 模板已生成，请编辑 ${SETTINGS_FILE} 后重启容器"
else
    echo "[entrypoint] settings.yaml 已存在，跳过生成"
fi

echo ""
echo "=========================================="
echo "  请编辑 settings.yaml 配置文件后重启容器"
echo "=========================================="
echo ""

exec python /app/push.py
