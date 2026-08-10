import crypto from "node:crypto";

const BREVO_API = "https://api.brevo.com/v3";
const OPENAI_API = "https://api.openai.com/v1";
const DEFAULT_REPOSITORY = "adseeker/siracusadaily";
const CAMPAIGN_PREFIX = "SiracusaDaily |";

const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "private, no-store, max-age=0",
  "x-content-type-options": "nosniff",
};

function response(statusCode, body) {
  return { statusCode, headers: jsonHeaders, body: JSON.stringify(body) };
}

function authorized(event) {
  const configured = process.env.DASHBOARD_ACCESS_TOKEN || "";
  const supplied = (event.headers.authorization || event.headers.Authorization || "")
    .replace(/^Bearer\s+/i, "");
  if (!configured || !supplied) return false;
  const expected = Buffer.from(configured);
  const actual = Buffer.from(supplied);
  return expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
}

async function fetchJson(url, options = {}) {
  const result = await fetch(url, {
    ...options,
    headers: { accept: "application/json", ...(options.headers || {}) },
    signal: AbortSignal.timeout(15000),
  });
  if (!result.ok) {
    const detail = (await result.text()).slice(0, 300);
    throw new Error(`${result.status} ${detail || result.statusText}`);
  }
  return result.json();
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function percentage(numerator, denominator) {
  return denominator > 0 ? (numerator / denominator) * 100 : 0;
}

function campaignDate(campaign) {
  return campaign.scheduledAt || campaign.sentDate || campaign.createdAt || campaign.modifiedAt || "";
}

async function brevoMetrics(days) {
  const apiKey = process.env.BREVO_API_KEY;
  if (!apiKey) throw new Error("BREVO_API_KEY non configurata");
  const headers = { "api-key": apiKey };
  const campaigns = [];
  for (let offset = 0; offset < 500; offset += 50) {
    const url = new URL(`${BREVO_API}/emailCampaigns`);
    url.searchParams.set("type", "classic");
    url.searchParams.set("statistics", "globalStats");
    url.searchParams.set("limit", "50");
    url.searchParams.set("offset", String(offset));
    url.searchParams.set("sort", "desc");
    const page = await fetchJson(url, { headers });
    const rows = Array.isArray(page.campaigns) ? page.campaigns : [];
    campaigns.push(...rows);
    if (rows.length < 50) break;
  }

  const cutoff = Date.now() - days * 86400000;
  const projectCampaigns = campaigns
    .filter((item) => String(item.name || "").startsWith(CAMPAIGN_PREFIX))
    .filter((item) => {
      const timestamp = Date.parse(campaignDate(item));
      return Number.isFinite(timestamp) && timestamp >= cutoff;
    });
  const sentCampaigns = projectCampaigns.filter((item) => item.status === "sent");
  const drafts = projectCampaigns.filter((item) => item.status === "draft");

  const aggregate = sentCampaigns.reduce((totals, campaign) => {
    const stats = campaign.statistics?.globalStats || {};
    for (const field of Object.keys(totals)) totals[field] += number(stats[field]);
    return totals;
  }, {
    sent: 0, delivered: 0, uniqueViews: 0, viewed: 0, clickers: 0,
    uniqueClicks: 0, hardBounces: 0, softBounces: 0, unsubscriptions: 0, complaints: 0,
  });

  let listId = Number(process.env.BREVO_LIST_ID || 0);
  if (!listId) {
    const lists = await fetchJson(`${BREVO_API}/contacts/lists?limit=50&offset=0&sort=desc`, { headers });
    const match = (lists.lists || []).find((item) => item.name === "Iscritti SiracusaDaily");
    listId = number(match?.id);
  }
  let audience = { subscribers: 0, blacklisted: 0, listId: listId || null };
  if (listId) {
    const list = await fetchJson(`${BREVO_API}/contacts/lists/${listId}`, { headers });
    audience = {
      subscribers: number(list.totalSubscribers),
      blacklisted: number(list.totalBlacklisted),
      listId,
    };
  }

  const campaignRows = projectCampaigns.slice(0, 40).map((campaign) => {
    const stats = campaign.statistics?.globalStats || {};
    const delivered = number(stats.delivered);
    const uniqueViews = number(stats.uniqueViews);
    const clickers = number(stats.clickers);
    return {
      id: campaign.id,
      name: campaign.name,
      subject: campaign.subject || "",
      status: campaign.status,
      date: campaignDate(campaign),
      sent: number(stats.sent),
      delivered,
      uniqueViews,
      clickers,
      openRate: percentage(uniqueViews, delivered),
      ctr: percentage(clickers, delivered),
      ctor: percentage(clickers, uniqueViews),
      bounces: number(stats.hardBounces) + number(stats.softBounces),
      unsubscriptions: number(stats.unsubscriptions),
    };
  });

  return {
    overview: {
      drafts: drafts.length,
      sentCampaigns: sentCampaigns.length,
      sent: aggregate.sent,
      delivered: aggregate.delivered,
      openRate: percentage(aggregate.uniqueViews, aggregate.delivered),
      ctr: percentage(aggregate.clickers, aggregate.delivered),
      ctor: percentage(aggregate.clickers, aggregate.uniqueViews),
      deliveryRate: percentage(aggregate.delivered, aggregate.sent),
      bounces: aggregate.hardBounces + aggregate.softBounces,
      unsubscriptions: aggregate.unsubscriptions,
      complaints: aggregate.complaints,
      subscribers: audience.subscribers,
      blacklisted: audience.blacklisted,
    },
    campaigns: campaignRows,
  };
}

async function paginatedOpenAI(path, params, apiKey) {
  const buckets = [];
  let page = "";
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const url = new URL(`${OPENAI_API}${path}`);
    for (const [key, value] of Object.entries(params)) {
      if (Array.isArray(value)) value.forEach((item) => url.searchParams.append(key, item));
      else if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
    if (page) url.searchParams.set("page", page);
    const result = await fetchJson(url, { headers: { authorization: `Bearer ${apiKey}` } });
    buckets.push(...(Array.isArray(result.data) ? result.data : []));
    if (!result.has_more || !result.next_page) break;
    page = result.next_page;
  }
  return buckets;
}

async function openAIMetrics(days) {
  const apiKey = process.env.OPENAI_ADMIN_KEY;
  if (!apiKey) throw new Error("OPENAI_ADMIN_KEY non configurata");
  const now = Math.floor(Date.now() / 1000);
  const start = now - days * 86400;
  const projectId = process.env.OPENAI_PROJECT_ID || "";
  const projectFilter = projectId ? [projectId] : undefined;
  const [usageBuckets, costBuckets] = await Promise.all([
    paginatedOpenAI("/organization/usage/completions", {
      start_time: start,
      end_time: now,
      bucket_width: "1d",
      limit: Math.min(days, 31),
      group_by: ["model"],
      models: ["gpt-5-mini"],
      project_ids: projectFilter,
    }, apiKey),
    paginatedOpenAI("/organization/costs", {
      start_time: start,
      end_time: now,
      bucket_width: "1d",
      limit: Math.min(days, 180),
      group_by: ["line_item"],
      project_ids: projectFilter,
    }, apiKey),
  ]);

  const totals = { requests: 0, inputTokens: 0, cachedInputTokens: 0, outputTokens: 0, costUsd: 0 };
  const dailyMap = new Map();
  for (const bucket of usageBuckets) {
    const date = new Date(number(bucket.start_time) * 1000).toISOString().slice(0, 10);
    const daily = dailyMap.get(date) || { date, requests: 0, inputTokens: 0, outputTokens: 0, costUsd: 0 };
    for (const item of bucket.results || []) {
      totals.requests += number(item.num_model_requests);
      totals.inputTokens += number(item.input_tokens);
      totals.cachedInputTokens += number(item.input_cached_tokens);
      totals.outputTokens += number(item.output_tokens);
      daily.requests += number(item.num_model_requests);
      daily.inputTokens += number(item.input_tokens);
      daily.outputTokens += number(item.output_tokens);
    }
    dailyMap.set(date, daily);
  }
  for (const bucket of costBuckets) {
    const date = new Date(number(bucket.start_time) * 1000).toISOString().slice(0, 10);
    const daily = dailyMap.get(date) || { date, requests: 0, inputTokens: 0, outputTokens: 0, costUsd: 0 };
    for (const item of bucket.results || []) {
      const amount = number(item.amount?.value);
      totals.costUsd += amount;
      daily.costUsd += amount;
    }
    dailyMap.set(date, daily);
  }
  return {
    ...totals,
    scope: projectId ? "Progetto SiracusaDaily" : "Intera organizzazione OpenAI",
    daily: [...dailyMap.values()].sort((a, b) => a.date.localeCompare(b.date)),
  };
}

function secondsBetween(start, end) {
  const startMs = Date.parse(start || "");
  const endMs = Date.parse(end || "");
  return Number.isFinite(startMs) && Number.isFinite(endMs) ? Math.max(0, (endMs - startMs) / 1000) : 0;
}

async function githubMetrics(days) {
  const token = process.env.GITHUB_DASHBOARD_TOKEN;
  if (!token) throw new Error("GITHUB_DASHBOARD_TOKEN non configurato");
  const repository = process.env.GITHUB_REPOSITORY || DEFAULT_REPOSITORY;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-github-api-version": "2022-11-28",
    "user-agent": "SiracusaDaily-dashboard",
  };
  const data = await fetchJson(
    `https://api.github.com/repos/${repository}/actions/workflows/newsletter-daily.yml/runs?per_page=100`,
    { headers },
  );
  const cutoff = Date.now() - days * 86400000;
  const runs = (data.workflow_runs || [])
    .filter((run) => Date.parse(run.created_at || "") >= cutoff)
    .slice(0, 40);
  const completed = runs.filter((run) => run.status === "completed");
  const successful = completed.filter((run) => run.conclusion === "success");
  const recentForSteps = completed.slice(0, 12);
  const jobPages = await Promise.all(recentForSteps.map((run) =>
    fetchJson(`https://api.github.com/repos/${repository}/actions/runs/${run.id}/jobs?per_page=20`, { headers })
      .catch(() => ({ jobs: [] })),
  ));
  const stepNames = new Map([
    ["Installa e verifica il motore", "Setup e test"],
    ["Verifica chiavi, database e Brevo", "Preflight"],
    ["Esegue retrieval, selezione, scrittura e bozza Brevo", "Motore editoriale"],
    ["Consolida il database", "Database"],
    ["Salva lo storico per il giorno successivo", "Persistenza"],
    ["Conserva HTML e log del run", "Archiviazione"],
  ]);
  const durationGroups = new Map();
  for (const page of jobPages) {
    for (const job of page.jobs || []) {
      for (const step of job.steps || []) {
        const label = stepNames.get(step.name);
        if (!label || step.conclusion === "skipped") continue;
        const seconds = secondsBetween(step.started_at, step.completed_at);
        if (!seconds) continue;
        durationGroups.set(label, [...(durationGroups.get(label) || []), seconds]);
      }
    }
  }
  const stepAverages = [...durationGroups.entries()].map(([name, values]) => ({
    name,
    seconds: values.reduce((sum, value) => sum + value, 0) / values.length,
    samples: values.length,
  }));
  const totalDurations = completed
    .map((run) => secondsBetween(run.run_started_at, run.updated_at))
    .filter(Boolean);
  return {
    totalRuns: runs.length,
    completedRuns: completed.length,
    successfulRuns: successful.length,
    successRate: percentage(successful.length, completed.length),
    averageDurationSeconds: totalDurations.length
      ? totalDurations.reduce((sum, value) => sum + value, 0) / totalDurations.length
      : 0,
    stepAverages,
    runs: runs.slice(0, 15).map((run) => ({
      id: run.id,
      date: run.created_at,
      status: run.status,
      conclusion: run.conclusion,
      event: run.event,
      durationSeconds: secondsBetween(run.run_started_at, run.updated_at),
      url: run.html_url,
    })),
  };
}

