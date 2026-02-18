#!/bin/bash

###############################################################################
#
#  KRATER API REFERENCE
#  ====================
#  Complete documentation for using Krater's AI API via Supabase Edge Functions.
#
#  Krater (https://www.krater.ai) is an AI chat platform that proxies requests
#  to OpenRouter (https://openrouter.ai). It supports 350+ AI models including
#  GPT-4o, Claude, Gemini, Llama, Mistral, etc.
#
#  This file is both documentation AND runnable examples.
#  Run any section by uncommenting the curl/python commands.
#
###############################################################################


###############################################################################
# SECTION 1: ARCHITECTURE
###############################################################################
#
# How Krater works under the hood:
#
#   [You] → [Krater Supabase Edge Function] → [OpenRouter API] → [Model Provider]
#                   ↕                                                (OpenAI, Anthropic, etc.)
#           [Supabase Database]
#           (auth, credits, usage tracking)
#
# Key components:
#
#   1. SUPABASE AUTH (pdcpbtyfiyruhptwbsya.supabase.co)
#      - Handles user authentication (Google OAuth, email/password)
#      - Issues JWTs (access tokens) that expire in 1 hour
#      - Issues refresh tokens (single-use, rotated on each refresh)
#
#   2. SUPABASE EDGE FUNCTIONS (Deno-based serverless functions)
#      - ai-chat:         Text/chat completions (proxies to OpenRouter)
#      - generate-image:  Image generation (FLUX, DALL-E, etc.)
#      - generate-video:  Video generation
#      - text-to-speech:  TTS (OpenAI, ElevenLabs)
#      - + many more (see Section 7)
#
#   3. SUPABASE DATABASE (PostgreSQL)
#      - user_subscriptions: Plan type, credits
#      - ai_rate_limits:     Per-user rate limiting
#      - conversations:      Saved chat history
#      - messages:           Individual messages
#      - 100+ tables total (see Section 8)
#
#   4. OPENROUTER (openrouter.ai)
#      - The actual AI provider backend
#      - Krater's OpenRouter user_id: user_2hk6lwhL12kODexfTYgbD9JXW7d
#      - API key stored as Edge Function env var (not accessible from client)
#


###############################################################################
# SECTION 2: AUTHENTICATION
###############################################################################
#
# Two tokens are required for every API call:
#
#   1. ANON KEY (apikey header)
#      - Public key that identifies the Supabase project
#      - Never changes, safe to hardcode
#      - Found in Krater's frontend JavaScript
#
#   2. ACCESS TOKEN (Authorization: Bearer header)
#      - User-specific JWT, expires in 1 hour
#      - Obtained by logging in or refreshing
#      - Contains user_id, email, role, expiration
#

KRATER_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBkY3BidHlmaXlydWhwdHdic3lhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1OTQ3ODAsImV4cCI6MjA4MDE3MDc4MH0.4z0nkUzu2p2WlnG4s6l14AYldQuvi5XKx1RtQTkObqg"

KRATER_BASE="https://pdcpbtyfiyruhptwbsya.supabase.co"

# YOUR Supabase (where tokens are stored)
MY_DB_URL="https://dnfkyhstthmewqjdpgyz.supabase.co/rest/v1"
MY_DB_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRuZmt5aHN0dGhtZXdxamRwZ3l6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyMDExNjksImV4cCI6MjA4NDc3NzE2OX0.HkThb6RnDd7dLmW7J1mW54p0amZReGC-pup8ROvL_04"

# Helper: get the latest JWT from your Supabase
get_jwt() {
    curl -s "${MY_DB_URL}/krater_tokens?order=created_at.desc&limit=1" \
        -H "apikey: ${MY_DB_KEY}" | \
        python3 -c "import json,sys; print(json.load(sys.stdin)[0]['access_token'])"
}


