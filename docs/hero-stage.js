'use strict';
/* Hero: una scheda mostra a turno due documenti (lettera di dimissione e registro Excel). Da sinistra
   scorrono i dati del documento in chiaro e si disfano in polvere contro un fascio di luce sul bordo
   della scheda; il fascio attraversa poi la scheda e ogni dato personale diventa il segnaposto che
   riceve l'agente. I contenuti clinici restano. Dati di esempio.
   Con "riduci movimento" la scheda resta ferma sulla lettera gia' anonimizzata, senza flusso. */
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
    </div>
    <canvas class="stage-stream" aria-hidden="true"></canvas>`;
  const $ = sel => stage.querySelector(sel);
  const file = $('.stage-file'), status = $('.stage-status'), content = $('.stage-content');
  const body = $('.stage-body'), scan = $('.stage-scan'), tabs = [...stage.querySelectorAll('.stage-tabs span')];
  const stream = makeStream($('.stage-stream'), body);
  const wait = ms => new Promise(r => setTimeout(r, ms));

  function show(i) {
    const s = SCENES[i];
    file.textContent = s.file;
    tabs.forEach((t, k) => t.classList.toggle('on', k === i));
    status.textContent = 'In chiaro';
    status.classList.remove('done');
    content.innerHTML = s.body;
    stream.feed([...content.querySelectorAll('.pii')].map(el => el.textContent));
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
      stream.boost(true);
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
      stream.boost(false);
      status.textContent = 'Anonimizzato in locale';
      status.classList.add('done');
      await wait(3400);
      body.classList.add('out');
      await wait(450);
      i = (i + 1) % SCENES.length;
    }
  }

  /* Flusso a sinistra della scheda: righe di dati in chiaro che scorrono verso il fascio e, arrivate
     li', si rimescolano e si sciolgono in particelle. Disegnato solo quando la hero e' visibile. */
  function makeStream(cv, body) {
    const ctx = cv.getContext('2d');
    const GLYPHS = '#%&*+=?@$/\\<>[]{}~^:;';
    let rows = [], parts = [], values = ['ROSSI MARIO'], W = 0, H = 0, raf = 0, last = 0, fast = false, visible = true, speed = 1;
    const rnd = (a, b) => a + Math.random() * (b - a);
    function line() {                                      // una riga: dati del documento separati da punti
      const v = values.slice().sort(() => Math.random() - .5);
      return '  ' + v.join('  ·  ') + '  ·  ';
    }
    function resize() {
      const dpr = Math.min(2, devicePixelRatio || 1);
      W = cv.clientWidth; H = cv.clientHeight;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const top = body.offsetTop + 8, n = Math.max(5, Math.floor((body.offsetHeight - 16) / 34));
      rows = Array.from({ length: n }, (_, i) => ({ y: top + 8 + i * ((body.offsetHeight - 16) / n), text: line(), off: rnd(0, 400), v: rnd(28, 54), a: rnd(.35, .85) }));
    }
    function frame(dt) {
      const bx = W - 31, cw = 8.4;                           // fascio appena prima del bordo della scheda
      speed += ((fast ? 3 : 1) - speed) * Math.min(1, dt * 3);
      ctx.clearRect(0, 0, W, H);
      // corsia scura sotto il flusso: il retino dello sfondo non disturba la lettura
      const lane = ctx.createLinearGradient(0, 0, W, 0);
      lane.addColorStop(0, 'rgba(8,17,11,0)'); lane.addColorStop(.45, 'rgba(8,17,11,.82)'); lane.addColorStop(1, 'rgba(8,17,11,.9)');
      ctx.fillStyle = lane; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'destination-in';
      const vm = ctx.createLinearGradient(0, 0, 0, H);
      vm.addColorStop(0, 'rgba(0,0,0,0)'); vm.addColorStop(.15, '#000'); vm.addColorStop(.85, '#000'); vm.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = vm; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'source-over';
      ctx.font = '500 14px ui-monospace, "SF Mono", Menlo, monospace';
      ctx.textBaseline = 'middle';
      for (const r of rows) {
        r.off += r.v * speed * dt;
        const len = r.text.length * cw;
        if (r.off > len) { r.off -= len; r.text = line(); }
        // la riga si ripete: il carattere i sta a x = bx - (len - (i*cw + off) mod len)
        for (let i = 0; i < r.text.length; i++) {
          const ch = r.text[i];
          if (ch === ' ') continue;
          const x = bx - ((len - ((i * cw + r.off) % len)) % len) - cw;
          if (x < 0) continue;
          const near = 1 - (bx - x) / 70;                    // ultimi 70 px: il dato si rimescola
          let g = ch, a = r.a * Math.min(1, Math.max(0, x - W * .2) / (W * .45));  // entra sfumato da sinistra
          if (near > 0) {
            if (Math.random() < near * .9) g = GLYPHS[(Math.random() * GLYPHS.length) | 0];
            a *= 1 - near * .55;
            if (Math.random() < near * .05 * speed) parts.push({ x, y: r.y + rnd(-4, 4), vx: rnd(10, 60), vy: rnd(-14, 14), life: 1, s: rnd(.8, 2) });
          }
          ctx.fillStyle = near > .4 ? `rgba(212,240,107,${a.toFixed(2)})` : `rgba(255,255,255,${a.toFixed(2)})`;
          ctx.fillText(g, x, r.y);
        }
      }
      // polvere attorno al fascio
      if (Math.random() < .6 * speed) parts.push({ x: bx + rnd(-30, 4), y: rnd(0, H), vx: rnd(-8, 20), vy: rnd(-10, 10), life: 1, s: rnd(.6, 1.6) });
      ctx.fillStyle = '#e8f8a8';
      parts = parts.filter(p => (p.life -= dt * .8) > 0);
      for (const p of parts) {
        p.x += p.vx * dt; p.y += p.vy * dt;
        ctx.globalAlpha = p.life * .9;
        ctx.fillRect(p.x, p.y, p.s, p.s);
      }
      ctx.globalAlpha = 1;
      // fascio: alone ampio e anima sottile, sfumati in alto e in basso
      const k = .55 + .45 * (speed - 1) / 2;
      const halo = ctx.createLinearGradient(bx - 44, 0, bx + 5, 0);
      halo.addColorStop(0, 'rgba(212,240,107,0)'); halo.addColorStop(.85, `rgba(212,240,107,${(.4 * k).toFixed(2)})`); halo.addColorStop(1, 'rgba(212,240,107,0)');
      ctx.fillStyle = halo; ctx.fillRect(bx - 44, H * .08, 49, H * .84);
      const core = ctx.createLinearGradient(0, 0, 0, H);
      core.addColorStop(0, 'rgba(240,255,190,0)'); core.addColorStop(.2, `rgba(240,255,190,${(.95 * k).toFixed(2)})`);
      core.addColorStop(.8, `rgba(240,255,190,${(.95 * k).toFixed(2)})`); core.addColorStop(1, 'rgba(240,255,190,0)');
      ctx.shadowColor = 'rgba(212,240,107,.9)'; ctx.shadowBlur = 14;
      ctx.fillStyle = core; ctx.fillRect(bx - 1, 0, 2, H);
      ctx.shadowBlur = 0;
    }
    function loop(now) {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(.1, (now - last) / 1000); last = now;
      frame(dt);
    }
    const start = () => { if (!raf && visible && !document.hidden && cv.offsetWidth) { last = performance.now(); raf = requestAnimationFrame(loop); } };
    const stop = () => { cancelAnimationFrame(raf); raf = 0; };
    new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop(); }).observe(stage);
    document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
    new ResizeObserver(() => { resize(); stop(); start(); }).observe(cv);
    return {
      feed(v) { if (v.length) values = v; rows.forEach(r => { r.text = line(); }); },
      boost(on) { fast = on; },
    };
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
