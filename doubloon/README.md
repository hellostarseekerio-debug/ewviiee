# ⚓ Doubloon

An AI chat SaaS built on the Claude API. Streaming answers, free-tier metering,
pricing page, and a straight line to the only number that matters.

## The math to $1M ARR

$1,000,000 / 12 = **$83,334 MRR**. Ways to get there:

| Lever | Price | Subscribers needed |
|---|---|---|
| Pro only | $25/mo | 3,334 |
| Crew only | $99/mo | 842 |
| Realistic mix (80% Pro / 20% Crew) | — | ~2,900 accounts |

At a typical 2–4% free→paid conversion, that means roughly **75k–150k free
signups**. The product is the easy part (it's in this folder). Distribution is
the game: SEO pages per use case, a generous free tier that demos itself, and
a payment link one click from the moment the daily limit hits.

## What's implemented

- **Streaming chat** — `POST /api/chat` streams Claude's answer over SSE,
  token by token, via `@anthropic-ai/sdk` (`claude-opus-4-8`, adaptive thinking).
- **Free-tier metering** — anonymous cookie, N messages per UTC day
  (`FREE_DAILY_LIMIT`, default 15). Hitting the cap returns 429 with the
  upgrade link.
- **Upgrade path** — set `STRIPE_PAYMENT_LINK` and every upgrade button on the
  landing page and in the 429 flow points at it. No Stripe SDK needed to take
  the first dollar.
- **Prompt-caching-friendly** — the system prompt is byte-stable and carries a
  `cache_control` breakpoint, so cache reads kick in as the prompt grows.
- **Demo mode** — with no `ANTHROPIC_API_KEY`, the server streams a canned
  reply so the whole loop (UI → SSE → render → quota) is testable keyless.
- **Landing + pricing page** — three tiers, zero build step, no framework tax.

## Run it

```bash
cd doubloon
npm install
cp .env.example .env   # add ANTHROPIC_API_KEY, or leave empty for demo mode
npm run dev            # http://localhost:3000
```

- `/` — landing page and pricing
- `/chat.html` — the chat app
- `/healthz` — liveness + demo-mode flag

## Architecture

```
doubloon/
  src/server.ts       # Express: static hosting, /api/chat SSE, metering
  public/index.html   # landing + pricing
  public/chat.html    # chat UI (fetch-streaming SSE client, no framework)
  .env.example
```

The Messages API is stateless — the browser keeps the conversation and sends
full history each turn. The server validates/caps it, meters the free tier,
and streams the reply back.

## Go-live checklist (in order of revenue impact)

1. **Stripe Payment Link** — create one, set `STRIPE_PAYMENT_LINK`. Revenue: on.
2. **Real accounts** — swap the anonymous cookie for email magic-link auth;
   store plan + usage in Postgres, meter in Redis (the in-memory `Map` dies
   with the process and doesn't share across replicas).
3. **Stripe webhooks** — `checkout.session.completed` → mark the account Pro
   and lift the cap automatically.
4. **Abuse controls** — per-IP limits alongside per-cookie, max concurrent
   streams per user, and a moderation pass if you open signups wide.
5. **Unit economics** — Pro at $25/mo is profitable as long as an average user
   stays under roughly $15/mo of model spend; watch p95 usage and add a
   fair-use cap before the top 1% eats the margin.
6. Then, and only then: teams, SSO, and the enterprise tier that actually gets
   you to seven figures.

*$1M ARR or Davy Jones' locker.* 🏴‍☠️