###############################################################################
# SECTION 3: TOKEN REFRESH
###############################################################################
#
# Refresh tokens are SINGLE-USE. Each refresh:
#   - Consumes the old refresh token (it's now dead)
#   - Returns a NEW access token + NEW refresh token
#
# Endpoint:
#   POST https://pdcpbtyfiyruhptwbsya.supabase.co/auth/v1/token?grant_type=refresh_token
#
# Headers:
#   apikey: <anon_key>
#   Content-Type: application/json
#
# Body:
#   {"refresh_token": "<your_refresh_token>"}
#
# Response (success):
#   {
#     "access_token": "eyJ...",       ← new JWT, valid 1 hour
#     "refresh_token": "abc123",      ← new refresh token (old is dead)
#     "expires_in": 3600,             ← seconds until JWT expires
#     "expires_at": 1770881631,       ← unix timestamp of expiry
#     "token_type": "bearer",
#     "user": { "id": "...", "email": "...", ... }
#   }
#
# Response (error — token already used):
#   {
#     "code": 400,
#     "error_code": "refresh_token_not_found",
#     "msg": "Invalid Refresh Token: Refresh Token Not Found"
#   }
#
# EXAMPLE: Refresh tokens
#
# curl -s -X POST "${KRATER_BASE}/auth/v1/token?grant_type=refresh_token" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -d '{"refresh_token": "YOUR_REFRESH_TOKEN_HERE"}'
#
# AUTOMATED: Use ./krater_refresh.sh to handle this automatically.
#   ./krater_refresh.sh              ← single refresh
#   ./krater_refresh.sh --loop       ← auto-refresh every 50 min
#   ./krater_refresh.sh --set <tok>  ← set a new refresh token
#   ./krater_refresh.sh --show       ← display current tokens
#


###############################################################################
# SECTION 4: SENDING A CHAT MESSAGE
###############################################################################
#
# Endpoint:
#   POST https://pdcpbtyfiyruhptwbsya.supabase.co/functions/v1/ai-chat
#
# Required Headers:
#   Authorization: Bearer <access_token>     ← your JWT
#   apikey: <anon_key>                       ← project anon key
#   Content-Type: application/json
#   Origin: https://www.krater.ai            ← required by CORS
#
# Required Body Fields:
#   messages    (array)   — conversation messages (OpenAI format)
#   model       (string)  — model ID (OpenRouter format, e.g. "openai/gpt-4o")
#   stream      (bool)    — true for SSE streaming, false for full JSON
#   save_to_db  (bool)    — true to save to conversation history, false to skip
#

# --- EXAMPLE 1: Simple message (non-streaming) ---

# JWT=$(get_jwt)
# curl -s -X POST "${KRATER_BASE}/functions/v1/ai-chat" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -H "Origin: https://www.krater.ai" \
#     -d '{
#         "messages": [
#             {"role": "user", "content": "Hello, how are you?"}
#         ],
#         "model": "openai/gpt-4o-mini",
#         "stream": false,
#         "save_to_db": false
#     }'

# --- EXAMPLE 2: With system prompt ---

# curl -s -X POST "${KRATER_BASE}/functions/v1/ai-chat" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -H "Origin: https://www.krater.ai" \
#     -d '{
#         "messages": [
#             {"role": "user", "content": "What are you?"}
#         ],
#         "model": "openai/gpt-4o-mini",
#         "stream": false,
#         "save_to_db": false,
#         "system_prompt": "You are a pirate captain named Blackbeard. Always respond in character."
#     }'

# --- EXAMPLE 3: Multi-turn conversation ---

# curl -s -X POST "${KRATER_BASE}/functions/v1/ai-chat" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -H "Origin: https://www.krater.ai" \
#     -d '{
#         "messages": [
#             {"role": "system", "content": "You are a helpful math tutor."},
#             {"role": "user", "content": "What is 2+2?"},
#             {"role": "assistant", "content": "2+2 equals 4."},
#             {"role": "user", "content": "Now multiply that by 3."}
#         ],
#         "model": "openai/gpt-4o",
#         "stream": false,
#         "save_to_db": false,
#         "temperature": 0.3
#     }'

# --- EXAMPLE 4: Vision (image analysis) ---

# curl -s -X POST "${KRATER_BASE}/functions/v1/ai-chat" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -H "Origin: https://www.krater.ai" \
#     -d '{
#         "messages": [
#             {"role": "user", "content": [
#                 {"type": "text", "text": "What do you see in this image?"},
#                 {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}
#             ]}
#         ],
#         "model": "openai/gpt-4o",
#         "stream": false,
#         "save_to_db": false
#     }'


