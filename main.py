
import asyncio
import aiohttp
import random
import string
import re
import json
import os
import urllib.parse
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

# ==========================================
# EMAIL PROVIDER 1: Emailnator (Gmail)
# ==========================================
async def emailnator_create(session):
    try:
        async with session.get("https://www.emailnator.com/", headers={"User-Agent": UA}) as r:
            cookies = session.cookie_jar.filter_cookies("https://www.emailnator.com/")
            xsrf = None
            for k, v in cookies.items():
                if "xsrf" in k.lower():
                    xsrf = urllib.parse.unquote(v.value)

        if not xsrf:
            return None, None

        async with session.post("https://www.emailnator.com/generate-email",
            headers={"User-Agent": UA, "x-xsrf-token": xsrf, "content-type": "application/json"},
            json={"email": ["dotGmail"]}) as r:
            data = await r.json()
            email = data["email"][0]
            return email, xsrf
    except Exception as e:
        log(f"[-] Emailnator create error: {e}")
        return None, None

async def emailnator_poll(session, email, xsrf, timeout=120):
    start = datetime.now()
    log("Polling Emailnator...")
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            # Refresh XSRF
            cookies = session.cookie_jar.filter_cookies("https://www.emailnator.com/")
            for k, v in cookies.items():
                if "xsrf" in k.lower():
                    xsrf = urllib.parse.unquote(v.value)

            async with session.post("https://www.emailnator.com/message-list",
                headers={"User-Agent": UA, "x-xsrf-token": xsrf, "content-type": "application/json"},
                json={"email": email}) as r:
                data = await r.json()
                msgs = data.get("messageData", [])
                real_msgs = [m for m in msgs if m.get("messageID") != "ADSVPN"]
                if not real_msgs:
                    continue

                msg_id = real_msgs[0]["messageID"]
                async with session.post("https://www.emailnator.com/message-list",
                    headers={"User-Agent": UA, "x-xsrf-token": xsrf, "content-type": "application/json"},
                    json={"email": email, "messageID": msg_id}) as r2:
                    body = await r2.text()
                    match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', body)
                    if match:
                        return match.group(0).replace("&amp;", "&")
        except:
            pass
    return None

# ==========================================
# EMAIL PROVIDER 2: tempmail.lol (fallback)
# ==========================================
async def tempmail_create(session):
    try:
        async with session.post("https://api.tempmail.lol/v2/inbox/create") as r:
            if r.status != 201:
                return None, None
            data = await r.json()
            return data["address"], data["token"]
    except Exception as e:
        log(f"[-] tempmail.lol create error: {e}")
        return None, None

async def tempmail_poll(session, token, timeout=120):
    start = datetime.now()
    log("Polling tempmail.lol...")
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            async with session.get(f"https://api.tempmail.lol/v2/inbox?token={token}") as r:
                if r.status != 200:
                    continue
                data = await r.json()
                emails = data.get("emails", [])
                if not emails:
                    continue
                body = emails[0].get("body", "") + emails[0].get("html", "")
                match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', body)
                if match:
                    return match.group(0).replace("&amp;", "&")
        except:
            pass
    return None

# ==========================================
# SUPABASE
# ==========================================
async def save_to_supabase(session, email, api_key):
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
                log(f"[-] Supabase: {r.status}")
    except Exception as e:
        log(f"[-] Supabase error: {e}")

# ==========================================
# FARMER CORE
# ==========================================
async def farm_one():
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        headers = {"User-Agent": UA}

        # --- Pick email provider ---
        # Try Emailnator (Gmail) first, fall back to tempmail.lol
        provider = None
        email = None
        poll_token = None

        # Provider 1: Emailnator (Gmail)
        email, xsrf = await emailnator_create(session)
        if email:
            provider = "emailnator"
            poll_token = xsrf
            log(f"[+] Gmail: {email}")
        else:
            # Provider 2: tempmail.lol
            email, poll_token = await tempmail_create(session)
            if email:
                provider = "tempmail"
                log(f"[+] TempMail: {email}")

        if not email:
            log("[-] All email providers failed.")
            return

        # --- Lemon Sign-in ---
        async with session.get(f"{LEMON_BASE}/api/auth/csrf") as r:
            auth_csrf = (await r.json()).get("csrfToken")

        payload = {"email": email, "csrfToken": auth_csrf, "callbackUrl": LEMON_BASE, "json": "true"}
        async with session.post(f"{LEMON_BASE}/api/auth/signin/email", data=payload, headers=headers) as r:
            body = await r.text()
            if r.status == 403 or "Access Denied" in body:
                log(f"[-] Domain blocked for {email}")
                return
            if r.status not in [200, 302]:
                log(f"[-] Sign-in failed: {r.status}")
                return
        log("[+] Sign-in triggered.")

        # --- Wait for magic link ---
        if provider == "emailnator":
            link = await emailnator_poll(session, email, poll_token)
        else:
            link = await tempmail_poll(session, poll_token)

        if not link:
            log("[-] No magic link received.")
            return
        log("[+] Got magic link.")

        # --- Activate session ---
        async with session.get(link, headers=headers) as r:
            log(f"[+] Session activated.")

        # --- Dashboard CSRF ---
        async with session.get(f"{LEMON_BASE}/api/csrf", headers=headers) as r:
            csrf_data = await r.json()
            custom_csrf = csrf_data.get("token")
        if not custom_csrf:
            log("[-] No dashboard CSRF.")
            return

        # --- Org ID ---
        org_id = None
        async with session.get(f"{LEMON_BASE}/api/dashboard/organizations", headers=headers) as r:
            data = await r.json()
            orgs = data.get("data", {}).get("organizations", [])
            if orgs:
                org_id = orgs[0].get("id")
        if not org_id:
            log("[-] No Org ID.")
            return

        # --- Create API Key ---
        log(f"Creating key...")
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
            if r.status in [200, 201]:
                resp = await r.json()
                api_key = resp.get("data", {}).get("key")
                if api_key:
                    log(f"[!!!] KEY: {api_key}")
                    await save_to_supabase(session, email, api_key)
                else:
                    log("[-] No key in response.")
            else:
                log(f"[-] Key creation failed: {r.status}")

# ==========================================
# INFINITE LOOP
# ==========================================
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

# ==========================================
# WEB
# ==========================================
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(farm_loop())

@app.get("/")
async def root():
    return {"status": "farming", "service": "Lemon Farmer v3 (Gmail)", "time": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
