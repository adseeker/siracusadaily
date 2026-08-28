const ROME_TIME_ZONE = "Europe/Rome";
const RECOVERY_HOUR = 7;
const REPOSITORY = "adseeker/siracusadaily";
const WORKFLOW = "newsletter-daily.yml";
const REF = "main";

export function romeHour(now) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: ROME_TIME_ZONE,
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  return Number(parts.find((part) => part.type === "hour")?.value);
}

export async function runRecovery({
  now = new Date(),
  token = process.env.SIRACUSA_GITHUB_ACTIONS_TOKEN,
  fetchImpl = fetch,
} = {}) {
  // La funzione gira alle 05:30 e alle 06:30 UTC. Questo controllo seleziona
  // automaticamente l'invocazione che corrisponde alle 07:30 Europe/Rome,
  // sia con l'ora solare sia con l'ora legale.
  if (romeHour(now) !== RECOVERY_HOUR) {
    console.log(`Recupero non necessario in questa finestra UTC: ${now.toISOString()}`);
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
      body: JSON.stringify({ ref: REF, inputs: { mode: "recovery" } }),
    },
  );

  if (response.status !== 204) {
    const detail = await response.text();
    throw new Error(`GitHub workflow dispatch fallito (${response.status}): ${detail}`);
  }

  console.log("Workflow di recupero SiracusaDaily richiesto a GitHub Actions");
  return { triggered: true };
}

export async function handler() {
  const result = await runRecovery();
  return {
    statusCode: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify(result),
  };
}
