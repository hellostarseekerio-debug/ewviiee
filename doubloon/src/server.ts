import crypto from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import type { Request, Response } from "express";
import Anthropic from "@anthropic-ai/sdk";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT ?? 3000);
const MODEL = process.env.CHAT_MODEL ?? "claude-opus-4-8";
// Deliberate cost cap for a metered SaaS free tier; raise via env for paid plans.
const MAX_TOKENS = Number(process.env.CHAT_MAX_TOKENS ?? 8192);
const FREE_DAILY_LIMIT = Number(process.env.FREE_DAILY_LIMIT ?? 15);
const PAYMENT_LINK = process.env.STRIPE_PAYMENT_LINK ?? "";
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET ?? "";
// Signs the Pro cookie. The per-boot fallback means Pro sessions don't survive
// a restart unless APP_SECRET is pinned in .env.
const APP_SECRET = process.env.APP_SECRET ?? crypto.randomBytes(32).toString("hex");
const PRO_DAYS = Number(process.env.PRO_DAYS ?? 31);

const HAS_CREDENTIALS = Boolean(
  process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN,
);
const client = HAS_CREDENTIALS ? new Anthropic() : null;

// Keep this byte-stable (no timestamps, no per-user interpolation) so the
// prompt-cache prefix survives across requests as it grows.
const SYSTEM_PROMPT = [
  "You are Doubloon, a sharp, friendly AI assistant built for people who ship.",
  "Be direct and concrete. Lead with the answer, then the reasoning.",
  "Use markdown formatting when it helps: code fences for code, short lists for steps.",
  "If a request is ambiguous, make the most reasonable assumption and state it in one line rather than interrogating the user.",
].join("\n");

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ---------------------------------------------------------------------------
// Free-tier metering — anonymous cookie, per-UTC-day counter.
// In-memory on purpose for the MVP; swap for Redis/Postgres before scaling
// past one process (see README go-live checklist).
// ---------------------------------------------------------------------------
const usage = new Map<string, { day: string; count: number }>();

function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

function getUid(req: Request, res: Response): string {
  const cookies = Object.fromEntries(
    (req.headers.cookie ?? "")
      .split(";")
      .map((c) => c.trim().split("=") as [string, string])
      .filter(([k, v]) => k && v),
  );
  let uid = cookies["dbl_uid"];
  if (!uid || !/^[a-f0-9]{32}$/.test(uid)) {
    uid = crypto.randomBytes(16).toString("hex");
    res.setHeader(
      "Set-Cookie",
      `dbl_uid=${uid}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax`,
    );
  }
  return uid;
}

function checkAndCount(uid: string): { ok: boolean; remaining: number } {
  const day = todayUTC();
  const entry = usage.get(uid);
  const count = entry && entry.day === day ? entry.count : 0;
  if (count >= FREE_DAILY_LIMIT) return { ok: false, remaining: 0 };
  usage.set(uid, { day, count: count + 1 });
  return { ok: true, remaining: FREE_DAILY_LIMIT - count - 1 };
}

// ---------------------------------------------------------------------------
// Pro plan — Stripe Payment Link → webhook records the checkout session id →
// the success page redeems it → signed HttpOnly cookie bypasses the meter.
// In-memory like the usage meter; same single-process caveat (see README).
// ---------------------------------------------------------------------------
const paidSessions = new Map<string, { email: string; activatedAt: number | null }>();

function hmac(payload: string): string {
  return crypto.createHmac("sha256", APP_SECRET).update(payload).digest("hex");
}

function makeProCookie(): string {
  const exp = Date.now() + PRO_DAYS * 86_400_000;
  return `${exp}.${hmac(`pro:${exp}`)}`;
}

function isPro(req: Request): boolean {
  const match = /(?:^|;\s*)dbl_pro=([^;]+)/.exec(req.headers.cookie ?? "");
  if (!match) return false;
  const [expStr, sig] = match[1].split(".");
  const exp = Number(expStr);
  if (!Number.isFinite(exp) || exp < Date.now() || !sig) return false;
  const expected = hmac(`pro:${exp}`);
  return (
    sig.length === expected.length &&
    crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))
  );
}

