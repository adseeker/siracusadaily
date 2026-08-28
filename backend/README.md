# Motore SiracusaDaily

Pipeline per retrieval, classificazione, deduplicazione, selezione, scrittura e consegna tramite Brevo.

## Automazione GitHub e recovery Netlify

Il workflow `.github/workflows/newsletter-daily.yml` riceve due trigger GitHub
giornalieri alle 06:30 e alle 07:00, ora `Europe/Rome`. Alle 07:30 la Scheduled
Function Netlify `newsletter-recovery.mjs` richiama lo stesso workflow con
`workflow_dispatch` e modalità `recovery`.

Netlify non prova a dedurre lo stato dello scheduler GitHub: invia sempre il trigger
delle 07:30. Il comando `run --skip-existing-brevo-date` usa Brevo come fonte
autoritativa; se la campagna del giorno esiste già, termina prima del retrieval e
non usa OpenAI. Se manca, il recovery esegue la pipeline completa e programma
l'invio come un run schedulato. La concorrenza GitHub serializza i run tardivi e il
secondo controllo Brevo chiude anche la finestra immediatamente precedente alla
creazione della campagna.

Il workflow:

- esegue tutti i test prima del run;
- verifica direttamente su Brevo che l'edizione non esista già;
- conserva il database nel branch separato `automation-state`;
- ritenta le chiamate OpenAI in caso di errori temporanei;
- salva HTML, log e materiali Facebook per 7 giorni;
- apre una issue GitHub se fallisce;
- programma automaticamente su Brevo la campagna prodotta dai run schedulati;
- programma automaticamente anche la campagna prodotta dal recovery Netlify;
- mantiene i run manuali in modalità bozza.

## Recap Facebook

Ogni run completo prodotto dal writer OpenAI genera anche due file deterministici,
senza una seconda chiamata AI:

- `facebook_post.txt`: post nativo con un massimo di 4 contenuti, uno per
  `Notizie e cronaca`, `Politica ed economia`, `Cultura` e `Sport`, con sintesi
  breve e fonte adiacente, senza URL nel corpo;
- `facebook_sources.txt`: primo commento con fonti numerate, URL e invito
  all'iscrizione alla newsletter.

I file sono inclusi nell'artifact `newsletter-<run id>` di GitHub Actions. La
pubblicazione resta manuale nella fase di validazione: prima viene inviata la
newsletter, poi si copia `facebook_post.txt` in un post Facebook e infine
`facebook_sources.txt` nel primo commento. Nessuna API Facebook è configurata e
un errore nella produzione di questi file genera un warning senza bloccare la
campagna email.

Per l'uso quotidiano non è necessario aprire gli artifact. Dopo il run, GitHub
aggiorna la pagina Notion fissa `Facebook — copia e incolla`, che mostra i due
testi in blocchi separati. Per abilitarla, condividere la pagina con una
connessione interna Notion dotata di lettura e aggiornamento dei contenuti, quindi
salvare il relativo token come secret GitHub `NOTION_TOKEN`.

Lo stesso run produce, soltanto quando esistono avvisi operativi validi, i file
`facebook_service_updates_post.txt` e `facebook_service_updates_sources.txt`.
In Notion vengono archiviati nella toggle `Aggiornamenti utili dd/mm/aaaa`.
Il flusso è limitato a cinque comunicazioni concrete su acqua, energia,
viabilità, trasporti, rifiuti, meteo/protezione civile e chiusure pubbliche.
Non viene creata alcuna toggle vuota.

Il link di iscrizione può essere personalizzato con
`SIRACUSA_FACEBOOK_SIGNUP_URL`; il valore predefinito include i parametri UTM per
il recap organico.

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
essere impostata a `true` per abilitare l'invio dei run pianificati e del recovery.
Dal pannello Actions si può lanciare `preflight`, che controlla l'infrastruttura
senza chiamare OpenAI né creare una bozza, oppure `full` per un run completo in
bozza. La modalità `recovery` è riservata alla Function Netlify e abilita la
programmazione automatica.

Netlify richiede `SIRACUSA_GITHUB_ACTIONS_TOKEN`, un personal access token
fine-grained limitato a `adseeker/siracusadaily`, con `Actions: read and write` e
`Metadata: read-only`. Sul piano Netlify attuale il valore è una variabile di sito
ordinaria disponibile a tutti gli scope, perché Secret Controller con scope
specifico richiede un upgrade. Non viene comunque usato dal frontend né incorporato
nel bundle; soltanto `newsletter-recovery.mjs` lo legge tramite `process.env`.

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
- salva `facebook_post.txt` e `facebook_sources.txt` in `backend/runtime/output/`;
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
