#!/bin/bash
set -e

CONFIG_DIR="/app/config"
SETTINGS_FILE="${CONFIG_DIR}/settings.yaml"

mkdir -p "${CONFIG_DIR}"

if [ ! -s "${SETTINGS_FILE}" ]; then
    echo "[entrypoint] settings.yaml 不存在，正在生成模板..."
    cat > "${SETTINGS_FILE}" << 'TEMPLATE'
# WeGmae API Key配置
# 若API Key失效请提交issues或自行寻找可用WeGmae API Key
wegame_api_key: "sk-ba042e079cf9ccb30e72b3d5af458f45"
base_url: "https://wegame.shallow.ink"

# 推送渠道开关（true 开启，false 关闭）
bark: true
feishu: false
serverchan: false
wecom: false

# Bark配置
bark_key: "enter_your_bark_key"
bark_server: "https://api.day.app"
bark_icon: "https://ghproxy.net/https://raw.githubusercontent.com/JayeGT002/RocoM-Webhook-Push/main/logo.png"

# 飞书配置
feishu_hook: "enter_your_feishu_hook"
# 飞书签名密钥（可选，启用签名校验后填入）
feishu_signing_secret: ""

# Serverchan配置
serverchan_uid: "enter_your_serverchan_uid"
serverchan_key: "enter_your_serverchan_key"

# 企业微信配置
wecom_hook: "enter_your_wecom_hook"
TEMPLATE
    echo "[entrypoint] 模板已生成，请编辑 ${SETTINGS_FILE} 后重启容器"
else
    echo "[entrypoint] settings.yaml 已存在，跳过生成"
fi

if grep -q "enter_your" "${SETTINGS_FILE}" 2>/dev/null || grep -q "placeholder" "${SETTINGS_FILE}" 2>/dev/null; then
    echo ""
    echo "=========================================="
    echo "  请编辑 settings.yaml 配置文件后重启容器"
    echo "=========================================="
    echo ""
fi

exec python /app/push.py
