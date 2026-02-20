
import asyncio
import aiohttp
import random
import string
import re
import json
import os
from datetime import datetime
from fastapi import FastAPI

app = FastAPI()

# --- CONFIG ---
LEMON_BASE = "https://lemondata.cc"
LEMON_API_BASE = "https://api.lemondata.cc"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ilhazkplkwibumwhxhpk.supabase.co/rest/v1/lemon_keys")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlsaGF6a3Bsa3dpYnVtd2h4aHBrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY5NjY4ODQsImV4cCI6MjA4MjU0Mjg4NH0.2lXYxiW3w6upUKB69qE6hOL9uFSNS4bPlSK_hGSVwDQ")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# --- EMAIL (tempmail.lol) ---
async def get_temp_email(session):
    try:
        async with session.post("https://api.tempmail.lol/v2/inbox/create") as r:
            if r.status != 201: return None, None
            data = await r.json()
            return data["address"], data["token"]
    except Exception as e:
        log(f"[-] Email creation error: {e}")
        return None, None

async def wait_for_lemon_link(session, token, timeout=120):
    start = datetime.now()
    log("Polling tempmail.lol...")
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            async with session.get(f"https://api.tempmail.lol/v2/inbox?token={token}") as r:
                if r.status != 200: continue
                data = await r.json()
                emails = data.get("emails", [])
                if not emails: continue
                body = emails[0].get("body", "") + emails[0].get("html", "")
                match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', body)
                if match:
                    return match.group(0).replace("&amp;", "&")
        except: pass
    return None

# --- SUPABASE ---
async def save_to_supabase(session, email, api_key):
    log(f"Saving to Supabase...")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    try:
        async with session.post(SUPABASE_URL, json={"email": email, "api_key": api_key}, headers=headers) as r:
            if r.status in [200, 201]:
                log("[+] Saved to Supabase.")
            else:
                log(f"[-] Supabase failed: {r.status}")
    except Exception as e:
        log(f"[-] Supabase error: {e}")

# --- FARMER CORE ---
async def farm_one():
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        headers = {"User-Agent": UA}

        # 1. Get email
        email, mail_token = await get_temp_email(session)
        if not email:
            log("[-] Failed to get email.")
            return
        log(f"[+] Email: {email}")

        # 2. Auth CSRF + Sign in
        async with session.get(f"{LEMON_BASE}/api/auth/csrf") as r:
            auth_csrf = (await r.json()).get("csrfToken")

        payload = {"email": email, "csrfToken": auth_csrf, "callbackUrl": LEMON_BASE, "json": "true"}
        async with session.post(f"{LEMON_BASE}/api/auth/signin/email", data=payload, headers=headers) as r:
            body = await r.text()
            if r.status == 403 or "Access Denied" in body:
                log(f"[-] Email domain blocked.")
                return
            if r.status not in [200, 302]:
                log(f"[-] Sign-in failed: {r.status}")
                return
        log("[+] Sign-in triggered.")

        # 3. Wait for magic link
        link = await wait_for_lemon_link(session, mail_token)
        if not link:
            log("[-] No magic link received.")
            return
        log("[+] Got magic link.")

        # 4. Activate session
        async with session.get(link, headers=headers) as r:
            log(f"[+] Session activated.")

        # 5. Get dashboard CSRF
        async with session.get(f"{LEMON_BASE}/api/csrf", headers=headers) as r:
            csrf_data = await r.json()
            custom_csrf = csrf_data.get("token")
        if not custom_csrf:
            log("[-] No dashboard CSRF.")
            return

        # 6. Get Org ID
        org_id = None
        async with session.get(f"{LEMON_BASE}/api/dashboard/organizations", headers=headers) as r:
            data = await r.json()
            orgs = data.get("data", {}).get("organizations", [])
            if orgs: org_id = orgs[0].get("id")
        if not org_id:
            log("[-] No Org ID.")
            return

        # 7. Create API Key
        log(f"Creating key for org {org_id}...")
        create_headers = {
            "x-csrf-token": custom_csrf,
            "content-type": "application/json",
            "origin": LEMON_BASE,
            "referer": f"{LEMON_BASE}/dashboard/api",
            "user-agent": UA
        }
        async with session.post(
            f"{LEMON_BASE}/api/dashboard/organizations/{org_id}/api-keys",
            json={"name": "k", "limitAmount": None},
            headers=create_headers
        ) as r:
            resp = await r.json()
            if r.status in [200, 201]:
                api_key = resp.get("data", {}).get("key")
                if api_key:
                    log(f"[!!!] KEY: {api_key}")
                    await save_to_supabase(session, email, api_key)
                else:
                    log(f"[-] No key in response.")
            else:
                log(f"[-] Key creation failed: {r.status}")

# --- INFINITE LOOP ---
async def farm_loop():
    log("Infinite farm loop started.")
    while True:
        try:
            delay = random.randint(5, 30)
            await asyncio.sleep(delay)
            log("--- New farm run ---")
            await farm_one()
        except Exception as e:
            log(f"LOOP ERROR: {e}")
            await asyncio.sleep(60)

# --- WEB ---
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(farm_loop())

@app.get("/")
async def root():
    return {"status": "farming", "service": "Lemon Farmer", "time": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
