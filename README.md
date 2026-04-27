<div align="center">
<img alt="LOGO" src="./logo.png" width="256" height="256" />

# RocoM-Webhook-Push
远行商人Webhook推送通知，支持Bark/飞书/Server酱³<br/>
本项目基于[astrbot_plugin_rocom](https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom)的「远行商人订阅」功能二次修改
</div>

## 工作原理

程序运行在**轮次触发模式**：
- **非活动时间**（20:00～次日 08:00）：程序休眠，不占用资源
- **轮次开始时**：唤醒并开始检查，每 2 分钟轮询一次
- **检测到变化**：立即推送，然后停止检查，等待下次轮次
- **内容无变化**：继续监控， 2 分钟后再次检查

## 快速部署

### Docker Compose（一键部署，推荐）

```bash
mkdir -p /opt/rocom-push && cd /opt/rocom-push
# 下载 docker-compose.yaml
curl -O https://raw.githubusercontent.com/JayeGT002/RocoM-Webhook-Push/main/docker-compose.yaml
# 下载配置文件
curl -O https://raw.githubusercontent.com/JayeGT002/RocoM-Webhook-Push/main/settings.yaml
# 启动
docker compose up -d
```

### 手动部署

#### 1. 克隆项目

```bash
git clone https://github.com/JayeGT002/RocoM-Webhook-Push.git
cd RocoM-Webhook-Push
```

#### 2. 配置

编辑 `settings.yaml`，填入你的凭证：

```yaml
# 推送配置

# WeGmae API配置
wegame_api_key: "从 https://wegame.shallow.ink 获取"
base_url: "https://wegame.shallow.ink"

# 推送渠道开关（true 开启，false 关闭，默认启用bark通道，如非必要请修改。）
bark: true
feishu: false
serverchan: false

# Bark配置
bark_key: "你的 Bark Key"
bark_server: "https://api.day.app"
bark_icon: "https://raw.githubusercontent.com/JayeGT002/RocoM-Webhook-Push/main/logo.png"

# 飞书配置
feishu_hook: "你的飞书 Webhook URL"

# Serverchan配置
# 不兼容Server酱Tubro，请从Server酱³官网 https://sc3.ft07.com 获取相关配置。
serverchan_uid: "你的 UID"
serverchan_key: "你的 SendKey"
```

#### 3. 启动

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

## 配置说明

### Wegame API Key

从 [wegame.shallow.ink](https://wegame.shallow.ink) 注册获取。

### Bark

- **Key**：在 Bark App 中获取
- **Server**：默认 `https://api.day.app`，使用第三方服务则填对应地址
- **Icon**：默认使用项目内置 Logo，可自定义替换

### 飞书

1. 在飞书群中添加「自定义机器人」
2. 复制 Webhook URL，填入 `feishu_hook`
3. 将 `feishu` 改为 `true`

### Server酱³

1. 访问 [sc3.ft07.com/sendkey](https://sc3.ft07.com/sendkey)
2. 复制 UID 和 SendKey 分别填入对应字段
3. 将 `serverchan` 改为 `true`

> ⚠️ 本项目未支持 Server酱Turbo ，请使用 Server酱³ 。

## 目录结构

```
RocoM-Webhook-Push/
├── settings.yaml       # 配置文件（包含所有凭证）
├── docker-compose.yaml
├── Dockerfile
├── push.py             # 主程序
└── logo.png            # 推送图标
```

## 特别感谢

- 本项目基于 [astrbot_plugin_rocom](https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom) 插件的「远行商人订阅」功能二次修改
- 感谢 [熵增项目组](https://github.com/Entropy-Increase-Team) 的 Wegame API Key 支持
- 感谢 @流绪 提供的 GPT image2 logo 支持

## License

本项目遵循 [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html) 协议。
