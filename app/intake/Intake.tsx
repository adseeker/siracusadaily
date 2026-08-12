"use client";

import { ChangeEvent, ClipboardEvent, DragEvent, FormEvent, useEffect, useRef, useState } from "react";
import styles from "./Intake.module.css";

const TOKEN_KEY = "siracusadaily-intake-token";
const ENDPOINT = "/.netlify/functions/social-intake";
const MAX_DIMENSION = 1600;

type Extracted = {
  pubblicabile: boolean;
  motivo_esclusione: string;
  titolo: string;
  tipo: string;
  categoria: string;
  data_inizio: string;
  data_fine: string;
  ora: string;
  luogo: string;
  indirizzo: string;
  organizzatore: string;
  prezzo: string;
  link: string;
  provenienza_campi: string;
  confidenza: string;
  da_rivedere: boolean;
};

type Phase = "edit" | "extracting" | "review" | "saving";
type Notice =
  | { kind: "done"; text: string; url: string }
  | { kind: "skipped"; text: string }
  | { kind: "error"; text: string };

// Ridimensiona e ricomprime l'immagine lato client per restare nei limiti della function.
function downscale(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Lettura file fallita"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Immagine non leggibile"));
      img.onload = () => {
        const scale = Math.min(1, MAX_DIMENSION / Math.max(img.width, img.height));
        const width = Math.round(img.width * scale);
        const height = Math.round(img.height * scale);
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) return reject(new Error("Canvas non disponibile"));
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  });
}

