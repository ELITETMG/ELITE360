# Deployment Guide (Render + GitHub)

This repo is configured for paid hosting on Render with easy redeploys.

## What You Get

- Render web service from [`render.yaml`](./render.yaml)
- Managed PostgreSQL database
- Persistent upload disk mounted at `/app/app/static/uploads`
- Auto-deploy on every push to `main`
- Optional one-click redeploy hook from GitHub Actions

## One-Time Setup

1. Push this repository to GitHub.
2. In Render, create a **Blueprint** and point it to this repo.
3. Apply the resources from `render.yaml`.
4. Set required environment values:
   - `MAPBOX_PUBLIC_TOKEN`
   - `OPENAI_API_KEY` (optional, only for AI features)
   - `CORS_ORIGINS` (your app domain, e.g. `https://app.yourdomain.com`)
5. Confirm service health at `/health`.

## Easy Redeploy Flow

1. Make code changes (manually or with your AI coding workflow).
2. Commit and push to `main`.
3. Render deploys automatically.

That is the autonomous loop: `change -> push -> deploy`.

## Optional: Explicit Redeploy Trigger

If you want manual redeploy triggers from GitHub Actions:

1. In Render, copy your service's deploy hook URL.
2. Add GitHub secret: `RENDER_DEPLOY_HOOK_URL`.
3. Use workflow [`render-redeploy.yml`](./.github/workflows/render-redeploy.yml) via:
   - manual `workflow_dispatch`.

You can also trigger from terminal:

```bash
RENDER_DEPLOY_HOOK_URL="https://api.render.com/deploy/..." ./scripts/redeploy-render.sh
```

## Environment Variables

Use [`.env.example`](./.env.example) as your source of truth:

- `DATABASE_URL`
- `SECRET_KEY`
- `MAPBOX_PUBLIC_TOKEN`
- `OPENAI_API_KEY` (optional)
- `OPENAI_BASE_URL` (optional)
- `CORS_ORIGINS` (comma-separated or JSON array)
- `PORT`
