# Processing

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Persistenza

SQLite è la memoria operativa del sistema. Usa modalità WAL e quattro tabelle principali:

| Tabella | Contenuto |
|---|---|
| `articles` | Articoli normalizzati, metadati, punteggio locale e URL univoco |
| `newsletter_runs` | Data edizione, writer, modello, oggetto, output e stato Brevo |
| `newsletter_items` | Posizione, articolo, cluster e punteggio per ciascun run |
| `newsletter_exclusions` | Elementi esclusi dal writer e relativa motivazione |

L'upsert avviene sulla `canonical_url`. Un nuovo retrieval aggiorna dati e metadati senza creare copie dello stesso URL.

## Filtro geografico

Il testo di titolo ed estratto viene normalizzato e confrontato con Siracusa, quartieri e comuni della provincia. Il punteggio cresce con il numero di località rilevate.

Regole principali:

- una località riconosciuta produce una base di 0,72;
- più riferimenti territoriali aumentano il punteggio fino a 1;
- “provincia di Siracusa” e “Libero Consorzio di Siracusa” portano il punteggio almeno a 0,9;
- alcune fonti istituzionali territoriali ricevono un minimo di 0,62 anche in assenza di un luogo nel titolo;
- la soglia di ammissione al dataset editoriale è 0,55;
- il nome della testata viene rimosso dai segnali, così “SiracusaNews” non rende automaticamente locale una notizia.

## Qualità degli eventi

Gli eventi datati provenienti da AllEvents e Virgilio devono dimostrare di essere rivolti a un pubblico locale italiano. Il gate può mettere in quarantena una scheda per:

- scrittura non latina prevalente;
- insufficiente evidenza linguistica italiana;
- descrizione troppo breve;
- organizzatore non verificabile;
- scheda troppo scarsa;
- duplicazione sospetta dello stesso evento in più lingue o alfabeti.

Gli elementi in quarantena restano nel database con stato e motivazioni, ma non raggiungono selezione e writer. Le fonti evento più strutturate non subiscono questa limitazione specifica, pur restando soggette agli altri controlli.

## Qualità delle opportunità

Una voce entra nel percorso persistente soltanto se è esplicitamente marcata come opportunità strutturata. La sede effettiva dichiarata nella scheda deve trovarsi a Siracusa o in provincia.

Sono messi in quarantena:

- offerte con sede fuori provincia;
- risultati ottenuti soltanto grazie al raggio geografico ma con luogo di lavoro diverso;
- procedure nazionali genericamente multi-sede senza un riferimento locale specifico;
- opportunità la cui sede viene esplicitamente marcata come non verificata.

## Finestra temporale

Le tre famiglie di contenuto usano regole diverse.

### Notizie

- finestra corrente di produzione: ultime 168 ore;
- una notizia già inclusa in una precedente bozza Brevo riuscita viene esclusa;
- l'esclusione si estende all'intero cluster, quindi rimuove anche duplicati successivi provenienti da altre fonti.

### I prossimi eventi

- finestra mobile di sette giorni: oggi più i sei giorni successivi;
- la data considerata è quella dell'evento, non quella di pubblicazione;
- un evento già iniziato rimane visibile se la data di fine cade nella finestra;
- gli eventi vengono ordinati cronologicamente;
- possono ricomparire nelle edizioni successive finché restano nella finestra;
- limite operativo: 8.

### Lavoro e opportunità

- una scadenza resta valida per l'intera giornata locale indicata;
- stati chiusi, scaduti o non disponibili escludono immediatamente la voce;
- senza scadenza sono ammessi soltanto stati aperti o elencati;
- una voce senza scadenza tollera fino a tre giorni dall'ultima verifica positiva;
- le scadenze entro sette giorni hanno priorità;
- possono ricomparire finché risultano attive;
- limite operativo: 6.

## Deduplicazione

Gli articoli vengono raggruppati in cluster tramite una combinazione trasparente di:

- similarità Jaccard tra token dei titoli, soglia 0,50;
- similarità sequenziale dei titoli, soglia 0,82;
- sovrapposizione tra titolo e contesto dell'estratto;
- finestra massima ordinaria di 96 ore;
- data, luogo e parole distintive per gli eventi;
- nessun limite temporale per le opportunità persistenti.

Il cluster mantiene tutte le fonti che hanno trattato lo stesso fatto, ma pubblica un solo rappresentante e un solo link.

## Ranking

Il punteggio qualitativo di un articolo combina:

```text
località × 3,2
+ affidabilità fonte × 1,4
+ priorità editoriale
+ freschezza × 1,8
+ completezza estratto × 0,6
```

La freschezza decade esponenzialmente con costante di 36 ore. La completezza raggiunge il massimo a 400 caratteri di estratto.

Al punteggio del cluster si aggiungono:

- fino a 0,8 punti per corroborazione da fonti differenti;
- un vantaggio moderato di 0,45 alla prima notizia valida di una categoria ancora scoperta;
- uno spareggio minimo a favore delle fonti usate meno recentemente.

Il limite ordinario è di tre elementi per fonte. Se la fonte migliore ha raggiunto il limite, il sistema prova a scegliere un altro rappresentante dello stesso cluster.

Per le opportunità viene applicato anche un round-robin tra fonti, preservando l'ordine editoriale interno di ciascuna fonte.

## Classificazione

L'ordine di presentazione è:

1. Notizie e cronaca;
2. Politica ed economia;
3. Cultura;
4. Sport;
5. Servizi e utilità;
6. I prossimi eventi;
7. Lavoro e opportunità.

La classificazione iniziale usa content bucket e parole chiave. Il writer può correggere semanticamente la sezione delle notizie ordinarie. Gli eventi datati e le opportunità strutturate vengono invece forzati nelle rispettive sezioni dopo la risposta del modello.

[← Precedente: Fonti e acquisizione](02-fonti-acquisizione.md) · [Successivo: Generazione →](04-generazione.md)
