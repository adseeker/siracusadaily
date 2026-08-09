"use client";

import { useEffect } from "react";

const BREVO_ACTION =
  "https://39cb48bf.sibforms.com/serve/MUIFAOp5zLTzYBJIMKOyXmZ89fHVYVveXCqSMnlReX5WUeIX7FpPiP7Ou3EUD5vsXDGFg-cuQaPOsZtPIh7nBEPouXEAYqUhZ5X1XhnuPQt-oPATCUJokJDYJti_4FLFJEIcluIFnBp2I17sWXA0wWgdBVE2dmimANrXp3ztKWtHebpEOvlTV32NutgYpFBBjdbYFKlUIYgnucRCpg==";

export function BrevoSignupForm() {
  useEffect(() => {
    const brevoWindow = window as typeof window & Record<string, unknown>;
    brevoWindow.REQUIRED_CODE_ERROR_MESSAGE = "Scegli un prefisso paese";
    brevoWindow.LOCALE = "it";
    brevoWindow.EMAIL_INVALID_MESSAGE = "Controlla che l’indirizzo email sia scritto correttamente.";
    brevoWindow.REQUIRED_ERROR_MESSAGE = "Questo campo è obbligatorio.";
    brevoWindow.GENERIC_INVALID_MESSAGE = "Controlla i dati inseriti.";
    brevoWindow.translation = {
      common: {
        selectedList: "{quantity} lista selezionata",
        selectedLists: "{quantity} liste selezionate",
      },
    };
    brevoWindow.AUTOHIDE = false;
    brevoWindow.handleCaptchaResponse = () => {
      const captcha = document.getElementById("sib-captcha");
      captcha?.parentElement?.querySelector(".sib-captcha-message")?.remove();
    };

    const loadScript = (id: string, src: string, async = false) => {
      if (document.getElementById(id)) return;
      const script = document.createElement("script");
      script.id = id;
      script.src = src;
      script.defer = !async;
      script.async = async;
      document.body.appendChild(script);
    };

    loadScript("brevo-main-script", "https://sibforms.com/forms/end-form/build/main.js");
    loadScript("brevo-recaptcha-script", "https://www.google.com/recaptcha/api.js?hl=it", true);
  }, []);

  return (
      <div className="sib-form siracusa-signup-form">
        <div id="sib-form-container" className="sib-form-container">
          <div id="error-message" className="sib-form-message-panel form-message form-message-error" role="alert">
            <div className="form-message-content">
              <span className="form-message-icon" aria-hidden="true">!</span>
              <div>
                <strong>Iscrizione non completata</strong>
                <span className="sib-form-message-panel__inner-text">
                  Controlla i dati inseriti e riprova.
                </span>
              </div>
            </div>
          </div>

          <div id="success-message" className="sib-form-message-panel form-message form-message-success" role="status" aria-live="polite">
            <div className="form-message-content">
              <span className="form-message-icon" aria-hidden="true">✓</span>
              <div>
                <strong>Iscrizione completata</strong>
                <span className="sib-form-message-panel__inner-text">
                  Ti abbiamo aggiunto alla lista. Riceverai la prossima edizione via email.
                </span>
              </div>
            </div>
          </div>

          <div id="sib-container" className="sib-container--large sib-container--vertical">
            <form id="sib-form" method="POST" action={BREVO_ACTION} data-type="subscription">
              <div className="form-field">
                <label className="entry__label" htmlFor="EMAIL">
                  Inserisci il tuo indirizzo email<span className="required-mark" aria-hidden="true">*</span>
                </label>
                <div className="entry__field">
                  <input
                    className="input"
                    type="email"
                    id="EMAIL"
                    name="EMAIL"
                    autoComplete="email"
                    placeholder="nome@esempio.it"
                    data-required="true"
                    required
                  />
                </div>
                <p className="entry__specification">Riceverai un’email per confermare l’iscrizione.</p>
              </div>

              <div className="form-consent">
                <label className="checkbox-container" htmlFor="OPT_IN">
                  <input type="checkbox" className="input_replaced" value="1" id="OPT_IN" name="OPT_IN" required />
                  <span className="checkbox checkbox_tick_positive" aria-hidden="true" />
                  <span>
                    Acconsento al trattamento del mio indirizzo email per ricevere la newsletter quotidiana
                    SiracusaDaily. Ho letto l’<a href="/privacy">Informativa sulla privacy</a>.
                    <span className="required-mark" aria-hidden="true">*</span>
                  </span>
                </label>
              </div>

              <div className="captcha-wrap">
                <div
                  className="g-recaptcha sib-visible-recaptcha"
                  id="sib-captcha"
                  data-sitekey="6Leph30tAAAAAHAIUcEFR-8g7rjOCdCS1TauL1I6"
                  data-callback="handleCaptchaResponse"
                />
              </div>

              <button className="sib-form-block__button form-submit" form="sib-form" type="submit">
                <svg className="icon clickable__icon progress-indicator__icon sib-hide-loader-icon" viewBox="0 0 512 512" aria-hidden="true">
                  <path d="M460.115 373.846l-74.262-43.328a184.69 184.69 0 0 0 18.909-73.207c1.18-18.196 18.434-31.23 36.63-30.05l54.143 3.51c18.196 1.18 31.23 18.434 30.05 36.63a307.77 307.77 0 0 1-31.982 123.77c-8.57 16.1-27.388 21.247-43.488 12.675z" />
                </svg>
                ISCRIVITI
              </button>

              <p className="form-disclaimer">
                L’iscrizione alla newsletter SiracusaDaily è completamente gratuita. Puoi annullare
                l’iscrizione in qualsiasi momento.
              </p>

              <input type="text" name="email_address_check" value="" className="input--hidden" readOnly />
              <input type="hidden" name="locale" value="it" />
            </form>
          </div>
        </div>
      </div>
  );
}
