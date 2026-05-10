#!/usr/bin/env python3
"""多轮独立模拟测试：验证推送逻辑每个环节"""
import sys, time, json, hashlib, threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request

def is_port(p):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', p)) == 0

# ── 模拟API服务器 ──
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        from urllib.parse import urlparse
        if '/api/v1/games/rocom/merchant/info' in self.path:
            data, status = self.server.h.next()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404); self.end_headers()

class MockAPI:
    def __init__(self, port=18989):
        self.port = port
        self.scenes = []
        self.pos = 0
        self._serv = None
        self._thread = None

    def set_scenes(self, scenes):
        self.scenes = scenes
        self.pos = 0

    def next(self):
        if self.pos < len(self.scenes):
            s = self.scenes[self.pos]
            self.pos += 1
            return s["data"], s["status"]
        return {"merchantActivities": []}, 200

    def start(self):
        if is_port(self.port): return False
        self._serv = HTTPServer(('localhost', self.port), H)
        self._serv.h = self
        self._thread = threading.Thread(target=self._serv.serve_forever, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if self._serv:
            self._serv.shutdown()
            self._thread.join(timeout=2)

# ── 核心逻辑（从 push.py 复制）──
def get_active_props(data):
    acts = data.get("merchantActivities", [])
    if not acts: return []
    now = int(time.time() * 1000)
    out = []
    for a in acts:
        for p in a.get("get_props", []):
            if p.get("start_time", 0) <= now <= p.get("end_time", 0):
                out.append(p)
    return out

def c_hash(props):
    return hashlib.md5("|".join(sorted(p.get("name","") for p in props)).encode()).hexdigest()

def get_round():
    h = datetime.now().hour
    if 8<=h<12: return 1,"1/4"
    elif 12<=h<16: return 2,"2/4"
    elif 16<=h<20: return 3,"3/4"
    elif 20<=h<24: return 4,"4/4"
    return 0,"0/4"

# ── 模拟一次检测，返回行为标签 ──
_state = {"last_hash": "", "last_round": 0, "pushed": 0}

def run_once(base_url, key):
    global _state
    now = datetime.now()
    r, rs = get_round()
    ct = now.strftime("%H:%M:%S")

    if r != _state["last_round"]:
        _state["last_hash"] = ""
        _state["last_round"] = r

    print(f"  [{ct}] 轮次 {rs} 检测中...")

    try:
        url = f"{base_url}/api/v1/games/rocom/merchant/info?refresh=true"
        req = urllib.request.Request(url, headers={"Authorization": key})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  获取数据失败: {e}")
        return "FAIL"

    active = get_active_props(data)
    cur = c_hash(active)
    print(f"  当前上架商品数: {len(active)}")
    for p in active:
        print(f"    - {p['name']} (截止 {datetime.fromtimestamp(p['end_time']/1000).strftime('%H:%M')})")

    if active and cur and cur != _state["last_hash"]:
        print("  检测到内容变化，推送！")
        _state["last_hash"] = cur
        _state["pushed"] += 1
        print("  推送完成，本轮结束，休眠至下一轮")
        return "PUSH"
    elif not active:
        print("  当前无上架商品，继续监控（API可能有延迟），2分钟后再次检测")
        return "RETRY"
    else:
        print("  内容无变化，本轮结束，休眠至下一轮")
        return "CONTINUE"

# ── 构建场景（8次检测的预期序列）──
def build_scenes():
    now = int(time.time() * 1000)
    H = 3600000
    return [
        # #1：无商品
        {"data": {"merchantActivities": []}, "status": 200},
        # #2：有过期商品（应被过滤）
        {"data": {"merchantActivities": [{"get_props": [
            {"name": "黄金契约", "start_time": now-3*H, "end_time": now-2*H}
        ]}]}, "status": 200},
        # #3：首次有有效商品 → PUSH
        {"data": {"merchantActivities": [{"get_props": [
            {"name": "神奇的蛋", "start_time": now-1*H, "end_time": now+3*H}
        ]}]}, "status": 200},
        # #4：同一商品 → CONTINUE
        {"data": {"merchantActivities": [{"get_props": [
            {"name": "神奇的蛋", "start_time": now-1*H, "end_time": now+3*H}
        ]}]}, "status": 200},
        # #5：新增商品 → PUSH
        {"data": {"merchantActivities": [{"get_props": [
            {"name": "神奇的蛋", "start_time": now-1*H, "end_time": now+3*H},
            {"name": "黄金契约", "start_time": now, "end_time": now+4*H}
        ]}]}, "status": 200},
        # #6：API 500
        {"data": {}, "status": 500},
        # #7：恢复，新商品 → PUSH
        {"data": {"merchantActivities": [{"get_props": [
            {"name": "稀有矿石", "start_time": now, "end_time": now+5*H}
        ]}]}, "status": 200},
        # #8：同一商品 → CONTINUE
        {"data": {"merchantActivities": [{"get_props": [
            {"name": "稀有矿石", "start_time": now, "end_time": now+5*H}
        ]}]}, "status": 200},
    ]

# ── 主测试 ──
print("=" * 60)
print("RocoM-Push 多轮模拟测试")
print("=" * 60)

api = MockAPI(18989)
ok = api.start()
print(f"  {'✅ API已启动' if ok else '⚠️  端口占用，跳过启动'}\n")

api.set_scenes(build_scenes())

results = []
for i in range(1, 9):
    if api.pos >= len(api.scenes):
        break
    print(f"-- 第 {i} 次检测 --")
    action = run_once("http://localhost:18989", "test-key")
    results.append((i, api.pos, action))
    time.sleep(0.01)

api.stop()

# ── 验证 ──
print("\n" + "=" * 60)
print("结果验证")
print("=" * 60)

passed = failed = 0
def check(label, cond):
    global passed, failed
    icon = "✅" if cond else "❌"
    print(f"  {icon} {label}")
    if cond: passed += 1
    else: failed += 1

nums = [r[1] for r in results]
acts = [r[2] for r in results]
print(f"\n  API调用: {nums}")
print(f"  行为:    {acts}")

check("API#1 → RETRY（无商品）", acts[0]=="RETRY" and nums[0]==1)
check("API#2 → RETRY（过期商品被过滤）", acts[1]=="RETRY" and nums[1]==2)
check("API#3 → PUSH（首次有有效商品）", acts[2]=="PUSH" and nums[2]==3)
check("API#4 → CONTINUE（商品无变化不推）", acts[3]=="CONTINUE" and nums[3]==4)
check("API#5 → PUSH（新增商品，再次推送）", acts[4]=="PUSH" and nums[4]==5)
check("API#6 → FAIL（API 500错误）", acts[5]=="FAIL" and nums[5]==6)
check("API#7 → PUSH（恢复后检测到新商品）", acts[6]=="PUSH" and nums[6]==7)
check("API#8 → CONTINUE（商品无变化）", acts[7]=="CONTINUE" and nums[7]==8)

push_count = sum(1 for a in acts if a == "PUSH")
check("总推送次数 = 3（API#3 #5 #7）", push_count == 3)

print(f"\n{'='*60}")
print(f"测试结果: {passed} 通过，{failed} 失败")
if failed == 0:
    print("全部通过 ✅")
else:
    for label, c in [(l,c) for l,c in [(r[0],r[2]) for r in results] if not c]:
        print(f"  ❌ {label}")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
