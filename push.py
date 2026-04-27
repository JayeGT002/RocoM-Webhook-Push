"""
洛克王国远行商人推送程序
持续运行，检测到订阅商品上货立即推送
"""

import asyncio
import hashlib
import json
import logging
import signal
import time
from datetime import datetime
from pathlib import Path

import aiohttp
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
    """加载凭证文件，支持 YAML 格式"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(path: str = "config.yaml", key_path: str = "credentials.key") -> dict:
    """加载主配置，凭证从 key 文件分离读取"""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    key_cfg = load_key_file(key_path)

    cfg["wegame_api_key"] = key_cfg.get("wegame_api_key", "")

    webhook_cfg = cfg.get("webhook", {})

    bark_cfg = webhook_cfg.get("bark", {})
    bark_cfg["enabled"] = key_cfg.get("bark_enabled", False)
    bark_cfg["key"] = key_cfg.get("bark_key", "")
    bark_cfg["server"] = key_cfg.get("bark_server", "https://bark.momolab.cc")

    feishu_cfg = webhook_cfg.get("feishu", {})
    feishu_cfg["url"] = key_cfg.get("feishu_hook", "")

    dingtalk_cfg = webhook_cfg.get("dingtalk", {})
    dingtalk_cfg["url"] = (
        f"https://oapi.dingtalk.com/robot/send?access_token={key_cfg.get('dingtalk_token', '')}"
        if key_cfg.get("dingtalk_token")
        else ""
    )
    dingtalk_cfg["secret"] = key_cfg.get("dingtalk_secret", "")

    discord_cfg = webhook_cfg.get("discord", {})
    discord_cfg["url"] = key_cfg.get("discord_hook", "")

    cfg["webhook"] = webhook_cfg
    cfg["bark_icon"] = key_cfg.get(
        "bark_icon",
        "https://d1.aag.moe/public/2026/04/27/63123bb80e86669b.png",
    )
    return cfg


# ─── API 请求 ───
async def fetch_merchant_info(
    session: aiohttp.ClientSession,
    api_key: str,
    base_url: str,
) -> dict | None:
    headers = {"X-API-Key": api_key}
    url = f"{base_url}/api/v1/games/rocom/merchant/info"

    try:
        async with session.get(
            url, headers=headers, params={"refresh": "true"}, timeout=15
        ) as resp:
            if resp.status != 200:
                log.warning(f"API 返回状态码 {resp.status}")
                return None
            data = await resp.json()
            if data.get("code") != 0:
                log.warning(f"API 错误: {data.get('message')}")
                return None
            return data.get("data", {})
    except asyncio.TimeoutError:
        log.warning("API 请求超时")
        return None
    except Exception as e:
        log.error(f"API 请求异常: {e}")
        return None


# ─── 钉钉签名 ───
def dingtalk_sign(secret: str, timestamp: str) -> str:
    import hmac
    import base64
    import urllib.parse

    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return sign


# ─── 推送 ───
async def send_bark(
    bark_key: str,
    server: str,
    title: str,
    body: str,
    icon: str,
    session: aiohttp.ClientSession,
):
    """Bark 推送"""
    if not bark_key or "你的" in bark_key:
        return

    url = f"{server.rstrip('/')}/{bark_key}"
    params = {
        "title": title,
        "body": body,
        "icon": icon,
        "sound": "new-mail",
    }

    try:
        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status == 200:
                log.info("Bark 推送成功")
            else:
                text = await resp.text()
                log.warning(f"Bark 推送失败: {resp.status} {text}")
    except Exception as e:
        log.warning(f"Bark 请求异常: {e}")


async def send_feishu(url: str, message: str, session: aiohttp.ClientSession):
    payload = {"msg_type": "text", "content": {"text": message}}
    async with session.post(url, json=payload, timeout=10) as resp:
        if resp.status == 200:
            log.info("飞书推送成功")
        else:
            text = await resp.text()
            log.warning(f"飞书推送失败: {resp.status} {text}")


async def send_dingtalk(
    url: str, message: str, secret: str, session: aiohttp.ClientSession
):
    timestamp = str(round(time.time() * 1000))
    sign = dingtalk_sign(secret, timestamp) if secret else ""
    full_url = f"{url}&timestamp={timestamp}&sign={sign}" if secret else url
    payload = {"msgtype": "text", "text": {"content": message}}
    async with session.post(full_url, json=payload, timeout=10) as resp:
        if resp.status == 200:
            log.info("钉钉推送成功")
        else:
            text = await resp.text()
            log.warning(f"钉钉推送失败: {resp.status} {text}")


async def send_discord(url: str, message: dict, session: aiohttp.ClientSession):
    async with session.post(url, json=message, timeout=10) as resp:
        if resp.status == 204:
            log.info("Discord推送成功")
        else:
            text = await resp.text()
            log.warning(f"Discord推送失败: {resp.status} {text}")


async def send_notifications(
    props: list[dict],
    round_str: str,
    check_time: str,
    cfg: dict,
    session: aiohttp.ClientSession,
):
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

        await send_bark(
            bark_key,
            bark_server,
            title="你远哥来咯！",
            body="\n".join(body_lines),
            icon=bark_icon,
            session=session,
        )

    # ── 飞书 ──
    if wh.get("feishu", {}).get("enabled"):
        url = wh["feishu"]["url"]
        if url and "你的" not in url:
            message = f"🏪 远行商人上新！\n轮次：{round_str}\n检测时间：{check_time}\n商品列表：\n" + "\n".join(
                f"  - {p['name']}" for p in props
            )
            await send_feishu(url, message, session)

    # ── 钉钉 ──
    if wh.get("dingtalk", {}).get("enabled"):
        url = wh["dingtalk"]["url"]
        secret = wh.get("dingtalk", {}).get("secret", "")
        if url and "你的" not in url:
            message = f"🏪 远行商人上新！\n轮次：{round_str}\n检测时间：{check_time}\n商品列表：\n" + "\n".join(
                f"  - {p['name']}" for p in props
            )
            await send_dingtalk(url, message, secret, session)

    # ── Discord ──
    if wh.get("discord", {}).get("enabled"):
        url = wh["discord"]["url"]
        if url and "xxx" not in url:
            discord_msg = {
                "embed": {
                    "title": "🏪 远行商人上新！",
                    "color": 0xFF6B00,
                    "fields": [
                        {"name": "轮次", "value": round_str, "inline": True},
                        {"name": "检测时间", "value": check_time, "inline": True},
                        {
                            "name": "商品列表",
                            "value": "\n".join(f"- {p['name']}" for p in props),
                        },
                    ],
                    "footer": {"text": "wegame.shallow.ink"},
                }
            }
            await send_discord(url, discord_msg, session)


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


# ─── 主循环 ───
async def main():
    config_path = Path(__file__).parent / "config.yaml"
    key_path = Path(__file__).parent / "credentials.key"
    cfg = load_config(config_path, key_path)

    log.info("启动 rocom-push")
    log.info(f"订阅商品: {cfg.get('subscription_items', [])}")
    log.info(f"检查间隔: {cfg.get('check_interval', 300)}秒")

    api_key = cfg["wegame_api_key"]
    base_url = cfg["base_url"]
    interval = cfg.get("check_interval", 300)
    record_file = cfg.get("record_file", "/data/last_push.json")

    record = load_record(record_file)
    last_round = record.get("last_round", 0)

    shutdown_event = asyncio.Event()

    def on_signal(signum, frame):
        log.info("收到退出信号，正在关闭...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    async with aiohttp.ClientSession() as session:
        while not shutdown_event.is_set():
            check_time = time.strftime("%Y-%m-%d %H:%M:%S")
            current_round, round_str = get_current_round()
            log.info(f"[{check_time}] 检查远行商人（轮次 {round_str}）...")

            data = await fetch_merchant_info(session, api_key, base_url)

            if data:
                current_round, round_str = get_current_round()
                active = get_active_props(data)
                log.info(f"当前轮次: {round_str}，上架商品数: {len(active)}")
                for p in active:
                    log.info(f"  - {p.get('name')} (截止 {datetime.fromtimestamp(p.get('end_time',0)/1000).strftime('%H:%M')})")

                if current_round > 0 and current_round != last_round:
                    log.info(f"轮次变化 ({last_round} → {current_round})，开始推送！")
                    if active:
                        await send_notifications(active, round_str, check_time, cfg, session)
                    else:
                        log.info("本轮无上架商品，跳过推送")
                    record["last_round"] = current_round
                    record["last_push"] = check_time
                    save_record(record_file, record)
                    last_round = current_round
                else:
                    log.info("轮次无变化")
            else:
                log.warning("获取数据失败，跳过本次")

            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=interval,
                )
                break
            except asyncio.TimeoutError:
                continue


if __name__ == "__main__":
    asyncio.run(main())
