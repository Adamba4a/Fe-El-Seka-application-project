# Running Fe El Seka Locally

## Prerequisites

- Node.js 20+ and pnpm 8.15.6
- Python 3.11+
- Supabase CLI (`npm i -g supabase`)
- uv (`pip install uv`) — Python package manager used by the API

---

## 1. Start Supabase (local database + auth)

```bash
supabase start
```

This starts PostgreSQL on port 54322 and the Supabase API on port 54321.
Run once; it stays up until you call `supabase stop`.

---

## 2. Apply migrations

```bash
supabase db push
```

Run this whenever you add a new migration file under `supabase/migrations/`.
Current migrations (in order):

- Foundation schema + extensions
- Profiles, verification, vehicles, admin tables, RLS, storage, grants
- `20260617000001_ride_management.sql` — rides, ride_history_logs, email_notifications

---

## 3. Install dependencies

### Frontend (run once, or after adding packages)
```bash
pnpm install
```

### Backend (run once, or after editing pyproject.toml)
```bash
cd services/api
uv sync
cd ../..
```

---

## 4. Configure environment variables

### Backend — `services/api/.env`
Already pre-filled for local Supabase. Set these two:
```
RESEND_API_KEY=re_your_key_here          # from resend.com (free)
WEBHOOK_SECRET=any_long_random_string    # generate: python -c "import secrets; print(secrets.token_hex(32))"
```

### Frontend — `apps/main/.env.local`
Already complete for local dev. No changes needed.

### Admin — `apps/admin/.env.local`
Copy from example if missing:
```bash
cp apps/admin/.env.example apps/admin/.env.local
```

---

## 5. Run everything (all services at once)

```bash
pnpm dev
```

This starts four services in parallel:

| Service | URL | Command |
|---------|-----|---------|
| Main app (driver + passenger) | http://localhost:3000 | `pnpm --filter @fe-el-seka/main dev` |
| Admin app | http://localhost:3001 | `pnpm --filter @fe-el-seka/admin dev` |
| FastAPI backend | http://localhost:8000 | `uvicorn app.main:app --port 8000 --reload` |
| AI service | http://localhost:8001 | `uvicorn app.main:app --port 8001 --reload` |

---

## 6. Run services individually

### Main Next.js app only
```bash
pnpm --filter @fe-el-seka/main dev
```

### Admin Next.js app only
```bash
pnpm --filter @fe-el-seka/admin dev
```

### FastAPI backend only
```bash
cd services/api
uv run uvicorn app.main:app --port 8000 --reload
```

### AI service only
```bash
cd services/ai
uv sync
uv run uvicorn app.main:app --port 8001 --reload
```

---

## 7. Useful Supabase commands

```bash
# Open Supabase Studio (DB browser) at http://localhost:54323
supabase studio

# Stop all local Supabase containers
supabase stop

# Reset DB and re-apply all migrations from scratch
supabase db reset

# Check local Supabase status + printed credentials
supabase status
```

---

## 8. API docs

FastAPI auto-generates interactive docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Quick-start checklist

- [ ] `supabase start`
- [ ] `supabase db push`
- [ ] `pnpm install` + `cd services/api && uv sync`
- [ ] Fill in `RESEND_API_KEY` and `WEBHOOK_SECRET` in `services/api/.env`
- [ ] `pnpm dev`
- [ ] Open http://localhost:3000
