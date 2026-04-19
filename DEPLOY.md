# Deploying cite2fn

Split deployment: the Next.js frontend runs on **Vercel**, the Python API runs on **Fly.io**. No code changes needed — everything here is one-time config.

The end state:
- `https://<your-app>.vercel.app` — the public site
- `https://<your-app>-api.fly.dev` — the API (also fine behind a custom subdomain if you set one up later)

## Prerequisites

- A Fly.io account with a card on file ([fly.io/signup](https://fly.io/signup)). Usage for this workload stays within the free-tier allowance.
- A Vercel account linked to your GitHub.
- The `flyctl` CLI installed locally: `brew install flyctl` (macOS) or see [fly.io/docs/flyctl](https://fly.io/docs/flyctl/).
- A Groq API key from [console.groq.com](https://console.groq.com).
- The repo pushed to GitHub (it already is).

## 1. Deploy the API to Fly.io

From the repo root:

```bash
# Log in once
fly auth login

# Create the app from our fly.toml. --no-deploy so we can set secrets first.
fly launch --no-deploy --copy-config --name cite2fn-api --region iad

# Persistent volume for SQLite + feedback attachments + transient job files
fly volumes create cite2fn_data --size 1 --region iad

# Secrets (none of these hit the git repo)
fly secrets set GROQ_API_KEY=<your-groq-key>
fly secrets set ADMIN_TOKEN="$(openssl rand -hex 16)"   # save this — you'll need it for /admin
# CORS_ORIGINS is set below once the Vercel URL is known. Until then, skip
# it — the API defaults to "*", which is fine for the initial test.

# Deploy
fly deploy
```

Fly prints the public URL on success (e.g. `https://cite2fn-api.fly.dev`). Verify:

```bash
curl https://cite2fn-api.fly.dev/health
# {"status":"ok","groq_configured":true,"max_upload_mb":25}
```

## 2. Deploy the frontend to Vercel

Easiest path: use the Vercel dashboard.

1. Go to [vercel.com/new](https://vercel.com/new) and import the GitHub repo.
2. In the project settings, set the **Root Directory** to `web`.
3. Framework preset: **Next.js** (should auto-detect).
4. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = `https://cite2fn-api.fly.dev` (from step 1)
   - `NEXT_PUBLIC_BUG_REPORT_URL` (optional; leave empty if you don't want a fallback GitHub link — the in-site modal is the primary path)
5. Click **Deploy**.

Vercel gives you the site URL, e.g. `https://cite2fn-xxx.vercel.app`.

## 3. Tighten CORS

Now that the Vercel URL exists, lock the API to accept only that origin:

```bash
fly secrets set CORS_ORIGINS=https://cite2fn-xxx.vercel.app
```

Fly will roll a new machine with the updated env. Done.

## 4. Smoke test

- Open the Vercel URL.
- Upload a small `.docx` with a linked source. Watch the progress bar, approve on review, download.
- Submit a test bug report with a screenshot attachment.
- Open `https://cite2fn-xxx.vercel.app/admin?token=<ADMIN_TOKEN-from-step-1>`. Confirm the dashboard loads and feedback + attachment show up.

## Custom domains (optional)

- **Frontend**: Vercel dashboard → project → Settings → Domains → add your domain, point DNS as instructed.
- **API**: `fly certs add api.yourdomain.com` then point a CNAME to `cite2fn-api.fly.dev`. Update `NEXT_PUBLIC_API_URL` on Vercel and `CORS_ORIGINS` on Fly to the new hostnames.

## Ongoing ops

- **Updating the API**: `git push` (optional) then `fly deploy` from repo root. Fly builds the Docker image, does a zero-downtime rollout.
- **Updating the frontend**: push to `main`. Vercel redeploys automatically.
- **Logs**: `fly logs` for the API; Vercel dashboard for the frontend.
- **SQLite backup**: `fly ssh console -C "sqlite3 /data/jobs.db '.backup /tmp/backup.db'"` then `fly ssh sftp get /tmp/backup.db`. (Not worth automating until there's real traffic.)
- **Rotate admin token**: `fly secrets set ADMIN_TOKEN=<new>` and update your bookmark.

## Cost expectations

- **Fly.io**: a single shared-cpu-1x 512MB VM. Should stay within the free allowance as long as traffic is modest. Watch the Fly dashboard's usage view.
- **Vercel**: Hobby plan is free and covers this site. Watch bandwidth.
- **Groq**: Free tier, ~6000 requests/day — plenty for individual users. You also pay nothing when users bring their own Claude API key (it goes directly to Anthropic).

## If you ever want to move off Fly.io

The API is just a stock Docker service. `fly deploy` → `docker push ... && docker run ...` on any VPS, or push to Railway / Render / Google Cloud Run / ECS with minimal changes. Persistent state lives entirely in the `/data` volume (SQLite + attachments), so the migration is: snapshot `/data`, restore on the new host, flip DNS.
