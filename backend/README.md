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

La sezione `I prossimi eventi` usa una logica distinta dalle notizie: legge gli
eventi strutturati già conservati nel database, seleziona quelli compresi tra il
giorno dell'edizione e i sei giorni successivi, mantiene gli appuntamenti ancora
in corso e li ordina cronologicamente. Gli eventi possono ricomparire nelle
edizioni successive finché restano nella finestra; il limite operativo
predefinito è 8 e si modifica con `--event-limit`.

La sezione `Lavoro e opportunità` è anch'essa indipendente dalle notizie. Concorsi,
bandi e offerte strutturate possono ricomparire ogni giorno finché risultano
aperti. Una scadenza esplicita vale fino alla fine del giorno indicato; uno stato
chiuso o scaduto rimuove subito la voce. Se manca la scadenza, la presenza viene
ricontrollata alla fonte e tollera fino a tre giorni senza conferma, così un errore
temporaneo del sito non fa sparire l'opportunità. L'ordine privilegia le scadenze
entro sette giorni e poi le pubblicazioni più recenti. Il limite predefinito è 6
e si modifica con `--opportunity-limit`.

L'oggetto non può essere guidato da decessi, incidenti gravi, violenza, vittime,
cronaca nera o altre formulazioni emotivamente forti. Queste notizie possono
restare nel corpo dell'edizione; un controllo deterministico obbliga l'oggetto a
usare un contenuto diverso e neutro, oppure blocca la creazione della bozza.

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
