# בסדר / Beseder — web

Next.js + Tailwind frontend: landing page (`/`) + live operator console (`/dashboard`).

## Run locally
```bash
npm install
npm run dev          # http://localhost:3000 (backend must run on :8000)
```

## Deploy to Vercel
```bash
npx vercel           # from this directory
```
Set one env var in Vercel: `NEXT_PUBLIC_API_BASE` — a publicly reachable URL of the
FastAPI backend (e.g. an ngrok/Cloudflare tunnel to localhost:8000). Without it the
console defaults to `http://localhost:8000`, which only works on the operator's machine.