export function Intake() {
  const [token, setToken] = useState("");
  const [draftToken, setDraftToken] = useState("");
  const [gateReady, setGateReady] = useState(false);

  const [image, setImage] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [account, setAccount] = useState("");
  const [dragging, setDragging] = useState(false);

  const [phase, setPhase] = useState<Phase>("edit");
  const [extracted, setExtracted] = useState<Extracted | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(TOKEN_KEY) || "";
    const timer = window.setTimeout(() => {
      if (saved) setToken(saved);
      setGateReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function saveToken(event: FormEvent) {
    event.preventDefault();
    const clean = draftToken.trim();
    if (!clean) return;
    sessionStorage.setItem(TOKEN_KEY, clean);
    setToken(clean);
  }

  function resetAll() {
    setImage(null);
    setText("");
    setLink("");
    setAccount("");
    setExtracted(null);
    setNotice(null);
    setPhase("edit");
    if (fileInput.current) fileInput.current.value = "";
  }

  // Ogni modifica agli input invalida un'estrazione già mostrata.
  function invalidate() {
    if (extracted) setExtracted(null);
    if (phase === "review") setPhase("edit");
    if (notice?.kind === "skipped") setNotice(null);
  }

  async function acceptFile(file: File | undefined | null) {
    if (!file || !file.type.startsWith("image/")) return;
    try {
      const dataUrl = await downscale(file);
      setImage(dataUrl);
      setNotice(null);
      void runExtract(dataUrl); // estrazione automatica appena caricato
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Immagine non valida" });
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void acceptFile(event.dataTransfer.files?.[0]);
  }

  function onPaste(event: ClipboardEvent) {
    const item = Array.from(event.clipboardData.items).find((entry) => entry.type.startsWith("image/"));
    if (item) void acceptFile(item.getAsFile());
  }

  async function runExtract(imageOverride?: string | null) {
    const img = imageOverride ?? image;
    if (!img && !text.trim()) {
      setNotice({ kind: "error", text: "Serve almeno uno screenshot o del testo" });
      return;
    }
    setPhase("extracting");
    setNotice(null);
    try {
      const response = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
        body: JSON.stringify({ action: "extract", image: img, text: text.trim(), link: link.trim(), account: account.trim() }),
      });
      if (response.status === 401) return handleUnauthorized();
      const data = await response.json();
      if (!response.ok) {
        setNotice({ kind: "error", text: data.error || `Errore ${response.status}` });
        setPhase("edit");
        return;
      }
      if (data.reason) {
        setNotice({ kind: "skipped", text: data.reason });
        setPhase("edit");
        return;
      }
      setExtracted(data.extracted);
      setPhase("review");
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Rete non disponibile" });
      setPhase("edit");
    }
  }

  async function runSave() {
    if (!extracted) return;
    setPhase("saving");
    setNotice(null);
    try {
      const response = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
        body: JSON.stringify({ action: "save", extracted, text: text.trim(), link: link.trim(), account: account.trim() }),
      });
      if (response.status === 401) return handleUnauthorized();
      const data = await response.json();
      if (!response.ok || !data.created) {
        setNotice({ kind: "error", text: data.error || `Errore ${response.status}` });
        setPhase("review");
        return;
      }
      const title = data.extracted?.titolo || "Contenuto";
      resetAll();
      setNotice({ kind: "done", text: title, url: data.url });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Rete non disponibile" });
      setPhase("review");
    }
  }

  function handleUnauthorized() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setNotice({ kind: "error", text: "Codice di accesso non valido" });
    setPhase("edit");
  }

  if (!gateReady) return <main className={styles.shell} />;

  if (!token) {
    return (
      <main className={styles.shell}>
        <form className={styles.gate} onSubmit={saveToken}>
          <h1 className={styles.gateTitle}>Intake social</h1>
          <p className={styles.gateHint}>Inserisci il codice di accesso per raccogliere contenuti.</p>
          <label htmlFor="intake-token">Codice di accesso</label>
          <input
            id="intake-token"
            type="password"
            value={draftToken}
            onChange={(event) => setDraftToken(event.target.value)}
            autoComplete="current-password"
            required
          />
          <button type="submit">Entra</button>
        </form>
      </main>
    );
  }

  const busy = phase === "extracting" || phase === "saving";

  return (
    <main className={styles.shell} onPaste={onPaste}>
      <div className={styles.card}>
        <header className={styles.head}>
          <h1 className={styles.title}>Nuovo contenuto</h1>
          <p className={styles.sub}>Trascina uno screenshot: l&apos;estrazione parte da sola. Puoi aggiungere la caption.</p>
        </header>

        <div
          className={`${styles.drop} ${dragging ? styles.dropActive : ""} ${image ? styles.dropFilled : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileInput.current?.click()}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInput.current?.click(); } }}
          role="button"
          tabIndex={0}
        >
          {image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={image} alt="Anteprima screenshot" className={styles.preview} />
          ) : (
            <div className={styles.dropInner}>
              <span className={styles.dropIcon}>＋</span>
              <span>Trascina o tocca per lo screenshot</span>
              <span className={styles.dropSmall}>oppure incolla dagli appunti</span>
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            className={styles.hiddenInput}
            onChange={(event: ChangeEvent<HTMLInputElement>) => void acceptFile(event.target.files?.[0])}
          />
        </div>
        {image && (
          <button
            type="button"
            className={styles.linkBtn}
            onClick={() => { setImage(null); invalidate(); if (fileInput.current) fileInput.current.value = ""; }}
          >
            Rimuovi immagine
          </button>
        )}

        <label className={styles.field}>
          <span>Caption</span>
          <textarea
            value={text}
            onChange={(event) => { setText(event.target.value); invalidate(); }}
            placeholder="Incolla qui il testo del post…"
            rows={4}
          />
        </label>

        <div className={styles.row}>
          <label className={styles.field}>
            <span>Link (opzionale)</span>
            <input type="url" value={link} onChange={(event) => { setLink(event.target.value); invalidate(); }} placeholder="https://instagram.com/p/…" />
          </label>
          <label className={styles.field}>
            <span>Account (opzionale)</span>
            <input type="text" value={account} onChange={(event) => { setAccount(event.target.value); invalidate(); }} placeholder="@profilo" />
          </label>
        </div>

        {phase === "extracting" && <p className={styles.working}>L&apos;agente sta leggendo il contenuto…</p>}

        {(phase === "review" || phase === "saving") && extracted && (
          <section className={styles.reviewBox}>
            <div className={styles.reviewHead}>
              <strong>{extracted.titolo || "Senza titolo"}</strong>
              {extracted.da_rivedere && <span className={styles.flag}>da rivedere</span>}
            </div>
            <Preview extracted={extracted} />
            {extracted.provenienza_campi && <p className={styles.prov}>{extracted.provenienza_campi}</p>}
          </section>
        )}

        {phase === "edit" || phase === "extracting" ? (
          <button type="button" className={styles.submit} onClick={() => void runExtract()} disabled={busy}>
            {phase === "extracting" ? "Estraggo…" : "Estrai contenuti"}
          </button>
        ) : (
          <div className={styles.actions}>
            <button type="button" className={styles.submit} onClick={() => void runSave()} disabled={busy}>
              {phase === "saving" ? "Salvo…" : "Salva su Notion"}
            </button>
            <button type="button" className={styles.linkBtn} onClick={() => void runExtract()} disabled={busy}>Ri-estrai</button>
            <button type="button" className={styles.linkBtn} onClick={resetAll} disabled={busy}>Ricomincia</button>
          </div>
        )}
      </div>

      {notice && (
        <section className={`${styles.result} ${styles[`result_${notice.kind}`]}`}>
          {notice.kind === "done" && (
            <>
              <strong>Salvato ✓</strong>
              <p>{notice.text}</p>
              <a href={notice.url} target="_blank" rel="noopener noreferrer" className={styles.linkBtn}>Apri la riga in Notion →</a>
            </>
          )}
          {notice.kind === "skipped" && (
            <>
              <strong>Non salvato</strong>
              <p>{notice.text}</p>
              <button type="button" className={styles.linkBtn} onClick={() => setNotice(null)}>Chiudi</button>
            </>
          )}
          {notice.kind === "error" && (
            <>
              <strong>Errore</strong>
              <p>{notice.text}</p>
              <button type="button" className={styles.linkBtn} onClick={() => setNotice(null)}>Chiudi</button>
            </>
          )}
        </section>
      )}
    </main>
  );
}

function Preview({ extracted }: { extracted: Extracted }) {
  const rows: Array<[string, string]> = [
    ["Tipo", extracted.tipo],
    ["Categoria", extracted.categoria],
    ["Data", [extracted.data_inizio, extracted.data_fine].filter(Boolean).join(" → ")],
    ["Ora", extracted.ora],
    ["Luogo", [extracted.luogo, extracted.indirizzo].filter(Boolean).join(", ")],
    ["Organizzatore", extracted.organizzatore],
    ["Prezzo", extracted.prezzo],
    ["Confidenza", extracted.confidenza],
  ];
  return (
    <dl className={styles.previewList}>
      {rows.filter(([, value]) => value && value.trim()).map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
