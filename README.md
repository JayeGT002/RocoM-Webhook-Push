<div align="center">
<img alt="LOGO" src="./logo.png" width="256" height="256" />

# RocoM-Webhook-Push

洛克王国远行商人 Webhook 推送通知，支持 Bark / 飞书 / Server酱³ / 企业微信

本项目基于 [astrbot_plugin_rocom](https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom) 的「远行商人订阅」功能二次修改

</div>

## ⚠️项目API变更通知

由于商人推送服务RocoM-Webhook-Push使用的上游接口开始收费，即日起本项目不再提供免费APIkey，您需要前往「洛克魔法书」（https://rocom.shallow.ink） 申请自用APIkey。

注意：使用「洛克魔法书」的APIkey服务需要收费，此费用与本项目无关，与「洛克魔法书」API相关的问题请咨询「洛克魔法书」官方。

本项目将在近期推送更新以便通知更多用户，如果有足够多的用户有需要，我们也将考虑更多替代方案。

## 工作原理

- **非活动时间**（20:00～次日 08:00）：程序休眠，不占用资源
- **轮次开始时**：唤醒并开始检查，每 1 分钟轮询一次
- **检测到变化**：立即推送，推送后休眠至下一轮次
- **内容无变化**：继续监控，1 分钟后再次检查

## 功能特点

- 🚀 **容器化部署**：一条命令即可启动
- 🔔 **多渠道推送**：Bark / 飞书 / 企业微信 / Server酱³ 支持同时启用
- 💤 **节能模式**：非活跃时段自动休眠，不占用资源
- 🎯 **限时商品识别**：智能区分全天商品与限时商品，仅推送限时变化
- 🔁 **推送去重**：基于商品 ID 去重，同轮次内相同商品不会重复推送
- 🛡️ **异常告警**：API 连续失败时主动推送错误通知
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

请前往「洛克魔法书」（https://rocom.shallow.ink） 申请自用APIkey。

### Bark

- **Key**：在 Bark App 中获取
- **Server**：默认 `https://api.day.app`，使用第三方服务则填对应地址
- **Icon**：推送图标，选填

### 飞书

1. 在飞书群中添加「自定义机器人」
2. 复制 Webhook URL，填入 `feishu_hook`
3. 将 `feishu` 改为 `true`

### 企业微信

1. 在企业微信群中添加「群机器人」
2. 复制 Webhook URL，填入 `wecom_hook`
3. 将 `wecom` 改为 `true`

### Server酱³

1. 访问 [sc3.ft07.com/sendkey](https://sc3.ft07.com/sendkey)
2. 复制 UID 和 SendKey 分别填入对应字段
3. 将 `serverchan` 改为 `true`

> ⚠️ 仅支持 Server酱³ ，不支持 Server酱Tubro ，请前往 https://sc3.ft07.com 获取 UID 和 Sendkey

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

A: 检查 `settings.yaml` 中对应渠道的 key 是否正确填写，以及渠道开关（bark/feishu/serverchan/wecom）是否为 `true`。

## 更新日志
### v0.3.0（2026-05-22）
- ⚡️ 轮询间隔从 2 分钟缩短至 1 分钟，推送更及时
- 🎯 新增限时商品智能识别，区分全天商品与限时商品
- 🔁 新增推送去重，基于商品 ID 避免同轮次重复推送
- 🛡️ 新增异常告警，API 连续失败时主动推送错误通知
- 🐛 修复：跨轮次残留商品不再触发误报
- 🔧 优化休眠逻辑，减少无效轮询

### v0.2.1（2026-04-28）
- 🛠️ 触发 Actions 重新构建镜像


### v0.2.0（2026-04-28）
- 🐛 修复：无商品时不推送空消息
- ✅ 飞书支持签名校验（`feishu_signing_secret` 字段）
- ✨ 新增企业微信 webhook 推送渠道
- 🛠️ 推送逻辑优化：启动后自动发送测试推送
- 📦 配置文件改为 `config/settings.yaml` 目录挂载
- 🚀 优化 entrypoint：自动生成配置模板

### v0.1.0（2026-04-27）
- 🎉 初始版本，支持 Bark / 飞书 / Server酱³ 三渠道

## 特别感谢

- [astrbot_plugin_rocom](https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom)：本项目基于其「远行商人订阅」功能二次修改
- [熵增项目组](https://github.com/Entropy-Increase-Team)：Wegame API Key 支持
- @流绪：GPT image2 logo 支持

## License

本项目遵循 [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html) 协议。