// Stripe-Signature: t=<unix>,v1=<hmac>[,v1=<hmac>...] — HMAC-SHA256 of
// "<t>.<raw body>" with the webhook signing secret.
function verifyStripeSignature(payload: Buffer, header: string): boolean {
  let timestamp = "";
  const signatures: string[] = [];
  for (const part of header.split(",")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    const key = part.slice(0, eq).trim();
    const value = part.slice(eq + 1).trim();
    if (key === "t") timestamp = value;
    else if (key === "v1") signatures.push(value);
  }
  if (!timestamp || signatures.length === 0) return false;
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > 300) return false;
  const expected = crypto
    .createHmac("sha256", STRIPE_WEBHOOK_SECRET)
    .update(`${timestamp}.`)
    .update(payload)
    .digest("hex");
  return signatures.some(
    (s) =>
      s.length === expected.length &&
      crypto.timingSafeEqual(Buffer.from(s), Buffer.from(expected)),
  );
}

// ---------------------------------------------------------------------------
// Request validation — the API is stateless, the client sends full history.
// ---------------------------------------------------------------------------
function sanitizeMessages(body: unknown): ChatMessage[] | null {
  if (typeof body !== "object" || body === null) return null;
  const raw = (body as { messages?: unknown }).messages;
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > 60) return null;
  const messages: ChatMessage[] = [];
  for (const m of raw) {
    if (
      typeof m !== "object" || m === null ||
      ((m as ChatMessage).role !== "user" && (m as ChatMessage).role !== "assistant") ||
      typeof (m as ChatMessage).content !== "string"
    ) {
      return null;
    }
    const content = (m as ChatMessage).content.slice(0, 32_000).trim();
    if (!content) return null;
    messages.push({ role: (m as ChatMessage).role, content });
  }
  if (messages[0].role !== "user" || messages[messages.length - 1].role !== "user") {
    return null;
  }
  return messages;
}

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------
function sseStart(res: Response): void {
  res.status(200);
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();
}

function sseSend(res: Response, payload: Record<string, unknown>): void {
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

// Demo mode: no API credentials configured — stream a canned reply so the
// full product loop (UI → SSE → render) is testable before keys exist.
async function streamDemoReply(res: Response, lastUserMessage: string): Promise<void> {
  const reply =
    `**Demo mode** — no \`ANTHROPIC_API_KEY\` is configured, so this reply is canned.\n\n` +
    `You said: "${lastUserMessage.slice(0, 140)}"\n\n` +
    `Once a key is set in \`.env\`, this exact stream is served by ${MODEL} instead. ` +
    `Everything else — metering, history, streaming — is already live. ⚓`;
  for (const word of reply.split(/(?<= )/)) {
    sseSend(res, { type: "text", text: word });
    await new Promise((r) => setTimeout(r, 12));
  }
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
const app = express();

// Raw body is required for signature verification, so this route is mounted
// ahead of the global JSON parser.
app.post(
  "/api/stripe/webhook",
  express.raw({ type: "application/json" }),
  (req, res) => {
    if (!STRIPE_WEBHOOK_SECRET) {
      res.status(503).json({ error: "webhook_not_configured" });
      return;
    }
    const header = req.headers["stripe-signature"];
    if (typeof header !== "string" || !verifyStripeSignature(req.body, header)) {
      res.status(400).json({ error: "bad_signature" });
      return;
    }
    let event: {
      type?: string;
      data?: { object?: { id?: string; customer_details?: { email?: string } } };
    };
    try {
      event = JSON.parse(req.body.toString("utf8"));
    } catch {
      res.status(400).json({ error: "bad_payload" });
      return;
    }
    if (event.type === "checkout.session.completed" && event.data?.object?.id) {
      paidSessions.set(event.data.object.id, {
        email: event.data.object.customer_details?.email ?? "",
        activatedAt: null,
      });
      console.log(`💰 checkout completed: ${event.data.object.id}`);
    }
    res.json({ received: true });
  },
);

app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "..", "public")));

