#!/bin/bash

###############################################################################
# Krater Token Refresher (Supabase-only storage)
#
# All tokens are stored in YOUR Supabase DB (dnfkyhstthmewqjdpgyz).
# No local files are created or read.
#
# USAGE:
#   ./krater_refresh.sh              Single refresh
#   ./krater_refresh.sh --loop       Auto-refresh every 50 minutes
#   ./krater_refresh.sh --show       Display current tokens
#   ./krater_refresh.sh --set <tok>  Set a new refresh token manually
#
###############################################################################

# --- CONFIGURATION ---

# Krater's Supabase (the service we're authenticating against)
KRATER_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkY3BidHlmaXlydWhwdHdic3lhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1OTQ3ODAsImV4cCI6MjA4MDE3MDc4MH0.4z0nkUzu2p2WlnG4s6l14AYldQuvi5XKx1RtQTkObqg"
KRATER_TOKEN_URL="https://pdcpbtyfiyruhptwbsya.supabase.co/auth/v1/token?grant_type=refresh_token"

# YOUR Supabase (where tokens are stored)
DB_URL="https://dnfkyhstthmewqjdpgyz.supabase.co/rest/v1"
DB_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRuZmt5aHN0dGhtZXdxamRwZ3l6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyMDExNjksImV4cCI6MjA4NDc3NzE2OX0.HkThb6RnDd7dLmW7J1mW54p0amZReGC-pup8ROvL_04"

# --- FUNCTIONS ---

# Read the latest refresh token from Supabase
get_current_refresh_token() {
    curl -s "${DB_URL}/krater_tokens?order=created_at.desc&limit=1" \
        -H "apikey: ${DB_KEY}" 2>/dev/null | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['refresh_token'] if d else '')" 2>/dev/null
}

# Save tokens to Supabase (update existing row or insert new)
save_tokens() {
    local access_token="$1"
    local refresh_token="$2"
    local expires_at="$3"
    local user_email="$4"

    local existing
    existing=$(curl -s "${DB_URL}/krater_tokens?order=created_at.desc&limit=1" \
        -H "apikey: ${DB_KEY}" 2>/dev/null | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)

    if [ -n "$existing" ] && [ "$existing" != "" ]; then
        curl -s -X PATCH "${DB_URL}/krater_tokens?id=eq.${existing}" \
            -H "apikey: ${DB_KEY}" \
            -H "Content-Type: application/json" \
            -d "{\"access_token\":\"${access_token}\",\"refresh_token\":\"${refresh_token}\",\"expires_at\":${expires_at},\"user_email\":\"${user_email}\"}" \
            > /dev/null 2>&1
    else
        curl -s -X POST "${DB_URL}/krater_tokens" \
            -H "apikey: ${DB_KEY}" \
            -H "Content-Type: application/json" \
            -d "{\"access_token\":\"${access_token}\",\"refresh_token\":\"${refresh_token}\",\"expires_at\":${expires_at},\"user_email\":\"${user_email}\"}" \
            > /dev/null 2>&1
    fi
}

