import { Router } from "express";
import { streamReply, hasKey, MODEL } from "../concierge.js";
import { clean } from "../middleware/validate.js";
import { chatLimiter } from "../middleware/rateLimit.js";

const router = Router();

// POST /api/chat — streams the concierge reply as Server-Sent Events.
router.post("/", chatLimiter, async (req, res) => {
  const message = clean(req.body?.message, 1500);
  if (!message) return res.status(422).json({ ok: false, error: "Please type a message for the concierge." });

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  send("start", { model: hasKey ? MODEL : "concierge-local", powered: hasKey });

  let aborted = false;
  req.on("close", () => { aborted = true; });

  let full = "";
  try {
    for await (const chunk of streamReply(message, req.body?.history)) {
      if (aborted) break;
      full += chunk;
      send("delta", { text: chunk });
    }
    if (!aborted) { send("done", { text: full }); }
  } catch (err) {
    console.error("[chat] error:", err?.message || err);
    if (!aborted) send("done", { text: full || "Apologies — please call us on 2529 7800.", degraded: true });
  } finally {
    res.end();
  }
});

export default router;
