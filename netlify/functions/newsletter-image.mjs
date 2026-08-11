import crypto from "node:crypto";
import { connectLambda, getStore } from "@netlify/blobs";

const STORE_NAME = "newsletter-images";
const MAX_IMAGE_BYTES = 300_000;
const KEY_PATTERN = /^\d{4}-\d{2}-\d{2}\/(notizie|cultura|sport|eventi)-[a-f0-9]{12}\.jpg$/;

function json(statusCode, body) {
  return {
    statusCode,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "private, no-store, max-age=0",
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

function validKey(event) {
  const key = event.queryStringParameters?.key || "";
  return KEY_PATTERN.test(key) ? key : null;
}

export async function handler(event) {
  const method = event.httpMethod || "GET";
  const key = validKey(event);
  if (!key) return json(400, { error: "Chiave immagine non valida" });

  if (method === "PUT") {
    if (!authorized(event)) return json(401, { error: "Non autorizzato" });
    const contentType = String(event.headers["content-type"] || "").toLowerCase();
    if (contentType !== "image/jpeg") {
      return json(415, { error: "Sono ammesse soltanto immagini JPEG ottimizzate" });
    }
    const payload = Buffer.from(event.body || "", event.isBase64Encoded ? "base64" : "binary");
    if (!payload.length || payload.length > MAX_IMAGE_BYTES) {
      return json(413, { error: "Dimensione immagine non valida" });
    }
    if (!(payload[0] === 0xff && payload[1] === 0xd8 && payload[2] === 0xff)) {
      return json(415, { error: "Contenuto JPEG non valido" });
    }
    connectLambda(event);
    const store = getStore(STORE_NAME);
    await store.set(key, payload, {
      metadata: {
        contentType: "image/jpeg",
        uploadedAt: new Date().toISOString(),
      },
    });
    return json(201, { key, path: `/media/newsletter/${key}` });
  }

  if (method !== "GET" && method !== "HEAD") {
    return { statusCode: 405, headers: { allow: "GET, HEAD, PUT" }, body: "" };
  }

  connectLambda(event);
  const store = getStore(STORE_NAME);
  const entry = await store.getWithMetadata(key, { type: "arrayBuffer" });
  if (entry === null) return json(404, { error: "Immagine non trovata" });
  const headers = {
    "content-type": entry.metadata?.contentType || "image/jpeg",
    "content-length": String(entry.data.byteLength),
    "cache-control": "public, max-age=31536000, immutable",
    "netlify-cdn-cache-control": "public, durable, s-maxage=31536000, stale-while-revalidate=86400",
    "x-content-type-options": "nosniff",
  };
  if (entry.etag) headers.etag = entry.etag;
  if (method === "HEAD") return { statusCode: 200, headers, body: "" };
  return {
    statusCode: 200,
    headers,
    isBase64Encoded: true,
    body: Buffer.from(entry.data).toString("base64"),
  };
}
