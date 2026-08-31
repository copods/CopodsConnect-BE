# Copods Connect — Backend API

FastAPI backend for **Copods Connect** (internally "Applaud"), using **PostgreSQL** and [**Prisma Client Python**](https://github.com/RobertCraigie/prisma-client-py) for persistence, **Google OAuth** for authentication, and multiple AI services for content moderation.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python** 3.10+ | 3.12 recommended; match your team if pinned elsewhere |
| **PostgreSQL** | Local, Docker, or hosted (e.g. Supabase) |
| **Git** | For clone / pull workflows |
| **Docker** *(optional)* | Only if you want to run the backend in a container |

**Recommended:** Python virtual environment (`venv`).
**Optional:** Node.js / npm if you prefer running the Prisma CLI with `npx prisma` instead of invoking it through Python.

---

## Environment Variables

> **Actual secret values, URLs, and keys for this project are shared separately in Google Chat.** Do not paste real credentials into GitHub issues, pull requests, or this repository.

Create a **`.env`** file in the **repository root** (next to `main.py`). `.env` is gitignored — never commit it.

Use this structure (fill values from Google Chat or `dev.env`):

```env
# ── PostgreSQL ──────────────────────────────────────────────
# Pooler / session URL for the running app (required by Supabase / PgBouncer)
DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE?pgbouncer=true"

# Direct URL for migrations (Supabase disallows DDL through the pooler)
DIRECT_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"

# ── JWT ─────────────────────────────────────────────────────
JWT_SECRET="your-secret-here"
JWT_EXPIRE_HOURS="24"                # Optional — defaults to 24

# ── Google OAuth ────────────────────────────────────────────
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
# Must exactly match redirect URIs in Google Cloud Console
GOOGLE_REDIRECT_URI="http://localhost:5173/auth/callback"
# Expo redirect for the mobile app
APP_GOOGLE_REDIRECT_URI="https://auth.expo.io/@your-expo-user/CopodsConnectApp-FE"

# ── Domain restriction ──────────────────────────────────────
ALLOWED_DOMAIN="copods.co"           # Only emails from this domain can sign up

# ── CORS (comma-separated origins, no spaces) ──────────────
CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

# ── Email (AWS SES) ────────────────────────────────────────
GMAIL_USER=""                        # Sender identity for email notifications
GMAIL_APP_PASSWORD=""                # Google App Password (for legacy SMTP fallback)
MAIL_FROM="dev@copods.co"           # Verified SES sender address
AWS_ACCESS_KEY_ID=""
AWS_SECRET_ACCESS_KEY=""
AWS_REGION="ap-south-1"

# ── Supabase Storage ───────────────────────────────────────
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY=""
SUPABASE_STORAGE_BUCKET="post-media"

# ── AI / Content Moderation ────────────────────────────────
OPENAI_API_KEY=""                    # OpenAI — text moderation
MISTRAL_API_KEY=""                   # Mistral — secondary moderation model
GEMINI_API_KEY=""                    # Gemini — additional moderation model
SIGHTENGINE_API_USER=""             # SightEngine — image moderation
SIGHTENGINE_API_SECRET=""

# ── Misc ───────────────────────────────────────────────────
BASE_URL="http://localhost:8000"     # This backend's own URL (used in email templates)
ADMIN_PANEL_URL="http://localhost:5173"  # Admin panel URL (used in email links)
APP_DOWNLOAD_URL=""                  # Mobile app download link (used in emails)
DEV_USER_EMAIL="you@copods.co"      # Default email for scripts/mint_dev_token.py
```

### Variable Reference

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | Prisma connection string (see `prisma/schema.prisma`) |
| `DIRECT_URL` | Yes | Direct DB URL for `prisma migrate` (bypasses PgBouncer) |
| `JWT_SECRET` | Yes | Signs and verifies access tokens |
| `JWT_EXPIRE_HOURS` | No | Token lifetime in hours (default: `24`) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Yes | OAuth redirect for the admin panel; must match Google Console |
| `APP_GOOGLE_REDIRECT_URI` | Yes | OAuth redirect for the Expo mobile app |
| `ALLOWED_DOMAIN` | No | Restricts sign-up to this email domain (default: `copods.co`) |
| `CORS_ORIGINS` | No | Allowed browser origins for the API |
| `GMAIL_USER` | Yes | Sender identity for outbound emails |
| `GMAIL_APP_PASSWORD` | Yes | Google App Password for SMTP fallback |
| `MAIL_FROM` | Yes | Verified SES "From" address |
| `AWS_ACCESS_KEY_ID` | Yes | AWS IAM key for SES + ECR |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS IAM secret |
| `AWS_REGION` | Yes | AWS region (e.g. `ap-south-1`) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key (full access) |
| `SUPABASE_STORAGE_BUCKET` | Yes | Storage bucket name for post media |
| `OPENAI_API_KEY` | Yes | OpenAI API key for text moderation |
| `MISTRAL_API_KEY` | Yes | Mistral API key for secondary moderation |
| `GEMINI_API_KEY` | Yes | Gemini API key for additional moderation |
| `SIGHTENGINE_API_USER` | Yes | SightEngine user ID for image moderation |
| `SIGHTENGINE_API_SECRET` | Yes | SightEngine secret |
| `BASE_URL` | No | Backend's own URL; used in email templates (default: `http://localhost:8000`) |
| `ADMIN_PANEL_URL` | No | Admin panel URL embedded in email links |
| `APP_DOWNLOAD_URL` | No | Mobile app download link used in invitation emails |
| `DEV_USER_EMAIL` | No | Default email for `scripts/mint_dev_token.py` |

---

## Local Setup

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

**Development** (creates/applies migrations interactively):

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
- **Interactive docs:** Disabled by default (`docs_url=None, redoc_url=None` in `main.py`).

---

## Docker Setup

The repository includes a `Dockerfile` for containerized deployment.

### Build the image

```bash
docker build -t copods-connect-be .
```

The Dockerfile:
- Uses `python:3.12-slim` as the base image
- Pre-installs **Node 20 LTS** via `nodeenv` (to work around a Prisma/npm 11 compatibility bug with Node 26)
- Installs Python dependencies from `requirements.txt`
- Runs `prisma generate` at build time

### Run the container

```bash
docker run -p 8000:8000 --env-file .env copods-connect-be
```

This maps port `8000` inside the container to port `8000` on your host.

### Important notes

- **Run migrations before starting the container.** Migrations execute DDL against your database — they don't need to run inside the container. Run them from your local machine:
  ```bash
  python -m prisma migrate deploy
  ```
- The `.dockerignore` excludes `.env`, `.venv`, `__pycache__`, and `.git` from the build context.
- For production, environment variables are injected through your deployment platform (e.g. AWS ECS task definition) — not via `--env-file`.

### Quick one-liner (build + run)

```bash
docker build -t copods-connect-be . && docker run -p 8000:8000 --env-file .env copods-connect-be
```

---

## Developer Utilities / Scripts

Located in the `scripts/` directory:

| Script | Purpose | Usage |
|---|---|---|
| `mint_dev_token.py` | Mint a JWT for local testing (Postman, curl) | `python scripts/mint_dev_token.py user@copods.co [app\|panel]` |
| `generate_postman_collection.py` | Auto-generate a Postman collection from route definitions | `python scripts/generate_postman_collection.py` |
| `test_jobs.py` | Manually trigger cron jobs for testing | `python scripts/test_jobs.py` |

`mint_dev_token.py` reads `DEV_USER_EMAIL` from `.env` as the default email if no argument is provided.

---

## Background Jobs / Cron

The server starts an **APScheduler** instance on boot (inside the FastAPI lifespan). Five jobs run automatically:

| Job | Schedule | Description |
|---|---|---|
| `clear_expired_bans` | Every 15 minutes | Unbans users whose ban period has elapsed |
| `purge_soft_deleted_users` | Every 24 hours | Permanently removes soft-deleted user records |
| `daily_celebrations` | Daily at **00:00 IST** | Creates auto-generated celebration posts (birthdays, anniversaries) |
| `most_appreciated_monthly` | **1st of each month at 09:00 IST** | Sends the "Most Appreciated" leaderboard digest email |
| `recover_pending_posts` | Every 5 minutes | Re-queues posts stuck in `PENDING` moderation status |

All jobs log to the `uvicorn.error` logger — look for `[cron]` prefixed lines.

---

## CI/CD — GitHub Actions

The repo has one workflow: `.github/workflows/deploy-dev.yml`

**Trigger:** Merged pull requests into the `dev` branch.

**Pipeline:**
1. Checkout code
2. Configure AWS credentials (from GitHub Secrets)
3. Login to **AWS ECR** (Elastic Container Registry)
4. Build the Docker image (linux/amd64) and push to ECR with `:latest` and `:<commit-sha>` tags
5. Force-redeploy the **AWS ECS** (Elastic Container Service) service
6. Wait for the service to stabilize

**Required GitHub Secrets:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

---

## Project Layout

| Path | Role |
|---|---|
| `main.py` | FastAPI app, CORS, lifespan (Prisma connect/disconnect, scheduler), routers |
| `constants.py` | App-wide constants (API prefix, pagination, moderation thresholds, leaderboard weights) |
| `prisma/schema.prisma` | Data model and `prisma-client-py` generator |
| `prisma/migrations/` | SQL migration files |
| `db/client.py` | Shared async Prisma client instance |
| `routes/` | HTTP route handlers (auth, users, polls, stats, alerts, appreciation types) |
| `routes/app/` | Mobile-app-specific routes (posts, appreciations, notifications, app auth) |
| `services/` | Business logic (auth, users, moderation, notifications, stats, alerts) |
| `middlewares/` | Auth helpers and request middleware |
| `models/` | Pydantic request/response models |
| `utils/` | Shared utilities (exception handlers, API response builder) |
| `jobs/` | Scheduled background jobs (APScheduler) |
| `scripts/` | Developer CLI utilities (token minting, Postman generation, job testing) |
| `public/assets/` | Static files served at `/assets` |
| `postman/` | Postman collection exports |
| `Dockerfile` | Container build definition |
| `.github/workflows/` | CI/CD pipeline (deploy-dev) |

---

## External Services

The backend integrates with the following third-party services:

| Service | Purpose | Required Env Vars |
|---|---|---|
| **PostgreSQL** (Supabase-hosted) | Primary database | `DATABASE_URL`, `DIRECT_URL` |
| **Supabase Storage** | File/image uploads for posts | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET` |
| **Google OAuth** | User authentication (admin panel + mobile app) | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `APP_GOOGLE_REDIRECT_URI` |
| **OpenAI** | AI text moderation | `OPENAI_API_KEY` |
| **Mistral** | Secondary AI moderation model | `MISTRAL_API_KEY` |
| **Gemini** | Additional AI moderation model | `GEMINI_API_KEY` |
| **SightEngine** | Image moderation (NSFW, violence detection) | `SIGHTENGINE_API_USER`, `SIGHTENGINE_API_SECRET` |
| **AWS SES** | Transactional email delivery | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `MAIL_FROM` |
| **AWS ECR + ECS** | Container registry and deployment | Configured via GitHub Secrets |

---

## Troubleshooting

### Prisma / client errors after `git pull`
Run `python -m prisma generate` again. The generated client may be stale after schema changes.

### Migration failures
Confirm `DIRECT_URL` is valid for DDL; many hosts (including Supabase) disallow migrations through the pooler URL.

### Google login redirects
`GOOGLE_REDIRECT_URI` must match the OAuth client configuration exactly (scheme, host, path, trailing slash).

### 401 on protected endpoints
Ensure `JWT_SECRET` is set and consistent between issuance and verification.

### Docker build fails with Node/npm errors
The Dockerfile pre-installs Node 20 LTS to avoid an npm 11 incompatibility with Prisma's `nodeenv`. If the build still fails:
- Check your Docker version supports multi-stage caching
- Ensure you have a stable internet connection (Node is downloaded during build)

### SES / email send errors
- Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` have SES permissions
- Ensure `MAIL_FROM` is a verified sender in your SES configuration
- Check if your SES account is still in sandbox mode (sandbox only allows sending to verified addresses)

### Content moderation API failures
- Verify `OPENAI_API_KEY`, `MISTRAL_API_KEY`, `GEMINI_API_KEY` are valid and have sufficient quota
- Check `SIGHTENGINE_API_USER` / `SIGHTENGINE_API_SECRET` — expired keys will silently fail moderation

### Container starts but API returns 500
- Ensure all required env vars are set (see the Variable Reference table above)
- Check container logs: `docker logs <container-id>`
- Verify the database is accessible from within the container (network/firewall rules)

---

Internal Copods project — follow team policies for credentials and handling production data.
