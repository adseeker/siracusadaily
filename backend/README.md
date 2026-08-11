# Motore SiracusaDaily

Pipeline per retrieval, classificazione, deduplicazione, selezione, scrittura e consegna tramite Brevo.

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
- programma automaticamente su Brevo la campagna prodotta dai run schedulati;
- mantiene i run manuali in modalità bozza.

La campagna ordinaria viene programmata alle 08:30, ora di Roma. Se la produzione
termina dopo le 08:15, l'invio viene spostato a 15 minuti dal completamento e
arrotondato al minuto successivo. La variabile GitHub
`SIRACUSA_AUTO_SEND_ENABLED` funziona da kill switch: con valore diverso da
`true`, la campagna viene creata ma resta in bozza.

La sezione `I prossimi eventi` usa una logica distinta dalle notizie: legge gli
eventi strutturati già conservati nel database, seleziona quelli compresi tra il
giorno dell'edizione e i sei giorni successivi, mantiene gli appuntamenti ancora
in corso e li ordina cronologicamente. Gli eventi possono ricomparire nelle
edizioni successive finché restano nella finestra; il limite operativo
predefinito è 8 e si modifica con `--event-limit`.

Gli aggregatori generalisti AllEvents e Virgilio alimentano un filtro editoriale
aggiuntivo. La presenza geografica a Siracusa non basta: gli eventi con pubblico
italiano non dimostrabile, scritture straniere prevalenti, descrizioni troppo
scarse o duplicazioni multilingua sospette vengono conservati nel database in
quarantena con la relativa motivazione. Sono esclusi prima della selezione e non
vengono mai inviati al writer. Eventbrite, il Comune e i calendari locali non sono
soggetti a questa limitazione specifica.

La sezione `Lavoro e opportunità` è anch'essa indipendente dalle notizie. Concorsi,
bandi e offerte strutturate possono ricomparire ogni giorno finché risultano
aperti. Una scadenza esplicita vale fino alla fine del giorno indicato; uno stato
chiuso o scaduto rimuove subito la voce. Se manca la scadenza, la presenza viene
ricontrollata alla fonte e tollera fino a tre giorni senza conferma, così un errore
temporaneo del sito non fa sparire l'opportunità. L'ordine privilegia le scadenze
entro sette giorni e poi le pubblicazioni più recenti. La selezione ruota tra le
fonti prima di ripeterne una, così un portale più ricco non monopolizza la sezione.
La sede effettiva deve appartenere alla provincia: i falsi positivi restano in
quarantena e non raggiungono il writer. Il limite predefinito è 6 e si modifica
con `--opportunity-limit`.

L'oggetto non può essere guidato da decessi, incidenti gravi, violenza, vittime,
cronaca nera o altre formulazioni emotivamente forti. Queste notizie possono
restare nel corpo dell'edizione; un controllo deterministico obbliga l'oggetto a
usare un contenuto diverso e neutro, oppure blocca la creazione della bozza.

I secret richiesti nel repository sono `OPENAI_API_KEY`, `BREVO_API_KEY` e
`SIRACUSA_IMAGE_UPLOAD_TOKEN`. Quest'ultimo deve contenere lo stesso valore della
variabile Netlify omonima: autorizza soltanto il caricamento delle thumbnail e non
viene mai inserito nell'HTML o inviato al browser.
La variabile GitHub Actions `SIRACUSA_AUTO_SEND_ENABLED` non è un secret e deve
essere impostata a `true` per abilitare l'invio dei soli run pianificati.
Dal pannello Actions si può lanciare `preflight`, che controlla l'infrastruttura
senza chiamare OpenAI né creare una bozza, oppure `full` per un run completo.

## Immagini nelle email

La pipeline cerca una sola immagine per il primo contenuto di `Notizie e cronaca`,
`Cultura`, `Sport` e `I prossimi eventi`. Usa i metadati pubblici dell'articolo,
scarica la risorsa, la verifica, la ritaglia in formato 480×300 e la converte in
JPEG ottimizzato entro 180 KB. Il file viene caricato nel Blob store Netlify del
sito e l'email usa l'indirizzo pubblico stabile della funzione immagini.

Se l'articolo non espone una foto valida, il server sorgente non risponde o
l'upload fallisce, quella singola immagine viene semplicemente omessa. Il run e la
campagna Brevo proseguono normalmente. Le altre categorie rimangono testuali.

Netlify deve avere la variabile protetta `SIRACUSA_IMAGE_UPLOAD_TOKEN`; GitHub
Actions deve avere un secret con lo stesso nome e lo stesso valore. La funzione
accetta soltanto JPEG ottimizzati, chiavi nel formato previsto e richieste PUT
autenticate. La lettura pubblica delle immagini è servita con cache CDN annuale.

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
