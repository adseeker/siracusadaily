# Motore SiracusaDaily

Pipeline locale per retrieval, classificazione, deduplicazione, selezione, scrittura e creazione della bozza Brevo.

## Prima configurazione

```bash
cd backend
scripts/setup_local.sh
```

Aprire `.env.local` e inserire `OPENAI_API_KEY` e `BREVO_API_KEY`. Il file è escluso da Git.

## Esecuzione manuale completa

```bash
backend/scripts/run_daily.sh
```

Il run:

- conserva il database in `backend/runtime/data/`;
- salva l’HTML in `backend/runtime/output/`;
- registra i log in `backend/runtime/logs/`;
- crea una bozza nella lista `Iscritti SiracusaDaily`;
- non invia automaticamente la campagna;
- non crea una seconda campagna Brevo per la stessa data;
- blocca la bozza se vengono selezionate meno di 6 notizie.

## Pianificazione macOS

Il LaunchAgent incluso è configurato per le 06:30, ora locale. Va installato solo dopo aver completato `.env.local` ed eseguito con successo almeno un run manuale.
