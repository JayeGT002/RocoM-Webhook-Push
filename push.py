# RocoM-Webhook-Push - 洛克王国远行商人推送服务
# Copyright (C) 2026 JayeGT002
#
# 本程序部分代码基于 astrbot_plugin_rocom (https://github.com/Entropy-Increase-Team/astrbot_plugin_rocom)
#  Copyright (C) 2026 熵增项目组 / bvzrays
#  遵循 GNU Affero General Public License v3.0
#
# 本程序遵循 AGPL-3.0 协议，完整许可证见 LICENSE 文件。

"""
洛克王国远行商人推送程序
轮次触发模式：整点唤醒 → 每1分钟检查一次 → 限时新商品立即推送 → 推送后继续检查直至本轮次结束
"""

import hashlib
import hmac
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
def load_settings(path: str = "config/settings.yaml") -> dict:
    """加载 settings.yaml（渠道总开关 + 各渠道配置 + 所有凭证）"""
    if not Path(path).exists():
        log.warning("settings.yaml 不存在，跳过渠道配置加载")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
            if raw is None or all(not v for v in raw.values() if not isinstance(v, dict)):
                log.warning("settings.yaml 为空，请配置 settings.yaml！")
                return {}
            return raw
    except Exception as e:
        log.warning(f"settings.yaml 加载异常: {e}")
        return {}


