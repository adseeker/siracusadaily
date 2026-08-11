# Publishing e operations

[← Indice della documentazione tecnica](../../SIRACUSADAILY_TECHNICAL.md)

Ultimo aggiornamento: 11 agosto 2026<br>
Stato: sistema operativo in produzione


## Pianificazione

Il workflow `.github/workflows/newsletter-daily.yml` usa il fuso `Europe/Rome` e tre trigger giornalieri:

- 06:30: run principale;
- 07:00: recupero;
- 07:30: secondo recupero.

I recuperi eseguono il controllo Brevo prima del retrieval. Se la campagna esiste già, terminano senza chiamare OpenAI. GitHub Actions può avviare il job con ritardo rispetto all'orario nominale a causa della coda del servizio.

È disponibile anche `workflow_dispatch` con due modalità:

- `preflight`: verifica l'infrastruttura senza generare contenuti;
- `full`: esegue l'intera pipeline e crea una bozza senza inviarla.

## Idempotenza e concorrenza

- Il workflow usa un gruppo di concorrenza unico e non cancella un run già attivo.
- Brevo è la fonte autoritativa per stabilire se esiste già un'edizione.
- Il controllo considera bozze, campagne programmate e campagne inviate.
- La verifica viene eseguita prima del retrieval e di nuovo immediatamente prima della POST di creazione.
- Il nome campagna segue `SiracusaDaily | dd/mm/aaaa | run N`.

## Brevo

La campagna viene creata nella lista `Iscritti SiracusaDaily`, attualmente ID 7, con:

- mittente `SiracusaDaily <newsletter@siracusadaily.com>`;
- reply-to `ciao@siracusadaily.com`;
- contenuto HTML completo;
- oggetto generato e validato;
- parametro UTM `SiracusaDaily YYYYMMDD`;
- programmazione automatica nei run schedulati;
- stato di bozza nei run manuali o quando il kill switch è disattivato.

L'orario ordinario è 08:30, `Europe/Rome`. Se la produzione termina dopo le 08:15, Brevo viene programmato a 15 minuti dal completamento, con arrotondamento al minuto successivo. `SIRACUSA_AUTO_SEND_ENABLED` deve essere `true`; qualsiasi valore falso riconosciuto mantiene la campagna in bozza, mentre un valore non valido blocca il preflight.

Il comando manuale `workflow_dispatch` in modalità `full` crea sempre una bozza e non programma l'invio. In questo modo i test o le rigenerazioni manuali non possono spedire accidentalmente una campagna.

## Iscrizione utenti

La landing page incorpora un form Brevo diretto con:

- email obbligatoria;
- consenso privacy obbligatorio;
- reCAPTCHA;
- honeypot;
- messaggio esplicito di successo o errore;
- conferma semplice configurata lato Brevo;
- collegamento alla privacy policy.

## Esecuzione locale

Il setup locale crea un virtual environment, installa il package, inizializza SQLite e prepara `.env.local`:

```bash
cd backend
scripts/setup_local.sh
scripts/run_daily.sh
```

Il run locale usa `backend/runtime/` per database, HTML e log. Le immagini sono disattivate per impostazione predefinita; per pubblicarle su Netlify servono modalità `netlify` e token dedicato.

Il LaunchAgent macOS incluso è soltanto una procedura di emergenza. Non deve essere attivo insieme a GitHub Actions; il suo plist storico è configurato alle 09:30 e resta in modalità bozza salvo configurazione locale esplicita.

[← Precedente: Quality Assurance](05-quality-assurance.md) · [Successivo: Monitoring e logging →](07-monitoring-logging.md)
