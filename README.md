<div align="center">
<img alt="LOGO" src="./logo.png" width="256" height="256" />

# RocoM-Webhook-Push

洛克王国远行商人 Webhook 推送通知，支持 Bark / 飞书 / Server酱³

本项目基于 [astrbot_plugin_rocom](https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom) 的「远行商人订阅」功能二次修改

</div>

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
- **内容无变化**：继续监控， 2 分钟后再次检查

## 功能特点

- 🚀 **容器化部署**：一条命令即可启动
- 🔔 **多渠道推送**：Bark / 飞书 / Server酱³ 支持同时启用
- 💤 **节能模式**：非活跃时段自动休眠，不占用资源
- 📡 **实时监控**：轮次内每 2 分钟检查一次，有变化立即推送
- 🧪 **启动自检**：容器启动时自动发送测试推送，验证配置是否正确

## 快速部署

### 第一步：创建目录

```bash
mkdir -p /opt/rocom-push && cd /opt/rocom-push
```

### 第二步：下载部署文件

```bash
curl -O https://raw.githubusercontent.com/JayeGT002/RocoM-Webhook-Push/main/docker-compose.yaml
mkdir -p config data
```

### 第三步：配置

编辑 `config/settings.yaml`，填入你的凭证：

```yaml
# WeGmae API配置
wegame_api_key: "从 https://wegame.shallow.ink 获取"
base_url: "https://wegame.shallow.ink"

# 推送渠道开关（true 开启，false 关闭）
bark: true
feishu: false
serverchan: false

# Bark配置
bark_key: "你的 Bark Key"
bark_server: "https://api.day.app"
bark_icon: ""

# 飞书配置
feishu_hook: "你的飞书 Webhook URL"

# Serverchan配置
serverchan_uid: "你的 UID"
serverchan_key: "你的 SendKey"
```

### 第四步：启动

```bash
docker compose up -d
```

查看日志：

```bash
docker compose logs -f
```

---

## 配置说明

### Wegame API Key

从 [wegame.shallow.ink](https://wegame.shallow.ink) 注册获取。

### Bark

- **Key**：在 Bark App 中获取
- **Server**：默认 `https://api.day.app`，使用第三方服务则填对应地址
- **Icon**：推送图标，选填

### 飞书

1. 在飞书群中添加「自定义机器人」
2. 复制 Webhook URL，填入 `feishu_hook`
3. 将 `feishu` 改为 `true`

### Server酱³

1. 访问 [sc3.ft07.com/sendkey](https://sc3.ft07.com/sendkey)
2. 复制 UID 和 SendKey 分别填入对应字段
3. 将 `serverchan` 改为 `true`

> ⚠️ Server酱³与 Turbo 不兼容，请使用³版本。

## 目录结构

```
RocoM-Webhook-Push/
├── config/
│   └── settings.yaml   # 配置文件（挂载到容器内 /app/config/settings.yaml）
├── data/                # 数据目录（推送记录持久化）
├── docker-compose.yaml  # 部署配置
├── Dockerfile           # 镜像构建文件
├── docker-entrypoint.sh # 容器启动脚本
├── push.py             # 主程序
└── logo.png            # 推送图标
```

## 常见问题

**Q: 容器启动后提示"请编辑 settings.yaml 配置文件后重启容器"**

A: 这是正常提示，编辑 `config/settings.yaml` 填入配置后执行 `docker compose restart` 即可。

**Q: 启动测试推送没收到**

A: 检查 `settings.yaml` 中对应渠道的 key 是否正确填写，以及渠道开关（bark/feishu/serverchan）是否为 `true`。

**Q: 国内拉取 GitHub 镜像速度慢**

A: 建议配置 Docker 镜像加速源，或使用代理。

## 特别感谢

- [astrbot_plugin_rocom](https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom)：本项目基于其「远行商人订阅」功能二次修改
- [熵增项目组](https://github.com/Entropy-Increase-Team)：Wegame API Key 支持
- @流绪：GPT image2 logo 支持

## License

本项目遵循 [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html) 协议。
