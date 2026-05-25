<<<<<<< Updated upstream
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
=======
# CopodsConnect — Backend

FastAPI backend for CopodsConnect, a workspace collaboration platform. Handles authentication via Google OAuth and manages users, workspaces, and memberships.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| ORM | Prisma (async, `prisma-client-py`) |
| Database | PostgreSQL |
| Auth | Google OAuth 2.0 + JWT (HS256) |
| Password hashing | Passlib + bcrypt |
| Validation | Pydantic v2 |

## Project Structure

```
CopodsConnect-BE/
├── main.py                  # App entry point — CORS, exception handlers, router registration
├── constants.py             # App-wide constants (name, API prefix, JWT algorithm)
├── requirements.txt
├── prisma/
│   └── schema.prisma        # Database schema (User, Workspace, WorkspaceMember)
├── db/
│   └── client.py            # Prisma client singleton
├── routes/
│   └── auth.py              # Auth endpoints
├── services/
│   └── auth_service.py      # Google OAuth flow, JWT creation, user upsert logic
├── middlewares/
│   └── auth.py              # JWT verification middleware
├── models/
│   └── schemas/
│       └── auth.py          # Pydantic request/response schemas
└── utils/
    ├── ApiResponse.py       # Standardised API response wrapper
    └── exceptions.py        # Custom exceptions + global exception handlers
```

## API Endpoints

Base path: `/api/v1`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/auth/google` | Get Google OAuth redirect URL |
| `POST` | `/api/v1/auth/google/callback` | Exchange OAuth code for JWT |
| `POST` | `/api/v1/auth/logout` | Client-side logout (delete JWT from storage) |

## Data Models

- **User** — platform account linked to a Google identity (`google_sub`), with a global `Role` (MEMBER / ADMIN / SUPER_ADMIN)
- **Workspace** — team space owned by a user, with allowed email domain restrictions
- **WorkspaceMember** — join table giving a user a `WorkspaceRole` within a workspace

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL database (or a Supabase / hosted Postgres connection)

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://user:password@host:port/dbname
DIRECT_URL=postgresql://user:password@host:port/dbname   # for Supabase / PgBouncer setups

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/callback   # must match Google Console

# JWT
JWT_SECRET=your-secret-key
JWT_EXPIRE_HOURS=24

# CORS (comma-separated list of allowed origins)
CORS_ORIGINS=http://localhost:5173
```

### Generate Prisma Client (one-time, local only)

```bash
prisma generate
```

This reads `prisma/schema.prisma` and generates the Python client into `.venv`. It does **not** touch the database. Run it once after install, or again if you change the schema.

### Run

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

## Auth Flow

1. Frontend calls `GET /api/v1/auth/google` → receives the Google OAuth URL
2. Frontend redirects the user to that URL
3. Google redirects back to the frontend with a `code` param
4. Frontend sends `code` to `POST /api/v1/auth/google/callback`
5. Backend exchanges the code for Google tokens, fetches user info, upserts the user in the DB, and returns a signed JWT
6. Frontend stores the JWT and sends it as `Authorization: Bearer <token>` on subsequent requests
>>>>>>> Stashed changes