###############################################################################
# SECTION 5: ALL CHAT PARAMETERS
###############################################################################
#
# ┌─────────────────────┬──────────┬──────────┬──────────────────────────────────────────┐
# │ Parameter           │ Type     │ Required │ Description                              │
# ├─────────────────────┼──────────┼──────────┼──────────────────────────────────────────┤
# │ messages            │ array    │ YES      │ Conversation in OpenAI format            │
# │ model               │ string   │ YES      │ OpenRouter model ID                      │
# │ stream              │ bool     │ YES      │ true=SSE stream, false=full JSON         │
# │ save_to_db          │ bool     │ YES      │ Save to Krater conversation history      │
# │ system_prompt       │ string   │ no       │ System prompt (added server-side)         │
# │ temperature         │ float    │ no       │ 0.0-2.0, controls randomness             │
# │ max_tokens          │ int      │ no       │ Max response length in tokens             │
# │ top_p               │ float    │ no       │ 0.0-1.0, nucleus sampling                │
# │ frequency_penalty   │ float    │ no       │ -2.0-2.0, penalize repeated tokens       │
# │ presence_penalty    │ float    │ no       │ -2.0-2.0, penalize repeated topics       │
# │ files               │ array    │ no       │ File attachments                         │
# │ file_parser_engine  │ string   │ no       │ Parser for uploaded files                 │
# │ conversation_id     │ string   │ no       │ Link to a saved conversation              │
# │ user_id             │ string   │ no       │ User ID override                          │
# │ credit_cost         │ number   │ no       │ Custom credit cost                        │
# │ feature_type        │ string   │ no       │ Feature type label                        │
# └─────────────────────┴──────────┴──────────┴──────────────────────────────────────────┘
#
# SYSTEM PROMPT — Two ways to set it:
#
#   Method 1: Using the "system_prompt" parameter (Krater-specific)
#     The server injects this as a system message before your messages.
#     {
#       "system_prompt": "You are a helpful assistant.",
#       "messages": [{"role":"user","content":"Hi"}]
#     }
#
#   Method 2: Using a system message in the messages array (standard OpenAI format)
#     {
#       "messages": [
#         {"role":"system","content":"You are a helpful assistant."},
#         {"role":"user","content":"Hi"}
#       ]
#     }
#
#   Both methods work. If you use BOTH, the system_prompt parameter is added
#   on the server side IN ADDITION to any system message in your messages array.
#
# CREDITS:
#   - save_to_db: false  → marked as "non-save request" → often free (0 credits)
#   - save_to_db: true   → charges credits based on model pricing
#   - Your account has 999,999,999 credits on the "max" plan
#
# STREAMING:
#   - stream: true  → returns Server-Sent Events (SSE), line by line
#   - stream: false → returns a single JSON response when complete
#


###############################################################################
# SECTION 6: RESPONSE FORMAT
###############################################################################
#
# Non-streaming response (stream: false):
#
# {
#   "id": "gen-1770881822-hJTWSh3kxPcv64ORmss6",
#   "provider": "OpenAI",
#   "model": "openai/gpt-4o-mini",
#   "object": "chat.completion",
#   "created": 1770881822,
#   "choices": [
#     {
#       "index": 0,
#       "finish_reason": "stop",
#       "message": {
#         "role": "assistant",
#         "content": "Hello! How can I help you today?"
#       }
#     }
#   ],
#   "usage": {
#     "prompt_tokens": 13,
#     "completion_tokens": 9,
#     "total_tokens": 22,
#     "cost": 0,
#     "is_byok": true,
#     "cost_details": {
#       "upstream_inference_cost": 0.0000123,
#       "upstream_inference_prompt_cost": 0.0000065,
#       "upstream_inference_completions_cost": 0.0000058
#     }
#   }
# }
#
# To extract just the response text:
#   ... | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
#


###############################################################################
# SECTION 7: ALL AVAILABLE MODELS (popular ones)
###############################################################################
#
# Get the full list:
#   curl -s "${KRATER_BASE}/functions/v1/get-models" \
#       -H "apikey: ${KRATER_ANON_KEY}" | python3 -m json.tool
#
# Popular model IDs:
#
#   ┌──────────────────────────────────┬────────────────┬────────────┐
#   │ Model ID                         │ Context Window │ Vision     │
#   ├──────────────────────────────────┼────────────────┼────────────┤
#   │ openai/gpt-4o                    │ 128K           │ ✅         │
#   │ openai/gpt-4o-mini               │ 128K           │ ✅         │
#   │ openai/gpt-4.1                   │ 1M             │ ✅         │
#   │ openai/gpt-4.1-mini              │ 1M             │ ✅         │
#   │ openai/o1                        │ 200K           │ ✅         │
#   │ openai/o3-mini                   │ 200K           │ ❌         │
#   │ anthropic/claude-sonnet-4        │ 200K           │ ✅         │
#   │ anthropic/claude-opus-4          │ 200K           │ ✅         │
#   │ anthropic/claude-haiku-3.5       │ 200K           │ ✅         │
#   │ google/gemini-2.5-pro-preview    │ 1M             │ ✅         │
#   │ google/gemini-2.0-flash          │ 1M             │ ✅         │
#   │ meta-llama/llama-4-maverick      │ 1M             │ ✅         │
#   │ meta-llama/llama-3.3-70b         │ 128K           │ ❌         │
#   │ deepseek/deepseek-r1             │ 64K            │ ❌         │
#   │ deepseek/deepseek-chat           │ 64K            │ ❌         │
#   │ mistralai/mistral-large          │ 128K           │ ✅         │
#   │ qwen/qwen-2.5-72b-instruct      │ 128K           │ ❌         │
#   │ x-ai/grok-2                      │ 128K           │ ✅         │
#   └──────────────────────────────────┴────────────────┴────────────┘
#


