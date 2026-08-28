# Monitoring e logging

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 28 agosto 2026<br>
Stato: sistema operativo in produzione


## Log di esecuzione

Il motore scrive nel log:

- endpoint riusciti e tentati;
- articoli acquisiti e articoli riconosciuti come locali;
- eventi e opportunità in quarantena;
- warning per singolo endpoint;
- immagini tentate, pubblicate e saltate;
- warning immagini;
- numero di contenuti e percorsi dei file Facebook;
- warning non bloccanti del renderer Facebook;
- esito dell'aggiornamento della pagina operativa Notion;
- numero e percorsi degli aggiornamenti utili, oppure motivazione esplicita
  dell'assenza del blocco operativo;
- ID del run editoriale;
- numero di contenuti finali;
- writer e percorso output;
- ID campagna e lista Brevo;
- stato bozza o programmato e orario previsto di invio.

## GitHub Actions

Ogni run espone stato e durata dei passaggi:

- setup e test;
- preflight;
- motore editoriale;
- consolidamento database;
- persistenza;
- archiviazione.

HTML, log, post Facebook e relativo blocco fonti vengono conservati come artifact
per 7 giorni. In caso di fallimento viene aperta una issue GitHub con data e
collegamento al run; per la stessa data non viene aperta una seconda issue identica.

Il timeout massimo del job è 55 minuti.

## Recovery Netlify

La Scheduled Function `newsletter-recovery` espone nei log Netlify:

- l'invocazione UTC e l'eventuale esclusione della finestra non corrispondente;
- l'invio del `workflow_dispatch` in modalità `recovery`;
- errori per token assente, risposta GitHub diversa da `204` o problemi di rete.

Il workflow generato dal recovery compare in GitHub Actions con evento
`workflow_dispatch`. La modalità `recovery`, a differenza della modalità manuale
`full`, abilita il percorso `--brevo-auto-schedule`. La presenza della campagna
Brevo del giorno permette di distinguere un recupero realmente produttivo da un
run terminato correttamente per idempotenza.

## Persistenza anche in caso di errore

Il checkpoint SQLite e il salvataggio del branch operativo vengono eseguiti con `if: always()` nei run completi. Gli articoli già acquisiti non vengono quindi persi se una fase successiva fallisce.

## Limiti attuali del monitoring

- Le issue GitHub segnalano i run falliti ma non l'assenza totale di un trigger;
  Netlify copre questo caso alle 07:30, senza ancora inviare un alert separato.
- Gli errori della Scheduled Function sono visibili nei log Netlify ma non generano
  attualmente una notifica esterna dedicata.
- I warning dei singoli endpoint non producono alert separati.
- La copertura immagini è disponibile nei log ma non ancora come KPI storico in dashboard.
- Le motivazioni di quarantena sono nel database, non visualizzate nella dashboard.
- Gli errori Notion restano warning di workflow e non generano issue dedicate.

[← Precedente: Publishing e operations](06-publishing-operations.md) · [Successivo: Analytics →](08-analytics.md)
