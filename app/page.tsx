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
          <h1>Ogni giorno le notizie più rilevanti di Siracusa e provincia, in una sola email.</h1>
          <div className="hero-description">
            <p>
              Selezioniamo e riassumiamo le notizie più utili per aiutarti a rimanere sempre aggiornato
              su quello che succede nella tua città.
            </p>
            <p>Ricevi ogni giorno una newsletter da leggere mentre bevi il caffè, gratis.</p>
          </div>
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
            <h2>Siracusa e provincia</h2>
            <p>Solo contenuti che riguardano Siracusa e i comuni della provincia.</p>
          </div>
        </article>
        <article>
          <span>02</span>
          <div>
            <h2>Newsletter curata</h2>
            <p>Le notizie vengono attentamente selezionate ogni giorno, per darti le informazioni più rilevanti.</p>
          </div>
        </article>
        <article>
          <span>03</span>
          <div>
            <h2>Aggiornati nel tempo di un caffè</h2>
            <p>Ogni notizia è spiegata in poche righe chiare, sintetiche, e complete.</p>
          </div>
        </article>
      </section>

      <section className="content-proof">
        <div className="content-proof-copy">
          <div className="content-proof-heading">
            <h2>La città, ordinata per te.</h2>
          </div>
          <div className="edition-preview">
            <p className="edition-intro">Ogni giorno, una selezione equilibrata tra:</p>
            <div className="category-list" aria-label="Categorie della newsletter">
              <span>Notizie e cronaca</span>
              <span>Politica ed economia</span>
              <span>Cultura</span>
              <span>Sport</span>
              <span>I prossimi eventi</span>
              <span>Servizi e utilità</span>
              <span>Lavoro e opportunità</span>
            </div>
            <a className="secondary-cta" href="#iscriviti">Voglio riceverla</a>
          </div>
        </div>

        <div className="phone-showcase" role="img" aria-label="Esempio di SiracusaDaily visualizzata su uno smartphone">
          <div className="phone-frame">
            <div className="phone-speaker" aria-hidden="true" />
            <div className="phone-screen">
              <div className="phone-mail-toolbar">
                <span className="phone-mail-icon" aria-hidden="true">✉</span>
                <strong>Posta</strong>
                <span className="phone-mail-menu" aria-hidden="true">•••</span>
              </div>
              <div className="phone-mail-heading">
                <span className="phone-mail-avatar" aria-hidden="true">S</span>
                <span>
                  <strong>SiracusaDaily</strong>
                  <small>newsletter@siracusadaily.com</small>
                </span>
              </div>
              <div className="phone-mail-subject">Le notizie di oggi a Siracusa</div>
              <div className="phone-email-body">
                <div className="phone-newsletter-header">
                  <strong>SiracusaDaily</strong>
                </div>
                <div className="phone-newsletter-section phone-newsletter-news">
                  <div className="phone-category">Notizie e cronaca</div>
                  <article>
                    <strong>Murro di Porco, il faro trasformato in discarica</strong>
                    <p>Il consigliere Ansaldi denuncia rifiuti e degrado nell’area del faro.</p>
                  </article>
                  <article>
                    <strong>Riparato il guasto idrico in Traversa Carrozziere</strong>
                    <p>Concluso l’intervento sulla rete e ripristinato il servizio.</p>
                  </article>
                </div>
                <div className="phone-newsletter-section phone-newsletter-politics">
                  <div className="phone-category">Politica ed economia</div>
                  <article>
                    <strong>Etna, la Cna propone un piano in tre livelli</strong>
                    <p>Comiso indicato come alternativa per limitare i disagi ai voli.</p>
                  </article>
                </div>
                <div className="phone-newsletter-section phone-newsletter-events">
                  <div className="phone-category">I prossimi eventi</div>
                  <article>
                    <strong>Frutta Fresca Home Edition a Palazzolo Acreide</strong>
                    <p>La quarta edizione torna in via Soccorso 7.</p>
                  </article>
                </div>
              </div>
            </div>
          </div>
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
