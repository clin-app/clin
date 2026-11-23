// Clin - richiesta di donazione a ogni download (sito ed app web).
// Un solo punto da configurare: il nome della pagina Ko-fi. Finche' e' vuoto non compare nulla
// e i download partono direttamente.
//
// Uso nell'HTML:
//   <a href="...zip" data-dona>...</a>          chiede prima di scaricare, poi scarica
//   <button data-dona="dopo">Copia</button>     chiede dopo il clic (l'azione avviene comunque)
// Uso da JavaScript:  import { chiediDonazione } from "./dona.js"; await chiediDonazione();

export const KOFI = "clinapp";
export const DONA_URL = KOFI ? "https://ko-fi.com/" + encodeURIComponent(KOFI) : "";

let dialog = null;

function build() {
  if (dialog) return dialog;
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = new URL("dona.css", import.meta.url).href;
  document.head.appendChild(css);

  dialog = document.createElement("dialog");
  dialog.className = "dona-dlg";
  dialog.setAttribute("aria-labelledby", "dona-t");
  dialog.innerHTML = `
    <div class="dona-in">
      <div class="dona-heart" aria-hidden="true">♥</div>
      <p class="dona-k">Download in partenza</p>
      <h2 id="dona-t">Clin è gratuito. Ti va di sostenerlo?</h2>
      <p class="dona-p">Nessun abbonamento e nessuna pubblicità: Clin vive di contributi volontari. Anche un caffè aiuta a mantenerlo aggiornato e sicuro.</p>
      <div class="dona-act">
        <a class="dona-yes" target="_blank" rel="noopener">Dona con Ko-fi</a>
        <button class="dona-no" type="button">Continua senza donare</button>
      </div>
      <p class="dona-s">Pagamento con PayPal o carta su Ko-fi. Clin non riceve né conserva dati di pagamento.</p>
    </div>`;
  document.body.appendChild(dialog);
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close("no"); });  // clic fuori
  return dialog;
}

// mostra la richiesta; si risolve quando l'utente sceglie (o chiude): il download prosegue comunque
export function chiediDonazione(kicker = "Download in partenza") {
  if (!DONA_URL || typeof HTMLDialogElement === "undefined") return Promise.resolve("nessuna");
  const d = build();
  d.querySelector(".dona-k").textContent = kicker;
  const yes = d.querySelector(".dona-yes"), no = d.querySelector(".dona-no");
  yes.href = DONA_URL;
  return new Promise((ok) => {
    const done = (v) => { yes.onclick = no.onclick = null; d.onclose = null; ok(v); };
    yes.onclick = () => { d.close("si"); };  // il link apre Ko-fi in una nuova scheda
    no.onclick = () => d.close("no");
    d.onclose = () => done(d.returnValue || "no");
    d.returnValue = "";
    d.showModal();
    no.focus();
  });
}

function wire() {
  document.querySelectorAll("a[data-dona]").forEach((a) => a.addEventListener("click", async (e) => {
    if (!DONA_URL || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    await chiediDonazione();
    location.href = a.href;  // il download parte dopo la scelta, in ogni caso
  }));
  document.querySelectorAll("button[data-dona]").forEach((b) => b.addEventListener("click", () => {
    setTimeout(() => chiediDonazione(b.dataset.donaTesto || "Comando copiato"), 400);
  }));
  const dona = document.getElementById("dona");  // pulsante della sezione «Sostieni» del sito
  if (dona && DONA_URL) { dona.href = DONA_URL; dona.target = "_blank"; dona.hidden = false; }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
else wire();
