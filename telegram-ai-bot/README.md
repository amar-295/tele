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

Requires `python-telegram-bot[job-queue]` (already in `requirements.txt`). The first digest runs about two minutes after startup, then on the interval you set. Only `OWNER_CHAT_ID` receives these messages.

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
3. Add your 3 env vars in the Railway dashboard
4. Done — runs 24/7 for free

> Note: Railway's free tier has sleep on inactivity. For always-on free hosting,
> use a VPS (Hetzner Cloud starts at €3.29/mo) or run on your own machine.

---

## Deploy on Render

This bot uses **long polling** (`python main.py`), so run it as a [**Background Worker**](https://render.com/docs/background-workers), not a public web service.

**Note:** Render’s **free** instance type does **not** apply to background workers. You need at least a **Starter** worker (paid). See [Render pricing](https://render.com/pricing).

### Option A — Blueprint (monorepo)

If your Git repo root matches this workspace (parent folder + `telegram-ai-bot/`):

1. Push to GitHub. The repo root should include [`render.yaml`](../render.yaml) next to the `telegram-ai-bot/` folder.
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** → select the repo.
3. Set secret env vars when prompted: `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`, `GROQ_API_KEY`.
4. Deploy. Build uses `rootDir: telegram-ai-bot` and runs `pip install -r requirements.txt` then `python main.py`.

The included blueprint attaches a **1 GB persistent disk** and sets `CHROMA_PATH`, `DB_PATH`, and `LOGS_PATH` under `/var/renderdisk` so memory survives redeploys. To use ephemeral storage only, remove the `disk` block and the three path env entries from `render.yaml`.

### Option B — Manual worker

1. **New** → **Background Worker** → connect the repo.
2. **Root Directory:** `telegram-ai-bot` if the app lives in that subfolder.
3. **Build command:** `pip install -r requirements.txt`  
   **Start command:** `python main.py`
4. Add environment variables from [`.env.example`](.env.example) (minimum: `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`, `GROQ_API_KEY`).
5. Optional: [Persistent disk](https://render.com/docs/disks) mounted e.g. at `/var/renderdisk`, then set `CHROMA_PATH`, `DB_PATH`, `LOGS_PATH` under that mount.

If the Git repo **is** only the `telegram-ai-bot` folder, put `render.yaml` in that repo’s root, remove the `rootDir` line from the service, and use the Blueprint from that repo.

Message your bot once the service is **Live**.
