
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
# PROVIDER: Emailnator (Gmail / Googlemail)
# ==========================================
async def emailnator_create(session, etype="dotGmail"):
    try:
        async with session.get("https://www.emailnator.com/", headers={"User-Agent": UA}) as r:
            cookies = session.cookie_jar.filter_cookies("https://www.emailnator.com/")
            xsrf = None
            for k, v in cookies.items():
                if "xsrf" in k.lower():
                    xsrf = urllib.parse.unquote(v.value)
        if not xsrf: return None, None
        async with session.post("https://www.emailnator.com/generate-email",
            headers={"User-Agent": UA, "x-xsrf-token": xsrf, "content-type": "application/json"},
            json={"email": [etype]}) as r:
            data = await r.json()
            return data["email"][0], xsrf
    except: return None, None

async def emailnator_poll(session, email, xsrf, timeout=120):
    start = datetime.now()
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            cookies = session.cookie_jar.filter_cookies("https://www.emailnator.com/")
            for k, v in cookies.items():
                if "xsrf" in k.lower():
                    xsrf = urllib.parse.unquote(v.value)
            async with session.post("https://www.emailnator.com/message-list",
                headers={"User-Agent": UA, "x-xsrf-token": xsrf, "content-type": "application/json"},
                json={"email": email}) as r:
                data = await r.json()
                msgs = [m for m in data.get("messageData", []) if m.get("messageID") != "ADSVPN"]
                if not msgs: continue
                msg_id = msgs[0]["messageID"]
                async with session.post("https://www.emailnator.com/message-list",
                    headers={"User-Agent": UA, "x-xsrf-token": xsrf, "content-type": "application/json"},
                    json={"email": email, "messageID": msg_id}) as r2:
                    body = await r2.text()
                    match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', body)
                    if match: return match.group(0).replace("&amp;", "&")
        except: pass
    return None

# ==========================================
# PROVIDER: tempmail.lol
# ==========================================
async def tempmail_create(session):
    try:
        async with session.post("https://api.tempmail.lol/v2/inbox/create") as r:
            data = await r.json()
            return data["address"], data["token"]
    except: return None, None

async def tempmail_poll(session, token, timeout=120):
    start = datetime.now()
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            async with session.get(f"https://api.tempmail.lol/v2/inbox?token={token}") as r:
                data = await r.json()
                emails = data.get("emails", [])
                if not emails: continue
                body = emails[0].get("body", "") + emails[0].get("html", "")
                match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', body)
                if match: return match.group(0).replace("&amp;", "&")
        except: pass
    return None

# ==========================================
# PROVIDER: Guerrilla Mail
# ==========================================
async def guerrilla_create(session):
    try:
        async with session.get("https://api.guerrillamail.com/ajax.php?f=get_email_address", headers={"User-Agent": UA}) as r:
            data = await r.json()
            return data["email_addr"], data["sid_token"]
    except: return None, None

async def guerrilla_poll(session, sid, timeout=120):
    start = datetime.now()
    while (datetime.now() - start).seconds < timeout:
        await asyncio.sleep(5)
        try:
            async with session.get(f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid}", headers={"User-Agent": UA}) as r:
                data = await r.json()
                msgs = [m for m in data.get("list", []) if "lemon" in m.get("mail_from","").lower()]
                if not msgs: continue
                mid = msgs[0]["mail_id"]
                async with session.get(f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={mid}&sid_token={sid}", headers={"User-Agent": UA}) as r2:
                    msg = await r2.json()
                    match = re.search(r'https://lemondata\.cc/api/auth/callback/email\?[^\s"''<>]+', msg.get("mail_body",""))
                    if match: return match.group(0).replace("&amp;", "&")
        except: pass
    return None

# ==========================================
# FARMER CORE
# ==========================================
async def farm_one():
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        # Provider selection
        choice = random.choice(["gmail", "duck", "guerrilla", "googlemail", "plus"])
        email, token, provider = None, None, None
        
        if choice == "gmail":
            email, token = await emailnator_create(session, "dotGmail")
            provider = "emailnator"
        elif choice == "googlemail":
            email, token = await emailnator_create(session, "googleMail")
            provider = "emailnator"
        elif choice == "plus":
            email, token = await emailnator_create(session, "plusGmail")
            provider = "emailnator"
        elif choice == "guerrilla":
            email, token = await guerrilla_create(session)
            provider = "guerrilla"
        else: # duck / fallback
            email, token = await tempmail_create(session)
            provider = "tempmail"

        if not email:
            email, token = await tempmail_create(session)
            provider = "tempmail"
        
        if not email: return

        log(f"[*] Trying {email} ({provider})")
        
        async with session.get(f"{LEMON_BASE}/api/auth/csrf") as r:
            auth_csrf = (await r.json()).get("csrfToken")
        
        async with session.post(f"{LEMON_BASE}/api/auth/signin/email", data={"email":email, "csrfToken":auth_csrf, "callbackUrl":LEMON_BASE, "json":"true"}, headers={"User-Agent":UA}) as r:
            if r.status == 403 or "Access Denied" in await r.text():
                log(f"[-] Domain BLOCKED: {email}")
                return

        # Poll
        link = None
        if provider == "emailnator": link = await emailnator_poll(session, email, token)
        elif provider == "guerrilla": link = await guerrilla_poll(session, token)
        else: link = await tempmail_poll(session, token)

        if not link: return
        
        # Activate + Org + CSRF + Key
        async with session.get(link, headers={"User-Agent":UA}) as r: pass
        async with session.get(f"{LEMON_BASE}/api/csrf", headers={"User-Agent":UA}) as r:
            custom_csrf = (await r.json()).get("token")
        async with session.get(f"{LEMON_BASE}/api/dashboard/organizations", headers={"User-Agent":UA}) as r:
            org_id = (await r.json())["data"]["organizations"][0]["id"]
        
        ch = {"x-csrf-token":custom_csrf, "content-type":"application/json", "origin":LEMON_BASE, "referer":f"{LEMON_BASE}/dashboard/api", "user-agent":UA}
        async with session.post(f"{LEMON_BASE}/api/dashboard/organizations/{org_id}/api-keys", json={"name":"k","limitAmount":None}, headers=ch) as r:
            if r.status in [200, 201]:
                api_key = (await r.json()).get("data", {}).get("key")
                if api_key:
                    log(f"[!!!] NEW KEY: {api_key}")
                    async with session.post(SUPABASE_URL, json={"email":email, "api_key":api_key}, headers={"apikey":SUPABASE_KEY, "Authorization":f"Bearer {SUPABASE_KEY}", "Content-Type":"application/json"}) as rs: pass

async def farm_loop():
    while True:
        try:
            await asyncio.sleep(random.randint(5, 15))
            await farm_one()
        except: await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(farm_loop())

@app.get("/")
async def root(): return {"status":"farming","version":"v4-multi-provider"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
