# Analytics

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Dashboard

La pagina `/dashboard` è una control room one-page. Il browser invia un bearer token a una Netlify Function; il token è conservato soltanto in `sessionStorage`. Le credenziali Brevo, OpenAI e GitHub rimangono sul server.

Sono disponibili finestre di 7, 30 e 90 giorni. Le tre sorgenti vengono interrogate in parallelo e con isolamento degli errori: se un provider fallisce, gli altri dati restano disponibili insieme a un avviso.

## Metriche Brevo

- bozze presenti;
- campagne inviate;
- email inviate e consegnate;
- delivery rate;
- aperture uniche e open rate;
- clicker unici, CTR e CTOR;
- bounce hard e soft;
- disiscrizioni;
- segnalazioni spam;
- iscritti attivi e contatti in blacklist;
- dettaglio delle campagne SiracusaDaily.

Le formule principali sono:

```text
open rate = aperture uniche / consegnate
CTR = clicker unici / consegnate
CTOR = clicker unici / aperture uniche
delivery rate = consegnate / inviate
```

Le aperture sono influenzate dai sistemi di privacy e prefetch dei client email e vanno interpretate insieme ai clic, non come misura assoluta di lettura.

## Metriche OpenAI

Con una Admin Key vengono letti:

- richieste al modello;
- token di input;
- token di input in cache;
- token di output;
- costo in USD;
- andamento giornaliero.

`OPENAI_PROJECT_ID` limita l'analisi al progetto SiracusaDaily. Se non è configurato, i valori possono rappresentare l'intera organizzazione OpenAI.

## Metriche GitHub Actions

- run totali, completati e riusciti;
- success rate;
- durata media totale;
- durata media dei singoli componenti;
- elenco degli ultimi run con evento, stato, durata e link.

Le medie per step usano gli ultimi 12 run completati; l'elenco visualizzato è limitato agli ultimi 15.

## Dati non ancora aggregati

La dashboard non legge attualmente SQLite. Non espone quindi come serie storiche:

- distribuzione dei contenuti per categoria;
- rotazione effettiva delle fonti;
- cluster deduplicati;
- esclusioni del writer;
- motivazioni di quarantena;
- copertura e fallimenti delle immagini.

Questi dati esistono nel database o nei log e possono essere aggiunti in futuro senza modificare la pipeline editoriale.

[← Precedente: Monitoring e logging](07-monitoring-logging.md) · [Successivo: Infrastructure →](09-infrastructure.md)
