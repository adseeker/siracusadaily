# Generazione

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Pacchetto di evidenze

OpenAI riceve soltanto dati strutturati per ciascun candidato:

- `candidate_id` controllato dal motore;
- titolo ed estratto della fonte;
- nome e URL della fonte;
- data di riferimento e sua semantica;
- content bucket;
- evidenze geografiche;
- altre fonti che corroborano il cluster.

URL, attribuzioni e associazione tra candidato e articolo non vengono generati dal modello.

## Writer OpenAI

Il modello predefinito è `gpt-5-mini`, chiamato tramite Responses API. Le richieste usano:

- JSON Schema in modalità strict;
- `store: false`;
- timeout di produzione di 240 secondi;
- fino a 3 tentativi per timeout, errori di rete, HTTP 408, 409, 429 e 5xx;
- backoff esponenziale limitato a 10 secondi.

Per ogni candidato il modello deve restituire:

- `candidate_id`;
- decisione `publishable`;
- eventuale motivazione di esclusione;
- headline;
- summary;
- sezione;
- formulazione di riserva per l'oggetto.

Restituisce inoltre l'oggetto dell'edizione e da uno a tre ID che ne dimostrano il grounding.

## Contratto editoriale

- Tutto il testo deve essere in italiano, anche quando la fonte è straniera.
- La headline deve essere informativa, sobria e lunga al massimo 110 caratteri.
- La summary deve essere autosufficiente, conclusiva e diversa dal titolo.
- La lunghezza ideale della summary è 170-230 caratteri; il massimo assoluto è 240.
- Non sono ammessi troncamenti, puntini di sospensione, clickbait, URL o inviti all'azione.
- L'em dash non è consentito.
- Numeri, date e quantità devono comparire nelle evidenze.
- Eventi e opportunità devono conservare luogo, data o scadenza quando disponibili.
- Se le evidenze non bastano, il candidato deve essere escluso invece di essere riempito con testo generico.

## Oggetto

L'oggetto è generato ad hoc per ogni edizione, senza prefissi o pattern ricorrenti. Deve:

- essere lungo tra 20 e 90 caratteri;
- basarsi su uno, due o tre contenuti effettivamente pubblicati;
- non contenere SiracusaDaily, la data o formule come “Siracusa oggi”;
- non contenere puntini di sospensione o em dash;
- non inventare numeri;
- evitare decessi, vittime, incidenti gravi, violenza, abusi, cronaca nera, catastrofi e formulazioni emotivamente forti.

Se l'oggetto generato non supera i controlli, il motore cerca un `subject_topic` sicuro tra i contenuti. Se nessun contenuto è utilizzabile, la bozza viene bloccata.

## Validazione e riparazione

Il motore valida in modo deterministico:

- presenza e unicità dei candidate ID;
- struttura e tipi richiesti;
- limiti di headline, summary e subject topic;
- punteggiatura conclusiva;
- categoria ammessa;
- assenza di em dash e troncamenti;
- grounding numerico;
- grounding e sicurezza dell'oggetto.

I soli candidati non validi vengono reinviati al modello con gli errori puntuali. Sono consentiti fino a tre round di correzione. Un candidato che continua a fallire viene escluso e registrato; non blocca gli altri contenuti. Un errore complessivo e persistente dell'API OpenAI interrompe invece il run.

Esiste un writer `fallback` esplicito per uso tecnico, ma una newsletter fallback non può essere pubblicata su Brevo né inviata via email. In produzione non esiste un downgrade silenzioso.

## Rendering HTML

L'HTML non viene scritto quotidianamente dal modello. Il template è deterministico e risiede in `writer.py`; il writer AI produce esclusivamente contenuti strutturati.

Caratteristiche del template:

- larghezza massima 640 px;
- layout email basato su tabelle e stili inline;
- sfondo bianco;
- logo centrale `🗞️ SiracusaDaily` e data dell'edizione;
- card di categoria con sfondo a lieve contrasto e angoli arrotondati;
- colore stabile per ciascuna categoria;
- titoli in Arial, 22 px per il primo elemento e 20 px per i successivi;
- summary a 16 px;
- link esplicito alla fonte;
- data e ora evidenti per gli eventi;
- scadenza e indicazione “In scadenza” per le opportunità urgenti;
- breakpoint mobile a 480 px;
- link di disiscrizione Brevo nel footer;
- nessun riferimento alla generazione automatica e nessuna data di pubblicazione ordinaria.

## Immagini

Il sistema prova a pubblicare una thumbnail sul primo elemento di:

- Notizie e cronaca;
- Cultura;
- Sport;
- I prossimi eventi.

La ricerca segue quest'ordine: Open Graph, Twitter Card, `image_src`, JSON-LD. Sono rifiutati URL riconducibili a loghi, avatar, placeholder, favicon, pixel di tracking e immagini predefinite.

La risorsa:

- può pesare al massimo 8 MB in ingresso;
- deve misurare almeno 320×180;
- viene corretta secondo l'orientamento EXIF;
- viene ritagliata a 480×300;
- viene convertita in JPEG;
- deve pesare al massimo 180 KB;
- viene caricata nel Blob store Netlify con chiave deterministica per data, categoria e URL articolo.

L'endpoint Netlify accetta in upload soltanto JPEG autenticati, con chiave conforme e massimo 300 KB. Le immagini pubbliche hanno cache annuale e URL stabile. Un 403 della fonte, un'immagine assente o un errore di upload produce un warning e omette soltanto quella thumbnail.

## Recap Facebook

Il recap Facebook riusa headline, summary, categoria e associazione alla fonte già
prodotte e validate per la newsletter. Non effettua una nuova chiamata OpenAI e
non chiede al modello di generare link o attribuzioni.

Il renderer deterministico `facebook.py` seleziona fino a 7 contenuti, cercando
prima una rappresentanza delle sezioni presenti e usando il punteggio editoriale
per completare gli eventuali posti liberi. Produce:

- `facebook_post.txt`, con titolo, sintesi e fonte per ciascun elemento, senza URL;
- `facebook_sources.txt`, con la stessa numerazione, i link originali e il link
  tracciato per iscriversi a SiracusaDaily.

Il formato implementato corrisponde alla variante A dell'esperimento editoriale.
La variante con un'unica pagina web quotidiana non è inclusa in questa fase.

[← Precedente: Processing](03-processing.md) · [Successivo: Quality Assurance →](05-quality-assurance.md)