// Redeemed by success.html after the Stripe Payment Link redirects back with
// ?session_id={CHECKOUT_SESSION_ID}. Idempotent: session ids are unguessable,
// and re-visiting the success page shouldn't strand a paying customer.
app.get("/api/activate", (req, res) => {
  const sid = String(req.query.session_id ?? "");
  const record = sid ? paidSessions.get(sid) : undefined;
  if (!record) {
    res.status(404).json({
      error: "unknown_session",
      message: "Payment not found yet — webhooks can lag a few seconds. Refresh to retry.",
    });
    return;
  }
  record.activatedAt = record.activatedAt ?? Date.now();
  res.setHeader(
    "Set-Cookie",
    `dbl_pro=${makeProCookie()}; Path=/; Max-Age=${PRO_DAYS * 86_400}; HttpOnly; SameSite=Lax`,
  );
  res.json({ ok: true, plan: "pro", days: PRO_DAYS });
});

app.get("/api/me", (req, res) => {
  res.json({ plan: isPro(req) ? "pro" : "free" });
});

app.get("/api/config", (_req, res) => {
  res.json({
    model: MODEL,
    freeDailyLimit: FREE_DAILY_LIMIT,
    paymentLink: PAYMENT_LINK,
    demoMode: !HAS_CREDENTIALS,
  });
});

app.post("/api/chat", async (req, res) => {
  const messages = sanitizeMessages(req.body);
  if (!messages) {
    res.status(400).json({ error: "invalid_request", message: "Bad messages payload." });
    return;
  }

  const pro = isPro(req);
  const uid = getUid(req, res);
  const quota = pro ? { ok: true, remaining: -1 } : checkAndCount(uid);
  if (!quota.ok) {
    res.status(429).json({
      error: "quota_exceeded",
      message: `Free plan is ${FREE_DAILY_LIMIT} messages/day. Upgrade to keep going.`,
      paymentLink: PAYMENT_LINK,
    });
    return;
  }

  sseStart(res);

  if (!client) {
    await streamDemoReply(res, messages[messages.length - 1].content);
    sseSend(res, { type: "done", remaining: quota.remaining, demo: true });
    res.end();
    return;
  }

  try {
    const stream = client.messages.stream({
      model: MODEL,
      max_tokens: MAX_TOKENS,
      thinking: { type: "adaptive" },
      system: [
        {
          type: "text",
          text: SYSTEM_PROMPT,
          cache_control: { type: "ephemeral" },
        },
      ],
      messages,
    });

    for await (const event of stream) {
      if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
        sseSend(res, { type: "text", text: event.delta.text });
      }
    }

    const final = await stream.finalMessage();
    sseSend(res, {
      type: "done",
      remaining: quota.remaining,
      stopReason: final.stop_reason,
      usage: {
        input: final.usage.input_tokens,
        output: final.usage.output_tokens,
        cacheRead: final.usage.cache_read_input_tokens,
      },
    });
  } catch (err) {
    if (err instanceof Anthropic.RateLimitError) {
      sseSend(res, { type: "error", message: "Upstream is busy — try again in a moment." });
    } else if (err instanceof Anthropic.AuthenticationError) {
      sseSend(res, { type: "error", message: "Server API key is invalid. Ping support." });
    } else if (err instanceof Anthropic.APIConnectionError) {
      sseSend(res, { type: "error", message: "Connection to the model dropped. Retry." });
    } else if (err instanceof Anthropic.APIError) {
      sseSend(res, { type: "error", message: `Model error (${err.status ?? "?"}).` });
    } else {
      sseSend(res, { type: "error", message: "Unexpected server error." });
    }
  }
  res.end();
});

app.get("/healthz", (_req, res) => {
  res.json({ ok: true, demoMode: !HAS_CREDENTIALS });
});

app.listen(PORT, () => {
  console.log(
    `⚓ Doubloon listening on http://localhost:${PORT}` +
      (HAS_CREDENTIALS ? ` (model: ${MODEL})` : " (DEMO MODE — no API key)"),
  );
});
