import assert from "node:assert/strict";
import test from "node:test";

import {
  romeHour,
  runDeliveryWatchdog,
} from "../netlify/functions/newsletter-delivery-watchdog.mjs";

test("riconosce le 09 italiane durante l'ora legale", () => {
  assert.equal(romeHour(new Date("2026-09-02T07:00:00Z")), 9);
});

test("riconosce le 09 italiane durante l'ora solare", () => {
  assert.equal(romeHour(new Date("2026-12-02T08:00:00Z")), 9);
});

test("richiede a GitHub il workflow di controllo alle 09 italiane", async () => {
  let request;
  const result = await runDeliveryWatchdog({
    now: new Date("2026-09-02T07:00:00Z"),
    token: "test-token",
    fetchImpl: async (url, options) => {
      request = { url, options };
      return new Response(null, { status: 204 });
    },
  });

  assert.deepEqual(result, { triggered: true });
  assert.equal(
    request.url,
    "https://api.github.com/repos/adseeker/siracusadaily/actions/workflows/newsletter-delivery-watchdog.yml/dispatches",
  );
  assert.equal(request.options.headers.authorization, "Bearer test-token");
  assert.deepEqual(JSON.parse(request.options.body), { ref: "main" });
});

test("ignora la finestra UTC che non corrisponde alle 09 a Roma", async () => {
  let called = false;
  const result = await runDeliveryWatchdog({
    now: new Date("2026-09-02T08:00:00Z"),
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
    runDeliveryWatchdog({ now: new Date("2026-09-02T07:00:00Z"), token: "" }),
    /SIRACUSA_GITHUB_ACTIONS_TOKEN/,
  );
});
