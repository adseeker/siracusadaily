import { BrevoSignupForm } from "./BrevoSignupForm";

export default function Home() {
  return (
    <main>
      <div className="category-rail" aria-hidden="true">
        <span /><span /><span /><span /><span /><span /><span />
      </div>

      <header className="site-header">
        <a className="wordmark" href="#top" aria-label="SiracusaDaily, torna all’inizio">
          SiracusaDaily
        </a>
        <a className="header-cta" href="#iscriviti">Iscriviti</a>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">Newsletter locale quotidiana</p>
          <h1>Siracusa, ogni giorno. Senza rumore.</h1>
          <p className="hero-description">
            Una selezione chiara delle notizie più importanti di Siracusa e provincia,
            direttamente nella tua email.
          </p>
          <a className="primary-cta" href="#iscriviti">Ricevi SiracusaDaily</a>
          <p className="microcopy">Un’unica email. Puoi annullare l’iscrizione quando vuoi.</p>
        </div>

        <aside className="issue-preview" aria-label="Cosa trovi nella newsletter">
          <p className="issue-kicker">Ogni edizione</p>
          <div className="issue-line issue-line-wide" />
          <div className="issue-line" />
          <div className="issue-categories">
            <span>Notizie</span>
            <span>Politica</span>
            <span>Cultura</span>
            <span>Sport</span>
            <span>Eventi</span>
            <span>Servizi</span>
            <span>Opportunità</span>
          </div>
          <blockquote>
            “Quello che serve sapere, scritto per essere capito anche senza aprire dieci link.”
          </blockquote>
        </aside>
      </section>

      <section className="principles" aria-label="Come funziona SiracusaDaily">
        <article>
          <span>01</span>
          <h2>Locale davvero</h2>
          <p>Solo fatti che riguardano Siracusa e i comuni della provincia.</p>
        </article>
        <article>
          <span>02</span>
          <h2>Essenziale</h2>
          <p>Notizie selezionate, ordinate e riassunte in modo chiaro.</p>
        </article>
        <article>
          <span>03</span>
          <h2>Una volta al giorno</h2>
          <p>Un solo appuntamento quotidiano, senza notifiche continue.</p>
        </article>
      </section>

      <section className="signup-section" id="iscriviti">
        <div className="signup-intro">
          <p className="eyebrow">Iscrizione</p>
          <h2>La città nella tua posta.</h2>
          <p>Inserisci il tuo indirizzo email per ricevere SiracusaDaily.</p>
        </div>
        <div className="form-shell">
          <BrevoSignupForm />
        </div>
      </section>

      <footer>
        <a className="wordmark footer-wordmark" href="#top">SiracusaDaily</a>
        <p>Le informazioni locali da conoscere, senza perdere tempo.</p>
        <p className="footer-meta">
          © {new Date().getFullYear()} SiracusaDaily · <a href="/privacy">Privacy</a>
        </p>
      </footer>
    </main>
  );
}
