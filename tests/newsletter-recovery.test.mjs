import assert from "node:assert/strict";
import test from "node:test";

import {
  romeHour,
  runRecovery,
} from "../netlify/functions/newsletter-recovery.mjs";

test("riconosce le 07:30 italiane durante l'ora legale", () => {
  assert.equal(romeHour(new Date("2026-08-28T05:30:00Z")), 7);
});

test("riconosce le 07:30 italiane durante l'ora solare", () => {
  assert.equal(romeHour(new Date("2026-12-28T06:30:00Z")), 7);
});

test("richiede a GitHub il workflow recovery alle 07:30 italiane", async () => {
  let request;
  const result = await runRecovery({
    now: new Date("2026-08-28T05:30:00Z"),
    token: "test-token",
    fetchImpl: async (url, options) => {
      request = { url, options };
      return new Response(null, { status: 204 });
    },
  });

  assert.deepEqual(result, { triggered: true });
  assert.equal(
    request.url,
    "https://api.github.com/repos/adseeker/siracusadaily/actions/workflows/newsletter-daily.yml/dispatches",
  );
  assert.equal(request.options.method, "POST");
  assert.equal(request.options.headers.authorization, "Bearer test-token");
  assert.deepEqual(JSON.parse(request.options.body), {
    ref: "main",
    inputs: { mode: "recovery" },
  });
});

test("ignora la seconda finestra UTC quando a Roma non sono le 07", async () => {
  let called = false;
  const result = await runRecovery({
    now: new Date("2026-08-28T06:30:00Z"),
    token: "test-token",
    fetchImpl: async () => {
      called = true;
      return new Response(null, { status: 204 });
    },
  });

  assert.deepEqual(result, { triggered: false });
  assert.equal(called, false);
});

test("fallisce in modo visibile se manca il token GitHub", async () => {
  await assert.rejects(
    runRecovery({ now: new Date("2026-08-28T05:30:00Z"), token: "" }),
    /SIRACUSA_GITHUB_ACTIONS_TOKEN/,
  );
});
