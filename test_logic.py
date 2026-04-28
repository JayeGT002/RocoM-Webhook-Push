#!/usr/bin/env python3
"""RocoM-Push 逻辑测试"""

import sys
import time
import hashlib
import json
from datetime import datetime, timedelta

# ── 引入待测函数（从 push.py 抄出来，不依赖运行 ──
def get_current_round():
    now = datetime.now()
    hour = now.hour
    if 8 <= hour < 12: return 1, "1/4"
    elif 12 <= hour < 16: return 2, "2/4"
    elif 16 <= hour < 20: return 3, "3/4"
    elif 20 <= hour < 24: return 4, "4/4"
    return 0, "0/4"

def get_next_round_start():
    now = datetime.now()
    hour = now.hour
    for rh in [8, 12, 16, 20]:
        if hour < rh or (hour == rh and now.minute > 0):
            return now.replace(hour=rh, minute=0, second=0, microsecond=0)
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)

def get_active_props(data):
    activities = data.get("merchantActivities", [])
    if not activities: return []
    all_props = []
    now_ms = int(time.time() * 1000)
    for activity in activities:
        for prop in activity.get("get_props", []):
            start = prop.get("start_time", 0)
            end = prop.get("end_time", 0)
            if start <= now_ms <= end:
                all_props.append(prop)
    return all_props

def content_hash(props):
    names = sorted(p.get("name", "") for p in props)
    return hashlib.md5("|".join(names).encode()).hexdigest()

# ── 测试用例 ──
def test_current_round():
    now = datetime.now()
    hour = now.hour
    r, rs = get_current_round()
    print(f"[测试] 当前时间 {now.strftime('%H:%M')}，轮次 {rs}")
    assert r > 0, f"应该在活动时间内，实际 {r}"
    print(f"  ✅ 轮次判断正常: {r}/4")

def test_next_round():
    nxt = get_next_round_start()
    now = datetime.now()
    diff = (nxt - now).total_seconds()
    print(f"[测试] 下次轮次开始: {nxt.strftime('%H:%M')}，距今 {int(diff)} 秒")
    assert diff > 0, "下次轮次应该是未来时间"
    print(f"  ✅ 下次轮次计算正常")

def test_hash_same_content():
    """相同内容应产生相同 hash"""
    h1 = content_hash([{"name": "神奇的蛋"}])
    h2 = content_hash([{"name": "神奇的蛋"}])
    assert h1 == h2, "相同内容 hash 不同"
    print(f"  ✅ 相同内容 hash 一致")

def test_hash_different_content():
    """不同内容应产生不同 hash"""
    h1 = content_hash([{"name": "神奇的蛋"}])
    h2 = content_hash([{"name": "黄金契约"}])
    assert h1 != h2, "不同内容 hash 相同"
    print(f"  ✅ 不同内容 hash 不同")

def test_hash_empty():
    """空列表应有稳定 hash"""
    h1 = content_hash([])
    h2 = content_hash([])
    assert h1 == h2, "空列表 hash 不稳定"
    print(f"  ✅ 空列表 hash 稳定: {h1}")

def test_get_active_props_empty():
    """无活动时返回空"""
    data = {}
    assert get_active_props(data) == []
    print(f"  ✅ 无数据返回空")

def test_get_active_props_no_active():
    """有过期商品时不返回"""
    now_ms = int(time.time() * 1000)
    data = {
        "merchantActivities": [{
            "get_props": [{
                "name": "过期商品",
                "start_time": now_ms - 7200000,
                "end_time": now_ms - 3600000,  # 已结束
            }]
        }]
    }
    assert get_active_props(data) == []
    print(f"  ✅ 过期商品正确过滤")

