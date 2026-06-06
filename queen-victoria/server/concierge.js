// Shared AI Concierge logic — used by both the local Express route and the
// Netlify serverless function. I/O-agnostic: exposes an async generator that
// yields reply text chunks, whether powered by Claude or the local fallback.

import Anthropic from "@anthropic-ai/sdk";
import { restaurant } from "./data/restaurant.js";
import { menu } from "./data/menu.js";

export const MODEL = process.env.ANTHROPIC_MODEL || "claude-opus-4-8";
export const hasKey = Boolean(process.env.ANTHROPIC_API_KEY);

let _client = null;
function getClient() {
  if (!hasKey) return null;
  if (!_client) _client = new Anthropic();
  return _client;
}

function menuToText() {
  return menu.categories
    .map((c) => {
      const items = c.items
        .map((i) => `  - ${i.name} (HK$${i.price})${i.description ? `: ${i.description}` : ""}`)
        .join("\n");
      return `${c.name}${c.description ? ` — ${c.description}` : ""}\n${items}`;
    })
    .join("\n\n");
}

const KNOWLEDGE = `
ABOUT
${restaurant.name} — ${restaurant.tagline}. Established ${restaurant.established}.
${restaurant.description}
Cuisine: ${restaurant.cuisine.join(", ")}. Typical spend: ${restaurant.pricePerPerson} per person.
Rating: ${restaurant.ratings.average}/5 from ${restaurant.ratings.count} ${restaurant.ratings.source} reviews.

LOCATION
${restaurant.address.full}
Plus code: ${restaurant.address.plusCode}. Nearest MTR: Wan Chai (Exit A3), ~5 minutes' walk.

CONTACT
Phone: ${restaurant.contact.phoneDisplay} (${restaurant.contact.phone}). Email: ${restaurant.contact.email}.

OPENING HOURS
${restaurant.hours.map((h) => `${h.day}: ${h.label}`).join("\n")}
${restaurant.hoursSummary}

WHAT'S ON
${restaurant.highlights.map((h) => `- ${h.title}: ${h.detail}`).join("\n")}

FEATURES
${restaurant.features.join(", ")}.

RESERVATIONS POLICY
Guests can book online on this website (the "Reserve" page) or by phone. Party sizes ${restaurant.reservation.minPartySize}-${restaurant.reservation.maxPartySize}. Parties of ${restaurant.reservation.largePartyThreshold}+ are confirmed manually by the team. Online seatings run ${restaurant.reservation.firstSeating}-${restaurant.reservation.lastSeating}; for later, call the bar.

MENU
${menuToText()}

FREQUENTLY ASKED
${restaurant.faq.map((f) => `Q: ${f.q}\nA: ${f.a}`).join("\n\n")}
`.trim();

export const SYSTEM_PROMPT = `You are the AI Concierge for The Queen Victoria, a British dining house and bar in Wan Chai, Hong Kong. You are warm, charming and genuinely helpful — think of a brilliant maître d' with a dry British wit, never stuffy.

Use ONLY the knowledge below to answer questions about the venue. If something isn't covered (e.g. a real-time table count, a specific allergy clearance, or today's exact guest ale), say you don't have that detail to hand and point the guest to book online, call ${restaurant.contact.phoneDisplay}, or ask the team on arrival. Never invent prices, dishes, hours or policies.

Guidelines:
- Keep replies concise and friendly — usually 1-3 short paragraphs. Use the occasional tasteful emoji only when it fits (🍺 🥧), never more than one.
- Prices are in Hong Kong dollars (HK$).
- When a guest wants to book, encourage them to use the Reserve page on this site or call ${restaurant.contact.phoneDisplay}. You cannot make the booking yourself, but you can guide them.
- Recommend signature dishes when asked what's good: the Steak & Ale Pie, Fish & Chips, the Queen Vic Burger and Sticky Toffee Pudding are favourites.
- Always answer in English.

KNOWLEDGE BASE:
${KNOWLEDGE}`;

