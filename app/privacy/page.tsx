import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Informativa sulla privacy | SiracusaDaily",
  description: "Informativa sul trattamento dei dati personali degli utenti di SiracusaDaily.",
};

export default function PrivacyPage() {
  return (
    <main className="privacy-page">
      <Link className="wordmark" href="/">SiracusaDaily</Link>
      <p className="eyebrow">Informativa sulla privacy</p>
      <h1>Come trattiamo i tuoi dati personali</h1>
      <p className="privacy-updated">Ultimo aggiornamento: 26 agosto 2026</p>

      <p>
        La presente informativa descrive come SiracusaDaily tratta i dati personali degli utenti che
        visitano il sito <strong>siracusadaily.com</strong> e si iscrivono alla newsletter.
      </p>

      <section>
        <h2>1. Titolare del trattamento</h2>
        <p>Il titolare del trattamento è <strong>Marco Cardile</strong>.</p>
        <p>Email: <a href="mailto:ciao@siracusadaily.com">ciao@siracusadaily.com</a></p>
        <p>
          Per qualsiasi domanda relativa al trattamento dei dati personali è possibile contattare il
          titolare all’indirizzo indicato.
        </p>
      </section>

      <section>
        <h2>2. Dati trattati</h2>
        <h3>Dati forniti per l’iscrizione</h3>
        <p>Quando ti iscrivi alla newsletter raccogliamo:</p>
        <ul>
          <li>indirizzo email;</li>
          <li>data e ora dell’iscrizione;</li>
          <li>stato dell’iscrizione e del consenso;</li>
          <li>informazioni tecniche necessarie a documentare la richiesta, come indirizzo IP e identificativo del modulo;</li>
          <li>eventuali informazioni relative alla conferma, alla disiscrizione o alla gestione delle preferenze.</li>
        </ul>
        <p>Non raccogliamo deliberatamente categorie particolari di dati personali.</p>

        <h3>Dati di navigazione</h3>
        <p>
          Durante la visita al sito, i sistemi informatici utilizzati per il suo funzionamento possono
          acquisire automaticamente dati tecnici, tra cui:
        </p>
        <ul>
          <li>indirizzo IP;</li>
          <li>tipo di browser e dispositivo;</li>
          <li>data e ora della richiesta;</li>
          <li>pagina richiesta;</li>
          <li>informazioni tecniche relative a errori, sicurezza e funzionamento del servizio.</li>
        </ul>
        <p>Questi dati vengono utilizzati esclusivamente per consentire il funzionamento e la sicurezza del sito.</p>

        <h3>Dati relativi alle newsletter</h3>
        <p>
          Il servizio di invio può registrare informazioni tecniche relative alla consegna dei messaggi,
          come email consegnate, respinte, segnalate come spam o oggetto di disiscrizione.
        </p>
        <p>
          Qualora siano attivate statistiche relative alle aperture o ai clic, tali dati saranno trattati
          esclusivamente secondo le scelte espresse dall’utente e nel rispetto della normativa applicabile.
          La mancata accettazione del tracciamento non impedisce di ricevere la newsletter.
        </p>
      </section>

      <section>
        <h2>3. Finalità e basi giuridiche</h2>
        <h3>Invio della newsletter</h3>
        <p>
          L’indirizzo email viene utilizzato per inviare la newsletter SiracusaDaily e le comunicazioni
          strettamente collegate al servizio. La base giuridica è il consenso dell’interessato, ai sensi
          dell’articolo 6, paragrafo 1, lettera a) del GDPR. Il consenso può essere revocato in qualsiasi momento.
        </p>

        <h3>Gestione dell’iscrizione</h3>
        <p>I dati vengono utilizzati per:</p>
        <ul>
          <li>registrare e confermare l’iscrizione;</li>
          <li>documentare il consenso;</li>
          <li>gestire richieste, preferenze e disiscrizioni;</li>
          <li>impedire invii successivi alla revoca del consenso.</li>
        </ul>

        <h3>Sicurezza e funzionamento del sito</h3>
        <p>
          I dati tecnici possono essere trattati per proteggere il sito, prevenire abusi, diagnosticare
          errori e garantire la disponibilità del servizio. La base giuridica è il legittimo interesse
          del titolare al funzionamento sicuro del sito, ai sensi dell’articolo 6, paragrafo 1, lettera f) del GDPR.
        </p>

        <h3>Adempimento di obblighi legali</h3>
        <p>
          I dati possono essere trattati quando necessario per adempiere a obblighi previsti dalla legge
          o rispondere a richieste delle autorità competenti.
        </p>
      </section>

      <section>
        <h2>4. Conferimento dei dati</h2>
        <p>
          Il conferimento dell’indirizzo email e del consenso è facoltativo. Se non fornisci questi dati,
          puoi continuare a visitare il sito, ma non potrai ricevere la newsletter.
        </p>
      </section>

      <section>
        <h2>5. Modalità del trattamento</h2>
        <p>
          I dati vengono trattati mediante strumenti informatici e adottando misure tecniche e
          organizzative adeguate a proteggerli da accessi non autorizzati, perdita, divulgazione, modifica o distruzione.
        </p>
        <p>
          SiracusaDaily non vende né cede gli indirizzi degli iscritti a soggetti terzi per finalità pubblicitarie.
          Non vengono effettuate decisioni esclusivamente automatizzate che producano effetti giuridici o
          conseguenze analogamente significative sull’utente.
        </p>
      </section>

      <section>
        <h2>6. Fornitori e destinatari</h2>
        <h3>Brevo</h3>
        <p>
          Brevo viene utilizzato per raccogliere e conservare le iscrizioni, documentare il consenso,
          gestire le liste dei destinatari, inviare le newsletter e gestire disiscrizioni, errori di consegna
          e statistiche tecniche. Brevo opera come responsabile del trattamento sulla base di un accordo
          conforme all’articolo 28 del GDPR.
        </p>
        <p><a href="https://www.brevo.com/legal/privacypolicy/" rel="noreferrer">Consulta l’informativa sulla privacy di Brevo</a></p>

        <h3>Netlify</h3>
        <p>
          Netlify ospita il sito e le relative funzioni tecniche. Nell’erogazione del servizio può trattare
          dati di navigazione e log tecnici.
        </p>
        <p><a href="https://www.netlify.com/privacy/" rel="noreferrer">Consulta l’informativa sulla privacy di Netlify</a></p>

        <h3>Google reCAPTCHA</h3>
        <p>
          Il modulo di iscrizione utilizza Google reCAPTCHA per prevenire spam e invii automatizzati.
          Il servizio può raccogliere informazioni tecniche sul dispositivo, sul browser e sull’interazione con il modulo.
        </p>
        <p>
          L’utilizzo di reCAPTCHA è soggetto alla <a href="https://policies.google.com/privacy" rel="noreferrer">Privacy Policy di Google</a>{" "}
          e ai <a href="https://policies.google.com/terms" rel="noreferrer">Termini di servizio di Google</a>.
        </p>
        <p>
          I dati possono inoltre essere comunicati a consulenti o autorità quando necessario per adempiere
          a obblighi legali o tutelare i diritti del titolare.
        </p>
      </section>

      <section>
        <h2>7. Trasferimenti fuori dallo Spazio economico europeo</h2>
        <p>
          Alcuni fornitori possono trattare dati anche al di fuori dello Spazio economico europeo.
          Quando necessario, tali trasferimenti avvengono sulla base di una decisione di adeguatezza della
          Commissione europea, delle clausole contrattuali standard o di altre garanzie previste dagli
          articoli 44 e seguenti del GDPR. Ulteriori informazioni sulle garanzie adottate possono essere richieste al titolare.
        </p>
      </section>

      <section>
        <h2>8. Conservazione</h2>
        <p>
          L’indirizzo email viene conservato per tutta la durata dell’iscrizione alla newsletter. In caso
          di disiscrizione, l’indirizzo viene rimosso dalla lista degli iscritti attivi.
        </p>
        <p>Potrà essere conservata una registrazione minima della disiscrizione per:</p>
        <ul>
          <li>evitare ulteriori invii;</li>
          <li>documentare la revoca del consenso;</li>
          <li>tutelare il titolare in caso di contestazioni;</li>
          <li>adempiere a eventuali obblighi di legge.</li>
        </ul>
        <p>
          Le prove del consenso vengono conservate per il periodo necessario a documentare la liceità del
          trattamento. I log tecnici sono conservati per il tempo strettamente necessario alla sicurezza,
          alla diagnosi degli errori e al funzionamento del servizio, salvo necessità di ulteriore
          conservazione connesse a incidenti o obblighi legali.
        </p>
      </section>

      <section>
        <h2>9. Disiscrizione e revoca del consenso</h2>
        <p>
          Puoi annullare l’iscrizione in qualsiasi momento utilizzando il collegamento presente in fondo
          a ogni newsletter oppure scrivendo a <a href="mailto:ciao@siracusadaily.com">ciao@siracusadaily.com</a>.
          La revoca non pregiudica la liceità dei trattamenti effettuati prima della revoca.
        </p>
      </section>

      <section>
        <h2>10. Diritti dell’interessato</h2>
        <p>Nei casi previsti dal GDPR puoi chiedere:</p>
        <ul>
          <li>l’accesso ai tuoi dati personali;</li>
          <li>la rettifica dei dati inesatti;</li>
          <li>la cancellazione dei dati;</li>
          <li>la limitazione del trattamento;</li>
          <li>la portabilità dei dati;</li>
          <li>l’opposizione al trattamento;</li>
          <li>la revoca del consenso.</li>
        </ul>
        <p>
          Per esercitare questi diritti puoi scrivere a <a href="mailto:ciao@siracusadaily.com">ciao@siracusadaily.com</a>.
          La richiesta sarà gestita senza ingiustificato ritardo e, di norma, entro un mese.
        </p>
        <p>
          Hai inoltre il diritto di proporre reclamo al <a href="https://www.garanteprivacy.it/" rel="noreferrer">Garante per la protezione dei dati personali</a>.
        </p>
      </section>

      <section>
        <h2>11. Cookie e strumenti tecnici</h2>
        <p>
          SiracusaDaily non utilizza attualmente cookie pubblicitari o sistemi propri di profilazione degli utenti del sito.
        </p>
        <p>
          Il modulo di iscrizione utilizza servizi tecnici di Brevo e Google reCAPTCHA, che possono impiegare
          cookie o strumenti analoghi necessari al funzionamento, alla sicurezza e alla prevenzione degli abusi.
        </p>
        <p>
          Qualora in futuro vengano introdotti strumenti analytics, pubblicitari o di profilazione non
          strettamente necessari, questa informativa verrà aggiornata e, quando richiesto, tali strumenti
          saranno attivati soltanto dopo aver raccolto il consenso dell’utente.
        </p>
      </section>

      <section>
        <h2>12. Collegamenti esterni</h2>
        <p>
          La newsletter e il sito contengono collegamenti a siti di terze parti. SiracusaDaily non controlla
          i trattamenti effettuati da tali siti, che operano secondo le proprie informative sulla privacy.
        </p>
      </section>

      <section>
        <h2>13. Modifiche all’informativa</h2>
        <p>
          La presente informativa può essere aggiornata per riflettere modifiche al servizio, ai fornitori
          utilizzati o alla normativa applicabile. La versione più recente sarà sempre disponibile su questa pagina.
        </p>
      </section>

      <Link className="text-link privacy-back-link" href="/">Torna alla pagina principale</Link>
    </main>
  );
}