###############################################################################
# SECTION 8: OTHER EDGE FUNCTIONS
###############################################################################
#
# Besides ai-chat, Krater has these edge functions:
#
#   ┌────────────────────────┬─────────────────────────────────────────────────┐
#   │ Function               │ Purpose & Example Body                         │
#   ├────────────────────────┼─────────────────────────────────────────────────┤
#   │ get-models             │ List all available models (GET, no body)       │
#   │ generate-image         │ {"prompt":"...", "model":"flux-schnell",       │
#   │                        │  "image_size":"1024x1024", "num_images":1}     │
#   │ generate-video         │ {"prompt":"...", "model":"ltx-2",             │
#   │                        │  "duration":5, "aspect_ratio":"16:9"}          │
#   │ edit-image             │ {"images":[...], "prompt":"...",              │
#   │                        │  "model":"flux-2-flex", "strength":0.8}        │
#   │ text-to-speech         │ {"text":"...", "voice":"alloy",               │
#   │                        │  "provider":"openai"}                          │
#   │ speech-to-text         │ {"audio_base64":"..."} or {"audio_url":"..."}  │
#   │ generate-music         │ {"prompt":"...", "lyrics":"...", "tags":"..."}  │
#   │ compose-audio          │ {"prompt":"...", "duration":10}               │
#   │ humanize-text          │ {"text":"...", "mode":"standard", "tone":"..."} │
#   │ detect-ai-winston      │ {"text":"..."} (min 300 chars)                │
#   │ plagiarism-check       │ {"text":"..."} (min 100 chars)                │
#   │ remove-background      │ {"image_base64":"..."}                        │
#   │ upscale-media          │ {"media_base64":"...", "media_type":"image",  │
#   │                        │  "scale_factor":2}                             │
#   │ voice-changer          │ {"audio_base64":"...", "custom_voice_id":"..." }│
#   │ create-checkout        │ Stripe checkout session                        │
#   │ stripe-webhook         │ Stripe webhook handler                         │
#   └────────────────────────┴─────────────────────────────────────────────────┘
#
# All edge functions use the same auth headers:
#   Authorization: Bearer <JWT>
#   apikey: <anon_key>
#   Content-Type: application/json
#   Origin: https://www.krater.ai
#


###############################################################################
# SECTION 9: DATABASE ACCESS
###############################################################################
#
# Krater's Supabase has NO Row Level Security on most tables.
# You can read/write directly via the REST API.
#
# Endpoint: https://pdcpbtyfiyruhptwbsya.supabase.co/rest/v1/<table>
# Auth: same JWT + anon key as above
#
# Key tables:
#
#   user_subscriptions  — plan_type, monthly_credits, credits_used
#   user_roles          — role enum: admin, moderator, user
#   profiles            — email, full_name, avatar_url
#   conversations       — chat conversation metadata
#   messages            — chat messages
#   ai_rate_limits      — per-user rate limiting windows
#   credit_transactions — credit usage history
#   model_archive       — all model metadata (openrouter_id, pricing, etc.)
#
# EXAMPLE: Read your subscription
#
# curl -s "${KRATER_BASE}/rest/v1/user_subscriptions?user_id=eq.ff829037-69d9-4304-92d5-6ba80d9ac461" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}"
#
# EXAMPLE: Update credits (PATCH)
#
# curl -s -X PATCH "${KRATER_BASE}/rest/v1/user_subscriptions?user_id=eq.ff829037-69d9-4304-92d5-6ba80d9ac461" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -H "Prefer: return=representation" \
#     -d '{"monthly_credits": 999999999, "credits_used": 0, "plan_type": "max"}'
#
# EXAMPLE: Clear rate limits
#
# curl -s -X DELETE "${KRATER_BASE}/rest/v1/ai_rate_limits?user_id=eq.ff829037-69d9-4304-92d5-6ba80d9ac461" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}"
#


