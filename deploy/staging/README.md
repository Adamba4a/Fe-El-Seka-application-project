# Triplyy staging VPS

This directory deploys a fully isolated staging stack. It pulls the `:staging` images published from the repository's `staging` branch and connects only to the separate Supabase staging project.

## Server baseline

- Ubuntu 24.04 LTS VPS, 2 vCPU and 4 GB RAM minimum.
- Docker Engine with the Compose plugin.
- Ports 80 and 443 open in the VPS firewall.
- A DNS A record for `staging.triplyy.net` pointing to the VPS public IPv4 address.

## Deploy

1. Copy this directory to `/opt/triplyy-staging` on the VPS.
2. Copy `.env.example` to `.env` and fill every placeholder with values from the **staging** Supabase project. Generate new random values for the three internal secrets.
3. Sign Docker in to GHCR with an account allowed to pull the Triplyy images.
4. Run `docker compose -f compose.yml pull` then `docker compose -f compose.yml up -d`.
5. Check `https://staging.triplyy.net/api/health` and `docker compose -f compose.yml ps`.

## Supabase staging checklist

1. Create a new Supabase project; do not restore or clone production data.
2. Link the project from a temporary clean checkout and apply all repository migrations with `supabase db push --linked`.
3. Set the Auth Site URL to `https://staging.triplyy.net` and add it to Redirect URLs.
4. Create a dedicated verified passenger for k6. Use no customer account or production token.

## Update

After a new `staging` branch image is published, run `docker compose -f compose.yml pull` and `docker compose -f compose.yml up -d` on the VPS. Production images use `:latest`, so this operation cannot update production.
