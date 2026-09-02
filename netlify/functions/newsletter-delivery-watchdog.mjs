const ROME_TIME_ZONE = "Europe/Rome";
const WATCHDOG_HOUR = 9;
const REPOSITORY = "adseeker/siracusadaily";
const WORKFLOW = "newsletter-delivery-watchdog.yml";
const REF = "main";

export function romeHour(now) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: ROME_TIME_ZONE,
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  return Number(parts.find((part) => part.type === "hour")?.value);
}

export async function runDeliveryWatchdog({
  now = new Date(),
  token = process.env.SIRACUSA_GITHUB_ACTIONS_TOKEN,
  fetchImpl = fetch,
} = {}) {
  // Netlify invokes both UTC windows; only the one matching 09:00 in Rome
  // dispatches the check, independently of daylight-saving time.
  if (romeHour(now) !== WATCHDOG_HOUR) {
    console.log(`Controllo consegna escluso in questa finestra UTC: ${now.toISOString()}`);
    return { triggered: false };
  }
  if (!token) {
    throw new Error("SIRACUSA_GITHUB_ACTIONS_TOKEN non configurato su Netlify");
  }

  const response = await fetchImpl(
    `https://api.github.com/repos/${REPOSITORY}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        accept: "application/vnd.github+json",
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
        "x-github-api-version": "2022-11-28",
      },
      body: JSON.stringify({ ref: REF }),
    },
  );
  if (response.status !== 204) {
    const detail = await response.text();
    throw new Error(`GitHub delivery watchdog dispatch fallito (${response.status}): ${detail}`);
  }
  console.log("Controllo consegna SiracusaDaily richiesto a GitHub Actions");
  return { triggered: true };
}

export async function handler() {
  const result = await runDeliveryWatchdog();
  return {
    statusCode: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify(result),
  };
}