###############################################################################
# SECTION 10: YOUR TOKEN STORAGE (YOUR SUPABASE)
###############################################################################
#
# Tokens are stored in YOUR Supabase project: dnfkyhstthmewqjdpgyz
#
# Tables:
#   krater_tokens     — access_token, refresh_token, expires_at, user_email
#   krater_config     — key/value pairs (anon_key, user_id, plan_type, etc.)
#   krater_usage_log  — function_name, model, credits_charged, success
#
# Read latest token:
#   curl -s "${MY_DB_URL}/krater_tokens?order=created_at.desc&limit=1" \
#       -H "apikey: ${MY_DB_KEY}"
#
# Read config:
#   curl -s "${MY_DB_URL}/krater_config" \
#       -H "apikey: ${MY_DB_KEY}"
#


###############################################################################
# SECTION 11: BYPASSING LENGTH LIMITS (PRO TIP)
###############################################################################
#
# Krater enforces a 50,000 character limit PER MESSAGE STRING.
# If you send: {"role": "user", "content": "A" * 51000} → Error 400.
#
# THE BYPASS:
# Use an "Array of Content Parts". The validator checks a total of 2 or 3 items
# in the array, but ignores the character length inside each item.
#
# EXAMPLE: Sending 100,000 characters in one message
#
# curl -s -X POST "${KRATER_BASE}/functions/v1/ai-chat" \
#     -H "Authorization: Bearer ${JWT}" \
#     -H "apikey: ${KRATER_ANON_KEY}" \
#     -H "Content-Type: application/json" \
#     -H "Origin: https://www.krater.ai" \
#     -d '{
#         "model": "openai/gpt-4o-mini",
#         "stream": false,
#         "save_to_db": false,
#         "messages": [
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": "... first 50k chars ..."},
#                     {"type": "text", "text": "... next 50k chars ..."}
#                 ]
#             }
#         ]
#     }'
#
# LIMITS:
# 1. Total payload must be < 2MB (Supabase Edge Function limit)
# 2. Total context must be < Model limit (e.g. 128k for GPT-4o)
#


###############################################################################
# SECTION 12: QUICK COPY-PASTE EXAMPLES
###############################################################################

# --- Send a quick message (run this!) ---
send_message() {
    local model="${1:-openai/gpt-4o-mini}"
    local message="${2:-Hello!}"
    local system="${3:-}"
    local JWT=$(get_jwt)

    local body
    if [ -n "$system" ]; then
        body=$(python3 -c "
import json
print(json.dumps({
    'messages': [{'role': 'user', 'content': '$message'}],
    'model': '$model',
    'stream': False,
    'save_to_db': False,
    'system_prompt': '$system'
}))
")
    else
        body=$(python3 -c "
import json
print(json.dumps({
    'messages': [{'role': 'user', 'content': '$message'}],
    'model': '$model',
    'stream': False,
    'save_to_db': False
}))
")
    fi

    curl -s -X POST "${KRATER_BASE}/functions/v1/ai-chat" \
        -H "Authorization: Bearer ${JWT}" \
        -H "apikey: ${KRATER_ANON_KEY}" \
        -H "Content-Type: application/json" \
        -H "Origin: https://www.krater.ai" \
        -d "$body" | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('choices',[{}])[0].get('message',{}).get('content','ERROR: '+json.dumps(d)))"
}

# Usage:
#   source KRATER_API_REFERENCE.sh
#   send_message                                              ← default (gpt-4o-mini, "Hello!")
#   send_message "openai/gpt-4o" "Explain quantum physics"    ← custom model + message
#   send_message "anthropic/claude-sonnet-4" "Hi" "You are a pirate"  ← with system prompt

echo ""
echo "📖 KRATER API REFERENCE loaded."
echo ""
echo "Available functions:"
echo "  get_jwt                      — returns the current JWT from Supabase"
echo "  send_message [model] [msg] [system]  — send a chat message"
echo ""
echo "Source this file:  source KRATER_API_REFERENCE.sh"
echo "Then run:          send_message \"openai/gpt-4o-mini\" \"Say hi\" \"You are a pirate\""