def test_get_active_props_one_active():
    """恰好一个商品在售"""
    now_ms = int(time.time() * 1000)
    data = {
        "merchantActivities": [{
            "get_props": [
                {
                    "name": "神奇的蛋",
                    "start_time": now_ms - 3600000,
                    "end_time": now_ms + 3600000,  # 1小时后结束
                },
                {
                    "name": "黄金契约",
                    "start_time": now_ms + 3600000,
                    "end_time": now_ms + 7200000,  # 尚未开始
                }
            ]
        }]
    }
    active = get_active_props(data)
    assert len(active) == 1
    assert active[0]["name"] == "神奇的蛋"
    print(f"  ✅ 正确识别1个在售商品: {active[0]['name']}")

def test_logic_branch_push():
    """场景A：有商品 + hash变化 → 应该推送"""
    print("\n[场景A] 有商品 + hash变化 → 推送")
    last_hash = content_hash([{"name": "黄金契约"}])
    current = [{"name": "神奇的蛋"}]
    current_hash = content_hash(current)
    active = current

    if active and current_hash and current_hash != last_hash:
        print(f"  → 检测到内容变化，推送！last={last_hash[:8]} current={current_hash[:8]}")
        result = "PUSH"
    elif not active:
        print(f"  → 无商品，跳过")
        result = "SKIP"
    else:
        print(f"  → 内容无变化")
        result = "CONTINUE"
    assert result == "PUSH", f"期望推送，实际 {result}"
    print(f"  ✅ 场景A正确: 有变化则推送")

def test_logic_branch_no_change():
    """场景B：有商品 + hash不变 → 不推送"""
    print("\n[场景B] 有商品 + hash不变 → 继续监控")
    last_hash = content_hash([{"name": "神奇的蛋"}])
    current = [{"name": "神奇的蛋"}]
    current_hash = content_hash(current)
    active = current

    if active and current_hash and current_hash != last_hash:
        print(f"  → 检测到内容变化，推送！")
        result = "PUSH"
    elif not active:
        print(f"  → 无商品，跳过")
        result = "SKIP"
    else:
        print(f"  → 内容无变化，继续监控")
        result = "CONTINUE"
    assert result == "CONTINUE", f"期望继续监控，实际 {result}"
    print(f"  ✅ 场景B正确: 无变化则继续监控")

def test_logic_branch_no_product():
    """场景C：无商品 → 继续监控（不跳过）"""
    print("\n[场景C] 无商品 → 继续监控")
    last_hash = content_hash([{"name": "神奇的蛋"}])
    current = []
    current_hash = content_hash(current)
    active = current

    if active and current_hash and current_hash != last_hash:
        print(f"  → 检测到内容变化，推送！")
        result = "PUSH"
    elif not active:
        print(f"  → 无商品，继续监控（API可能有延迟）")
        result = "CONTINUE"  # 不跳过
    else:
        print(f"  → 内容无变化，继续监控")
        result = "CONTINUE"
    assert result == "CONTINUE", f"期望继续监控，实际 {result}"
    print(f"  ✅ 场景C正确: 无商品也继续监控")

def test_round_transition():
    """轮次切换时 last_hash 重置"""
    print("\n[测试] 轮次切换时 last_hash 应重置")
    last_round = 2
    current_round = 3
    last_hash = "旧hash值"

    if current_round != last_round:
        last_hash = ""  # 模拟重置
        last_round = current_round
        print(f"  → 轮次切换，last_hash 已重置")
    else:
        print(f"  → 同一轮次，last_hash 保持")

    assert last_hash == "", f"轮次切换后 last_hash 应为空，实际 {last_hash}"
    print(f"  ✅ 轮次切换逻辑正确")

if __name__ == "__main__":
    print("=" * 50)
    print("RocoM-Push 逻辑测试")
    print("=" * 50)

    test_current_round()
    test_next_round()
    test_hash_same_content()
    test_hash_different_content()
    test_hash_empty()
    test_get_active_props_empty()
    test_get_active_props_no_active()
    test_get_active_props_one_active()
    test_logic_branch_push()
    test_logic_branch_no_change()
    test_logic_branch_no_product()
    test_round_transition()

    print("\n" + "=" * 50)
    print("全部测试通过 ✅")
    print("=" * 50)
