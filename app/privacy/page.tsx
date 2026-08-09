import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="privacy-page">
      <Link className="wordmark" href="/">SiracusaDaily</Link>
      <p className="eyebrow">Informativa sulla privacy</p>
      <h1>Come trattiamo il tuo indirizzo email</h1>
      <p>
        L’informativa completa, con i dati identificativi del titolare del trattamento, sarà pubblicata
        prima dell’apertura del sito al pubblico. Questa versione privata serve esclusivamente a verificare
        il funzionamento tecnico della pagina e del modulo di iscrizione.
      </p>
      <p>
        Gli indirizzi inseriti nel modulo vengono gestiti tramite Brevo per l’invio della newsletter.
        Non utilizzare ancora questo modulo per raccogliere iscrizioni pubbliche.
      </p>
      <Link className="text-link" href="/">Torna alla pagina principale</Link>
    </main>
  );
}
