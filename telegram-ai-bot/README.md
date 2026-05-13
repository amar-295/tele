# Personal AI Telegram Bot

A production-grade Telegram bot that learns from your conversations using
vector memory, fact extraction, and Groq-hosted LLMs. Built for personal use — only
responds to you.

## Setup (5 minutes, zero cost)

### 1. Get your credentials

| What | Where | Free? |
|------|-------|-------|
| Telegram bot token | Message `@BotFather`, send `/newbot` | ✅ Always |
| Your chat ID | Message `@userinfobot`, send `/start` | ✅ Always |
| Groq API key | https://console.groq.com (OpenAI-compatible endpoint) | Generous free tier |

### 2. Install & configure

```bash
git clone <your-repo>
cd telegram-ai-bot

pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in your Telegram + Groq values
```

### 3. Run

```bash
python main.py
```

Open Telegram, message your bot. It's alive.

**Local default:** leave `TELEGRAM_WEBHOOK_URL` unset to use **long polling** (no public URL needed).

**Cloud (Render, Railway, etc.):** set **webhooks** — see [Webhooks](#webhooks-telegram) below.

Copy `.env.example` to `.env` and fill in the three required values. Never commit `.env` (it is gitignored).

**Windows:** If `pip install -r requirements.txt` fails while building `chroma-hnswlib`, install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Desktop development with C++ workload) and retry, or use a Python version for which Chroma publishes prebuilt wheels.

---

## Tuning memory and cost

After you have real conversations, adjust these in `.env` if recall feels wrong or API cost is high:

| Variable | What it does | If recall is too noisy | If recall misses context |
|----------|----------------|-------------------------|---------------------------|
| `MEMORY_THRESHOLD` | Max cosine distance to keep a Chroma hit (stricter = lower number) | Lower it (for example `0.45`–`0.55`) | Raise it (for example `0.65`–`0.75`) |
| `MEMORY_TOP_K` | How many hits to pull from each Chroma collection before merge | Lower (for example `4`–`6`) | Raise (for example `10`–`12`) |
| `MAX_HISTORY_MESSAGES` | Cap on recent turns before token trim | Lower to save tokens | Raise if the bot forgets the immediate thread |
| `MAX_HISTORY_TOKENS` | Approximate token budget for trimmed history | Lower to save cost | Raise if long threads get cut too aggressively |
| `MAX_FACTS_IN_PROMPT` | Bullet facts injected into the system prompt | Lower if the prompt feels crowded | Raise if important facts are omitted |

Defaults are conservative for a personal bot; change one knob at a time.

---

## Proactive check-ins (optional)

By default the bot only replies when you message it. To get periodic **stats-only** check-ins (no extra LLM call), set in `.env`:

```env
PROACTIVE_DIGEST_ENABLED=true
PROACTIVE_DIGEST_INTERVAL_HOURS=24
```

Requires `python-telegram-bot[job-queue,webhooks]` (see `requirements.txt`). The first digest runs about two minutes after startup, then on the interval you set. Only `OWNER_CHAT_ID` receives these messages.

---

## Webhooks (Telegram)

If `TELEGRAM_WEBHOOK_URL` and `TELEGRAM_WEBHOOK_SECRET` are set in `.env`, the bot runs in **webhook** mode (embedded HTTP server via `python-telegram-bot[webhooks]`). Otherwise it uses **long polling** (default for local dev).

1. **HTTPS URL** Telegram can reach (production). Example: `https://your-service.onrender.com/telegram` — the path (`telegram` here) must match the path your host forwards to the app. If you omit a path (e.g. `https://host.com` only), the app defaults the path to `telegram`.
2. **`TELEGRAM_WEBHOOK_SECRET`** — long random string; Telegram sends it as `X-Telegram-Bot-Api-Secret-Token` and PTB rejects wrong/missing values.
3. **`PORT`** — bind port for the webhook server (Render injects `PORT`, often `10000`).
4. **`WEBHOOK_LISTEN`** — default `0.0.0.0`.
5. **`DROP_PENDING_UPDATES`** — optional `true` to clear pending updates when the webhook is set.