// Deterministic, knowledge-base-driven responder used when no API key is set
// (and as a safety net if a live call fails). Always returns a useful answer.
export function fallbackReply(message) {
  const m = String(message || "").toLowerCase();
  const r = restaurant;
  const pick = (...phrases) => phrases.join(" ");

  if (/(happy hour|happyhour|deal|cheap|discount)/.test(m))
    return "Our happy hour is one of Wan Chai's best — half-price house pints, wines and selected spirits every weekday from open until 8 pm. 🍺";
  if (/(hour|open|close|time|when.*open)/.test(m))
    return pick("We're open daily from noon. 🕛", r.hoursSummary, "Here's the week: " + r.hours.map((h) => `${h.day.slice(0, 3)} ${h.label}`).join("; ") + ".");
  if (/(quiz|trivia)/.test(m))
    return "Quiz night is every Tuesday at 8 pm — teams of up to six, free to enter, and the winners take a bar tab. Book a table so you don't miss out.";
  if (/(where|location|address|find|map|mtr|getting)/.test(m))
    return `You'll find us at ${r.address.full}. We're about five minutes from Wan Chai MTR (Exit A3). Plus code ${r.address.plusCode}.`;
  if (/(book|reserv|table)/.test(m))
    return `Happy to help! You can book a table on the Reserve page right here on our site, or call us on ${r.contact.phoneDisplay}. For groups of ${r.reservation.largePartyThreshold} or more we'll confirm the details personally.`;
  if (/(pie)/.test(m))
    return "The pies are our pride and joy — all-butter pastry and proper gravy. The Steak & Ale Pie (HK$168) is the one we're known for, and there's always a Pie of the Day. 🥧";
  if (/(fish|chips)/.test(m))
    return "Our Fish & Chips (HK$178) is beer-battered North Atlantic cod with triple-cooked chips, mushy peas and tartare. A proper plate.";
  if (/(burger)/.test(m))
    return "The Queen Vic Burger (HK$158) — two smashed beef patties, cheddar, bacon, house sauce and fries. There's a buttermilk chicken and a plant-based Beyond version too.";
  if (/(veg|vegan|vegetarian|plant)/.test(m))
    return "Plenty for you — wild mushroom & spinach pie, halloumi fries, the Beyond Burger, mac & cheese and more. Just flag any allergies and the kitchen will guide you.";
  if (/(gin|cocktail|drink|beer|ale|wine|guinness)/.test(m))
    return "The bar's the heart of the place: hand-pulled ales, a properly poured Guinness, over forty gins in our Gin Library, and classic cocktails like a Pimm's or an Espresso Martini.";
  if (/(menu|eat|food|dish|serve)/.test(m))
    return "We serve British pub classics all day — pies, fish & chips, bangers & mash, burgers, an all-day breakfast and puddings like sticky toffee. The full menu is on the Menu page. What are you in the mood for?";
  if (/(event|private|party|birthday|function|corporate)/.test(m))
    return `We'd love to host you. We do birthdays, corporate drinks, leaving dos and watch parties — fill in the private events form on the Contact page or email ${r.contact.email}.`;
  if (/(dog|pet)/.test(m)) return "Well-behaved dogs are very welcome in the bar. 🐾";
  if (/(sport|football|rugby|match|premier|game)/.test(m))
    return "We show all the big fixtures — Premier League, rugby, the Six Nations and more — across our screens. Message us to check what's on and grab a good seat.";
  if (/(deliver|takeaway|take away|pick up)/.test(m))
    return "Yes — the full menu is available for dine-in, takeaway and delivery around Wan Chai.";
  if (/(hello|hi|hey|good (morning|afternoon|evening))/.test(m))
    return "Hello and welcome to The Queen Victoria! 🍺 I can help with our menu, opening hours, happy hour, the quiz, bookings and finding us. What can I get you?";
  if (/(thank|cheers|ta )/.test(m)) return "My pleasure — cheers! Anything else I can help with?";

  return `I can tell you about our menu, opening hours, happy hour, quiz night, private events and how to find us — or help you book a table. For anything specific, call us on ${r.contact.phoneDisplay}. What would you like to know?`;
}

// Cap and sanitise client-supplied history; ensure first message is from user.
export function buildMessages(history, message) {
  const msgs = [];
  if (Array.isArray(history)) {
    for (const turn of history.slice(-8)) {
      if (turn && (turn.role === "user" || turn.role === "assistant")) {
        const content = String(turn.content || "").trim().slice(0, 1500);
        if (content) msgs.push({ role: turn.role, content });
      }
    }
  }
  msgs.push({ role: "user", content: message });
  while (msgs.length && msgs[0].role !== "user") msgs.shift();
  return msgs;
}

// Async generator yielding reply text chunks. Powers both transports.
export async function* streamReply(message, history) {
  const client = getClient();
  if (!client) {
    for (const word of fallbackReply(message).split(/(\s+)/)) if (word) yield word;
    return;
  }
  try {
    const stream = client.messages.stream({
      model: MODEL,
      max_tokens: 1024,
      system: [{ type: "text", text: SYSTEM_PROMPT, cache_control: { type: "ephemeral" } }],
      thinking: { type: "adaptive" },
      output_config: { effort: "low" },
      messages: buildMessages(history, message),
    });
    for await (const event of stream) {
      if (event.type === "content_block_delta" && event.delta?.type === "text_delta") {
        yield event.delta.text;
      }
    }
    await stream.finalMessage().catch(() => {});
  } catch (err) {
    console.error("[concierge] live error, falling back:", err?.message || err);
    yield fallbackReply(message);
  }
}

export default { streamReply, fallbackReply, buildMessages, SYSTEM_PROMPT, MODEL, hasKey };
