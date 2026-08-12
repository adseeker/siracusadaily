import crypto from "node:crypto";

// Intake manuale delle fonti social: riceve uno screenshot e/o una caption,
// estrae i campi rilevanti con un modello multimodale e scrive una riga
// strutturata nel database Notion "Raccolta manuale — Fonti Social".

const OPENAI_API = "https://api.openai.com/v1/responses";
const NOTION_API = "https://api.notion.com/v1/pages";
const NOTION_VERSION = "2022-06-28";
const MODEL = process.env.SIRACUSA_INTAKE_MODEL || "gpt-5-mini";
const MAX_IMAGE_BYTES = 6_000_000; // limite sull'immagine in ingresso (base64 decodificato)

const TIPI = ["Evento", "News", "Lavoro", "Avviso"];
const CATEGORIE = [
  "Notizie e cronaca",
  "Politica ed economia",
  "Cultura",
  "Sport",
  "Servizi e utilità",
  "Eventi",
  "Lavoro e opportunità",
];
const CONFIDENZE = ["Alta", "Media", "Bassa"];

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
  const configured = process.env.SIRACUSA_INTAKE_TOKEN || "";
  const supplied = (event.headers.authorization || event.headers.Authorization || "")
    .replace(/^Bearer\s+/i, "");
  if (!configured || !supplied) return false;
  const expected = Buffer.from(configured);
  const actual = Buffer.from(supplied);
  return expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
}

// Converte un data URL (data:image/...;base64,XXXX) in { mediaType, bytes }.
function parseDataUrl(value) {
  const match = /^data:(image\/(?:png|jpe?g|webp|gif));base64,([A-Za-z0-9+/=]+)$/.exec(value || "");
  if (!match) return null;
  const bytes = Buffer.from(match[2], "base64");
  if (!bytes.length || bytes.length > MAX_IMAGE_BYTES) return null;
  return { mediaType: match[1], dataUrl: value, size: bytes.length };
}

const ITEM_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    pubblicabile: { type: "boolean" },
    motivo_esclusione: { type: "string" },
    titolo: { type: "string" },
    tipo: { type: "string", enum: TIPI },
    categoria: { type: "string", enum: CATEGORIE },
    data_inizio: { type: "string", description: "AAAA-MM-GG oppure stringa vuota" },
    data_fine: { type: "string", description: "AAAA-MM-GG oppure stringa vuota" },
    ora: { type: "string" },
    luogo: { type: "string" },
    indirizzo: { type: "string" },
    organizzatore: { type: "string" },
    prezzo: { type: "string" },
    link: { type: "string" },
    provenienza_campi: { type: "string", description: "Da dove viene ogni campo: immagine, caption, metadato" },
    confidenza: { type: "string", enum: CONFIDENZE },
    da_rivedere: { type: "boolean" },
  },
  required: [
    "pubblicabile", "motivo_esclusione", "titolo", "tipo", "categoria",
    "data_inizio", "data_fine", "ora", "luogo", "indirizzo", "organizzatore",
    "prezzo", "link", "provenienza_campi", "confidenza", "da_rivedere",
  ],
};

// Un post può contenere più eventi distinti: l'estrazione restituisce un elenco,
// un elemento per ciascun contenuto separato.
const EXTRACTION_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    contenuti: { type: "array", items: ITEM_SCHEMA },
  },
  required: ["contenuti"],
};

