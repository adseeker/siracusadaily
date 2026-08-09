# SiracusaDaily

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
selezione, scrittura OpenAI e creazione della bozza Brevo. Database operativo,
newsletter generate, log e chiavi API restano locali e non vengono pubblicati su GitHub.

Consultare `backend/README.md` per configurazione ed esecuzione.
