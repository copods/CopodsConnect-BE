# Copods Connect — Backend API

FastAPI backend for Copods Connect, using **PostgreSQL** and [**Prisma Client Python**](https://github.com/RobertCraigie/prisma-client-py) for persistence and **Google OAuth** for authentication.

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python** 3.10+ | 3.12 works; match your team if pinned elsewhere |
| **PostgreSQL** | Local, Docker, or hosted (e.g. Supabase) |
| **Git** | For clone / pull workflows |

Recommended: Python **virtual environment** (`venv`).  
Optional: **Node.js / npm** if you prefer running the Prisma CLI with `npx prisma` instead of invoking it through Python.

## Environment variables

**Actual secret values, URLs, and keys for this project are shared separately in Google Chat.** Do not paste real credentials into GitHub issues, pull requests, or this repository.

Create a **`.env`** file in the **repository root** (next to `main.py`). `.env` is gitignored — never commit it.

Use this structure (fill values from Google Chat):

```env
# --- PostgreSQL ---
# Pooler/session URL for the running app (as required by your host)
DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"

# Direct URL for migrations (often required on Supabase and similar hosts)
DIRECT_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"

# --- JWT ---
JWT_SECRET="your-secret-here"
# Optional — defaults to 24 if omitted
JWT_EXPIRE_HOURS="24"

# --- Google OAuth ---
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
# Must exactly match redirect URIs in Google Cloud Console
GOOGLE_REDIRECT_URI="http://localhost:5173/auth/callback"

# --- CORS (comma-separated origins, no spaces after commas) ---
CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Prisma connection string (see `prisma/schema.prisma`) |
| `DIRECT_URL` | Direct DB URL for `prisma migrate` when the pooler URL is not suitable |
| `JWT_SECRET` | Signs and verifies access tokens |
| `JWT_EXPIRE_HOURS` | Token lifetime in hours |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth client |
| `GOOGLE_REDIRECT_URI` | OAuth redirect; must match Google Console |
| `CORS_ORIGINS` | Allowed browser origins for the API |

## Local setup

### 1. Clone and enter the repo

```bash
git clone <repository-url>
cd CopodsConnect-BE
```

### 2. Virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate the Prisma client

From the repository root:

```bash
python -m prisma generate
```

(Alternatively, if the Prisma CLI is installed globally or via npm: `prisma generate`.)

### 5. Apply database migrations

Ensure `DATABASE_URL` and `DIRECT_URL` in `.env` point at your target database.

**Development** (creates/applying migrations interactively):

```bash
python -m prisma migrate dev
```

**Deploy / CI** (applies existing migrations only):

```bash
python -m prisma migrate deploy
```

### 6. Run the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **Health:** `GET http://127.0.0.1:8000/health`
- **API prefix:** Routes are mounted under **`/api/v1`** (see `constants.API_PREFIX`).

## Project layout

| Path | Role |
|------|------|
| `main.py` | FastAPI app, CORS, lifespan (Prisma connect/disconnect), routers |
| `prisma/schema.prisma` | Data model and `prisma-client-py` generator |
| `prisma/migrations/` | SQL migrations |
| `db/client.py` | Shared async Prisma client |
| `routes/` | HTTP routes |
| `services/` | Business logic (auth, OAuth, JWT) |
| `middlewares/` | Auth helpers |

## Troubleshooting

- **`prisma` / client errors after `git pull`** — Run `python -m prisma generate` again.
- **Migration failures** — Confirm `DIRECT_URL` is valid for DDL; many hosts disallow migrations through the pooler URL.
- **Google login redirects** — `GOOGLE_REDIRECT_URI` must match the OAuth client configuration exactly (scheme, host, path, trailing slash).
- **401 on protected endpoints** — Ensure `JWT_SECRET` is set and consistent between issuance and verification.

Internal Copods project — follow team policies for credentials and handling production data.
