# AuthentiQ Cloudflare API

This is the laptop-free deployment target. It keeps the existing local FastAPI backend available for development, while the Cloudflare version uses:

- Python Workers + FastAPI for HTTP API routes.
- D1 (SQLite-compatible) instead of SQLAlchemy/PostgreSQL.
- Durable Objects for room presence/signaling and future rate-limit coordination.
- Browser-to-browser WebRTC for interview audio/video, avoiding a paid media server.
- Cloudflare Email Service for OTP delivery after a sending domain is onboarded.

## One-time setup

Install the Python Worker toolchain, log in, and create D1:

```bash
cd cloudflare
uvx --from workers-py pywrangler login
uvx --from workers-py pywrangler d1 create authentiq
```

Copy the returned database ID into `wrangler.toml`, then initialize the schema:

```bash
uvx --from workers-py pywrangler d1 execute authentiq --remote --file=schema.sql
```

Run and deploy:

```bash
uvx --from workers-py pywrangler dev
uvx --from workers-py pywrangler deploy
```

After deployment, set Vercel `NEXT_PUBLIC_API_URL` to the Worker URL, for example `https://authentiq-api.<your-subdomain>.workers.dev`, and redeploy the frontend.

## Email OTP

Email Service requires a domain onboarded to Cloudflare Email Sending. Once available, add the `send_email` binding to `wrangler.toml` and implement OTP delivery in the auth routes. Do not put SMTP passwords in the repository or Vercel public variables.

## Migration status

The health/readiness and D1 foundation are implemented first so deployment can be verified independently. The existing local backend remains the reference implementation while auth, interviews, invitations, integrity events, reviews, and WebSocket signaling are moved route-by-route onto this Worker.
