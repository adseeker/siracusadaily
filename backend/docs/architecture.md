# SiracusaDaily — architettura MVP

## Obiettivo

Produrre ogni giorno una bozza verificabile della newsletter partendo dalla source map, senza legare il sistema a un singolo sito o modello linguistico.

```text
Source map → Adapter retrieval → Articoli normalizzati → Filtro geografico
           → Deduplicazione/cluster → Ranking + source fairness
           → Pacchetto evidenze → Writer editoriale → Controlli grounding
           → Bozza Markdown → Revisione editoriale → Invio
```

## Componenti

- **Retrieval:** adapter per metodo (`rss`, successivamente `web_html`, `browser_multimodal_assisted`, API).
- **Persistenza:** SQLite conserva articoli, URL canonici, punteggi e storico delle selezioni.
- **Filtro geografico:** riconoscimento iniziale di Siracusa, quartieri e comuni provinciali; le fonti istituzionali territoriali ricevono un segnale aggiuntivo.
- **Deduplicazione:** similarità di titolo e finestra temporale; un cluster conserva tutte le fonti che hanno trattato lo stesso fatto.
- **Ranking:** località, affidabilità, priorità editoriale, freschezza, completezza e corroborazione.
- **Fairness:** limite per fonte e spareggio a favore della fonte usata meno recentemente; non sostituisce la qualità.
- **Writer:** invia al modello soltanto un pacchetto strutturato di evidenze e richiede JSON conforme a schema. Candidate ID, URL e attribuzioni restano sotto il controllo del renderer.
- **Grounding:** vengono validati soltanto vincoli oggettivi: identità del candidato, presenza e lunghezza dei campi, punteggiatura conclusiva e numeri supportati dalle evidenze.
- **Correzione:** gli elementi fuori contratto vengono riscritti in una seconda richiesta mirata con gli errori di validazione. Se falliscono ancora, sono esclusi e registrati.
- **Continuità:** il problema di un singolo candidato non blocca l'edizione; un errore complessivo del servizio AI invece ferma la generazione. Non esiste downgrade silenzioso al fallback.

## Decisioni e compromessi

- Python standard library riduce dipendenze e rende facile il deployment, ma l'estrazione HTML avanzata richiederà un adapter più ricco.
- SQLite è adatto a una pipeline giornaliera e a un singolo processo. PostgreSQL diventerà utile con più worker o una redazione multiutente.
- La deduplicazione lessicale è trasparente e testabile; embedding e clustering semantico saranno introdotti dopo la raccolta di un dataset di valutazione.
- La bozza Markdown permette revisione umana immediata. La distribuzione email resta fuori dal primo vertical slice.

## Prossime estensioni

1. Coda multimodale assistita per social e locandine.
2. Valutazione annotata per filtro geografico e deduplicazione.
3. Dataset di valutazione editoriale e controllo automatico più ampio di nomi, date e luoghi.
4. Scheduler, metriche di copertura e pannello di revisione.

## Adapter HTML operativi

- Eventbrite: dati incorporati `__SERVER_DATA__`, con data, ora, venue e filtro della provincia.
- Comune di Siracusa: card di eventi; comunicati, avvisi e concorsi continuano a preferire RSS.
- Agenda eventi: finestra mobile di sette giorni a partire dalla data dell'edizione; usa la data dell'evento, non quella di pubblicazione, e conserva gli appuntamenti futuri nel database fino alla conclusione.
- ConcorsiPubblici.com: solo bandi attivi, con scadenza e descrizione; resta obbligatoria la verifica primaria.
- ASP Siracusa: card delle procedure aperte, data di pubblicazione e permalink.