function buildPrompt({ text, link, account, today }) {
  return [
    "Sei un redattore di SiracusaDaily, una newsletter locale su Siracusa e provincia.",
    "Ricevi il materiale grezzo di un post social (una locandina come immagine e/o la caption).",
    "Restituisci un elenco 'contenuti': UN elemento per ogni evento/contenuto DISTINTO presente nel materiale.",
    "Se il post contiene più date o più eventi separati (anche con organizzatori, luoghi od orari diversi), crea un elemento distinto per CIASCUNO, ognuno con la propria data, ora, luogo e organizzatore.",
    "Se invece è un unico contenuto, restituisci un solo elemento. Non unire mai eventi con date diverse nello stesso elemento.",
    "Estrai SOLO le informazioni effettivamente presenti nel materiale. Non inventare nulla.",
    "Se un campo non è ricavabile, lascialo come stringa vuota.",
    "Fondi le evidenze: la locandina di solito porta data, ora e luogo; la caption porta contesto, organizzatore e link.",
    "In 'provenienza_campi' indica in modo sintetico da dove viene ogni dato (immagine/caption/metadato) e segnala eventuali contraddizioni.",
    "Metti 'da_rivedere' a true se ci sono conflitti tra immagine e caption, dati mancanti importanti, o testo illeggibile.",
    "Le date relative ('domani', 'sabato', 'questo weekend') vanno risolte rispetto a oggi, " + today + ", e la loro natura inferita va notata in provenienza_campi.",
    "'tipo': Evento (appuntamento datato), News (notizia/cronaca), Lavoro (offerta/concorso), Avviso (servizio/utilità).",
    "'categoria': scegli tra le sezioni della newsletter coerente con il contenuto.",
    "'pubblicabile' è false se il post è pura promozione senza informazione concreta, non è locale a Siracusa/provincia, o è illeggibile: in tal caso spiega in 'motivo_esclusione'.",
    "Tutto il testo in italiano.",
    account ? `Account di provenienza dichiarato: ${account}` : "",
    link ? `Link/permalink fornito: ${link}` : "",
    text ? `Caption fornita:\n"""${text}"""` : "Nessuna caption testuale fornita: usa l'immagine.",
  ].filter(Boolean).join("\n");
}

