'use strict';
/* Hero: una scheda mostra a turno due documenti (lettera di dimissione e registro Excel). Un fascio di luce
   la attraversa da sinistra, con una scia di polvere, e ogni dato personale diventa il segnaposto che
   riceve l'agente; i contenuti clinici restano. Dati di esempio.
   Con "riduci movimento" la scheda resta ferma sulla lettera gia' anonimizzata. */
(() => {
  const stage = document.querySelector('.hero-stage');
  if (!stage) return;
  const still = matchMedia('(prefers-reduced-motion: reduce)');
  const pii = (text, repl) => `<span class="pii" data-repl="${repl}">${text}</span>`;

  const SCENES = [
    {
      file: 'lettera_dimissione.pdf',
      body: `
        <div class="doc">
          <p class="doc-h">Lettera di dimissione · U.O.C. Cardiologia</p>
          <dl class="doc-f">
            <dt>Paziente</dt><dd>${pii('ROSSI MARIO', '[PAZIENTE_1]')}</dd>
            <dt>Nato il</dt><dd>${pii('10/12/1985', '[DATA_NASCITA_1]')}</dd>
            <dt>Codice fiscale</dt><dd>${pii('RSSMRA85T10A562S', '[ID_1]')}</dd>
            <dt>Residenza</dt><dd>${pii('Via Garibaldi 12, Ancona', '[CONTATTO_1]')}</dd>
          </dl>
          <p>Ricoverato dal ${pii('02/11/2026', '[DATA_1]')} per NSTEMI. Coronarografia: stenosi critica IVA prossimale, PTCA con impianto di DES.</p>
          <p>Terapia: ASA 100 mg, ticagrelor 90 mg × 2/die, bisoprololo 2,5 mg.</p>
          <p>Informata la moglie, sig.ra ${pii('Anna Bianchi', '[PERSONA_1]')} (tel. ${pii('347 123 4567', '[CONTATTO_2]')}).</p>
          <p class="doc-sign">Firmato digitalmente da Dott. ${pii('Paolo Neri', '[MEDICO_1]')}</p>
        </div>`,
    },
    {
      file: 'registro_TAVI.xlsx',
      body: `
        <table class="sheet-mini">
          <thead><tr><th>Cognome e nome</th><th>Codice fiscale</th><th>NYHA</th><th>EuroSCORE</th><th>Esito</th></tr></thead>
          <tbody>
            ${[['ROSSI MARIO', 'RSSMRA85T10A562S', 'III', '4,2', 'vivo', 1],
               ['POPESCU IONUȚ', 'PPSNTI70A01Z129X', 'II', '2,8', 'deceduto', 2],
               ['BIANCHI ANNA', 'BNCNNA32A41H501X', 'IV', '8,9', 'vivo', 3],
               ['ESPOSITO LUCA', 'SPSLCU58M12F839D', 'III', '3,6', 'vivo', 4],
               ['NGUYEN THI LAN', 'NGYTLN66E52Z251K', 'II', '1,9', 'vivo', 5],
               ['CONTI SARA', 'CNTSRA49P61A271B', 'IV', '7,4', 'deceduto', 6]]
              .map(([n, cf, ny, es, ex, i]) => `<tr><td>${pii(n, `PAZ-000${i}`)}</td><td>${pii(cf, `ID-000${i}`)}</td><td>${ny}</td><td>${es}</td><td>${ex}</td></tr>`).join('')}
          </tbody>
        </table>
        <p class="doc-note">Classe NYHA, EuroSCORE ed esiti restano intatti; i fogli restano collegabili tramite PAZ.</p>`,
    },
  ];

  stage.innerHTML = `
    <div class="ui stage-card">
      <div class="stage-head">
        <span class="stage-file"></span>
        <span class="stage-status">In chiaro</span>
      </div>
      <div class="stage-tabs">${SCENES.map(s => `<span>${s.file}</span>`).join('')}</div>
      <div class="stage-body"><div class="stage-scan"></div><div class="stage-content"></div></div>
      <p class="stage-foot">Dati di esempio · elaborazione in locale</p>
    </div>`;
  const $ = sel => stage.querySelector(sel);
  const file = $('.stage-file'), status = $('.stage-status'), content = $('.stage-content');
  const body = $('.stage-body'), scan = $('.stage-scan'), tabs = [...stage.querySelectorAll('.stage-tabs span')];
  const wait = ms => new Promise(r => setTimeout(r, ms));

  function show(i) {
    const s = SCENES[i];
    file.textContent = s.file;
    tabs.forEach((t, k) => t.classList.toggle('on', k === i));
    status.textContent = 'In chiaro';
    status.classList.remove('done');
    content.innerHTML = s.body;
  }

  function anonymize(el) {
    el.classList.add('flip');
    setTimeout(() => { el.textContent = el.dataset.repl; el.classList.remove('flip'); el.classList.add('done'); }, 180);
  }

  async function run() {
    let i = 0;
    for (;;) {
      show(i);
      body.classList.remove('out');
      await wait(1600);
      // il fascio entra da sinistra: ogni dato cambia quando la linea lo raggiunge
      status.textContent = 'In elaborazione…';
      const W = body.clientWidth, T = 2200;
      scan.style.transition = 'none'; scan.style.transform = 'translateX(0)'; scan.classList.add('on');
      void scan.offsetWidth;
      scan.style.transition = `transform ${T}ms cubic-bezier(.45,.05,.55,.95)`;
      scan.style.transform = `translateX(${W}px)`;
      const left = body.getBoundingClientRect().left;
      content.querySelectorAll('.pii').forEach(el => {
        const x = el.getBoundingClientRect().left - left;
        setTimeout(() => anonymize(el), Math.max(0, x / W) * T);
      });
      await wait(T + 200);
      scan.classList.remove('on');
      status.textContent = 'Anonimizzato in locale';
      status.classList.add('done');
      await wait(3400);
      body.classList.add('out');
      await wait(450);
      i = (i + 1) % SCENES.length;
    }
  }

  if (still.matches) {
    show(0);
    content.querySelectorAll('.pii').forEach(el => { el.textContent = el.dataset.repl; el.classList.add('done'); });
    status.textContent = 'Anonimizzato in locale';
    status.classList.add('done');
  } else {
    run();
  }
})();
