"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import styles from "./Dashboard.module.css";

type Campaign = {
  id: number;
  subject: string;
  status: string;
  date: string;
  sent: number;
  delivered: number;
  uniqueViews: number;
  clickers: number;
  openRate: number;
  ctr: number;
  ctor: number;
  bounces: number;
  unsubscriptions: number;
};

type DashboardData = {
  generatedAt: string;
  periodDays: number;
  availability: { brevo: boolean; openai: boolean; github: boolean };
  notices: string[];
  overview: {
    drafts?: number;
    sentCampaigns?: number;
    sent?: number;
    delivered?: number;
    openRate?: number;
    ctr?: number;
    ctor?: number;
    deliveryRate?: number;
    bounces?: number;
    unsubscriptions?: number;
    subscribers?: number;
  };
  campaigns: Campaign[];
  openai: null | {
    requests: number;
    inputTokens: number;
    cachedInputTokens: number;
    outputTokens: number;
    costUsd: number;
    scope: string;
    daily: Array<{ date: string; requests: number; inputTokens: number; outputTokens: number; costUsd: number }>;
  };
  automation: null | {
    totalRuns: number;
    completedRuns: number;
    successfulRuns: number;
    successRate: number;
    averageDurationSeconds: number;
    stepAverages: Array<{ name: string; seconds: number; samples: number }>;
    runs: Array<{
      id: number;
      date: string;
      status: string;
      conclusion: string | null;
      event: string;
      durationSeconds: number;
      url: string;
    }>;
  };
};

const numberFormat = new Intl.NumberFormat("it-IT");
const decimalFormat = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const currencyFormat = new Intl.NumberFormat("it-IT", { style: "currency", currency: "USD", minimumFractionDigits: 3 });

function formatNumber(value?: number) {
  return value === undefined ? "N/D" : numberFormat.format(value);
}

function formatPercent(value?: number) {
  return value === undefined ? "N/D" : `${decimalFormat.format(value)}%`;
}

