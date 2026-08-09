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
        <a className="header-cta" href="#iscriviti">Iscriviti gratis</a>
      </header>

      <section className="conversion-hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">Newsletter locale quotidiana</p>
          <h1>Tutto quello che conta a Siracusa. In una sola email.</h1>
          <p className="hero-description">
            Ogni giorno selezioniamo e riassumiamo le notizie più utili di Siracusa e provincia.
            Tu apri la newsletter e sai già cosa è successo.
          </p>
          <ul className="trust-list" aria-label="Vantaggi dell’iscrizione">
            <li>Gratis</li>
            <li>Un solo invio al giorno</li>
            <li>Disiscrizione con un clic</li>
          </ul>
        </div>

        <div className="signup-card" id="iscriviti">
          <h2>Iscriviti a SiracusaDaily</h2>
          <p className="signup-description">
            Ogni giorno, una selezione chiara delle notizie più importanti su Siracusa e provincia.
          </p>
          <BrevoSignupForm />
        </div>
      </section>

      <section className="value-strip" aria-label="Perché leggere SiracusaDaily">
        <article>
          <span>01</span>
          <div>
            <h2>Locale davvero</h2>
            <p>Solo contenuti che riguardano Siracusa e i comuni della provincia.</p>
          </div>
        </article>
        <article>
          <span>02</span>
          <div>
            <h2>Già selezionato</h2>
            <p>Le notizie duplicate vengono unite e quelle irrilevanti escluse.</p>
          </div>
        </article>
        <article>
          <span>03</span>
          <div>
            <h2>Subito comprensibile</h2>
            <p>Ogni notizia è spiegata in poche righe chiare e complete.</p>
          </div>
        </article>
      </section>

      <section className="content-proof">
        <div>
          <p className="eyebrow">Dentro ogni edizione</p>
          <h2>La città, ordinata per te.</h2>
        </div>
        <div className="edition-preview">
          <p className="edition-intro">Una selezione equilibrata tra:</p>
          <div className="category-list" aria-label="Categorie della newsletter">
            <span>Notizie e cronaca</span>
            <span>Politica ed economia</span>
            <span>Cultura</span>
            <span>Sport</span>
            <span>Eventi</span>
            <span>Servizi</span>
            <span>Opportunità</span>
          </div>
          <a className="secondary-cta" href="#iscriviti">Voglio riceverla</a>
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
