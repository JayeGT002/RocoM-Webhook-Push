# rocom-push

洛克王国远行商人推送工具。

## 功能

- 每分钟检查 WeGame API 获取当前上架商品
- 轮次切换时自动推送 Bark 通知
- 支持持久化推送记录，重启不重复推

## 目录结构

```
rocom-push/
├── push.py              # 主程序
├── config.yaml          # 公开配置（检查间隔等）
├── credentials.key      # 敏感凭证（Bark Key / WeGame API Key）
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## 部署

```bash
docker compose up -d --build
```

## 配置

编辑 `credentials.key`：

```yaml
bark_server: https://bark.momolab.cc
bark_key: 你的BarkKey
bark_icon: https://d1.aag.moe/public/2026/04/27/91e1e7cbf665f0a4.png
wegame_api_key: 你的WeGame API Key
```
