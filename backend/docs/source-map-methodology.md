# SiracusaDaily — Source map

La source map è il registro operativo delle fonti locali utilizzate dalla pipeline di raccolta.

## Modello dati

- `Fonti`: una riga per ogni soggetto editoriale o organizzazione, con un `source_id` stabile nel formato `SRC-####`.
- `Endpoint`: una riga per ogni canale tecnico della fonte (sito, RSS, Instagram, Facebook, API, newsletter, PDF), collegato tramite `source_id` e identificato da `endpoint_id` nel formato `END-####`.
- `Valori controllati`: vocabolari usati dalle convalide del foglio; vanno estesi con cautela per mantenere dati confrontabili.

## Regole di aggiornamento

1. Normalizzare l'URL rimuovendo parametri di tracciamento, frammenti e slash finale non significativo.
2. Cercare prima una corrispondenza per dominio e identità editoriale, poi per URL esatto.
3. Se la fonte esiste, aggiornare il record e aggiungere solo gli endpoint mancanti.
4. Se il canale appartiene allo stesso soggetto, riutilizzare il suo `source_id`; non creare una nuova fonte per ogni social.
5. Aggiornare `last_checked` con la data della verifica e annotare ambiguità o limitazioni in `notes`.
6. Impostare `active=FALSE` per fonti non più disponibili; non cancellare gli ID storici.

## Criteri sintetici

- `reliability`: qualità e verificabilità della fonte, privilegiando fonti primarie e testate riconoscibili.
- `editorial_priority`: utilità attesa per rispondere a ciò che una persona a Siracusa deve sapere oggi.
- `requires_image_extraction`: `TRUE` quando informazioni essenziali sono pubblicate prevalentemente in locandine o immagini.
- `content_buckets`: valori multipli separati da punto e virgola, ad esempio `news; mobilità; eventi`.
- `geographic_scope`: area effettivamente coperta, ad esempio `Siracusa; Ortigia` o `Provincia di Siracusa`.

## Acquisizione di un nuovo URL

Per ogni URL si verificano identità della fonte, titolarità, copertura geografica, frequenza, formati pubblicati, RSS/API/social visibili, accessibilità tecnica e necessità di OCR. Il risultato aggiorna sia la riga della fonte sia gli endpoint correlati.

## Regole editoriali iniziali

- **Filtro geografico:** un articolo entra nel corpus editoriale solo se riguarda Siracusa o uno dei comuni della provincia. I contenuti esterni sono ammessi soltanto quando hanno un impatto diretto e documentato sul territorio.
- **Deduplicazione:** gli articoli sullo stesso fatto vengono raggruppati in un cluster usando titolo normalizzato, entità, luogo, tempo e URL canonico. Il cluster mantiene la provenienza da tutte le fonti.
- **Rotazione delle fonti:** quando due o più articoli equivalenti hanno pari rilevanza, completezza, tempestività e affidabilità, viene preferita come rappresentante la fonte usata meno recentemente. La rotazione è un criterio di spareggio e non sostituisce la qualità editoriale.
- **Fonti social di discovery:** hashtag e ricerche social generano lead, non contenuti automaticamente pubblicabili. Ogni post richiede verifica della pertinenza geografica e dell'organizzatore. L'acquisizione usa procedure assistite o API/autorizzazioni ufficiali; caption, immagini e video alimentano rispettivamente estrazione testuale, OCR e trascrizione.
