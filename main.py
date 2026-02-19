
import asyncio
import aiohttp
import random
import string
import re
import json
import os
from datetime import datetime
from yarl import URL
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()

# --- CONFIG ---
LEMON_BASE = "https://lemondata.cc"
LEMON_API_BASE = "https://api.lemondata.cc"

# Use environment variables for secrets on Render
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ilhazkplkwibumwhxhpk.supabase.co/rest/v1/lemon_keys")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlsaGF6a3Bsa3dpYnVtd2h4aHBrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY5NjY4ODQsImV4cCI6MjA4MjU0Mjg4NH0.2lXYxiW3w6upUKB69qE6hOL9uFSNS4bPlSK_hGSVwDQ")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- EMAIL UTILS ---
async def get_mail_gw_token(session):
    try:
        async with session.get("https://api.mail.gw/domains") as r:
            if r.status != 200: return None, None
            data = await r.json()
            domain = random.choice(data.get("hydra:member")).get("domain")
        
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        address = f"{username}@{domain}"
        pwd = "Pass123!"
        
        async with session.post("https://api.mail.gw/accounts", json={"address": address, "password": pwd}) as r:
            if r.status not in [200, 201]: return None, None
            
        async with session.post("https://api.mail.gw/token", json={"address": address, "password": pwd}) as r:
            js = await r.json()
            return address, js.get("token")
    except: return None, None

async def wait_for_lemon_link(session, token, timeout=120):
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime.now()
    log("Polling Mail.gw...")
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            async with session.get("https://api.mail.gw/messages", headers=headers) as r:
                if r.status != 200: continue
                items = (await r.json()).get("hydra:member")
                if not items: continue
                
                msg_id = items[0].get("id")
                async with session.get(f"https://api.mail.gw/messages/{msg_id}", headers=headers) as r2:
                    content = await r2.json()
                    text = (content.get("html") or [])
                    if isinstance(text, list): text = "".join(text)
                    text += (content.get("text") or "")
                    
                    match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', text)
                    if match:
                        return match.group(0).replace("&amp;", "&")
        except: pass
    return None

async def save_to_supabase(session, email, api_key):
    log(f"Saving {email} to Supabase...")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    payload = {"email": email, "api_key": api_key}
    try:
        async with session.post(SUPABASE_URL, json=payload, headers=headers) as r:
            if r.status in [200, 201]:
                log("[+] Successfully saved to Supabase.")
            else:
                log(f"[-] Supabase save failed: {r.status} {await r.text()}")
    except Exception as e:
        log(f"[-] Supabase Error: {e}")

# --- FARMER CORE ---
async def farm_one():
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        log("Starting farm run...")
        email, mail_token = await get_mail_gw_token(session)
        if not email: return
        
        async with session.get(f"{LEMON_BASE}/api/auth/csrf") as r:
            auth_csrf = (await r.json()).get("csrfToken")
        
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"}
        payload = {"email": email, "csrfToken": auth_csrf, "callbackUrl": LEMON_BASE, "json": "true"}
        async with session.post(f"{LEMON_BASE}/api/auth/signin/email", data=payload, headers=headers) as r:
            if r.status not in [200, 302]: return

        link = await wait_for_lemon_link(session, mail_token)
        if not link: return
        
        async with session.get(link, headers=headers) as r:
            log("[+] Session Activated.")

        async with session.get(f"{LEMON_BASE}/api/csrf", headers=headers) as r:
            csrf_data = await r.json()
            custom_csrf = csrf_data.get("token")
        
        if not custom_csrf: return

        org_id = None
        async with session.get(f"{LEMON_BASE}/api/dashboard/organizations", headers=headers) as r:
            data = await r.json()
            orgs = data.get("data", {}).get("organizations", [])
            if orgs: org_id = orgs[0].get('id')
        
        if not org_id: return

        create_url = f"{LEMON_BASE}/api/dashboard/organizations/{org_id}/api-keys"
        create_headers = {
            "x-csrf-token": custom_csrf,
            "content-type": "application/json",
            "origin": LEMON_BASE,
            "referer": f"{LEMON_BASE}/dashboard/api",
            "user-agent": headers["User-Agent"]
        }
        create_payload = {"name": "lemon_farmer_key", "limitAmount": None}
        
        async with session.post(create_url, json=create_payload, headers=create_headers) as r:
            resp_text = await r.text()
            if r.status in [200, 201]:
                log("[+] KEY CREATION SUCCESS!")
                key_data = json.loads(resp_text)
                api_key = key_data.get("data", {}).get("key")
                if api_key:
                    log(f"[!!!] NEW KEY: {api_key}")
                    await save_to_supabase(session, email, api_key)
            else:
                log(f"[-] Key creation failed: {r.status}")

# --- FARMER LOOP ---
async def farm_loop():
    log("Infinite farm loop started.")
    while True:
        try:
            # Random delay between 5 and 30 seconds to look slightly more human
            # and avoid hitting rate limits too aggressively
            delay = random.randint(5, 30)
            await asyncio.sleep(delay)
            
            log("Starting new farm run...")
            await farm_one()
            
        except Exception as e:
            log(f"CRITICAL LOOP ERROR: {e}")
            await asyncio.sleep(60) # Wait a bit more on error

# --- WEB OVERLAY ---
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(farm_loop())

@app.get("/")
async def root():
    return {
        "status": "farming",
        "service": "Lemon Farmer Infinite",
        "time": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
