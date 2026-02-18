#!/usr/bin/env python3
"""
Multi-Farmer Web Service
Supports: 🐯 Tiger & 🐉 Qidian
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

# --- CONFIG & STATE ---
SITES = {
    "tiger": {
        "base": "https://tiger.bookapi.cc",
        "aff": "njVk",
        "log": "tiger_bypass_log.txt",
        "db": "tiger_accounts.json",
        "concurrent": 15,
        "prefix": "u"
    },
    "qidian": {
        "base": "https://api.qidianai.xyz",
        "aff": "NPF1",
        "log": "qidian_bypass_log.txt",
        "db": "qidian_accounts.json",
        "concurrent": 10,
        "prefix": "q"
    }
}

stats = {
    "tiger": {"ok": 0, "fail": 0, "running": True, "tasks": []},
    "qidian": {"ok": 0, "fail": 0, "running": True, "tasks": []}
}

stats_lock = asyncio.Lock()
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]

# --- UTILS ---
def log(site_id, msg):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] [{site_id.upper()}] {msg}"
    print(line, flush=True)
    try:
        with open(SITES[site_id]["log"], "a") as f:
            f.write(line + "\n")
    except: pass

def get_headers(site_id):
    ip = ".".join(str(random.randint(1, 254)) for _ in range(4))
    base = SITES[site_id]["base"]
    aff = SITES[site_id]["aff"]
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": f"{base}/register?aff={aff}",
        "Origin": base,
    }

async def get_temp_email(session):
    try:
        async with session.get("https://api.mail.tm/domains", timeout=10) as r:
            if r.status != 200: return None, None
            data = await r.json()
            domain = random.choice(data.get("hydra:member")).get("domain")
        address = "".join(random.choices(string.ascii_lowercase, k=10)) + "@" + domain
        pwd = "Pass123!"
        await session.post("https://api.mail.tm/accounts", json={"address": address, "password": pwd}, timeout=10)
        async with session.post("https://api.mail.tm/token", json={"address": address, "password": pwd}, timeout=10) as r:
            return address, (await r.json()).get("token")
    except: return None, None

async def wait_for_code(session, token, timeout=45):
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime.now()
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(4)
        try:
            async with session.get("https://api.mail.tm/messages", headers=headers, timeout=10) as r:
                items = (await r.json()).get("hydra:member")
                if not items: continue
                async with session.get(f"https://api.mail.tm{items[0].get('@id')}", headers=headers, timeout=10) as r2:
                    text = (await r2.json()).get("text", "")
                    match = re.search(r'[：:]\s*([a-zA-Z0-9]{6})', text)
                    if match: return match.group(1)
        except: pass
    return None

# --- WORKER ---
async def farmer_worker(site_id, worker_id, semaphore):
    config = SITES[site_id]
    log(site_id, f"Worker {worker_id} started.")
    
    while stats[site_id]["running"]:
        async with semaphore:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                try:
                    h = get_headers(site_id)
                    email, mail_token = await get_temp_email(session)
                    if not email:
                        async with stats_lock: stats[site_id]["fail"] += 1
                        await asyncio.sleep(2)
                        continue

                    # Verification
                    async with session.get(f"{config['base']}/api/verification", params={"email": email}, headers=h, timeout=15) as r:
                        if r.status != 200:
                            async with stats_lock: stats[site_id]["fail"] += 1
                            continue

                    code = await wait_for_code(session, mail_token)
                    if not code:
                        async with stats_lock: stats[site_id]["fail"] += 1
                        continue

                    # Register
                    username = config["prefix"] + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
                    password = "Tp" + "".join(random.choices(string.ascii_letters + string.digits, k=10)) + "!"
                    reg_data = {
                        "username": username, "password": password, "email": email,
                        "verification_code": code, "aff": config["aff"]
                    }
                    async with session.post(f"{config['base']}/api/user/register", json=reg_data, headers=h, timeout=15) as r:
                        if r.status != 200 or not (await r.json()).get("success"):
                            async with stats_lock: stats[site_id]["fail"] += 1
                            continue

                    # Login
                    async with session.post(f"{config['base']}/api/user/login", json={"username": username, "password": password}, headers=h, timeout=10) as r:
                        user_id = (await r.json()).get("data", {}).get("id")

                    # Token
                    h["new-api-user"] = str(user_id)
                    key_data = {"name": "key", "unlimited_quota": True, "expired_time": -1}
                    async with session.post(f"{config['base']}/api/token/", json=key_data, headers=h, timeout=10) as r:
                        if r.status == 200:
                            key = (await r.json()).get("data", {}).get("key")
                            log(site_id, f"✅ Created: {username}")
                            async with aiofiles.open(config["db"], "a") as f:
                                await f.write(json.dumps({
                                    "username": username, "password": password, "user_id": user_id,
                                    "api_key": f"sk-{key}", "created_at": datetime.now().isoformat()
                                }) + ",\n")
                            async with stats_lock: stats[site_id]["ok"] += 1
                        else:
                            async with stats_lock: stats[site_id]["fail"] += 1
                except:
                    async with stats_lock: stats[site_id]["fail"] += 1
                    
            await asyncio.sleep(random.uniform(5, 10))

# --- WEB HANDLERS ---
async def handle_dashboard(request):
    async with aiofiles.open("dashboard.html", mode='r') as f:
        return aiohttp.web.Response(text=await f.read(), content_type='text/html')

async def handle_api(request):
    site_id = request.match_info['site']
    action = request.match_info['action']
    
    if site_id not in SITES: return aiohttp.web.json_response({"error": "Unknown site"}, status=404)
    
    if action == "status":
        return aiohttp.web.json_response({
            "ok": stats[site_id]["ok"],
            "fail": stats[site_id]["fail"],
            "running": stats[site_id]["running"]
        })
    elif action == "accounts":
        if os.path.exists(SITES[site_id]["db"]):
            async with aiofiles.open(SITES[site_id]["db"], mode='r') as f:
                content = await f.read()
            return aiohttp.web.Response(text="[" + content.rstrip(",\n") + "]", content_type='application/json')
        return aiohttp.web.json_response([])
    elif action == "logs":
        if os.path.exists(SITES[site_id]["log"]):
            async with aiofiles.open(SITES[site_id]["log"], mode='r') as f:
                return aiohttp.web.Response(text=(await f.read())[-30000:])
        return aiohttp.web.Response(text="No logs.")
    
    return aiohttp.web.json_response({"error": "Unknown action"}, status=404)

async def handle_proxy(request):
    """Proxy that picks a random site and random key"""
    site_id = random.choice([s for s in SITES if stats[s]["ok"] > 0] or ["tiger"])
    config = SITES[site_id]
    
    try:
        if not os.path.exists(config["db"]): return aiohttp.web.json_response({"error": "No keys"}, status=503)
        async with aiofiles.open(config["db"], 'r') as f: content = await f.read()
        accounts = json.loads("[" + content.rstrip(",\n") + "]")
        keys = [a['api_key'] for a in accounts if a.get('api_key') and 'None' not in a['api_key']]
        if not keys: return aiohttp.web.json_response({"error": "No valid keys"}, status=503)
        
        target_key = random.choice(keys)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{config['base']}/v1/chat/completions", json=await request.json(), 
                                     headers={"Authorization": f"Bearer {target_key}", "Content-Type": "application/json"}) as r:
                return aiohttp.web.json_response(await r.json(), status=r.status)
    except Exception as e: return aiohttp.web.json_response({"error": str(e)}, status=500)

async def main():
    app = aiohttp.web.Application()
    app.add_routes([
        aiohttp.web.get('/', handle_dashboard),
        aiohttp.web.get('/api/{site}/{action}', handle_api),
        aiohttp.web.post('/v1/chat/completions', handle_proxy),
    ])
    
    port = int(os.environ.get("PORT", 8080))
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, '0.0.0.0', port).start()
    
    # Start all farmers
    for s_id in SITES:
        sem = asyncio.Semaphore(SITES[s_id]["concurrent"])
        for i in range(SITES[s_id]["concurrent"]):
            stats[s_id]["tasks"].append(asyncio.create_task(farmer_worker(s_id, i+1, sem)))
            await asyncio.sleep(0.5)
            
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
