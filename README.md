# 洛克王国远行商人推送

监控洛克王国远行商人商品上架，有更新立即推送到你的设备。

![Logo](logo.png)

## 支持的推送渠道

| 渠道 | 说明 |
|------|------|
| **Bark** | iOS 推送，支持自定义图标 |
| **飞书** | 飞书机器人 Webhook |
| **Server酱³** | 支持 Server酱 V3（不兼容 Turbo） |

## 工作原理

程序运行在**轮次触发模式**：

```
8:00 ──→ 12:00 ──→ 16:00 ──→ 20:00 ──→ 次日 8:00
  │          │          │          │
检查中...   检查中...   检查中...   检查中...
  ↓          ↓          ↓          ↓
 每2分钟检查一次，有变化立即推送
```

- **非活动时间**（20:00～次日 08:00）：程序休眠，不占用资源
- **轮次开始时**：唤醒并开始检查，每 2 分钟轮询一次
- **检测到变化**：立即推送，然后停止检查，等待下次轮次
- **内容无变化**：继续监控，2 分钟后再次检查

推送判断基于商品列表的 **MD5 内容哈希**，与具体商品无关 —— 远行商人卖什么就推什么，不做白名单过滤。

## 快速部署

### 1. 下载项目

```bash
git clone https://github.com/JayeGT002/rocom-push.git
cd rocom-push
```

### 2. 配置

编辑 `settings.yaml`，填入你的凭证：

```yaml
# ── 基础配置 ──
wegame_api_key: "从 Wegame API 获取"

# ── 渠道开关 ──
bark: true
feishu: false
serverchan: false

# ── Bark ──
bark_key: "你的 Bark Key"
bark_server: "https://api.day.app"         # 默认，无需修改
bark_icon: "https://raw.githubusercontent.com/JayeGT002/rocom-push/main/logo.png"

# ── 飞书 ──
feishu_hook: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# ── Server酱³ ──
# 从 https://sc3.ft07.com/sendkey 获取 UID 和 SendKey
serverchan_uid: "你的 UID"
serverchan_key: "你的 SendKey"
```

### 3. 启动

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

## 配置说明

### Wegame API Key

从 [wegame.shallow.ink](https://wegame.shallow.ink) 获取，填入 `wegame_api_key`。

### Bark

- **Key**：在 Bark App 中获取
- **Server**：默认 `https://api.day.app`，使用第三方服务则填对应地址
- **Icon**：默认使用项目内置 Logo，可自定义替换

### 飞书

1. 在飞书群中添加「自定义机器人」
2. 复制 Webhook URL 填入 `feishu_hook`
3. 将 `feishu` 改为 `true`

### Server酱³

1. 访问 [sc3.ft07.com/sendkey](https://sc3.ft07.com/sendkey)
2. 复制 UID 和 SendKey 分别填入对应字段
3. 将 `serverchan` 改为 `true`

> ⚠️ Server酱³与 Turbo 不兼容，请使用³版本。

## 目录结构

```
rocom-push/
├── settings.yaml       # 配置文件（包含所有凭证）
├── docker-compose.yaml
├── Dockerfile
├── push.py             # 主程序
└── logo.png            # 推送图标
```

## 项目 License

MIT
