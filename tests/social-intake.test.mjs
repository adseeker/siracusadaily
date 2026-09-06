import assert from "node:assert/strict";
import test from "node:test";

import { handler } from "../netlify/functions/social-intake.mjs";

test("l'intake pubblico estrae contenuti senza token di accesso", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalOpenAIKey = process.env.OPENAI_API_KEY;
  const originalIntakeToken = process.env.SIRACUSA_INTAKE_TOKEN;
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalOpenAIKey === undefined) delete process.env.OPENAI_API_KEY;
    else process.env.OPENAI_API_KEY = originalOpenAIKey;
    if (originalIntakeToken === undefined) delete process.env.SIRACUSA_INTAKE_TOKEN;
    else process.env.SIRACUSA_INTAKE_TOKEN = originalIntakeToken;
  });

  process.env.OPENAI_API_KEY = "test-openai-key";
  delete process.env.SIRACUSA_INTAKE_TOKEN;
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.headers.authorization, "Bearer test-openai-key");
    return Response.json({
      output_text: JSON.stringify({
        contenuti: [{
          pubblicabile: true,
          motivo_esclusione: "",
          titolo: "Evento di prova",
          tipo: "Evento",
          categoria: "Eventi",
          data_inizio: "2026-09-06",
          data_fine: "",
          ora: "18:00",
          luogo: "Siracusa",
          indirizzo: "",
          organizzatore: "",
          prezzo: "",
          link: "",
          provenienza_campi: "caption",
          confidenza: "Alta",
          da_rivedere: false,
        }],
      }),
    });
  };

  const response = await handler({
    httpMethod: "POST",
    headers: {},
    body: JSON.stringify({ action: "extract", text: "Evento a Siracusa alle 18" }),
  });

  assert.equal(response.statusCode, 200);
  const body = JSON.parse(response.body);
  assert.equal(body.items[0].titolo, "Evento di prova");
});
