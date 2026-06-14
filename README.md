# Fe El Seka — فى السكة

> AI-powered route-sharing and carpooling platform for Egypt.

## Monorepo Structure

```
fe-el-seka/
├── apps/
│   ├── main/          # Passenger & driver app (Next.js 14, port 3000)
│   └── admin/         # Operations dashboard (Next.js 14, port 3001)
├── packages/
│   ├── ui/            # Shared React components (@fe-el-seka/ui)
│   └── shared/        # Shared TypeScript types & utils (@fe-el-seka/shared)
├── services/
│   ├── api/           # Core REST API (FastAPI, port 8000)
│   └── ai/            # AI/ML service (FastAPI, port 8001)
├── supabase/
│   ├── config.toml
│   └── migrations/    # SQL migrations (PostGIS + RLS)
└── docs/
```

## Quickstart

```bash
# 1. Install Node dependencies
pnpm install

# 2. Copy environment files
cp .env.example .env
cp apps/main/.env.example apps/main/.env.local
cp apps/admin/.env.example apps/admin/.env.local
cp services/api/.env.example services/api/.env
cp services/ai/.env.example services/ai/.env

# 3. Install Python dependencies
cd services/api && uv sync --dev && cd ../..
cd services/ai && uv sync --dev && cd ../..

# 4. Start Supabase locally
supabase start

# 5. Run all services
pnpm dev
```

Services will be available at:
- Main app: http://localhost:3000
- Admin app: http://localhost:3001
- API health: http://localhost:8000/health
- AI health: http://localhost:8001/health

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| API | Python FastAPI, asyncpg |
| AI | Python FastAPI |
| Database | Supabase PostgreSQL 15 + PostGIS |
| Package manager | pnpm 8 + Turborepo |
| Python tooling | uv |
| CI | GitHub Actions |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for branch naming, PR requirements, and branch protection setup.
