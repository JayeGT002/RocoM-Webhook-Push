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
def load_settings(path: str = "settings.yaml") -> dict:
    """加载 settings.yaml（渠道总开关 + 各渠道配置）"""
    if Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_key_file(path: str = "credentials.key") -> dict:
    """加载 credentials.key 作为补充配置"""
    if Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def merge_config() -> dict:
    """
    配置合并优先级（高 → 低）：
    环境变量 > credentials.key > settings.yaml 默认值
    """
    # 1. 加载 settings.yaml
    settings_path = Path(__file__).parent / "settings.yaml"
    settings = load_settings(settings_path)

    # 2. credentials.key
    key_path = Path(__file__).parent / "credentials.key"
    key_cfg = load_key_file(key_path)

    # 3. 环境变量（来自 .wegame.env，通过 docker-compose env_file 注入）
    def env(key: str, fallback="") -> str:
        return os.environ.get(key, key_cfg.get(key.lower(), fallback))

    def env_bool(key: str, fallback: bool = False) -> bool:
        val = os.environ.get(key, str(key_cfg.get(key.lower(), fallback)))
        return val.lower() in ("true", "1", "yes")

    # ── 渠道开关 ──
    cfg = {
        "bark_enabled": env_bool("BARK_ENABLED", settings.get("bark", True)),
        "feishu_enabled": env_bool("FEISHU_ENABLED", settings.get("feishu", False)),
        "serverchan_enabled": env_bool("SERVERCHAN_ENABLED", settings.get("serverchan", False)),
    }

    # ── 基础配置 ──
    cfg["wegame_api_key"] = env("WEGAME_API_KEY", "")
    cfg["base_url"] = os.environ.get("BASE_URL") or key_cfg.get("base_url", "https://wegame.shallow.ink")
    cfg["record_file"] = os.environ.get("RECORD_FILE") or key_cfg.get("record_file", "/data/last_push.json")

    # ── Bark ──
    bark_cfg = settings.get("bark", {})
    cfg["bark_key"] = env("BARK_KEY", "")
    cfg["bark_server"] = env("BARK_SERVER", bark_cfg.get("server", "https://bark.momolab.cc"))
    cfg["bark_icon"] = env("BARK_ICON", bark_cfg.get("icon", "https://d1.aag.moe/public/2026/04/27/91e1e7cbf665f0a4.png"))

    # ── 飞书 ──
    cfg["feishu_hook"] = env("FEISHU_HOOK", "")

    # ── Server酱 ──
    cfg["serverchan_key"] = env("SERVERCHAN_KEY", "")

    return cfg


# ─── API 请求 ───
def fetch_merchant_info(api_key: str, base_url: str) -> dict | None:
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


# ─── 推送 ───
def send_bark(cfg: dict, title: str, body: str):
    if not cfg["bark_enabled"] or not cfg["bark_key"] or "你的" in cfg["bark_key"]:
        return
    url = f"{cfg['bark_server'].rstrip('/')}/{cfg['bark_key']}"
    params = urllib.parse.urlencode({
        "title": title,
        "body": body,
        "icon": cfg["bark_icon"],
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


def send_feishu(cfg: dict, message: str):
    if not cfg["feishu_enabled"]:
        return
    url = cfg["feishu_hook"]
    if not url or "你的" in url:
        return
    payload = {"msg_type": "text", "content": {"text": message}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("飞书推送成功")
            else:
                log.warning(f"飞书推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"飞书请求异常: {e}")


def send_serverchan(cfg: dict, title: str, desp: str):
    if not cfg["serverchan_enabled"]:
        return
    key = cfg["serverchan_key"]
    if not key or "你的" in key:
        return
    url = f"https://sctapi.ftqq.com/{key}.send"
    params = urllib.parse.urlencode({"title": title, "desp": desp})
    try:
        req = urllib.request.Request(f"{url}?{params}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("Server酱推送成功")
            else:
                log.warning(f"Server酱推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"Server酱请求异常: {e}")


def send_notifications(props: list[dict], round_str: str, check_time: str, cfg: dict):
    names = [p["name"] for p in props]
    body_lines = [
        f"轮次：{round_str}",
        f"商品：{'、'.join(names)}",
        f"检测时间：{check_time}",
    ]
    body = "\n".join(body_lines)
    title = "你远哥来咯！"

    send_bark(cfg, title, body)
    send_feishu(cfg, f"🏪 远行商人上新！\n{body}")
    send_serverchan(cfg, title, body)


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
    now = datetime.now()
    hour = now.hour
    for rh in [8, 12, 16, 20]:
        if hour < rh or (hour == rh and now.minute > 0):
            return now.replace(hour=rh, minute=0, second=0, microsecond=0)
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)


def get_active_props(data: dict) -> list[dict]:
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


def content_hash(props: list[dict]) -> str:
    names = sorted(p.get("name", "") for p in props)
    return hashlib.md5("|".join(names).encode()).hexdigest()


# ─── 主循环 ───
def main():
    cfg = merge_config()

    log.info("启动 rocom-push（轮次触发模式）")
    log.info(f"渠道开关: bark={cfg['bark_enabled']} feishu={cfg['feishu_enabled']} serverchan={cfg['serverchan_enabled']}")
    log.info(f"等待下次轮次开始（8/12/16/20点）...")

    if not cfg["wegame_api_key"]:
        log.error("WEGAME_API_KEY 未配置，请检查 .wegame.env 或 credentials.key")
        return

    record_file = cfg["record_file"]
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

    while not shutdown:
        now = datetime.now()
        current_round, round_str = get_current_round()
        check_time = now.strftime("%Y-%m-%d %H:%M:%S")

        if current_round == 0:
            next_start = get_next_round_start()
            sleep_seconds = (next_start - now).total_seconds()
            log.info(f"当前非活动时间，下次轮次 {next_start.strftime('%H:%M')}，休眠 {int(sleep_seconds)} 秒")
            time.sleep(max(sleep_seconds, 0))
            continue

        if current_round != last_round:
            log.info(f"=== 轮次 {round_str} 开始 ===")
            last_hash = ""
            last_round = current_round

        log.info(f"[{check_time}] 轮次 {round_str} 检测中...")

        data = fetch_merchant_info(cfg["wegame_api_key"], cfg["base_url"])

        if data:
            active = get_active_props(data)
            current_hash = content_hash(active)
            log.info(f"当前上架商品数: {len(active)}")
            for p in active:
                log.info(f"  - {p.get('name')} (截止 {datetime.fromtimestamp(p.get('end_time',0)/1000).strftime('%H:%M')})")

            if current_hash and current_hash != last_hash:
                log.info("检测到内容变化，推送！")
                send_notifications(active, round_str, check_time, cfg)
                last_hash = current_hash
                record["last_round"] = current_round
                record["last_hash"] = current_hash
                record["last_push"] = check_time
                save_record(record_file, record)
                log.info("推送完成，停止检查，等待下次轮次")
            else:
                log.info("内容无变化，继续监控")
        else:
            log.warning("获取数据失败")

        time.sleep(120)


if __name__ == "__main__":
    main()