async function extract({ image, text, link, account }) {
  const apiKey = process.env.SIRACUSA_INTAKE_OPENAI_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("SIRACUSA_INTAKE_OPENAI_KEY non configurata sul server");
  const today = new Date().toISOString().slice(0, 10);
  const content = [{ type: "input_text", text: buildPrompt({ text, link, account, today }) }];
  if (image) content.push({ type: "input_image", image_url: image.dataUrl });

  const result = await fetch(OPENAI_API, {
    method: "POST",
    headers: {
      authorization: `Bearer ${apiKey}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      input: [{ role: "user", content }],
      text: {
        format: {
          type: "json_schema",
          name: "estrazione_social",
          strict: true,
          schema: EXTRACTION_SCHEMA,
        },
      },
    }),
    signal: AbortSignal.timeout(120000),
  });
  if (!result.ok) {
    const detail = (await result.text()).slice(0, 400);
    throw new Error(`OpenAI ${result.status}: ${detail || result.statusText}`);
  }
  const payload = await result.json();
  const raw = readOutputText(payload);
  if (!raw) throw new Error("Risposta del modello vuota");
  const parsed = JSON.parse(raw);
  return Array.isArray(parsed.contenuti) ? parsed.contenuti : [];
}

function readOutputText(payload) {
  if (typeof payload.output_text === "string" && payload.output_text) return payload.output_text;
  for (const item of payload.output || []) {
    for (const part of item.content || []) {
      if (part.type === "refusal") throw new Error(part.refusal || "Richiesta rifiutata dal modello");
      if (part.type === "output_text" && part.text) return part.text;
    }
  }
  return "";
}

// Costruisce le proprietà Notion, omettendo i campi vuoti per non rompere lo schema.
function notionProperties(data, { link, account }) {
  const props = {};
  const richText = (value) => ({ rich_text: [{ type: "text", text: { content: String(value).slice(0, 1900) } }] });
  const setText = (name, value) => { if (value && String(value).trim()) props[name] = richText(value); };
  const setSelect = (name, value, allowed) => { if (value && allowed.includes(value)) props[name] = { select: { name: value } }; };
  const setDate = (name, value) => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(value || "")) props[name] = { date: { start: value } };
  };

  props["Titolo"] = { title: [{ type: "text", text: { content: (data.titolo || "Senza titolo").slice(0, 190) } }] };
  setSelect("Tipo", data.tipo, TIPI);
  setSelect("Categoria", data.categoria, CATEGORIE);
  setDate("Data inizio", data.data_inizio);
  setDate("Data fine", data.data_fine);
  setText("Ora", data.ora);
  setText("Luogo", data.luogo);
  setText("Indirizzo", data.indirizzo);
  setText("Organizzatore", data.organizzatore);
  setText("Prezzo", data.prezzo);
  const finalLink = data.link || link || "";
  if (/^https?:\/\//i.test(finalLink)) props["Link"] = { url: finalLink };
  setText("Fonte account", account || "");
  setText("Testo grezzo", data._captionRaw || "");
  setText("Provenienza campi", data.provenienza_campi);
  setSelect("Confidenza", data.confidenza, CONFIDENZE);
  props["Da rivedere"] = { checkbox: Boolean(data.da_rivedere) };
  props["Stato"] = { select: { name: "Da elaborare" } };
  return props;
}

async function createNotionRow(data, context) {
  const token = process.env.NOTION_TOKEN;
  const databaseId = process.env.NOTION_SOCIAL_DB_ID;
  if (!token) throw new Error("NOTION_TOKEN non configurato sul server");
  if (!databaseId) throw new Error("NOTION_SOCIAL_DB_ID non configurato sul server");
  const iconByType = { Evento: "🎟️", News: "📰", Lavoro: "💼", Avviso: "⚠️" };
  const result = await fetch(NOTION_API, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "notion-version": NOTION_VERSION,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      parent: { database_id: databaseId },
      icon: { type: "emoji", emoji: iconByType[data.tipo] || "📥" },
      properties: notionProperties(data, context),
    }),
    signal: AbortSignal.timeout(15000),
  });
  if (!result.ok) {
    const detail = (await result.text()).slice(0, 400);
    throw new Error(`Notion ${result.status}: ${detail || result.statusText}`);
  }
  return result.json();
}

export async function handler(event) {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: { allow: "POST, OPTIONS" }, body: "" };
  }
  if (event.httpMethod !== "POST") return json(405, { error: "Metodo non consentito" });
  if (!process.env.SIRACUSA_INTAKE_TOKEN) {
    return json(503, { error: "Intake non configurato sul server" });
  }
  if (!authorized(event)) return json(401, { error: "Codice di accesso non valido" });

  let body;
  try {
    body = JSON.parse(event.isBase64Encoded ? Buffer.from(event.body || "", "base64").toString("utf-8") : (event.body || "{}"));
  } catch {
    return json(400, { error: "Corpo della richiesta non valido" });
  }

  const text = typeof body.text === "string" ? body.text.trim() : "";
  const link = typeof body.link === "string" ? body.link.trim() : "";
  const account = typeof body.account === "string" ? body.account.trim() : "";
  // action: "extract" analizza soltanto; "save" scrive su Notion partendo da un
  // risultato già estratto; "full" (default) fa entrambe le cose in un colpo.
  const action = ["extract", "save", "full"].includes(body.action) ? body.action : "full";

  // Fase di sola scrittura: riusa gli eventi già estratti, una riga Notion ciascuno.
  if (action === "save") {
    const items = Array.isArray(body.items) ? body.items.filter((item) => item && item.titolo) : [];
    if (!items.length) {
      return json(400, { error: "Nessun contenuto estratto da salvare" });
    }
    const results = [];
    const errors = [];
    for (const item of items) {
      item._captionRaw = text;
      try {
        const page = await createNotionRow(item, { link, account });
        results.push({ url: page.url, id: page.id, titolo: item.titolo });
      } catch (error) {
        errors.push(`${item.titolo}: ${error.message}`);
      }
    }
    if (!results.length) {
      return json(502, { error: `Scrittura Notion fallita: ${errors.join("; ")}` });
    }
    return json(201, { created: true, results, errors });
  }

  // Fasi con estrazione ("extract" e "full").
  const image = body.image ? parseDataUrl(body.image) : null;
  if (body.image && !image) {
    return json(400, { error: "Immagine non valida: usa PNG/JPEG/WebP fino a ~6 MB" });
  }
  if (!image && !text) {
    return json(400, { error: "Serve almeno uno screenshot o del testo" });
  }

  let items;
  try {
    items = await extract({ image, text, link, account });
  } catch (error) {
    return json(502, { error: `Estrazione fallita: ${error.message}` });
  }
  for (const item of items) item._captionRaw = text;

  if (!items.length) {
    return json(200, { created: false, reason: "Nessun contenuto rilevante trovato", items: [] });
  }

  // Sola estrazione: restituisce gli eventi senza scrivere, la scrittura arriva dopo.
  if (action === "extract") {
    return json(200, { created: false, items });
  }

  // "full": estrae e salva tutti gli eventi pubblicabili in un colpo.
  const publishable = items.filter((item) => item.pubblicabile !== false);
  const results = [];
  const errors = [];
  for (const item of publishable) {
    try {
      const page = await createNotionRow(item, { link, account });
      results.push({ url: page.url, id: page.id, titolo: item.titolo });
    } catch (error) {
      errors.push(`${item.titolo}: ${error.message}`);
    }
  }
  if (!results.length) {
    return json(502, { error: `Scrittura Notion fallita: ${errors.join("; ") || "nessun contenuto pubblicabile"}`, items });
  }
  return json(201, { created: true, results, errors, items });
}
