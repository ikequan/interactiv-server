import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests
import psycopg2
from llm import get_ai_service

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

    # Combine user-provided tone with stored tone
    tone = user_commenting_tone or (row["commenting_tone"] or "")
    
    try:
        # Get the AI service (defaults to 'xai' if AI_SERVICE env var not set)
        ai_service = get_ai_service()
        
        # Generate comment using the modular AI service
        reply = ai_service.generate_comment(
            post_description=post_description,
            comment_to_reply_to=comment_to_reply_to,
            commenting_tone=tone
        )
        
        return jsonify({"reply": reply})
        
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"Comment generation failed: {str(e)}")
        return jsonify({"error": "request failed", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)