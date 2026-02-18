#!/usr/bin/env python3
"""
Qidian Account Farmer - Infinite Async Loop + Web Service
Target: https://api.qidianai.xyz
Referral: NPF1
"""
import asyncio
import aiohttp
import aiohttp.web
import aiofiles
import json
import random
import string
import re
import os
from datetime import datetime

BASE = "https://api.qidianai.xyz"
REFERRAL_CODE = "NPF1"
REFERRAL_URL = f"{BASE}/register?aff={REFERRAL_CODE}"
LOG_FILE = "qidian_bypass_log.txt"
ACCOUNTS_FILE = "qidian_accounts.json"
DASHBOARD_FILE = "qidian_dashboard.html"

MAX_CONCURRENT = 15 # Slightly lower to be safe initially
SEMAPHORE = None

# Global State
state = {
    "ok": 0,
    "fail": 0,
    "running": True,
    "tasks": []
}
state_lock = asyncio.Lock()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except: pass

def rand_ip():
    return ".".join(str(random.randint(1, 254)) for _ in range(4))

def get_headers():
    ip = rand_ip()
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": REFERRAL_URL,
        "Origin": BASE,
    }

async def save_account(acc):
    try:
        async with aiofiles.open(ACCOUNTS_FILE, "a") as f:
            await f.write(json.dumps(acc) + ",\n")
    except Exception as e:
        log(f"Save error: {e}")

async def get_temp_email(session):
    try:
        async with session.get("https://api.mail.tm/domains", timeout=10) as r:
            if r.status != 200: return None, None
            data = await r.json()
            domains = data.get("hydra:member")
            if not domains: return None, None
            domain = random.choice(domains).get("domain")

        address = "".join(random.choices(string.ascii_lowercase, k=10)) + "@" + domain
        password = "Pass123!"
        
        async with session.post("https://api.mail.tm/accounts", 
                                json={"address": address, "password": password}, 
                                timeout=10) as r:
            if r.status not in [200, 201]: return None, None

        async with session.post("https://api.mail.tm/token", 
                                json={"address": address, "password": password}, 
                                timeout=10) as r:
            if r.status != 200: return None, None
            data = await r.json()
            return address, data.get("token")
    except: return None, None

async def wait_for_code(session, token, timeout=45):
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime.now()
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(3)
        try:
            async with session.get("https://api.mail.tm/messages", headers=headers, timeout=10) as r:
                if r.status != 200: continue
                data = await r.json()
                items = data.get("hydra:member")
                if not items: continue
                msg_id = items[0].get("@id")
                async with session.get(f"https://api.mail.tm{msg_id}", headers=headers, timeout=10) as r2:
                    if r2.status != 200: continue
                    msg_data = await r2.json()
                    text = msg_data.get("text", "")
                    match = re.search(r'[：:]\s*([a-zA-Z0-9]{6})', text)
                    if match: return match.group(1)
        except: pass
    return None