**Local testing:** use [ngrok](https://ngrok.com/) (or similar) to expose `http://localhost:PORT` as HTTPS, then set `TELEGRAM_WEBHOOK_URL` to the ngrok HTTPS URL including the path.

---

## Commands

| Command | What it does |
|---------|-------------|
| `/remember <fact>` | Force-save a fact about yourself |
| `/forget <keyword>` | Delete memories matching keyword |
| `/memory` | List all stored facts |
| `/clear` | Wipe conversation history (facts kept) |
| `/stats` | Show usage and memory stats |

---

## Architecture

```
You (Telegram)
      ↓
Bot server (python-telegram-bot)
  ├─ Long polling OR HTTPS webhook (env-driven)
  ├─ Rate filter (owner-only hard gate)
  ├─ Error boundary (never crashes)
  └─ Message handler
         ↓
   AI Pipeline
     1. Fetch: history (SQLite) + facts (SQLite) + recall (ChromaDB)  ← parallel
     2. Build system prompt with injected memory
     3. Trim history to token budget
     4. Call Groq API (retry + backoff)
     5. Save reply to SQLite
     6. Background: embed exchange → ChromaDB
     7. Background: extract new facts → SQLite + ChromaDB
         ↓
   Storage (100% local)
     ├─ SQLite (WAL)  — messages, facts, stats
     └─ ChromaDB      — vector embeddings (facts + conversations)

Optional: JobQueue periodic digest → owner chat (stats only, see README)
```

---

## Deploy free on Railway

1. Push to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add environment variables from [`.env.example`](.env.example) (at minimum `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`, `GROQ_API_KEY`). For **HTTPS webhooks** on a public URL, also set `TELEGRAM_WEBHOOK_URL` and `TELEGRAM_WEBHOOK_SECRET` (see [Webhooks](#webhooks-telegram)).
4. Done — runs 24/7 for free

> Note: Railway's free tier has sleep on inactivity. For always-on free hosting,
> use a VPS (Hetzner Cloud starts at €3.29/mo) or run on your own machine.

---

## Deploy on Render (webhooks + free web tier)

The blueprint at [`render.yaml`](../render.yaml) defines a **Web** service (not a background worker) so Telegram can **POST** updates over HTTPS while staying on Render’s **free** web plan.

1. Push the repo (root contains `render.yaml` and `telegram-ai-bot/`).
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** → connect the repo.
3. After the first deploy, note the service URL, e.g. `https://telegram-ai-bot.onrender.com`.
4. In the service **Environment**, set:
   - `TELEGRAM_WEBHOOK_URL` = `https://<your-host>/<path>` (example: `https://telegram-ai-bot.onrender.com/telegram`). Path must match what you choose; default path segment if you use only the hostname is `telegram` — see [Webhooks](#webhooks-telegram).
   - `TELEGRAM_WEBHOOK_SECRET` = a long random string.
   - Existing secrets: `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`, `GROQ_API_KEY`.
5. **Redeploy** (or restart) so the process starts with the webhook env set. Telegram will call your HTTPS URL; Render forwards to `PORT`.

**Python on Render:** new services default to **Python 3.14**, which can break `python-telegram-bot` 21.x. This repo pins **`PYTHON_VERSION=3.12.8`** in the blueprint (and includes [`.python-version`](.python-version)). If you create the service manually, set that env var to a **full** `3.12.x` patch (see [Render Python version](https://render.com/docs/python-version)).

**Port:** Render sets **`PORT`**; the bot uses it in webhook mode. After deploy, set **`TELEGRAM_WEBHOOK_URL`** and **`TELEGRAM_WEBHOOK_SECRET`**, then redeploy so the process starts in webhook mode and listens on `PORT`.


Create a **Web Service**, root directory `telegram-ai-bot`, build `pip install -r requirements.txt`, start `python main.py`, set the same environment variables as the blueprint.

If the Git repo **is** only the `telegram-ai-bot` folder, put `render.yaml` in that repo’s root and remove the `rootDir` line.

Message your bot once logs show webhook mode and the service is **Live**.