export const handler = async (event) => {
  if (event.httpMethod !== "GET") return response(405, { error: "Metodo non consentito" });
  if (!process.env.DASHBOARD_ACCESS_TOKEN) {
    return response(503, { error: "Dashboard non configurata sul server" });
  }
  if (!authorized(event)) return response(401, { error: "Codice di accesso non valido" });

  const requestedDays = Number(event.queryStringParameters?.days || 30);
  const days = [7, 30, 90].includes(requestedDays) ? requestedDays : 30;
  const [brevo, openai, github] = await Promise.allSettled([
    brevoMetrics(days), openAIMetrics(days), githubMetrics(days),
  ]);
  const notices = [];
  const availability = {
    brevo: brevo.status === "fulfilled",
    openai: openai.status === "fulfilled",
    github: github.status === "fulfilled",
  };
  for (const [name, result] of [["Brevo", brevo], ["OpenAI", openai], ["GitHub", github]]) {
    if (result.status === "rejected") notices.push(`${name}: ${result.reason?.message || "dato non disponibile"}`);
  }
  const brevoData = brevo.status === "fulfilled" ? brevo.value : { overview: {}, campaigns: [] };
  return response(200, {
    generatedAt: new Date().toISOString(),
    periodDays: days,
    availability,
    notices,
    overview: brevoData.overview,
    campaigns: brevoData.campaigns,
    openai: openai.status === "fulfilled" ? openai.value : null,
    automation: github.status === "fulfilled" ? github.value : null,
  });
};
