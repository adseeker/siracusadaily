# Quality Assurance

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 12 agosto 2026<br>
Stato: sistema operativo in produzione


## Test automatici

Il repository contiene attualmente 112 test automatici eseguiti prima di ogni run:

- 84 test di pipeline;
- 10 test dedicati alle immagini;
- 5 test dedicati al recap Facebook;
- 5 test dedicati alla pubblicazione operativa su Notion;
- 8 test dedicati agli aggiornamenti utili.

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
- creazione della campagna Brevo, programmazione e idempotenza;
- estrazione, compressione e upload delle thumbnail;
- selezione, attribuzione, separazione dei link e salvataggio del recap Facebook;
- aggiornamento sicuro della pagina Notion e suddivisione dei testi lunghi.
- esclusione degli avvisi amministrativi, validità degli alert, ripetizione dei
  soli casi critici e isolamento della toggle operativa.

Se un test fallisce, GitHub Actions non avvia il motore editoriale.

## Gate di pubblicazione

Prima di creare o programmare una campagna devono essere veri tutti i seguenti punti:

- database accessibile;
- `OPENAI_API_KEY` configurata;
- lista Brevo risolta in modo univoco;
- nessuna campagna Brevo già esistente per la data;
- writer effettivamente OpenAI;
- output HTML valido e inferiore a 1 MB;
- almeno 6 contenuti pubblicabili;
- oggetto valido e grounded;
- secondo controllo Brevo immediatamente prima della creazione.

I run schedulati programmano l'invio soltanto dopo questi controlli. I run manuali continuano a creare una bozza. Il kill switch consente di riportare immediatamente anche l'automazione quotidiana alla sola modalità bozza.

## Comportamento in caso di errore

| Errore | Comportamento |
|---|---|
| Singolo endpoint non raggiungibile | Warning, le altre fonti proseguono |
| Evento o opportunità sospetta | Quarantena, non raggiunge il writer |
| Candidato AI non valido | Correzione mirata; poi esclusione del solo candidato |
| OpenAI non disponibile dopo i retry | Run fallito, nessuna campagna |
| Immagine assente, bloccata o non valida | Thumbnail omessa, campagna invariata |
| Output Facebook non disponibile | Warning, campagna email invariata |
| Nessun aggiornamento operativo valido | Nessuna toggle vuota; email invariata |
| Brevo non raggiungibile nel preflight | Run interrotto prima della produzione |
| Campagna già esistente | Run ignorato senza costi OpenAI |
| Meno di 6 contenuti | Campagna bloccata |
| Fallimento GitHub Actions | Issue GitHub automatica |

## Verifica client email

Il template è costruito con tabelle, stili inline e una media query mobile, ed è controllato tramite le anteprime di Brevo. Non esiste attualmente una suite automatizzata esterna di rendering su Gmail, Apple Mail e Outlook; questa verifica è deliberatamente affidata all'anteprima Brevo e alla revisione umana.

[← Precedente: Generazione](04-generazione.md) · [Successivo: Publishing e operations →](06-publishing-operations.md)
