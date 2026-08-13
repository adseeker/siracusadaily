"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import styles from "./Eventi.module.css";

const ENDPOINT = "/.netlify/functions/events";
const SIGNUP_URL = "https://siracusadaily.com/?utm_source=eventi&utm_medium=web&utm_campaign=eventi_page";

type EventItem = {
  id: string;
  title: string;
  start: string;
  end: string | null;
  all_day: boolean;
  location: string;
  address: string;
  description: string;
  image: string;
  booking_url: string;
  category: string;
  past: boolean;
};

type ListResponse = {
  events: EventItem[];
  page: number;
  total_pages: number;
  total: number;
  scope: "upcoming" | "past";
};

const dateFmt = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit" });

function formatWhen(item: EventItem): string {
  const start = new Date(item.start);
  let label = dateFmt.format(start);
  if (!item.all_day) label += ` · ${timeFmt.format(start)}`;
  if (item.end) {
    const end = new Date(item.end);
    if (end.toDateString() !== start.toDateString()) label += ` → ${dateFmt.format(end)}`;
  }
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function readEventParam(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("event");
}

export function Eventi() {
  const [eventId, setEventId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const [scope, setScope] = useState<"upcoming" | "past">("upcoming");
  const [page, setPage] = useState(1);
  const [list, setList] = useState<ListResponse | null>(null);
  const [detail, setDetail] = useState<EventItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const sync = () => setEventId(readEventParam());
    const timer = window.setTimeout(() => { sync(); setReady(true); }, 0);
    window.addEventListener("popstate", sync);
    return () => { window.clearTimeout(timer); window.removeEventListener("popstate", sync); };
  }, []);

  const fetchList = useCallback(async (nextScope: "upcoming" | "past", nextPage: number) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${ENDPOINT}?scope=${nextScope}&page=${nextPage}`);
      if (!res.ok) throw new Error(`Errore ${res.status}`);
      setList(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossibile caricare gli eventi");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: string) => {
    setLoading(true);
    setError("");
    setDetail(null);
    try {
      const res = await fetch(`${ENDPOINT}?event=${encodeURIComponent(id)}`);
      if (res.status === 404) throw new Error("Questo evento non è più disponibile.");
      if (!res.ok) throw new Error(`Errore ${res.status}`);
      const data = await res.json();
      setDetail(data.event);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossibile caricare l'evento");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    const timer = window.setTimeout(() => {
      if (eventId) void fetchDetail(eventId);
      else void fetchList(scope, page);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [ready, eventId, scope, page, fetchDetail, fetchList]);

  function openEvent(id: string) {
    window.history.pushState({}, "", `/eventi?event=${encodeURIComponent(id)}`);
    setEventId(id);
  }

  function backToList() {
    window.history.pushState({}, "", "/eventi");
    setEventId(null);
  }

  function changeScope(next: "upcoming" | "past") {
    setScope(next);
    setPage(1);
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/" className={styles.wordmark}>SiracusaDaily</Link>
        <Link href="/#iscriviti" className={styles.headerCta}>Iscriviti</Link>
      </header>

      {eventId ? (
        <Detail detail={detail} loading={loading} error={error} onBack={backToList} />
      ) : (
        <section className={styles.listWrap}>
          <h1 className={styles.pageTitle}>Eventi a Siracusa e provincia</h1>
          <p className={styles.pageSub}>Tutti gli appuntamenti raccolti da SiracusaDaily, in un solo posto.</p>

          <div className={styles.tabs}>
            <button className={`${styles.tab} ${scope === "upcoming" ? styles.tabOn : ""}`} onClick={() => changeScope("upcoming")}>Prossimi</button>
            <button className={`${styles.tab} ${scope === "past" ? styles.tabOn : ""}`} onClick={() => changeScope("past")}>Passati</button>
          </div>

          {loading && <p className={styles.info}>Caricamento…</p>}
          {error && <p className={styles.infoError}>{error}</p>}
          {!loading && !error && list && list.events.length === 0 && (
            <p className={styles.info}>{scope === "upcoming" ? "Nessun evento in programma al momento." : "Nessun evento passato."}</p>
          )}

          {list && list.events.length > 0 && (
            <>
              <div className={styles.grid}>
                {list.events.map((item) => (
                  <button key={item.id} className={styles.card} onClick={() => openEvent(item.id)}>
                    <div className={styles.cardImageWrap}>
                      {item.image
                        // eslint-disable-next-line @next/next/no-img-element
                        ? <img src={item.image} alt="" className={styles.cardImage} loading="lazy" />
                        : <div className={styles.cardImagePlaceholder}>SiracusaDaily</div>}
                      {item.past && <span className={styles.pastBadge}>Evento passato</span>}
                    </div>
                    <div className={styles.cardBody}>
                      {item.category && <span className={styles.cardCategory}>{item.category}</span>}
                      <h2 className={styles.cardTitle}>{item.title}</h2>
                      <p className={styles.cardMeta}>{formatWhen(item)}</p>
                      {item.location && <p className={styles.cardLocation}>{item.location}</p>}
                    </div>
                  </button>
                ))}
              </div>

              {list.total_pages > 1 && (
                <div className={styles.pager}>
                  <button className={styles.pagerBtn} disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>← Precedenti</button>
                  <span className={styles.pagerInfo}>Pagina {list.page} di {list.total_pages}</span>
                  <button className={styles.pagerBtn} disabled={page >= list.total_pages} onClick={() => setPage((p) => p + 1)}>Successivi →</button>
                </div>
              )}
            </>
          )}
        </section>
      )}
    </main>
  );
}

function Detail({ detail, loading, error, onBack }: { detail: EventItem | null; loading: boolean; error: string; onBack: () => void }) {
  return (
    <section className={styles.detailWrap}>
      <button className={styles.back} onClick={onBack}>← Tutti gli eventi</button>
      {loading && <p className={styles.info}>Caricamento…</p>}
      {error && <p className={styles.infoError}>{error}</p>}
      {detail && (
        <article className={styles.detail}>
          {detail.image && (
            <div className={styles.detailImageWrap}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={detail.image} alt="" className={styles.detailImage} />
              {detail.past && <span className={styles.pastBadge}>Evento passato</span>}
            </div>
          )}
          {detail.category && <span className={styles.detailCategory}>{detail.category}</span>}
          <h1 className={styles.detailTitle}>{detail.title}</h1>
          <p className={styles.detailWhen}>{formatWhen(detail)}</p>
          {(detail.location || detail.address) && (
            <p className={styles.detailWhere}>{[detail.location, detail.address].filter(Boolean).join(" · ")}</p>
          )}
          {detail.description && <p className={styles.detailDesc}>{detail.description}</p>}
          {detail.booking_url && (
            <a className={styles.book} href={detail.booking_url} target="_blank" rel="noopener noreferrer">Prenota / Vai al sito →</a>
          )}
          <div className={styles.subscribe}>
            <strong>Non perderti i prossimi eventi.</strong>
            <a href={SIGNUP_URL} className={styles.subscribeCta}>Iscriviti gratis a SiracusaDaily →</a>
          </div>
        </article>
      )}
    </section>
  );
}
