# Incidente Brevo del 27 agosto 2026

Stato: risolto<br>
Severità: SEV2 rispetto al servizio newsletter<br>
Impatto: edizione non consegnata da Brevo a 165 iscritti; nessun destinatario accodato

## Sintesi

Le campagne Brevo `#29` e `#30` sono rimaste ferme senza destinatari raggiunti.
La causa definitiva, comunicata dal team tecnico Brevo il 31 agosto, era un
carattere invisibile e non valido nell'oggetto: durante la creazione automatica
il valore era stato troncato nel mezzo di un carattere speciale e non poteva
essere elaborato dal motore di invio.

Non si trattava di lista vuota, quota esaurita, contenuto HTML, blocco di
sicurezza, reputazione del dominio o semplice ritardo dei provider destinatari.

## Timeline

- 09:15: campagna originale `#29` programmata; resta ferma con zero destinatari.
- 11:00: prima risposta automatica Brevo attribuisce il ritardo alla normale coda.
- 12:41: il supporto umano ipotizza un'anomalia dello scheduler e consiglia la duplicazione.
- 13:00: la copia `#30` eredita lo stesso oggetto e rimane bloccata.
- 12:59-13:35: entrambe le campagne vengono annullate; l'annullamento resta inizialmente in sospeso.
- Pomeriggio: l'edizione viene inviata manualmente tramite Sender.
- 31 agosto: Brevo comunica la root cause Unicode e conferma zero messaggi accodati o inviati.

## Root cause

L'oggetto proveniente dall'automazione era formalmente inadatto al sistema di
invio Brevo. La pipeline verificava lunghezza, contenuto editoriale e grounding,
ma non applicava un contratto di trasporto Unicode dedicato prima della POST.
La duplicazione della campagna non poteva mitigare il problema perché copiava
anche il valore corrotto.

## Correzione

- normalizzazione Unicode NFC;
- conversione degli spazi Unicode in spazi semplici;
- rifiuto di caratteri di controllo, formato, surrogati, privati o non assegnati;
- codifica UTF-8 strict;
- limite di 90 caratteri e 180 byte;
- divieto assoluto di troncamento automatico;
- validazione dopo il writer e immediatamente prima della chiamata Brevo;
- fallback soltanto verso un oggetto che supera lo stesso contratto;
- test di regressione per accenti, caratteri combinati, spazi anomali, zero-width,
  surrogati e limiti UTF-8.

## Rilevamento

Alle 09:00 Europe/Rome una Scheduled Function Netlify avvia il workflow GitHub
`Controllo consegna newsletter`. Il controllo considera regolare una campagna se:

- lo stato Brevo è `sent`; oppure
- risultano messaggi inviati o consegnati; oppure
- l'orario programmato più 15 minuti non è ancora trascorso.

Campagna assente o ferma a zero oltre la tolleranza produce una issue GitHub.
Il watchdog non annulla, duplica o invia campagne.

## Runbook Sender

1. Verificare in Brevo ID, stato e destinatari accodati.
2. Se esiste il rischio che Brevo stia inviando, non usare il fallback.
3. Se Brevo conferma zero destinatari, annullare la campagna anomala.
4. Non duplicare la campagna problematica.
5. Recuperare l'HTML dall'artifact GitHub del run.
6. Aggiornare manualmente la lista Sender.
7. Inserire un oggetto nuovo e verificato.
8. Inviare manualmente da Sender e registrare l'intervento.

Sender rimane un piano B manuale: non è integrato nel motore e non viene mai
attivato dal watchdog.

## Cosa ha funzionato

- il supporto ha confermato che nessun messaggio era stato inviato;
- il fallback Sender ha consentito di consegnare l'edizione;
- gli invii Brevo successivi sono tornati regolari;
- la separazione tra produzione HTML e provider ha reso possibile il cambio manuale.

## Cosa non ha funzionato

- la prima risposta automatica era generica e non coerente con zero destinatari;
- la prima diagnosi umana dello scheduler era incompleta;
- duplicare la campagna ha duplicato anche il difetto;
- mancava un controllo Unicode specifico e un alert post-invio.
