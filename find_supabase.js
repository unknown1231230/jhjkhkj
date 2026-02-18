/**
 * Finder for Supabase instance in the console
 */
function findSupabase() {
    const candidates = [
        window.supabase,
        window.sb,
        window.client,
        window.auth,
        window.__SUPABASE_CLIENT__
    ];
    
    for (let c of candidates) {
        if (c && c.auth && c.from) return c;
    }
    
    // Search all global keys
    for (let key in window) {
        if (key.length < 2) continue;
        try {
            const val = window[key];
            if (val && val.auth && val.from) {
                console.log(`✅ Found Supabase client in: window.${key}`);
                return val;
            }
        } catch(e){}
    }
    
    console.error("❌ Supabase client not found in window object.");
    return null;
}

const sb = findSupabase();
if (sb) {
    console.log("Supabase found. You can now use it to sign up new accounts.");
}
