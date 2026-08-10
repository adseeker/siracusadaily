# Motore SiracusaDaily

Pipeline per retrieval, classificazione, deduplicazione, selezione, scrittura e creazione della bozza Brevo.

## Automazione GitHub

Il workflow `.github/workflows/newsletter-daily.yml` parte ogni giorno alle 06:30,
ora `Europe/Rome`. I passaggi delle 07:00 e 07:30 sono recuperi automatici: se la
campagna del giorno esiste già su Brevo, terminano prima del retrieval e non usano
OpenAI.

Il workflow:

- esegue tutti i test prima del run;
- verifica direttamente su Brevo che l'edizione non esista già;
- conserva il database nel branch privato `automation-state`;
- ritenta le chiamate OpenAI in caso di errori temporanei;
- salva HTML e log per 7 giorni;
- apre una issue GitHub se fallisce;
- crea soltanto una bozza Brevo, senza inviarla.

I secret richiesti nel repository sono `OPENAI_API_KEY` e `BREVO_API_KEY`.
Dal pannello Actions si può lanciare `preflight`, che controlla l'infrastruttura
senza chiamare OpenAI né creare una bozza, oppure `full` per un run completo.

Brevo deve accettare chiamate API dai runner GitHub, i cui indirizzi IP cambiano.
In `Settings > Security > Authorized IPs` il blocco degli IP sconosciuti va quindi
disattivato per le sole **API keys**. Il blocco SMTP può restare attivo: questo
workflow non usa SMTP.

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

## Pianificazione macOS, solo emergenza

Il LaunchAgent incluso è una procedura di riserva e non va lasciato attivo insieme
a GitHub Actions. La copia operativa
va installata in `~/Library/Application Support/SiracusaDaily`, così il processo in
background non dipende dai permessi macOS della cartella `Documents`. Va attivato
solo dopo aver completato `.env.local` ed eseguito con successo almeno un run manuale.
