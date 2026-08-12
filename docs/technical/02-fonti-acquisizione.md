# Fonti e acquisizione

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Source map

La configurazione editoriale è separata dal codice:

- `backend/data/source_map.csv`: una riga per fonte editoriale;
- `backend/data/endpoint_map.csv`: una riga per endpoint operativo.

Al momento risultano attive 18 fonti e 49 endpoint:

- 36 endpoint RSS;
- 12 endpoint HTML automatizzati;
- 1 endpoint manuale, Instagram `#eventisiracusa`, registrato nella source map ma escluso dall'automazione.

Ogni fonte include almeno identificativo, nome, categoria, content bucket, URL, metodo di acquisizione, ambito geografico, frequenza, affidabilità, priorità editoriale, stato e note. Gli endpoint separano le diverse sezioni o interfacce della stessa fonte.

## Fonti attive

### Comunicazioni di servizio

Il flusso operativo integra Aretusacque per il servizio idrico, il Dipartimento
regionale della Protezione civile per gli avvisi ufficiali e il registro delle
Ordinanze dirigenziali del Comune per viabilità, lavori stradali e reti. Le
testate locali e gli avvisi comunali già presenti restano fonti integrative.

Un bollettino regionale generico non diventa automaticamente un aggiornamento
locale: serve un riferimento esplicito a Siracusa nel titolo o un provvedimento
locale collegato. E-distribuzione non viene interrogata perché non offre un
elenco pubblico territoriale affidabile senza dati del cliente.

### Testate locali

- SiracusaNews;
- SiracusaOggi.it;
- La Gazzetta Siracusana;
- Siracusa2000.com;
- La Civetta di Minerva.

Le testate vengono acquisite principalmente tramite feed RSS di categoria. Il filtro geografico resta obbligatorio perché alcune pubblicano anche notizie regionali o riferite ad altri territori.

### Eventi

- Eventbrite, eventi a Siracusa;
- Comune di Siracusa;
- AllEvents, Siracusa;
- Eventi Siracusa;
- Virgilio Eventi, Siracusa;
- Instagram `#eventisiracusa`, solo come fonte manuale e non automatizzata.

AllEvents e Virgilio sono considerati aggregatori di discovery e sono sottoposti a un gate qualitativo più severo. Eventbrite, Comune ed Eventi Siracusa sono trattati come calendari più strutturati.

### Lavoro e opportunità

- Comune di Siracusa;
- ConcorsiPubblici.com;
- ASP Siracusa;
- Randstad;
- Gi Group;
- Synergie;
- Centro per l'impiego di Siracusa, Regione Siciliana;
- inPA.

Non sono usati scraper LinkedIn né API commerciali aggiuntive.

## Adapter di acquisizione

### RSS

Il parser RSS/Atom usa la standard library XML, legge titolo, link, data, estratto e autore, rimuove HTML e normalizza i permalink. Ogni endpoint restituisce al massimo il numero di elementi configurato, attualmente 30 nel workflow.

### HTML e dati incorporati

Gli adapter specializzati sfruttano soltanto dati pubblicamente accessibili:

- Eventbrite: dati strutturati incorporati, date, orari e venue;
- Comune di Siracusa: card di eventi e contenuti istituzionali;
- AllEvents: dataset eventi incorporato nella pagina;
- Eventi Siracusa: endpoint pubblico delle entità Base44;
- Virgilio: microdati `schema.org/Event`;
- ConcorsiPubblici.com: schede di concorsi attivi;
- ASP Siracusa: procedure e concorsi pubblicati;
- Randstad: dataset pubblico incorporato nel sito;
- Gi Group: card HTML con sede e identificativo dell'offerta;
- Synergie: configurazione pubblica della ricerca Algolia e filtro entro la provincia;
- Centro per l'impiego: sezione territoriale e lettura PDF tramite `pypdf`;
- inPA: ricerca pubblica ufficiale filtrata per provincia e stato aperto.

Le letture di dettaglio delle opportunità sono parallelizzate con un massimo di sei worker. Gli endpoint principali sono invece processati uno alla volta, così gli errori restano attribuibili alla fonte specifica.

## Normalizzazione iniziale

Per ogni elemento viene creato un record `Article` contenente:

- fonte ed endpoint;
- titolo e URL canonico;
- data di pubblicazione o data operativa;
- estratto e autore;
- content bucket;
- timestamp di retrieval;
- punteggio e motivazioni geografiche;
- metadati strutturati per eventi, opportunità, qualità e immagini.

La canonicalizzazione:

- converte schema e host in minuscolo;
- rimuove frammenti e slash finali superflui;
- elimina parametri UTM e identificativi di tracking comuni;
- conserva i parametri funzionali necessari alla risorsa.

Un errore su un endpoint genera un warning e non interrompe l'acquisizione delle altre fonti.

[← Precedente: Motore](01-motore.md) · [Successivo: Processing →](03-processing.md)
