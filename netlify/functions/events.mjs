import crypto from "node:crypto";
import { connectLambda, getStore } from "@netlify/blobs";

// Archivio eventi pubblico servito a /eventi. La pipeline carica l'intero feed
// (PUT autenticato); la pagina lo consuma paginato (GET) o per singolo evento.

const STORE_NAME = "events-feed";
const FEED_KEY = "feed.json";
const MAX_FEED_BYTES = 5_000_000;
const DEFAULT_PAGE_SIZE = Number(process.env.EVENTS_PAGE_SIZE || 24);

function json(statusCode, body, cache = "no-store") {
  return {
    statusCode,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": cache,
      "netlify-cdn-cache-control": cache === "no-store"
        ? "no-store"
        : "public, durable, s-maxage=300, stale-while-revalidate=86400",
      "x-content-type-options": "nosniff",
    },
    body: JSON.stringify(body),
  };
}

function authorized(event) {
  const configured = process.env.SIRACUSA_IMAGE_UPLOAD_TOKEN || "";
  const supplied = (event.headers.authorization || event.headers.Authorization || "")
    .replace(/^Bearer\s+/i, "");
  if (!configured || !supplied) return false;
  const expected = Buffer.from(configured);
  const actual = Buffer.from(supplied);
  return expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
}

async function readFeed(event) {
  connectLambda(event);
  const store = getStore(STORE_NAME);
  const raw = await store.get(FEED_KEY, { type: "json" });
  return raw && Array.isArray(raw.events) ? raw : { generated_at: null, events: [] };
}

export async function handler(event) {
  const method = event.httpMethod || "GET";

  if (method === "PUT") {
    if (!authorized(event)) return json(401, { error: "Non autorizzato" });
    const contentType = String(event.headers["content-type"] || "").toLowerCase();
    if (!contentType.includes("application/json")) {
      return json(415, { error: "Sono ammessi soltanto feed JSON" });
    }
    const body = event.isBase64Encoded
      ? Buffer.from(event.body || "", "base64").toString("utf-8")
      : (event.body || "");
    if (!body || body.length > MAX_FEED_BYTES) {
      return json(413, { error: "Dimensione feed non valida" });
    }
    let parsed;
    try {
      parsed = JSON.parse(body);
    } catch {
      return json(400, { error: "JSON non valido" });
    }
    if (!parsed || !Array.isArray(parsed.events)) {
      return json(422, { error: "Il feed deve contenere un array 'events'" });
    }
    connectLambda(event);
    const store = getStore(STORE_NAME);
    await store.setJSON(FEED_KEY, parsed);
    return json(201, { stored: parsed.events.length });
  }

  if (method !== "GET") {
    return { statusCode: 405, headers: { allow: "GET, PUT" }, body: "" };
  }

  const params = event.queryStringParameters || {};
  const feed = await readFeed(event);

  // Dettaglio di un singolo evento.
  if (params.event) {
    const found = feed.events.find((item) => item.id === params.event);
    if (!found) return json(404, { error: "Evento non trovato" });
    return json(200, { event: found, generated_at: feed.generated_at }, "public");
  }

  // Lista paginata per ambito.
  const scope = params.scope === "past" ? "past" : "upcoming";
  const size = Math.min(60, Math.max(1, Number(params.size) || DEFAULT_PAGE_SIZE));
  const page = Math.max(1, Number(params.page) || 1);
  const filtered = feed.events.filter((item) => (scope === "past" ? item.past : !item.past));
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / size));
  const start = (page - 1) * size;
  const events = filtered.slice(start, start + size);
  return json(200, {
    events,
    page,
    size,
    total,
    total_pages: totalPages,
    scope,
    generated_at: feed.generated_at,
  }, "public");
}
