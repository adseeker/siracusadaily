# Monitoring e logging

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Log di esecuzione

Il motore scrive nel log:

- endpoint riusciti e tentati;
- articoli acquisiti e articoli riconosciuti come locali;
- eventi e opportunità in quarantena;
- warning per singolo endpoint;
- immagini tentate, pubblicate e saltate;
- warning immagini;
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

HTML e log vengono conservati come artifact per 7 giorni. In caso di fallimento viene aperta una issue GitHub con data e collegamento al run; per la stessa data non viene aperta una seconda issue identica.

Il timeout massimo del job è 55 minuti.

## Persistenza anche in caso di errore

Il checkpoint SQLite e il salvataggio del branch operativo vengono eseguiti con `if: always()` nei run completi. Gli articoli già acquisiti non vengono quindi persi se una fase successiva fallisce.

## Limiti attuali del monitoring

- Non esiste un sistema esterno di alerting oltre alle issue GitHub.
- I warning dei singoli endpoint non producono alert separati.
- La copertura immagini è disponibile nei log ma non ancora come KPI storico in dashboard.
- Le motivazioni di quarantena sono nel database, non visualizzate nella dashboard.

[← Precedente: Publishing e operations](06-publishing-operations.md) · [Successivo: Analytics →](08-analytics.md)
