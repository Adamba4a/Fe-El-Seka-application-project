# Implementation Plan: Isolated Staging Environment

The repository preserves the production `:latest` images on `main` and publishes isolated `:staging` images from the `staging` branch. Bunny staging always pulls `:staging`.

The Bunny staging app mirrors the production service topology: nginx as the public entrypoint, then main, API, AI, and OSRM on a private network. It receives a distinct `.env` set. The main image needs staging build variables because Next.js inlines public configuration at build time; GitHub environment variables supply those values only to the staging frontend-push job.

Supabase staging is a separately provisioned project. Every repository migration is applied there before it is connected to Bunny. Auth site and redirect URLs point only to the staging frontend, and no production secrets or database URLs are copied.

The first capacity test will use a dedicated verified passenger account created in staging after auth is configured. It will exercise only the read-only k6 paths documented in `performance/README.md`.
