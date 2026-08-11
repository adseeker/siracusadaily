# Quality Assurance

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Test automatici

Il repository contiene attualmente 89 test automatici eseguiti prima di ogni run:

- 79 test di pipeline;
- 10 test dedicati alle immagini.

La suite copre, tra le altre cose:

- parser RSS, HTML, JSON, microdata e PDF;
- canonicalizzazione URL;
- filtro geografico;
- deduplicazione cross-source;
- limiti e rotazione delle fonti;
- finestra mobile degli eventi;
- quarantena di eventi stranieri o multilingua sospetti;
- persistenza e scadenza delle opportunità;
- verifica della sede delle offerte di lavoro;
- classificazione delle categorie;
- grounding numerico;
- limiti, lingua, punteggiatura ed em dash;
- correzioni selettive del writer;
- protezione dell'oggetto sensibile;
- rendering HTML, ordine sezioni, date e scadenze;
- creazione della sola bozza Brevo e idempotenza;
- estrazione, compressione e upload delle thumbnail.

Se un test fallisce, GitHub Actions non avvia il motore editoriale.

## Gate di pubblicazione

Prima di creare una bozza devono essere veri tutti i seguenti punti:

- database accessibile;
- `OPENAI_API_KEY` configurata;
- lista Brevo risolta in modo univoco;
- nessuna campagna Brevo già esistente per la data;
- writer effettivamente OpenAI;
- output HTML valido e inferiore a 1 MB;
- almeno 6 contenuti pubblicabili;
- oggetto valido e grounded;
- secondo controllo Brevo immediatamente prima della creazione.

La pipeline crea soltanto una bozza. La revisione editoriale su Brevo rimane il controllo umano finale prima dell'invio.

## Comportamento in caso di errore

| Errore | Comportamento |
|---|---|
| Singolo endpoint non raggiungibile | Warning, le altre fonti proseguono |
| Evento o opportunità sospetta | Quarantena, non raggiunge il writer |
| Candidato AI non valido | Correzione mirata; poi esclusione del solo candidato |
| OpenAI non disponibile dopo i retry | Run fallito, nessuna bozza |
| Immagine assente, bloccata o non valida | Thumbnail omessa, bozza invariata |
| Brevo non raggiungibile nel preflight | Run interrotto prima della produzione |
| Campagna già esistente | Run ignorato senza costi OpenAI |
| Meno di 6 contenuti | Bozza bloccata |
| Fallimento GitHub Actions | Issue GitHub automatica |

## Verifica client email

Il template è costruito con tabelle, stili inline e una media query mobile, ed è controllato tramite le anteprime di Brevo. Non esiste attualmente una suite automatizzata esterna di rendering su Gmail, Apple Mail e Outlook; questa verifica è deliberatamente affidata all'anteprima Brevo e alla revisione umana.

[← Precedente: Generazione](04-generazione.md) · [Successivo: Publishing e operations →](06-publishing-operations.md)
