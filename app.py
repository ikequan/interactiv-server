import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests
import psycopg2

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_03OFdNuJbEQq@ep-sparkling-math-adb5h9qe-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "dev")
PORT = int(os.getenv("PORT", "5001"))  # run on 5001
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_METHODS = "GET,POST,OPTIONS"
ALLOWED_HEADERS = "Authorization,Content-Type"

app = Flask(__name__)

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Initialize database tables"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create api_keys table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                token VARCHAR PRIMARY KEY,
                commenting_tone VARCHAR DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Initialize database on startup
init_db()

def get_bearer_from_header():
    auth = request.headers.get("Authorization", "")
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

def get_token_row(token):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT token, commenting_tone FROM api_keys WHERE token = %s", (token,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                'token': row[0],
                'commenting_tone': row[1]
            }
        return None
    except Exception as e:
        print(f"Database query error: {e}")
        return None

@app.after_request
def apply_cors(resp):
    origin = request.headers.get("Origin")
    # Allow any origin (safe here because we don't use cookies/credentials)
    if ALLOWED_ORIGINS == "*":
        resp.headers["Access-Control-Allow-Origin"] = "*"
    else:
        allowed = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
        if origin in allowed:
            resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
    resp.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
    resp.headers["Access-Control-Max-Age"] = "86400"
    return resp

@app.route("/api/create_api_key", methods=["POST", "OPTIONS"])
def create_api_key():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.headers.get("X-Admin-Secret") != ADMIN_SECRET:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token", "").strip()
    commenting_tone = (data.get("commenting_tone") or "").strip()
    if not token:
        return jsonify({"error": "token required"}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Use UPSERT (INSERT ... ON CONFLICT)
        cur.execute("""
            INSERT INTO api_keys (token, commenting_tone, created_at) 
            VALUES (%s, %s, %s)
            ON CONFLICT (token) 
            DO UPDATE SET 
                commenting_tone = EXCLUDED.commenting_tone,
                created_at = EXCLUDED.created_at
        """, (token, commenting_tone, datetime.now(timezone.utc)))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True, "token": token})
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.get("/health")
def health():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({"ok": True, "database": "connected"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/generate_comment", methods=["POST", "OPTIONS"])
def generate_comment():
    if request.method == "OPTIONS":
        return ("", 204)

    token = get_bearer_from_header()
    if not token:
        return jsonify({"error": "missing bearer"}), 401
    row = get_token_row(token)
    if not row:
        return jsonify({"error": "invalid token"}), 401

    data = request.get_json(force=True, silent=True) or {}
    post_description = (data.get("post_description") or "").strip()
    comment_to_reply_to = (data.get("comment_to_reply_to") or "").strip()
    user_commenting_tone = (data.get("commenting_tone") or "").strip()

    system_parts = [
        "You are an expert facebook page manager in charge of user interaction and engagement, your goal is to keep",
        "user engaged and active by reply to their comments in a way that keeps the conversation going, your target to",
        "spark debate and discussion. and you don't always have to agree with the user, you can disagree and argue with them",
        "in a meaningful and respectful way. The the info improved to get the context of the post and the user's comment. The reply should be in the same language as the user's comment.",
        "Note: long comments should be replied in a longer way and short comments should be replied in a shorter way."
        "Throw in some emojis when needed, don't ambuse this"
    ]
    tone = user_commenting_tone or (row["commenting_tone"] or "")
    if tone:
        system_parts.append("Always consider this user commenting preference:")
        system_parts.append(tone)
    system_prompt = "\n".join(system_parts)

    user_prompt = f"""post_description:{post_description}, 
comment_to_reply_to: {comment_to_reply_to}""".strip()

    if not XAI_API_KEY:
        return jsonify({"reply": "Interesting take. What specific evidence leads you there?", "mock": True})

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "model": "grok-4-latest",
        "stream": False,
        "temperature": 0.5
    }

    try:
        resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {XAI_API_KEY}"
            },
            json=payload,
            timeout=60
        )
        if resp.status_code != 200:
            return jsonify({"error": "x.ai error", "details": resp.text}), 502
        out = resp.json()
        reply = out.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not reply:
            reply = "Appreciate your perspective—can you expand a bit more?"
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": "request failed", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)