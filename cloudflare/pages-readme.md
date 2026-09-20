# AuthentiQ frontend on Cloudflare Pages

The frontend is configured for a static Cloudflare Pages deployment. It uses browser-side API calls, so the API URL must be available at build time.

## Dashboard deployment

In Cloudflare Pages, connect the `FahadBinNasir/AuthentiQ` repository with:

- Framework preset: Next.js (Static HTML Export)
- Build command: `npm run build:cloudflare`
- Build output directory: `out`
- Root directory: `/`
- Environment variable: `NEXT_PUBLIC_API_URL=https://authentiq-api.authentiq-integrity.workers.dev`

The same deployment can be performed from the repository with:

```bash
npm install
NEXT_PUBLIC_API_URL=https://authentiq-api.authentiq-integrity.workers.dev npm run build:cloudflare
npx wrangler pages deploy out --project-name authentiq
```

The current Vercel project can remain connected during verification. Once the Pages deployment is confirmed, use its production hostname as the canonical frontend URL and update the Worker `FRONTEND_ORIGIN` variable to that hostname.