def merge_config() -> dict:
    """
    配置全部来自 settings.yaml（含基础配置、渠道开关、各渠道凭证）
    """
    settings_path = Path(__file__).parent / "config" / "settings.yaml"
    settings = load_settings(settings_path)

    # ── 基础配置 ──
    cfg = {
        "wegame_api_key": settings.get("wegame_api_key", ""),
        "base_url": settings.get("base_url", "https://wegame.shallow.ink"),
        "record_file": "/data/last_push.json",
    }

    # ── 渠道开关 ──
    cfg["bark_enabled"] = settings.get("bark", True)
    cfg["feishu_enabled"] = settings.get("feishu", False)
    cfg["serverchan_enabled"] = settings.get("serverchan", False)

    # ── Bark ──
    cfg["bark_key"] = settings.get("bark_key", "")
    cfg["bark_server"] = settings.get("bark_server", "https://bark.momolab.cc")
    cfg["bark_icon"] = settings.get("bark_icon", "https://raw.githubusercontent.com/JayeGT002/rocom-push/main/logo.png")

    # ── 飞书 ──
    cfg["feishu_hook"] = settings.get("feishu_hook", "")
    cfg["feishu_signing_secret"] = settings.get("feishu_signing_secret", "")

    # ── Server酱 ──
    cfg["serverchan_key"] = settings.get("serverchan_key", "")
    cfg["serverchan_uid"] = settings.get("serverchan_uid", "")

    # ── 企业微信 ──
    cfg["wecom_enabled"] = settings.get("wecom", False)
    cfg["wecom_hook"] = settings.get("wecom_hook", "")

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

    timestamp = str(int(time.time()))
    headers = {"Content-Type": "application/json"}

    # 签名校验（可选）
    secret = cfg.get("feishu_signing_secret", "")
    if secret:
        sign_str = f"{timestamp}\n{secret}"
        signature = hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
        headers["X-Lark-Signature"] = signature
        headers["X-Lark-Request-Timestamp"] = timestamp

    payload = {"msg_type": "text", "content": {"text": message}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("飞书推送成功")
            else:
                log.warning(f"飞书推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"飞书请求异常: {e}")


def send_wecom(cfg: dict, message: str):
    if not cfg.get("wecom_enabled"):
        return
    url = cfg.get("wecom_hook", "")
    if not url or "你的" in url or "enter" in url:
        return
    payload = {"msgtype": "text", "text": {"content": message}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.info("企业微信推送成功")
            else:
                log.warning(f"企业微信推送失败: {resp.status}")
    except Exception as e:
        log.warning(f"企业微信请求异常: {e}")


def send_serverchan(cfg: dict, title: str, desp: str):
    if not cfg.get("serverchan_enabled"):
        return
    uid = cfg.get("serverchan_uid", "")
    sendkey = cfg.get("serverchan_key", "")
    if not uid or not sendkey or "placeholder" in (uid + sendkey):
        return
    # Server酱 V3
    url = f"https://{uid}.push.ft07.com/send/{sendkey}.send"
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
    send_wecom(cfg, f"🏪 远行商人上新！\n{body}")
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
        if hour < rh:
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


def get_prop_ids(props: list[dict]) -> set[int]:
    """提取商品唯一标识集合，用于判断商品列表是否变化。"""
    ids = set()
    for p in props:
        # 优先使用 id，其次用 name + start_time 组合做唯一标识
        pid = p.get("id")
        if pid is not None:
            ids.add(pid)
        else:
            # 回退：用 name 和 start_time 拼接
            name = p.get("name", "")
            start = p.get("start_time", 0)
            ids.add(hash((name, start)))
    return ids


def is_limited_time_prop(prop: dict) -> bool:
    """
    判断商品是否为「限时商品」。
    全天商品：从当天 0 点左右开始上架，到 23:59 左右结束，开始时间早于 8:00。
    限时商品：从轮次开始时间（8:00/12:00/16:00/20:00）上架。
    """
    end_time_ms = prop.get("end_time", 0)
    start_time_ms = prop.get("start_time", 0)
    if end_time_ms <= 0 or start_time_ms <= 0:
        return False
    end_dt = datetime.fromtimestamp(end_time_ms / 1000)
    start_dt = datetime.fromtimestamp(start_time_ms / 1000)
    # 全天商品：开始时间早于 8:00，且结束时间在 23:xx（允许分钟偏差）
    if start_dt.hour < 8 and end_dt.hour == 23 and end_dt.minute >= 50:
        return False
    return True


def is_current_round_prop(prop: dict, round_start: datetime) -> bool:
    """判断商品是否是在当前轮次内开始上架的（用于区分跨轮次残留的全天商品）。"""
    start_time_ms = prop.get("start_time", 0)
    if start_time_ms <= 0:
        return False
    start_dt = datetime.fromtimestamp(start_time_ms / 1000)
    # 允许 5 分钟偏差，兼容 API 延迟
    return start_dt >= (round_start - timedelta(minutes=5))


def has_limited_time_props(props: list[dict]) -> bool:
    """判断商品列表中是否存在限时商品。"""
    return any(is_limited_time_prop(p) for p in props)


# ─── 主循环 ───
def main():
    cfg = merge_config()

    log.info("启动 rocom-push（轮次触发模式）")
    log.info(f"渠道开关: bark={cfg['bark_enabled']} feishu={cfg['feishu_enabled']} serverchan={cfg['serverchan_enabled']}")

    # 启动时发送测试推送
    if cfg["bark_enabled"] and cfg["bark_key"] and "你的" not in cfg["bark_key"]:
        send_bark(cfg, "你远哥来咯", "启动成功，通知功能正常")
        log.info("[启动测试] Bark 测试推送已发送")
    elif cfg["feishu_enabled"] and cfg["feishu_hook"]:
        send_feishu(cfg, "✅ 启动成功，通知功能正常")
        log.info("[启动测试] 飞书测试推送已发送")
    elif cfg["serverchan_enabled"] and cfg["serverchan_key"] and "placeholder" not in cfg["serverchan_key"]:
        send_serverchan(cfg, "你远哥来咯", "启动成功，通知功能正常")
        log.info("[启动测试] Server酱测试推送已发送")
    elif cfg.get("wecom_enabled") and cfg.get("wecom_hook") and "enter" not in cfg.get("wecom_hook", ""):
        send_wecom(cfg, "✅ 启动成功，通知功能正常")
        log.info("[启动测试] 企业微信测试推送已发送")
    else:
        log.info("未启用任何推送渠道，跳过启动测试")

    log.info(f"等待下次轮次开始（8/12/16/20点）...")

    if not cfg["wegame_api_key"]:
        log.error("WEGAME_API_KEY 未配置，请检查 .wegame.env 或 credentials.key")
        return

    record_file = cfg["record_file"]
    record = load_record(record_file)
    last_round = record.get("last_round", 0)
    last_pushed_prop_ids = set(record.get("last_pushed_prop_ids", []))

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
            last_round = current_round
            record["last_round"] = last_round
            # 轮次切换时清空已推送商品记录，确保新轮次能正常检测
            last_pushed_prop_ids = set()
            record["last_pushed_prop_ids"] = []
            save_record(record_file, record)

        log.info(f"[{check_time}] 轮次 {round_str} 检测中...")

        data = fetch_merchant_info(cfg["wegame_api_key"], cfg["base_url"])

        if data:
            active = get_active_props(data)
            log.info(f"当前上架商品数: {len(active)}")
            for p in active:
                log.info(f"  - {p.get('name')} (截止 {datetime.fromtimestamp(p.get('end_time',0)/1000).strftime('%H:%M')})")

            # 分离限时商品与全天商品
            limited_props = [p for p in active if is_limited_time_prop(p)]
            all_day_props = [p for p in active if not is_limited_time_prop(p)]

            # 获取当前轮次开始时间，用于过滤跨轮次残留商品
            round_start = now.replace(hour=(current_round - 1) * 4 + 8, minute=0, second=0, microsecond=0)
            # 只关注「当前轮次才开始上架」的限时商品
            fresh_limited = [p for p in limited_props if is_current_round_prop(p, round_start)]

            if all_day_props and not fresh_limited:
                names = [p.get('name') for p in all_day_props]
                log.info(f"当前仅有全天商品（{'、'.join(names)}），本轮次限时商品尚未刷新，1分钟后再次检测")
                time.sleep(60)
                continue

            if fresh_limited:
                current_fresh_ids = get_prop_ids(fresh_limited)
                new_ids = current_fresh_ids - last_pushed_prop_ids

                if new_ids:
                    log.info(f"检测到本轮次限时新商品（{len(new_ids)} 个），推送！")
                    send_notifications(fresh_limited, round_str, check_time, cfg)
                    last_pushed_prop_ids = current_fresh_ids
                    record["last_pushed_round"] = current_round
                    record["last_pushed_time"] = check_time
                    record["last_pushed_prop_ids"] = list(current_fresh_ids)
                    save_record(record_file, record)
                    log.info("推送完成，本轮结束，休眠至下一轮")
                    time.sleep(max((get_next_round_start() - datetime.now()).total_seconds(), 60))
                    continue
                else:
                    log.info("本轮次限时商品列表与上次推送一致，无新商品，1分钟后再次检测")
            else:
                log.info("当前无上架商品，1分钟后再次检测")

            time.sleep(60)
        else:
            log.warning("获取数据失败，1分钟后重试")
            time.sleep(60)


if __name__ == "__main__":
    main()
