# Motore

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Obiettivo operativo

Il motore risponde ogni giorno alla domanda editoriale: quali informazioni deve conoscere oggi una persona che vive a Siracusa o in uno dei comuni della provincia?

Il processo è progettato per:

- privilegiare la rilevanza locale;
- evitare duplicazioni della stessa notizia;
- mantenere una copertura equilibrata delle categorie;
- non far dominare stabilmente una singola testata;
- trattare eventi e opportunità con logiche temporali diverse dalle notizie;
- programmare l'invio soltanto dopo il superamento di tutti i gate;
- interrompere la pubblicazione quando viene meno un controllo essenziale.

## Componenti principali

Il backend è un package Python chiamato `siracusa-daily`, compatibile con Python 3.11 o superiore. GitHub Actions usa Python 3.12.

| Componente | Responsabilità |
|---|---|
| `config.py` | Caricamento delle fonti e degli endpoint attivi dai CSV |
| `retrieval.py` | Adapter RSS e HTML, parsing di eventi, bandi e offerte di lavoro |
| `geography.py` | Valutazione della pertinenza geografica |
| `event_quality.py` | Quarantena degli eventi sospetti provenienti dagli aggregatori generalisti |
| `opportunity_quality.py` | Verifica della sede effettiva delle opportunità |
| `database.py` | Persistenza SQLite, storico dei run, selezioni ed esclusioni |
| `selection.py` | Deduplicazione, ranking, scelta della fonte rappresentativa e fairness |
| `categories.py` | Classificazione preliminare e ordine delle sezioni |
| `events.py` | Finestra mobile, durata e ordinamento degli eventi |
| `opportunities.py` | Stato, scadenza, ordinamento e rotazione delle opportunità |
| `editorial.py` | Pacchetto evidenze, chiamata OpenAI, validazioni, riparazioni e oggetto |
| `images.py` | Estrazione, ottimizzazione e pubblicazione delle thumbnail |
| `writer.py` | Rendering deterministico Markdown o HTML |
| `brevo.py` | Controllo campagne, risoluzione lista, creazione e programmazione Brevo |
| `pipeline.py` | Orchestrazione di ingestione e costruzione dell'edizione |
| `cli.py` | Interfaccia operativa e controlli di pubblicazione |

## Comandi disponibili

La CLI espone i seguenti comandi:

- `init`: inizializza il database;
- `preflight`: verifica database, chiave OpenAI, lista Brevo e presenza di una campagna per la data;
- `ingest`: esegue soltanto acquisizione e persistenza;
- `build`: costruisce una newsletter dai dati già presenti;
- `run`: esegue acquisizione, processing, generazione e opzionalmente pubblicazione;
- `brevo-draft`: riprova la sola creazione Brevo partendo da un run OpenAI già completato.

Il workflow di produzione usa:

```text
writer: gpt-5-mini
lookback notizie: 168 ore
item limit per endpoint: 30
limite notizie ordinarie: 10
limite eventi: 8
limite opportunità: 6
minimo contenuti pubblicabili: 6
output: HTML
destinazione: campagna Brevo programmata nei run automatici, bozza nei run manuali
```

[Successivo: Fonti e acquisizione →](02-fonti-acquisizione.md)