async def worker(worker_id):
    log(f"Worker {worker_id} started.")
    while state["running"]:
        async with SEMAPHORE:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                username = "q" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
                try:
                    h = get_headers()
                    # 1. Warm up with referral
                    try:
                        async with session.get(REFERRAL_URL, headers=h, timeout=5) as r: pass
                    except: pass
                    
                    # 2. Email
                    email, mail_token = await get_temp_email(session)
                    if not email:
                        async with state_lock: state["fail"] += 1
                        await asyncio.sleep(2)
                        continue

                    # 3. Verification
                    async with session.get(f"{BASE}/api/verification", params={"email": email}, headers=h, timeout=15) as r:
                        if r.status == 429:
                            await asyncio.sleep(30)
                            async with state_lock: state["fail"] += 1
                            continue
                        if r.status != 200:
                            async with state_lock: state["fail"] += 1
                            continue

                    code = await wait_for_code(session, mail_token)
                    if not code:
                        async with state_lock: state["fail"] += 1
                        continue

                    # 4. Register
                    password = "Qp" + "".join(random.choices(string.ascii_letters + string.digits, k=10)) + "!"
                    reg_data = {
                        "username": username, "password": password, "email": email,
                        "verification_code": code, "aff": REFERRAL_CODE
                    }
                    async with session.post(f"{BASE}/api/user/register", json=reg_data, headers=h, timeout=15) as r:
                        if r.status != 200:
                            async with state_lock: state["fail"] += 1
                            continue
                        resp = await r.json()
                        if not resp.get("success"):
                            log(f"Worker {worker_id}: Reg Fail: {resp.get('message')}")
                            async with state_lock: state["fail"] += 1
                            continue

                    # 5. Login
                    async with session.post(f"{BASE}/api/user/login", json={"username": username, "password": password}, headers=h, timeout=10) as r:
                        if r.status != 200:
                            async with state_lock: state["fail"] += 1
                            continue
                        user_id = (await r.json()).get("data", {}).get("id")

                    # 6. API Key
                    h["new-api-user"] = str(user_id)
                    key_data = {"name": "qidian", "unlimited_quota": True, "expired_time": -1}
                    async with session.post(f"{BASE}/api/token/", json=key_data, headers=h, timeout=10) as r:
                        if r.status == 200:
                            key = (await r.json()).get("data", {}).get("key")
                            log(f"✅ Created Qidian: {username}")
                            await save_account({
                                "username": username, "password": password, "user_id": user_id,
                                "api_key": f"sk-{key}", "created_at": datetime.now().isoformat()
                            })
                            async with state_lock: state["ok"] += 1
                        else:
                            async with state_lock: state["fail"] += 1
                except Exception:
                    async with state_lock: state["fail"] += 1
            await asyncio.sleep(random.uniform(2, 5))

# --- WEB SERVICE HANDLERS ---
async def handle_dashboard(request):
    with open("dashboard.html", "r") as f:
        html = f.read().replace("Tiger", "Qidian").replace("🐯", "🐉")
        html = html.replace("/api/status", "/q/api/status")
        html = html.replace("/accounts", "/q/accounts")
        html = html.replace("/logs", "/q/logs")
        html = html.replace("/api/start", "/q/api/start")
        html = html.replace("/api/stop", "/q/api/stop")
        return aiohttp.web.Response(text=html, content_type='text/html')

async def handle_status(request):
    return aiohttp.web.json_response(state)

async def handle_start(request):
    if not state["running"]:
        state["running"] = True
        for i in range(MAX_CONCURRENT):
            state["tasks"].append(asyncio.create_task(worker(i+1)))
        log("Qidian Farmer started.")
    return aiohttp.web.json_response({"status": "started"})

async def handle_stop(request):
    state["running"] = False
    for t in state["tasks"]: t.cancel()
    state["tasks"] = []
    log("Qidian Farmer stopped.")
    return aiohttp.web.json_response({"status": "stopped"})

async def handle_accounts(request):
    if os.path.exists(ACCOUNTS_FILE):
        async with aiofiles.open(ACCOUNTS_FILE, mode='r') as f:
            content = await f.read()
        return aiohttp.web.Response(text="[" + content.rstrip(",\n") + "]", content_type='application/json')
    return aiohttp.web.json_response([])

async def handle_logs(request):
    if os.path.exists(LOG_FILE):
        async with aiofiles.open(LOG_FILE, mode='r') as f:
            return aiohttp.web.Response(text=(await f.read())[-50000:])
    return aiohttp.web.Response(text="No logs yet.")

async def main():
    global SEMAPHORE
    SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT)
    
    app = aiohttp.web.Application()
    app.add_routes([
        aiohttp.web.get('/q', handle_dashboard),
        aiohttp.web.get('/q/api/status', handle_status),
        aiohttp.web.post('/q/api/start', handle_start),
        aiohttp.web.post('/q/api/stop', handle_stop),
        aiohttp.web.get('/q/accounts', handle_accounts),
        aiohttp.web.get('/q/logs', handle_logs),
    ])
    
    port = int(os.environ.get("PORT", 8081)) # Run on different port if local
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, '0.0.0.0', port).start()
    log(f"Qidian Web service running on port {port}")
    
    for i in range(MAX_CONCURRENT):
        state["tasks"].append(asyncio.create_task(worker(i+1)))
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
