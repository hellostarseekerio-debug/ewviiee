# Office Automation Platform - Web Frontend

Enterprise web UI for the Office Automation Platform's existing FastAPI backend
(`app/` at the repo root, deployed separately - see `docs/RENDER_DEPLOYMENT.md`).
This frontend is a pure client of that API: it adds no backend logic of its own
beyond calling documented endpoints.

Built with Next.js 15 (App Router), React 19, TypeScript (strict), Tailwind CSS
v4, and hand-built shadcn/ui-style components (Radix UI primitives + `cva`) -
no `shadcn` CLI dependency at build time, so `npm install && npm run build`
works offline once dependencies are installed.

## What's implemented (and what isn't)

Every screen below calls a real backend endpoint - nothing is mocked. Two
gaps between the original feature list and the actual backend were closed by
adding a small number of new, minimal endpoints to the existing FastAPI app
(no new service, no architecture change - see "Backend additions" below).

| Feature | Status |
|---|---|
| Login, logout, session persistence, expired-session handling | Done (`/api/auth/token`, `/me`) |
| MFA (TOTP) setup/confirm/disable during login and in Settings | Done |
| Dashboard (document/user/AI-usage stats, recent activity, quick actions) | Done (`/api/dashboard/stats`, added this project) |
| Documents: upload (drag-and-drop, progress), browse, keyword search, metadata, download, delete | Done |
| Document review: approve/reject, version history, rollback | Done |
| Enterprise Search page: filters (district/estate/politician/reference/workflow), pagination, `/` shortcut | Done |
| User management: list/create/edit/deactivate/reset password, roles | Done (list/edit/deactivate/reset-password endpoints added this project) |
| Settings: profile (read-only), self-service password change, MFA, org/AI runtime settings, light/dark/system theme | Done (`/api/auth/change-password` added this project) |
| Command palette (`Cmd+K` / `Ctrl+K`) | Done |
| **AI Assistant chat (ChatGPT-style, streaming, conversation history)** | **Not implemented.** The backend has no chat/completion endpoint - AI here runs automatically inside document workflows (OCR, extraction, classification), not as free-form chat. The "AI Insights" page is honest about this and shows real AI-usage stats and workflow info instead of a fabricated chat UI. Building a real assistant would need a new backend chat endpoint and conversation storage - a substantial addition, deliberately out of scope here per "don't invent APIs." |

## Backend additions made to support this frontend

These live in the main repo, not here - `app/api/routes/auth.py`,
`app/api/routes/documents.py`, and the new `app/api/routes/dashboard.py`:

- `GET /api/auth/me` - current user info
- `GET /api/auth/admin/users`, `PATCH .../{username}`, `DELETE .../{username}` (deactivates, never hard-deletes), `POST .../{username}/reset-password`
- `POST /api/auth/change-password` - self-service password change
- `GET /api/documents/{id}/download`
- `GET /api/dashboard/stats`

All covered by backend tests in `tests/integration/test_frontend_support_endpoints.py`.

## Getting started

```bash
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL to your backend
npm install
npm run dev                  # http://localhost:3000
```

You'll need the backend running too (see the repo root `README.md` /
`docs/DEPLOYMENT.md`), with its CORS origins including this frontend's URL
(`OAP_CORS_ALLOWED_ORIGINS`).

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes | Base URL of the FastAPI backend, no trailing slash. Must be reachable from the *browser*, not just the server - this app calls the API client-side. |

See `.env.example`.

## Production build

```bash
npm run build
npm start
```

`npm run build` runs the TypeScript compiler and ESLint as part of the Next.js
build - a failing type check or lint error fails the build.

## Deployment

### Vercel

1. Import this repository into Vercel, set the project's **Root Directory** to `frontend`.
2. Set the `NEXT_PUBLIC_API_URL` environment variable to your deployed backend's URL (e.g. `https://office-ai-api.onrender.com`).
3. Deploy. Vercel auto-detects Next.js and runs `npm run build`.
4. On the backend, add the Vercel-assigned URL to `OAP_CORS_ALLOWED_ORIGINS`.

### Render (Web Service, Node runtime)

1. **New +** -> **Web Service**, connect this repo, set **Root Directory** to `frontend`.
2. Build command: `npm install && npm run build`. Start command: `npm start`.
3. Add environment variable `NEXT_PUBLIC_API_URL` pointing at your backend service.
4. Deploy, then add the resulting `*.onrender.com` URL to the backend's `OAP_CORS_ALLOWED_ORIGINS`.

Either way, the frontend and backend are two independently deployed services -
this app never needs its own database, disk, or server-side secrets.

## Project structure

```
app/                  Next.js App Router pages
  (app)/              Authenticated shell (sidebar + topbar) and its pages
  login/              Login + MFA verification
components/
  ui/                 Hand-built shadcn/ui-style primitives (Radix + cva)
  layout/             Sidebar, topbar, command palette, nav config
  documents/           Upload dropzone, status badges
lib/
  api/                Typed API client (client.ts, endpoints.ts, types.ts)
  auth-context.tsx    Auth state, session persistence, 401 handling
```
