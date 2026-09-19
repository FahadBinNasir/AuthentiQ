# AuthentiQ API

The first API slice keeps storage replaceable. It exposes the contract for interviews, secure invitations, monitoring policies, and integrity events while PostgreSQL and authentication are added next.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

OpenAPI is available at `http://localhost:8000/docs`.

## Persistence

Set `DATABASE_URL` to a PostgreSQL connection string in deployed environments:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/authentiq
```

Without `DATABASE_URL`, local development uses `authentiq.local.db` so data survives backend restarts.

## Local public testing with Cloudflare Tunnel

Keep the API running in one terminal:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second terminal, install Cloudflare Tunnel (`cloudflared`) and run:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Copy the temporary `https://....trycloudflare.com` URL and set it in Vercel as `NEXT_PUBLIC_API_URL`. Never use the Vercel frontend URL as the API URL. The temporary URL changes when the tunnel restarts.

## Authentication configuration

In development, OTPs are printed in the API terminal. For real email delivery, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `APP_ENV=production`. OTPs expire after 10 minutes, verification is limited to five attempts, and requests are rate-limited per email and client IP.
