"""
洛克王国远行商人推送程序
轮次触发模式：整点唤醒 → 每2分钟检查一次 → 有变化立即推送 → 推送完停止检查直至下次轮次
"""

import hashlib
import json
import logging
import os
import signal
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import yaml

# ─── 日志 ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rocom-push")


# ─── 配置加载 ───
def load_key_file(path: str = "credentials.key") -> dict:
    """加载凭证文件，支持 YAML 格式。文件不存在时尝试环境变量。"""
    if Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # 兜底：从环境变量读取
    return {
        "wegame_api_key": os.environ.get("WEGAME_API_KEY", ""),
        "bark_enabled": os.environ.get("BARK_ENABLED", "false").lower() == "true",
        "bark_key": os.environ.get("BARK_KEY", ""),
        "bark_server": os.environ.get("BARK_SERVER", "https://bark.momolab.cc"),
        "bark_icon": os.environ.get("BARK_ICON", ""),
        "feishu_hook": os.environ.get("FEISHU_HOOK", ""),
    }


def load_config(path: str = "config.yaml", key_path: str = "credentials.key") -> dict:
    """加载主配置，凭证从 key 文件或环境变量读取"""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    key_cfg = load_key_file(key_path)

    # 凭证注入：环境变量 > credentials.key
    cfg["wegame_api_key"] = os.environ.get("WEGAME_API_KEY") or key_cfg.get("wegame_api_key", "")

    webhook_cfg = cfg.setdefault("webhook", {})

    bark_cfg = webhook_cfg.setdefault("bark", {})
    bark_cfg["enabled"] = os.environ.get("BARK_ENABLED", "").lower() == "true" or key_cfg.get("bark_enabled", False)
    bark_cfg["key"] = os.environ.get("BARK_KEY") or key_cfg.get("bark_key", "")
    bark_cfg["server"] = os.environ.get("BARK_SERVER") or key_cfg.get("bark_server", "https://bark.momolab.cc")

    feishu_cfg = webhook_cfg.setdefault("feishu", {})
    feishu_cfg["url"] = os.environ.get("FEISHU_HOOK") or key_cfg.get("feishu_hook", "")

    dingtalk_cfg = webhook_cfg.setdefault("dingtalk", {})
    dingtalk_cfg["url"] = (
        f"https://oapi.dingtalk.com/robot/send?access_token="
        f"{os.environ.get('DINGTALK_TOKEN') or key_cfg.get('dingtalk_token', '')}"
    )
    dingtalk_cfg["secret"] = os.environ.get("DINGTALK_SECRET") or key_cfg.get("dingtalk_secret", "")

    discord_cfg = webhook_cfg.setdefault("discord", {})
    discord_cfg["url"] = os.environ.get("DISCORD_HOOK") or key_cfg.get("discord_hook", "")

    cfg["bark_icon"] = os.environ.get("BARK_ICON") or key_cfg.get(
        "bark_icon", "https://d1.aag.moe/public/2026/04/27/91e1e7cbf665f0a4.png"
    )
    return cfg


# ─── API 请求 ───
def fetch_merchant_info(api_key: str, base_url: str) -> dict | None:
    """使用 urllib 同步请求"""
    headers = {"X-API-Key": api_key}
    url = f"{base_url}/api/v1/games/rocom/merchant/info?refresh=true"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                log.warning(f"API 返回状态码 {resp.status}")
                return None
            data = json.loads(resp.read())
            if data.get("code") != 0:
                log.warning(f"API 错误: {data.get('message')}")
                return None
            return data.get("data", {})
    except urllib.error.HTTPError as e:
        log.warning(f"API HTTP 错误: {e.code}")
        return None
    except Exception as e:
        log.error(f"API 请求异常: {e}")
        return None


# ─── 钉钉签名 ───
def dingtalk_sign(secret: str, timestamp: str) -> str:
    import hmac
    import base64

    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return sign


