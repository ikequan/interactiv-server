# InterActiv Flask Server

A tiny Flask service that authenticates requests with **Bearer tokens** (stored in **SQLite**) and calls
**x.ai** (`grok-4-latest`) to generate a comment reply. It mirrors the prompt structure you provided.

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env
# Edit .env:
#   XAI_API_KEY=sk-... (from x.ai)
#   ADMIN_SECRET=some-strong-string
#   PORT=5000
python app.py
```

The DB `server/interactiv.db` is created automatically with a single table:

```sql
CREATE TABLE IF NOT EXISTS api_keys (
  token TEXT PRIMARY KEY,
  commenting_tone TEXT DEFAULT '',
  created_at TEXT DEFAULT ''
);
```

---

## Authentication Model

- Clients send `Authorization: Bearer <token>`
- Tokens are created via an **admin‑protected** endpoint and stored with an optional default `commenting_tone`

### Create/Upsert a Token

```
POST /api/create_api_key
Headers:
  X-Admin-Secret: <ADMIN_SECRET from .env>
  Content-Type: application/json
Body:
  {
    "token": "YOUR_RANDOM_TOKEN",
    "commenting_tone": "witty but respectful"
  }
Response: { "ok": true, "token": "YOUR_RANDOM_TOKEN" }
```

> There’s no “list tokens” endpoint in this minimal sample. You can inspect tokens locally:
> ```bash
> sqlite3 interactiv.db 'select * from api_keys;'
> ```

---

## Generate Comment

```
POST /api/generate_comment
Headers:
  Authorization: Bearer <token>
  Content-Type: application/json
Body:
  {
    "post_description": "<post text>",
    "comment_to_reply_to": "<target comment>",
    "commenting_tone": "<optional per-request tone override>"
  }
Response:
  { "reply": "..." }
```

### Prompting

- **system_prompt**

  > You are an expert facebook page manager in charge of user interaction and engagement, your goal is to keep
  > user engaged and active by reply to their comments in a way that keeps the conversation going, your target to
  > spark debate and discussion. and you don't always have to agree with the user, you can disagree and argue with them
  > in a meaningful and respectful way. The the info improved to get the context of the post and the user's comment. The reply should be in the same language as the user's comment.  
  > Note: long comments should be replied in a longer way and short comments should be replied in a shorter way.  
  > *(If a tone exists, it is appended as: “Always consider this user commenting preference: …”)*

- **user_prompt**

  ```
  post_description:{post_description}, 
  comment_to_reply_to: {comment_to_reply_to}
  ```

### x.ai Call

```json
{
  "messages": [
    { "role": "system", "content": "<system_prompt>" },
    { "role": "user",   "content": "<user_prompt>" }
  ],
  "model": "grok-4-latest",
  "stream": false,
  "temperature": 0
}
```

If `XAI_API_KEY` is not configured, the server returns a simple deterministic fallback line.

---

## Deployment Notes

- Bind `PORT` via `.env`, default `5000`
- For production, proxy through Nginx and run with Gunicorn/Uvicorn
- Restrict admin access to `/api/create_api_key`
- Back up `interactiv.db` regularly

---

## Health Check

```
GET /health -> { "ok": true }
```

---

## Error Codes

- `401` Missing/invalid bearer token
- `403` Invalid admin secret (create key)
- `502` Upstream x.ai error
- `500` Server exception (network/timeout etc.)