function formatDuration(seconds?: number) {
  if (!seconds) return "N/D";
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} min ${rest} sec`;
}

function formatDate(value: string, withTime = false) {
  if (!value) return "N/D";
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit", month: "short", year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(new Date(value));
}

function Sparkline({ campaigns }: { campaigns: Campaign[] }) {
  const sent = [...campaigns].filter((item) => item.status === "sent").reverse().slice(-16);
  if (!sent.length) {
    return <div className={styles.emptyChart}>Il grafico comparirà dopo il primo invio.</div>;
  }
  const width = 720;
  const height = 230;
  const padding = 28;
  const x = (index: number) => padding + (index * (width - padding * 2)) / Math.max(1, sent.length - 1);
  const y = (value: number) => height - padding - (Math.min(100, value) * (height - padding * 2)) / 100;
  const points = (field: "openRate" | "ctr") => sent.map((item, index) => `${x(index)},${y(item[field])}`).join(" ");
  return (
    <div className={styles.sparklineWrap}>
      <svg className={styles.sparkline} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Andamento di open rate e click through rate">
        {[0, 25, 50, 75, 100].map((tick) => (
          <g key={tick}>
            <line x1={padding} x2={width - padding} y1={y(tick)} y2={y(tick)} className={styles.chartGrid} />
            <text x="2" y={y(tick) + 4} className={styles.chartLabel}>{tick}%</text>
          </g>
        ))}
        <polyline points={points("openRate")} className={styles.openLine} />
        <polyline points={points("ctr")} className={styles.clickLine} />
        {sent.map((item, index) => <circle key={`o-${item.id}`} cx={x(index)} cy={y(item.openRate)} r="4" className={styles.openPoint} />)}
        {sent.map((item, index) => <circle key={`c-${item.id}`} cx={x(index)} cy={y(item.ctr)} r="4" className={styles.clickPoint} />)}
      </svg>
      <div className={styles.legend}><span><i className={styles.openKey} /> Open rate</span><span><i className={styles.clickKey} /> CTR</span></div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label: Record<string, string> = { draft: "Bozza", sent: "Inviata", queued: "In coda", scheduled: "Programmata" };
  return <span className={`${styles.status} ${styles[`status_${status}`] || ""}`}>{label[status] || status}</span>;
}

export function Dashboard() {
  const [token, setToken] = useState("");
  const [draftToken, setDraftToken] = useState("");
  const [days, setDays] = useState(30);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (accessToken: string, selectedDays: number) => {
    if (!accessToken) return;
    setLoading(true);
    setError("");
    try {
      const result = await fetch(`/.netlify/functions/dashboard?days=${selectedDays}`, {
        headers: { authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      });
      const payload = await result.json();
      if (!result.ok) throw new Error(payload.error || "Dashboard non disponibile");
      setData(payload);
      setToken(accessToken);
      sessionStorage.setItem("siracusadaily-dashboard-token", accessToken);
    } catch (caught) {
      setData(null);
      setError(caught instanceof Error ? caught.message : "Dashboard non disponibile");
      if ((caught instanceof Error ? caught.message : "").includes("accesso")) {
        sessionStorage.removeItem("siracusadaily-dashboard-token");
        setToken("");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const saved = sessionStorage.getItem("siracusadaily-dashboard-token") || "";
    if (!saved) return;
    const timer = window.setTimeout(() => void load(saved, days), 0);
    return () => window.clearTimeout(timer);
  }, [days, load]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void load(draftToken, days);
  };

  const sentCampaigns = useMemo(() => data?.campaigns.filter((item) => item.status === "sent") || [], [data]);
  const funnel = data ? [
    { label: "Email inviate", value: data.overview.sent || 0, color: "#111111" },
    { label: "Consegnate", value: data.overview.delivered || 0, color: "#1d4ed8" },
    { label: "Aperte", value: sentCampaigns.reduce((sum, item) => sum + item.uniqueViews, 0), color: "#7e22ce" },
    { label: "Cliccate", value: sentCampaigns.reduce((sum, item) => sum + item.clickers, 0), color: "#15803d" },
  ] : [];
  const funnelMax = Math.max(1, ...funnel.map((item) => item.value));
  const maxStep = Math.max(1, ...(data?.automation?.stepAverages || []).map((item) => item.seconds));

  if (!token || (!data && !loading)) {
    return (
      <main className={styles.loginPage}>
        <div className={styles.colorRail} aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div>
        <section className={styles.loginCard}>
          <Link href="/" className={styles.wordmark}>SiracusaDaily</Link>
          <p className={styles.kicker}>Control room</p>
          <h1>Una sola fonte per capire come sta andando.</h1>
          <p className={styles.loginCopy}>Dati editoriali, tecnici e di business della newsletter.</p>
          <form onSubmit={submit} className={styles.loginForm}>
            <label htmlFor="dashboard-token">Codice di accesso</label>
            <input id="dashboard-token" type="password" value={draftToken} onChange={(event) => setDraftToken(event.target.value)} autoComplete="current-password" required />
            <button type="submit" disabled={loading}>{loading ? "Caricamento..." : "Apri la dashboard"}</button>
          </form>
          {error && <p className={styles.loginError}>{error}</p>}
        </section>
      </main>
    );
  }

  if (!data) return <main className={styles.loadingPage}>Aggiornamento dati in corso...</main>;

  return (
    <main className={styles.page}>
      <div className={styles.colorRail} aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div>
      <header className={styles.header}>
        <div>
          <Link href="/" className={styles.wordmark}>SiracusaDaily</Link>
          <span className={styles.controlRoom}>Control room</span>
        </div>
        <div className={styles.headerControls}>
          <span className={styles.live}><i /> Dati aggiornati</span>
          <label>
            Periodo
            <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
              <option value={7}>7 giorni</option>
              <option value={30}>30 giorni</option>
              <option value={90}>90 giorni</option>
            </select>
          </label>
          <button type="button" onClick={() => void load(token, days)} disabled={loading}>{loading ? "..." : "Aggiorna"}</button>
        </div>
      </header>

      <section className={styles.intro}>
        <p className={styles.kicker}>Panoramica degli ultimi {data.periodDays} giorni</p>
        <h1>Newsletter health, in un colpo d’occhio.</h1>
        <p>La fonte operativa per prendere decisioni editoriali, tecniche e di crescita.</p>
      </section>

      {data.notices.length > 0 && (
        <section className={styles.notices} aria-label="Dati non disponibili">
          {data.notices.map((notice) => <p key={notice}>{notice}</p>)}
        </section>
      )}

      <section className={styles.kpiGrid} aria-label="Indicatori principali">
        <article><span>Bozze presenti</span><strong>{formatNumber(data.overview.drafts)}</strong><small>Campagne Brevo nel periodo</small></article>
        <article><span>Campagne inviate</span><strong>{formatNumber(data.overview.sentCampaigns)}</strong><small>{formatNumber(data.overview.delivered)} email consegnate</small></article>
        <article><span>Iscritti attivi</span><strong>{formatNumber(data.overview.subscribers)}</strong><small>{formatNumber(data.overview.unsubscriptions)} disiscrizioni nel periodo</small></article>
        <article className={styles.accentBlue}><span>Open rate</span><strong>{formatPercent(data.overview.openRate)}</strong><small>Aperture uniche su consegnate</small></article>
        <article className={styles.accentGreen}><span>Click through rate</span><strong>{formatPercent(data.overview.ctr)}</strong><small>Clicker unici su consegnate</small></article>
        <article className={styles.accentGold}><span>Costi OpenAI</span><strong>{data.openai ? currencyFormat.format(data.openai.costUsd) : "N/D"}</strong><small>{data.openai?.scope || "Chiave amministrativa richiesta"}</small></article>
      </section>

      <section className={styles.twoColumns}>
        <article className={styles.panel}>
          <div className={styles.panelHeading}><div><p>Business</p><h2>Performance delle campagne</h2></div><span>{sentCampaigns.length} invii</span></div>
          <Sparkline campaigns={data.campaigns} />
        </article>
        <article className={styles.panel}>
          <div className={styles.panelHeading}><div><p>Conversione</p><h2>Dal recapito al clic</h2></div><span>CTOR {formatPercent(data.overview.ctor)}</span></div>
          <div className={styles.funnel}>
            {funnel.map((item) => (
              <div key={item.label} className={styles.funnelRow}>
                <div><span>{item.label}</span><strong>{formatNumber(item.value)}</strong></div>
                <div className={styles.barTrack}><i style={{ width: `${(item.value / funnelMax) * 100}%`, background: item.color }} /></div>
              </div>
            ))}
            {!data.overview.sent && <p className={styles.emptySmall}>I dati appariranno dopo il primo invio effettivo.</p>}
          </div>
        </article>
      </section>

      <section className={styles.technicalGrid}>
        <article className={styles.panel}>
          <div className={styles.panelHeading}><div><p>Tecnica</p><h2>Automazione</h2></div><span className={data.automation?.successRate === 100 ? styles.good : ""}>{formatPercent(data.automation?.successRate)}</span></div>
          <div className={styles.techStats}>
            <div><span>Run completati</span><strong>{formatNumber(data.automation?.completedRuns)}</strong></div>
            <div><span>Durata media</span><strong>{formatDuration(data.automation?.averageDurationSeconds)}</strong></div>
            <div><span>Run riusciti</span><strong>{formatNumber(data.automation?.successfulRuns)}</strong></div>
          </div>
          <div className={styles.stepList}>
            {(data.automation?.stepAverages || []).map((step) => (
              <div key={step.name} className={styles.stepRow}>
                <div><span>{step.name}</span><strong>{formatDuration(step.seconds)}</strong></div>
                <div className={styles.barTrack}><i style={{ width: `${(step.seconds / maxStep) * 100}%` }} /></div>
              </div>
            ))}
            {!data.automation && <p className={styles.emptySmall}>Collega GitHub per visualizzare affidabilità e tempi.</p>}
          </div>
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHeading}><div><p>API</p><h2>GPT‑5 mini</h2></div><span>{data.openai ? data.openai.scope : "Non collegata"}</span></div>
          <div className={styles.tokenGrid}>
            <div><span>Richieste</span><strong>{formatNumber(data.openai?.requests)}</strong></div>
            <div><span>Token input</span><strong>{formatNumber(data.openai?.inputTokens)}</strong></div>
            <div><span>Input in cache</span><strong>{formatNumber(data.openai?.cachedInputTokens)}</strong></div>
            <div><span>Token output</span><strong>{formatNumber(data.openai?.outputTokens)}</strong></div>
          </div>
          <div className={styles.costBlock}>
            <span>Costo API nel periodo</span>
            <strong>{data.openai ? currencyFormat.format(data.openai.costUsd) : "N/D"}</strong>
          </div>
          {!data.openai && <p className={styles.emptySmall}>Serve una chiave amministrativa OpenAI per leggere utilizzo e costi reali.</p>}
        </article>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeading}><div><p>Editoriale</p><h2>Ultime campagne</h2></div><span>{data.campaigns.length} risultati</span></div>
        <div className={styles.tableWrap}>
          <table>
            <thead><tr><th>Data</th><th>Oggetto</th><th>Stato</th><th>Consegnate</th><th>Open rate</th><th>CTR</th></tr></thead>
            <tbody>
              {data.campaigns.map((campaign) => (
                <tr key={campaign.id}>
                  <td>{formatDate(campaign.date)}</td>
                  <td><strong>{campaign.subject}</strong><small>Campagna #{campaign.id}</small></td>
                  <td><StatusBadge status={campaign.status} /></td>
                  <td>{formatNumber(campaign.delivered)}</td>
                  <td>{formatPercent(campaign.openRate)}</td>
                  <td>{formatPercent(campaign.ctr)}</td>
                </tr>
              ))}
              {!data.campaigns.length && <tr><td colSpan={6} className={styles.emptyTable}>Nessuna campagna nel periodo selezionato.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {data.automation?.runs.length ? (
        <section className={styles.runStrip}>
          <div><p>Tecnica</p><h2>Ultime esecuzioni</h2></div>
          <div className={styles.runList}>
            {data.automation.runs.slice(0, 6).map((run) => (
              <a key={run.id} href={run.url} target="_blank" rel="noreferrer">
                <i className={run.conclusion === "success" ? styles.runGood : styles.runBad} />
                <span>{formatDate(run.date, true)}</span>
                <strong>{formatDuration(run.durationSeconds)}</strong>
              </a>
            ))}
          </div>
        </section>
      ) : null}

      <footer className={styles.footer}>
        <span>Ultimo aggiornamento: {formatDate(data.generatedAt, true)}</span>
        <span>Le percentuali Brevo utilizzano aperture e clicker unici.</span>
      </footer>
    </main>
  );
}