# Refresh the Krater tokens
refresh_tokens() {
    local current_refresh_token
    current_refresh_token=$(get_current_refresh_token)

    if [ -z "$current_refresh_token" ]; then
        echo "❌ ERROR: No refresh token found in Supabase."
        echo "   Run: ./krater_refresh.sh --set <refresh_token>"
        exit 1
    fi

    echo "🔄 Refreshing tokens..."
    echo "   Using refresh token: ${current_refresh_token:0:6}...${current_refresh_token: -4}"

    local response
    response=$(curl -s -X POST "$KRATER_TOKEN_URL" \
        -H "apikey: $KRATER_ANON_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"refresh_token\":\"$current_refresh_token\"}")

    # Check for errors
    local error
    error=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if 'error_code' in data:
        print(data.get('msg', data['error_code']))
    elif 'error' in data:
        print(data.get('error_description', data['error']))
except:
    print('Failed to parse response')
" 2>/dev/null)

    if [ -n "$error" ]; then
        echo "❌ ERROR: Token refresh failed: $error"
        echo ""
        echo "   Grab a fresh token from your browser:"
        echo "   1. Go to https://www.krater.ai/"
        echo "   2. DevTools (F12) → Application → Local Storage"
        echo "   3. Find key: sb-pdcpbtyfiyruhptwbsya-auth-token"
        echo "   4. Copy the refresh_token value"
        echo "   5. Run: ./krater_refresh.sh --set <paste_token_here>"
        exit 1
    fi

    # Parse and save to Supabase
    echo "$response" | python3 -c "
import json, sys
from datetime import datetime

data = json.load(sys.stdin)
exp_time = datetime.fromtimestamp(data['expires_at']).strftime('%I:%M:%S %p')
email = data.get('user', {}).get('email', 'unknown')

print(f'✅ Tokens refreshed successfully!')
print(f'')
print(f'   📧 User:           {email}')
print(f'   🔑 New JWT:        {data[\"access_token\"][:40]}...')
print(f'   🔄 New Refresh:    {data[\"refresh_token\"]}')
print(f'   ⏰ Expires at:     {exp_time} (in {data[\"expires_in\"]}s)')

# Output values for bash to capture
with open('/tmp/.krater_refresh_tmp', 'w') as f:
    json.dump({'at': data['access_token'], 'rt': data['refresh_token'], 'exp': data['expires_at'], 'email': email}, f)
" 2>/dev/null

    # Read parsed values and save to Supabase
    local new_access new_refresh new_expires new_email
    new_access=$(python3 -c "import json; print(json.load(open('/tmp/.krater_refresh_tmp'))['at'])")
    new_refresh=$(python3 -c "import json; print(json.load(open('/tmp/.krater_refresh_tmp'))['rt'])")
    new_expires=$(python3 -c "import json; print(json.load(open('/tmp/.krater_refresh_tmp'))['exp'])")
    new_email=$(python3 -c "import json; print(json.load(open('/tmp/.krater_refresh_tmp'))['email'])")
    rm -f /tmp/.krater_refresh_tmp

    save_tokens "$new_access" "$new_refresh" "$new_expires" "$new_email"
    echo "   ☁️  Saved to:       Supabase (dnfkyhstthmewqjdpgyz)"

    return 0
}

# Display current tokens from Supabase
show_tokens() {
    local data
    data=$(curl -s "${DB_URL}/krater_tokens?order=created_at.desc&limit=1" \
        -H "apikey: ${DB_KEY}" 2>/dev/null)

    echo "$data" | python3 -c "
import json, sys
from datetime import datetime

rows = json.load(sys.stdin)
if not rows:
    print('No tokens found in Supabase. Run the script first.')
    sys.exit(1)

t = rows[0]
exp_time = datetime.fromtimestamp(int(t['expires_at']))
now = datetime.now()
remaining = (exp_time - now).total_seconds()

print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print('📋 CURRENT TOKENS (from Supabase)')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print(f'JWT (access_token):')
print(f'  {t[\"access_token\"]}')
print()
print(f'Refresh token:')
print(f'  {t[\"refresh_token\"]}')
print()
if remaining > 0:
    print(f'⏰ Expires in {int(remaining // 60)} minutes ({exp_time.strftime(\"%I:%M:%S %p\")})')
else:
    print(f'⚠️  EXPIRED {int(-remaining // 60)} minutes ago! Run refresh to get new tokens.')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
" 2>/dev/null
}

# --- MAIN ---

case "${1:-}" in
    --loop)
        echo "🔁 Auto-refresh mode — refreshing every 50 minutes (Ctrl+C to stop)"
        echo ""
        while true; do
            refresh_tokens
            echo ""
            echo "💤 Sleeping 50 minutes until next refresh..."
            echo "   (Next refresh at $(date -v+50M '+%I:%M:%S %p'))"
            echo ""
            sleep 3000
        done
        ;;
    --show)
        show_tokens
        ;;
    --set)
        if [ -z "${2:-}" ]; then
            echo "❌ Usage: ./krater_refresh.sh --set <refresh_token>"
            exit 1
        fi
        echo "📝 Setting new refresh token: ${2:0:6}...${2: -4}"
        save_tokens "" "${2}" "0" "unknown"
        echo "✅ Token saved to Supabase. Now refreshing..."
        echo ""
        refresh_tokens
        ;;
    *)
        refresh_tokens
        echo ""
        echo "💡 Tip: Run with --loop   to auto-refresh every 50 minutes"
        echo "💡 Tip: Run with --show   to display current tokens"
        echo "💡 Tip: Run with --set    to set a new refresh token"
        ;;
esac
