# Infrastructure

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Stack

| Area | Tecnologia | Ruolo |
|---|---|---|
| Repository | GitHub privato `adseeker/siracusadaily` | Codice, workflow e issue |
| Automazione | GitHub Actions, Ubuntu | Scheduler e motore quotidiano |
| Backend | Python 3.12 in produzione | Retrieval, processing e generazione |
| Persistenza | SQLite WAL | Articoli, run e storico editoriale |
| Writer | OpenAI Responses API, `gpt-5-mini` | Headline, summary, categoria e oggetto |
| Email | Brevo API v3 | Lista, campagne, statistiche e form |
| Frontend | Next.js 16, React 19, TypeScript | Landing, privacy e dashboard |
| Hosting | Netlify | Export statico e Functions |
| Immagini | Pillow e Netlify Blobs | Thumbnail e CDN |
| PDF | pypdf | Avvisi del Centro per l'impiego |
| Dominio | `siracusadaily.com` | Sito, mittente e identità email |

## Deploy web

Next.js usa `output: export`. Netlify esegue:

```text
build command: npm run build
publish directory: out
Node.js: 22
```

Ogni push su `main` attiva il deploy del sito e delle Netlify Functions.

## Branch e stato

- `main`: codice e configurazione;
- `automation-state`: database `siracusa_daily.db` aggiornato dal workflow.

Il database viene sottoposto a checkpoint WAL, committato dal bot e usato dal run successivo. Questa scelta evita un server database e mantiene basso il costo operativo, ma presuppone un solo writer concorrente.

## Netlify Functions

### `dashboard.mjs`

- accetta soltanto GET;
- richiede `DASHBOARD_ACCESS_TOKEN`;
- confronta il token in tempo costante;
- interroga Brevo, OpenAI e GitHub con timeout di 15 secondi;
- restituisce dati con `private, no-store`;
- consente degradazione parziale dei provider.

### `newsletter-image.mjs`

- accetta GET, HEAD e PUT;
- PUT richiede `SIRACUSA_IMAGE_UPLOAD_TOKEN`;
- ammette soltanto JPEG e verifica la firma binaria;
- limita l'upload a 300 KB;
- valida la chiave con regex e categorie consentite;
- salva nel Blob store `newsletter-images`;
- espone lettura pubblica con ETag e cache annuale.

## Segreti GitHub

| Variabile | Utilizzo |
|---|---|
| `OPENAI_API_KEY` | Generazione editoriale |
| `BREVO_API_KEY` | Preflight, creazione e programmazione campagna |
| `SIRACUSA_IMAGE_UPLOAD_TOKEN` | Upload protetto delle thumbnail |

La variabile repository `SIRACUSA_AUTO_SEND_ENABLED` non contiene credenziali e agisce da kill switch dell'invio automatico. Deve valere esattamente `true` per i run schedulati.

## Variabili Netlify

| Variabile | Utilizzo |
|---|---|
| `DASHBOARD_ACCESS_TOKEN` | Accesso alla control room |
| `BREVO_API_KEY` | Metriche campagne e lista |
| `BREVO_LIST_ID` | Lista SiracusaDaily, attualmente 7 |
| `OPENAI_ADMIN_KEY` | Uso e costi dell'organizzazione |
| `OPENAI_PROJECT_ID` | Filtro del progetto OpenAI |
| `GITHUB_DASHBOARD_TOKEN` | Lettura read-only dei workflow |
| `GITHUB_REPOSITORY` | Repository monitorata |
| `SIRACUSA_IMAGE_UPLOAD_TOKEN` | Autorizzazione upload immagini |

I valori segreti non vengono incorporati nel bundle statico o inviati al browser.

## Sicurezza e deliverability

- Repository privata.
- Segreti cifrati in GitHub e Netlify.
- Token dashboard e immagini confrontati con `timingSafeEqual`.
- Nessuna chiave provider nel frontend.
- Upload immagini limitato per tipo, firma, dimensione e naming.
- Header web `X-Content-Type-Options`, `Referrer-Policy` e `X-Frame-Options`.
- Dominio mittente autenticato in Brevo con SPF, DKIM e DMARC.
- Il blocco Brevo degli IP sconosciuti deve essere disattivato per le API key perché gli IP dei runner GitHub cambiano; il blocco SMTP può restare attivo.
- Link di disiscrizione inserito nell'HTML Brevo.

## Dipendenze e costi operativi

Le dipendenze Python runtime sono limitate a Pillow e pypdf. Il frontend usa Next.js, React e `@netlify/blobs`.

Le superfici di costo sono:

- chiamate OpenAI, variabili in base al numero di candidati e ai retry;
- piano Brevo e volume email;
- piano Netlify e traffico delle immagini;
- eventuali minuti GitHub Actions oltre la quota inclusa.

L'acquisizione delle fonti non usa API commerciali aggiuntive.

## Backup e retention

- Database operativo: storico Git del branch `automation-state`;
- HTML e log: artifact GitHub per 7 giorni;
- campagne e statistiche: conservazione Brevo;
- immagini: Netlify Blobs, senza pulizia automatica attualmente configurata;
- codice e configurazione: branch `main` del repository privato.

## Limiti architetturali noti

- SQLite e branch di stato sono adatti a un singolo processo, non a più worker editoriali concorrenti.
- Il retrieval HTML dipende dalla struttura pubblica dei siti e può richiedere manutenzione quando cambia il markup.
- Le fonti social Meta e LinkedIn non sono automatizzate.
- Le immagini possono mancare quando una fonte blocca il download o non espone metadati idonei.
- I run schedulati inviano automaticamente; la revisione umana preventiva è disponibile disattivando il kill switch o usando un run manuale.
- Non esiste ancora un pannello editoriale per modificare la selezione prima della creazione della bozza.

## Riferimenti nel repository

- `README.md`: panoramica di sito e dashboard;
- `backend/README.md`: operazioni del motore;
- `backend/docs/source-map-methodology.md`: struttura e manutenzione delle fonti;
- `backend/data/source_map.csv`: dataset fonti;
- `backend/data/endpoint_map.csv`: dataset endpoint;
- `.github/workflows/newsletter-daily.yml`: automazione di produzione;
- `netlify.toml`: build e Functions;
- `backend/tests/`: suite di verifica.

[← Precedente: Analytics](08-analytics.md) · [Torna all'indice](../../SIRACUSADAILY_TECHNICAL.md)
