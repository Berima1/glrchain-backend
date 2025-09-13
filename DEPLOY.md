# Deploy & CI Quick Guide

## GitHub Secrets to add (Repo Settings → Secrets → Actions)
- RENDER_API_KEY
- RENDER_SERVICE_ID
- DATABASE_URL
- SECRET_KEY
- ANCHOR_RPC_URL
- IPFS_PINATA_KEY
- IPFS_PINATA_SECRET
- KMS_ARN (optional)

## Option A — Import to Render (recommended)
1. Go to https://dashboard.render.com → New → Web Service → Connect to GitHub.
2. Select this repo (`glrchain-backend`).
3. When asked, import `render.yaml` (or set build/start commands manually).
4. Add env vars in Render service settings (use values above).
5. Trigger deploy — Render will run `pip install -r requirements.txt` and start `uvicorn app.main:app`.

## Option B — Deploy manually with GitHub Actions
1. Add `RENDER_API_KEY` and `RENDER_SERVICE_ID` to GitHub Secrets.
2. On Actions → Deploy to Render → Run workflow.

## Notes
- Use managed Postgres (Railway/Render lead) for production.
- Use KMS/HSM to store blockchain private keys.
- Pin evidence to IPFS (Pinata or Infura) for immutable storage.
