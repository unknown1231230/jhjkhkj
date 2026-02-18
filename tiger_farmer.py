#!/usr/bin/env python3
"""
Tiger Account Farmer - Infinite Async Loop
1. Runs forever (until stopped).
2. Uses asyncio + aiohttp.
3. Handles 429s with backoff.
4. Detailed error logging.
5. Built-in web server for Render.
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

BASE = "https://tiger.bookapi.cc"
REFERRAL_CODE = "njVk"
REFERRAL_URL = f"{BASE}/ref/{REFERRAL_CODE}"
LOG_FILE = "tiger_bypass_log.txt"
ACCOUNTS_FILE = "tiger_accounts.json"

MAX_CONCURRENT = 20       # Reduced to avoid instant WAF ban
SEMAPHORE = None          # Limit creating tasks

# Stats
stats = {"ok": 0, "fail": 0}
stats_lock = asyncio.Lock()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

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
        "Referer": f"{BASE}/register?aff={REFERRAL_CODE}",
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
    except:
        return None, None

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

async def update_stats(success):
    async with stats_lock:
        if success: stats["ok"] += 1
        else: stats["fail"] += 1
        ok = stats["ok"]
        fail = stats["fail"]
        if (ok + fail) % 10 == 0:
            log(f"STATS: {ok} Created | {fail} Failed")

async def worker(worker_id):
    log(f"Worker {worker_id} started.")
    while True:
        async with SEMAPHORE:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                username = "u" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
                try:
                    h = get_headers()
                    try:
                        async with session.get(REFERRAL_URL, headers=h, timeout=5) as r: pass
                    except: pass
                    
                    email, mail_token = await get_temp_email(session)
                    if not email:
                        await update_stats(False)
                        await asyncio.sleep(2)
                        continue

                    verify_params = {"email": email}
                    async with session.get(f"{BASE}/api/verification", params=verify_params, headers=h, timeout=15) as r:
                        if r.status == 429:
                            log(f"Worker {worker_id}: 429 Rate Limit on Verify. Sleeping 30s.")
                            await asyncio.sleep(30)
                            await update_stats(False)
                            continue
                        if r.status != 200:
                            await update_stats(False)
                            continue

                    code = await wait_for_code(session, mail_token)
                    if not code:
                        await update_stats(False)
                        continue

                    password = "Tp" + "".join(random.choices(string.ascii_letters + string.digits, k=10)) + "!"
                    reg_data = {
                        "username": username,
                        "password": password,
                        "email": email,
                        "verification_code": code,
                        "aff_code": REFERRAL_CODE,
                        "aff": REFERRAL_CODE,
                        "invitation_code": REFERRAL_CODE
                    }
                    path = random.choice(["/api/user/register", "/api/user/register/"])
                    async with session.post(f"{BASE}{path}", params={"aff": REFERRAL_CODE}, json=reg_data, headers=h, timeout=15) as r:
                        if r.status == 429:
                            log(f"Worker {worker_id}: 429 Rate Limit on Register. Sleeping 30s.")
                            await asyncio.sleep(30)
                            await update_stats(False)
                            continue
                        resp_data = await r.json()
                        if not resp_data.get("success"):
                            log(f"Worker {worker_id}: Reg Fail: {resp_data}")
                            await update_stats(False)
                            continue

                    login_data = {"username": username, "password": password}
                    async with session.post(f"{BASE}/api/user/login", json=login_data, headers=h, timeout=10) as r:
                        if r.status != 200:
                            await update_stats(False)
                            continue
                        l_resp = await r.json()
                        user_id = l_resp.get("data", {}).get("id")

                    h["new-api-user"] = str(user_id)
                    key_data = {"name": "key", "unlimited_quota": True, "expired_time": -1}
                    async with session.post(f"{BASE}/api/token/", json=key_data, headers=h, timeout=10) as r:
                        if r.status == 200:
                            k_resp = await r.json()
                            key = k_resp.get("data", {}).get("key")
                            log(f"✅ Created: {username} | ID: {user_id}")
                            await save_account({
                                "username": username,
                                "password": password,
                                "user_id": user_id,
                                "api_key": f"sk-{key}",
                                "created_at": datetime.now().isoformat()
                            })
                            await update_stats(True)
                        else:
                            await update_stats(False)
                except Exception:
                    await update_stats(False)
            await asyncio.sleep(random.uniform(1, 4))

async def handle_home(request):
    return aiohttp.web.Response(text="Tiger Farmer is running!")

async def handle_accounts(request):
    try:
        if os.path.exists(ACCOUNTS_FILE):
            async with aiofiles.open(ACCOUNTS_FILE, mode='r') as f:
                content = await f.read()
            return aiohttp.web.Response(text="[" + content.rstrip(",\n") + "]", content_type='application/json')
        return aiohttp.web.Response(text="[]", content_type='application/json')
    except Exception as e:
        return aiohttp.web.Response(text=str(e), status=500)

async def handle_logs(request):
    try:
        if os.path.exists(LOG_FILE):
            async with aiofiles.open(LOG_FILE, mode='r') as f:
                content = await f.read()
            return aiohttp.web.Response(text=content[-50000:])
        return aiohttp.web.Response(text="No logs yet.")
    except Exception as e:
        return aiohttp.web.Response(text=str(e), status=500)

async def run_server():
    app = aiohttp.web.Application()
    app.add_routes([
        aiohttp.web.get('/', handle_home),
        aiohttp.web.get('/accounts', handle_accounts),
        aiohttp.web.get('/logs', handle_logs),
    ])
    port = int(os.environ.get("PORT", 8080))
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', port)
    log(f"Web server starting on port {port}...")
    await site.start()

async def main():
    global SEMAPHORE
    SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT)
    log(f"--- TIGER INFINITE FARMER ---")
    log(f"Concurrency: {MAX_CONCURRENT}")
    asyncio.create_task(run_server())
    workers = [asyncio.create_task(worker(i+1)) for i in range(MAX_CONCURRENT)]
    await asyncio.gather(*workers)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