# ─── 推送 ───
def send_bark(bark_key: str, server: str, title: str, body: str, icon: str):
    """Bark 推送（urllib 版本）"""
    if not bark_key or "你的" in bark_key:
        return

    url = f"{server.rstrip('/')}/{bark_key}"
    params = urllib.parse.urlencode({
        "title": title,
        "body": body,
        "icon": icon,
        "sound": "new-mail",
    })

    try:
        req = urllib.request.Request(f"{url}?{params}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("Bark 推送成功")
            else:
                log.warning(f"Bark 推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"Bark 请求异常: {e}")


def send_feishu(url: str, message: str):
    """飞书推送"""
    if not url or "你的" in url:
        return
    payload = {"msg_type": "text", "content": {"text": message}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("飞书推送成功")
            else:
                log.warning(f"飞书推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"飞书请求异常: {e}")


def send_dingtalk(url: str, message: str, secret: str):
    """钉钉推送"""
    if not url or "你的" in url:
        return
    timestamp = str(round(time.time() * 1000))
    sign = dingtalk_sign(secret, timestamp) if secret else ""
    full_url = f"{url}&timestamp={timestamp}&sign={sign}" if secret else url
    payload = {"msgtype": "text", "text": {"content": message}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        full_url, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("钉钉推送成功")
            else:
                log.warning(f"钉钉推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"钉钉请求异常: {e}")


def send_discord(url: str, message: dict):
    """Discord 推送"""
    if not url or "你的" in url:
        return
    data = json.dumps(message).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 204:
                log.info("Discord 推送成功")
            else:
                log.warning(f"Discord 推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"Discord 请求异常: {e}")


def send_notifications(props: list[dict], round_str: str, check_time: str, cfg: dict):
    wh = cfg.get("webhook", {})

    # ── Bark ──
    bark = wh.get("bark", {})
    if bark.get("enabled"):
        bark_key = bark.get("key", "")
        bark_server = bark.get("server", "https://bark.momolab.cc")
        bark_icon = cfg.get("bark_icon", "")

        names = [p["name"] for p in props]
        body_lines = [
            f"轮次：{round_str}",
            f"商品：{'、'.join(names)}",
        ]

        send_bark(
            bark_key,
            bark_server,
            title="你远哥来咯！",
            body="\n".join(body_lines),
            icon=bark_icon,
        )

    # ── 飞书 ──
    feishu_url = wh.get("feishu", {}).get("url", "")
    if feishu_url and "你的" not in feishu_url:
        message = f"🏪 远行商人上新！\n轮次：{round_str}\n检测时间：{check_time}\n商品：{'、'.join(p['name'] for p in props)}"
        send_feishu(feishu_url, message)

    # ── 钉钉 ──
    dingtalk_url = wh.get("dingtalk", {}).get("url", "")
    dingtalk_secret = wh.get("dingtalk", {}).get("secret", "")
    if dingtalk_url and "你的" not in dingtalk_url:
        message = f"🏪 远行商人上新！\n轮次：{round_str}\n检测时间：{check_time}\n商品：{'、'.join(p['name'] for p in props)}"
        send_dingtalk(dingtalk_url, message, dingtalk_secret)

    # ── Discord ──
    discord_url = wh.get("discord", {}).get("url", "")
    if discord_url and "你的" not in discord_url:
        discord_msg = {
            "content": f"**🏪 远行商人上新！**\n> 轮次：{round_str}\n> 检测时间：{check_time}\n> 商品：{'、'.join(p['name'] for p in props)}"
        }
        send_discord(discord_url, discord_msg)


# ─── 持久化 ───
def load_record(path: str) -> dict:
    if Path(path).exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_record(path: str, record: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


# ─── 数据解析 ───
def get_current_round() -> tuple[int, str]:
    """返回 (当前轮次 1-4, 轮次描述字符串)"""
    now = datetime.now()
    hour = now.hour
    if 8 <= hour < 12:
        return 1, "1/4"
    elif 12 <= hour < 16:
        return 2, "2/4"
    elif 16 <= hour < 20:
        return 3, "3/4"
    elif 20 <= hour < 24:
        return 4, "4/4"
    return 0, "0/4"


def get_next_round_start() -> datetime:
    """计算距今最近的下次轮次开始时间"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    second = now.second

    round_hours = [8, 12, 16, 20]
    for rh in round_hours:
        if hour < rh or (hour == rh and (minute > 0 or second > 0)):
            # 今天还有这个轮次
            target = now.replace(hour=rh, minute=0, second=0, microsecond=0)
            return target

    # 今天所有轮次已过，等明天8点
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)


def get_active_props(data: dict) -> list[dict]:
    """从 merchantActivities 中提取当前时间段内上架的全部商品"""
    activities = data.get("merchantActivities", [])
    if not activities:
        return []

    all_props = []
    now_ms = int(time.time() * 1000)

    for activity in activities:
        for prop in activity.get("get_props", []):
            start = prop.get("start_time", 0)
            end = prop.get("end_time", 0)
            if start <= now_ms <= end:
                all_props.append(prop)

    return all_props


def content_hash(data: dict, props: list[dict]) -> str:
    """计算商品内容的简易哈希，用于判断内容是否变化"""
    names = sorted(p.get("name", "") for p in props)
    return hashlib.md5("|".join(names).encode()).hexdigest()


# ─── 主循环 ───
def main():
    config_path = Path(__file__).parent / "config.yaml"
    key_path = Path(__file__).parent / "credentials.key"
    cfg = load_config(config_path, key_path)

    log.info("启动 rocom-push（轮次触发模式）")
    log.info(f"轮次检查间隔: 每2分钟")

    api_key = cfg["wegame_api_key"]
    base_url = cfg["base_url"]
    record_file = cfg.get("record_file", "/data/last_push.json")

    record = load_record(record_file)
    last_round = record.get("last_round", 0)
    last_hash = record.get("last_hash", "")

    shutdown = False

    def on_signal(signum, frame):
        nonlocal shutdown
        log.info("收到退出信号，正在关闭...")
        shutdown = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    log.info("等待下次轮次开始（8/12/16/20点）...")

    while not shutdown:
        now = datetime.now()
        current_round, round_str = get_current_round()
        check_time = now.strftime("%Y-%m-%d %H:%M:%S")

        if current_round == 0:
            # 非活动时段：休眠到下次轮次
            next_start = get_next_round_start()
            sleep_seconds = (next_start - now).total_seconds()
            log.info(f"当前非活动时间，下次轮次 {next_start.strftime('%H:%M')}，休眠 {int(sleep_seconds)} 秒")
            time.sleep(max(sleep_seconds, 0))
            continue

        # 轮次进行中
        if current_round != last_round:
            # 刚进入新轮次，清空上次状态，重新开始检测
            log.info(f"=== 轮次 {round_str} 开始 ===")
            last_hash = ""
            last_round = current_round

        log.info(f"[{check_time}] 轮次 {round_str} 检测中...")

        data = fetch_merchant_info(api_key, base_url)

        if data:
            active = get_active_props(data)
            current_hash = content_hash(data, active)
            log.info(f"当前上架商品数: {len(active)}")
            for p in active:
                log.info(f"  - {p.get('name')} (截止 {datetime.fromtimestamp(p.get('end_time',0)/1000).strftime('%H:%M')})")

            if current_hash and current_hash != last_hash:
                log.info(f"检测到内容变化，推送！")
                send_notifications(active, round_str, check_time, cfg)
                last_hash = current_hash
                # 推送完毕，记录并停止检查，等待下次轮次
                record["last_round"] = current_round
                record["last_hash"] = current_hash
                record["last_push"] = check_time
                save_record(record_file, record)
                log.info("推送完成，停止检查，等待下次轮次")
            else:
                log.info("内容无变化，继续监控")
        else:
            log.warning("获取数据失败")

        # 每2分钟检查一次
        time.sleep(120)


if __name__ == "__main__":
    main()
