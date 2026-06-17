FROM node:20-alpine AS deps

WORKDIR /app

RUN corepack enable pnpm

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/ ./packages/
COPY apps/main/package.json ./apps/main/package.json

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
COPY package.json pnpm-workspace.yaml turbo.json* ./

RUN pnpm --filter @fe-el-seka/main build && mkdir -p ./apps/main/public

# ---- runner ----
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --gid 1001 nodejs && adduser --uid 1001 --ingroup nodejs --disabled-password nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/main/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/main/.next/static ./apps/main/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/main/public ./apps/main/public

USER nextjs

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/main/server.js"]
