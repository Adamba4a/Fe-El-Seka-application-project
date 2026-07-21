FROM node:20-alpine AS deps

WORKDIR /app

RUN corepack enable pnpm

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/ ./packages/
COPY apps/main/package.json apps/main/next.config.mjs apps/main/tsconfig.json apps/main/postcss.config.mjs apps/main/tailwind.config.ts ./apps/main/

RUN pnpm install --frozen-lockfile

# ---- builder ----
FROM node:20-alpine AS builder

WORKDIR /app

RUN corepack enable pnpm

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/packages ./packages
COPY --from=deps /app/apps/main/node_modules ./apps/main/node_modules

COPY packages/ ./packages/
COPY apps/main/ ./apps/main/
COPY package.json pnpm-workspace.yaml tsconfig.base.json turbo.json* ./

# Next.js inlines NEXT_PUBLIC_* into the client bundle at build time, so they
# must be supplied here — setting them at container runtime has no effect.
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_NOMINATIM_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_NOMINATIM_URL=$NEXT_PUBLIC_NOMINATIM_URL

RUN pnpm --filter @fe-el-seka/main build && mkdir -p ./apps/main/public

# ---- runner ----
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --gid 1001 nodejs && adduser --uid 1001 --ingroup nodejs --disabled-password nextjs

# Next.js standalone output only holds symlinks into the pnpm-hoisted
# `.pnpm` store for shared deps (next/react) — the real files live in the
# workspace root node_modules built in the `deps` stage, so that has to be
# copied alongside it for those symlinks to resolve.
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/apps/main/.next/standalone ./apps/main
COPY --from=builder --chown=nextjs:nodejs /app/apps/main/.next/static ./apps/main/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/main/public ./apps/main/public

USER nextjs

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/main/server.js"]
