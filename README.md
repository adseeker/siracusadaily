# SiracusaDaily

## Dashboard operativa

La pagina `/dashboard` aggrega in tempo reale i dati di Brevo, OpenAI e GitHub Actions tramite una Netlify Function protetta. Nessuna chiave viene inviata al browser.

Variabili Netlify:

- `DASHBOARD_ACCESS_TOKEN`: codice privato richiesto dalla dashboard;
- `BREVO_API_KEY`: metriche di campagne e lista iscritti;
- `BREVO_LIST_ID`: ID della lista SiracusaDaily, attualmente `7`;
- `OPENAI_ADMIN_KEY`: utilizzo e costi API OpenAI, facoltativa;
- `OPENAI_PROJECT_ID`: limita costi e utilizzo al progetto SiracusaDaily, consigliata;
- `GITHUB_DASHBOARD_TOKEN`: token read-only per leggere i run della repository privata;
- `GITHUB_REPOSITORY`: repository nel formato `owner/repo`, predefinita `adseeker/siracusadaily`.
- `SIRACUSA_IMAGE_UPLOAD_TOKEN`: token privato condiviso con GitHub Actions per
  pubblicare le thumbnail della newsletter nel Blob store Netlify.

Landing page e motore editoriale della newsletter quotidiana SiracusaDaily.

## Sviluppo locale

```bash
npm install
npm run dev
```

## Pubblicazione

Il sito è esportato staticamente e pubblicato automaticamente su Netlify a ogni aggiornamento del branch `main`.

- Build command: `npm run build`
- Publish directory: `out`
- Node.js: `22`

## Motore della newsletter

Il backend Python è in `backend/`. Esegue retrieval, classificazione, deduplicazione,
selezione, scrittura OpenAI e creazione della bozza Brevo. GitHub Actions avvia la
pipeline alle 06:30, ora di Roma; due controlli successivi alle 07:00 e alle 07:30
recuperano eventuali ritardi o errori temporanei senza creare campagne duplicate.

Le chiavi API sono cifrate nei GitHub Actions Secrets. Il database operativo è
conservato nel branch privato `automation-state`; HTML e log restano disponibili
come artifact del run per 7 giorni. La campagna viene creata come bozza e non viene
inviata automaticamente.

Consultare `backend/README.md` per configurazione ed esecuzione.
