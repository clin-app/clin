'use strict';
/* Demo: una sessione reale di Claude Code con /Clin (demo.json, registrata su dati sintetici),
   riprodotta in due ricostruzioni dell'interfaccia: l'app desktop (chat) e il terminale.
   Il selettore cambia vista e riparte dall'inizio. Play/pausa, ricomincia, avanzamento.
   Parte quando entra nello schermo; con "riduci movimento" mostra la sessione completa. */
(() => {
  const root = document.querySelector('.demo');
  if (!root) return;
  const stage = root.querySelector('.demo-stage');
  const btn = root.querySelector('.demo-play');
  const again = root.querySelector('.demo-again');
  const bar = root.querySelector('.demo-progress i');
  const tabs = [...root.querySelectorAll('.demo-tabs button')];
  const still = matchMedia('(prefers-reduced-motion: reduce)');
  let data = null, view = null, i = 0, playing = false, timer = 0, started = false, instant = false;

  // ---------------------------------------------------------------- testo
  const esc = s => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const inline = s => esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[[A-Z_]+_\d+\]|\bPAZ-\d{4}\b|\bID-\d{4}\b/g, m => `<span class="ph">${m}</span>`);
  function md(text) {                                   // markdown minimo: paragrafi, elenchi, tabelle
    const out = []; let list = null, table = null;
    const flush = () => {
      if (list) { out.push(`<ul>${list.map(l => `<li>${inline(l)}</li>`).join('')}</ul>`); list = null; }
      if (table) {
        const rows = table.filter(r => !/^\|?\s*:?-{2,}/.test(r)).map(r => r.replace(/^\||\|$/g, '').split('|'));
        out.push(`<table>${rows.map((r, k) => `<tr>${r.map(c => k ? `<td>${inline(c.trim())}</td>` : `<th>${inline(c.trim())}</th>`).join('')}</tr>`).join('')}</table>`);
        table = null;
      }
    };
    for (const raw of text.split('\n')) {
      const line = raw.trimEnd();
      if (line.startsWith('|')) { if (list) flush(); (table = table || []).push(line); continue; }
      if (/^\s*[-*] /.test(line)) { if (table) flush(); (list = list || []).push(line.replace(/^\s*[-*] /, '')); continue; }
      flush();
      if (!line.trim()) continue;
      if (/^#+ /.test(line)) out.push(`<p><b>${inline(line.replace(/^#+ /, ''))}</b></p>`);
      else out.push(`<p>${inline(line)}</p>`);
    }
    flush();
    return out.join('');
  }
  const mentions = text => text.split(/(@[\w.\-/]+)/g);        // testo e file allegati con @
  const slashMenu = (cls) => `<div class="${cls}-mi on"><b>/clin</b><span>Anonimizza documenti sanitari e dati di ricerca in locale con Clin (user)</span></div><div class="${cls}-mi"><b>/clear</b><span>Clear conversation history and free up context</span></div><div class="${cls}-mi"><b>/compact</b><span>Clear conversation history but keep a summary in context</span></div>`;

  // streaming del testo dell'agente, condiviso dalle due viste
  function stream(el, text, scroll, done) {
    let k = 0;
    const tick = () => {
      if (!playing) { timer = setTimeout(tick, 120); return; }
      k = Math.min(text.length, k + (instant ? text.length : 14));
      el.innerHTML = md(text.slice(0, k));
      scroll();
      if (k >= text.length) done(); else timer = setTimeout(tick, 24);
    };
    tick();
  }

  // ---------------------------------------------------------------- vista: app desktop (chat)
  const ext = f => (f.split('.').pop() || '').toUpperCase();
  const card = f => `<span class="cd-att"><span class="cd-att-i" data-x="${esc(ext(f)).replace(/"/g, '&quot;')}">${esc(ext(f))}</span><span class="cd-att-t"><b>${esc(f)}</b><em>${ext(f) === 'PDF' ? 'PDF' : 'Foglio di calcolo'}</em></span></span>`;
  const SPARK = '<svg class="cd-spark" viewBox="0 0 24 24" aria-hidden="true"><g stroke="#d97757" stroke-width="2.3" stroke-linecap="round"><path d="M12 2.5v19M2.5 12h19M5.3 5.3l13.4 13.4M18.7 5.3L5.3 18.7M8.2 3.2l7.6 17.6M15.8 3.2L8.2 20.8M3.2 8.2l17.6 7.6M3.2 15.8l17.6-7.6"/></g></svg>';
  const desktop = {
    build() {
      const g = d => `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
      const folder = g('M1.8 4.2c0-.7.5-1.2 1.2-1.2h3l1.4 1.6H13c.7 0 1.2.5 1.2 1.2v6c0 .7-.5 1.2-1.2 1.2H3c-.7 0-1.2-.5-1.2-1.2z');
      stage.innerHTML = `
        <div class="cd">
          <aside class="cd-side">
            <div class="cd-lights"><i></i><i></i><i></i>${g('M2.5 3.5h11v9h-11zM6 3.5v9')}</div>
            <div class="cd-seg"><span>Chat</span><span>Cowork</span><span class="on">Code</span></div>
            <div class="cd-new">${g('M8 3.2v9.6M3.2 8h9.6')}Nuova sessione</div>
            <div class="cd-nav">${g('M2.8 4.5h10.4M2.8 8h10.4M2.8 11.5h6')}Routine</div>
            <p class="cd-sec">Oggi</p>
            <div class="cd-sess on"><i class="run"></i><span>Mortalità a 12 mesi per NYHA</span></div>
            <div class="cd-sess"><i></i><span>Pulizia registro ambulatorio</span></div>
            <p class="cd-sec">Ieri</p>
            <div class="cd-sess"><i></i><span>Curve di sopravvivenza follow-up</span></div>
            <div class="cd-sess"><i></i><span>Tabella 1 dello studio</span></div>
          </aside>
          <section class="cd-main">
            <header class="cd-top">
              <span class="cd-title">Mortalità a 12 mesi per NYHA</span>
              <span class="cd-chip">${folder}${esc(data.cwd.split('/').pop())}</span>
              <span class="cd-chip">${g('M3 4.2h10v6H3zM6 12.8h4M8 10.2v2.6')}Locale</span>
            </header>
            <div class="cd-log"><div class="cd-col"></div></div>
            <div class="cd-bottom">
              <div class="cd-spin" hidden>${SPARK}<span class="cd-spin-t"></span></div>
              <div class="cd-menu" hidden></div>
              <div class="cd-composer">
                <div class="cd-chips"></div>
                <div class="cd-input"><span class="cd-ph">Rispondi a Claude…</span><span class="cd-typed"></span><span class="cd-caret" hidden></span></div>
                <div class="cd-tools">
                  <span class="cd-plus">${g('M8 3.2v9.6M3.2 8h9.6')}</span>
                  <span class="cd-mode">${g('M3 8.4l3 3 7-7')}Accetta modifiche<i>⌄</i></span>
                  <span class="cd-model">Sonnet 5.5<i>⌄</i></span>
                  <span class="cd-send">${g('M8 12.5v-9M4.2 7.2L8 3.4l3.8 3.8')}</span>
                </div>
              </div>
            </div>
          </section>
        </div>`;
      this.log = stage.querySelector('.cd-log');
      this.col = stage.querySelector('.cd-col');
    },
    scroll() { this.log.scrollTop = this.log.scrollHeight; },
    add(html) { this.col.insertAdjacentHTML('beforeend', html); this.scroll(); },
    type(st, done) {
      const typed = stage.querySelector('.cd-typed'), chips = stage.querySelector('.cd-chips');
      const ph = stage.querySelector('.cd-ph'), menu = stage.querySelector('.cd-menu'), caret = stage.querySelector('.cd-caret');
      const files = st.files || [], text = st.shown || st.text;
      let f = 0, k = 0;
      const tick = () => {
        if (!playing) { timer = setTimeout(tick, 120); return; }
        if (f < files.length) {                          // file trascinati nel campo: schede allegato
          chips.insertAdjacentHTML('beforeend', card(files[f++]));
          timer = setTimeout(tick, instant ? 0 : 380);
          return;
        }
        ph.hidden = true; caret.hidden = false;
        k = Math.min(text.length, k + 2);
        typed.textContent = text.slice(0, k);
        menu.hidden = !(text.startsWith('/') && k < 6);
        if (!menu.hidden) menu.innerHTML = slashMenu('cd');
        if (k < text.length) { timer = setTimeout(tick, instant ? 0 : 26); return; }
        timer = setTimeout(() => {
          typed.textContent = ''; chips.innerHTML = ''; ph.hidden = false; caret.hidden = true; menu.hidden = true;
          stage.querySelector('.cd-send').classList.add('go');
          setTimeout(() => stage.querySelector('.cd-send').classList.remove('go'), 300);
          const body = esc(text).replace(/^\/clin\b/, '<span class="cd-cmd">/clin</span>');
          this.add(`<div class="cd-user">${files.length ? `<div class="cd-files">${files.map(card).join('')}</div>` : ''}<div class="cd-bubble">${body}</div></div>`);
          done();
        }, instant ? 0 : 500);
      };
      tick();
    },
    think(text) { const s = stage.querySelector('.cd-spin'); s.hidden = false; s.querySelector('.cd-spin-t').textContent = text + '…'; },
    idle() { stage.querySelector('.cd-spin').hidden = true; },
    tool(st) {
      const arg = st.name === 'Bash' ? st.arg : st.arg.split('/').pop();
      const icon = st.name === 'Bash' ? 'M3.5 5.5l2.5 2.5-2.5 2.5M8 10.5h4.5' : 'M4 2.5h5.5L12 5v8.5H4zM9.5 2.5V5H12';
      this.add(`<div class="cd-tool${st.ok ? '' : ' err'}"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icon}"/></svg><span class="cd-tv">${esc(st.name)}</span><span class="cd-ta">${esc(arg)}</span><span class="cd-chev">›</span></div>`);
    },
    clin(text) { this.add(`<div class="cd-clin"><span class="clin">/Clin</span><span>${inline(text)}</span></div>`); },
    assistant(text, done) {
      this.add(`<div class="cd-asst"><div class="cd-text"></div></div>`);
      stream(this.col.lastElementChild.querySelector('.cd-text'), text, () => this.scroll(), done);
    },
  };

  // ---------------------------------------------------------------- vista: terminale
  const SPIN = ['·', '✢', '✳', '∗', '✻', '✽'];
  let spinTimer = 0;
  const terminal = {
    build() {
      stage.innerHTML = `
        <div class="cc">
          <div class="cc-bar"><i></i><i></i><i></i><span>✳ Claude Code — ${esc(data.cwd.split('/').pop())} — 96×30</span></div>
          <div class="cc-log">
            <div class="cc-head">
              <pre class="cc-logo cc-orange" aria-hidden="true"> ▐▛███▜▌\n▝▜█████▛▘\n  ▘▘ ▝▝</pre>
              <div><p><b>Claude Code</b> <span class="cc-dim">v2.1.326</span></p><p class="cc-dim">Sonnet 5.5 · Claude Pro</p><p class="cc-dim">${esc(data.cwd)}</p></div>
            </div>
          </div>
          <div class="cc-spin" hidden><span class="cc-glyph">✻</span> <span class="cc-spin-t"></span> <span class="cc-dim">(<span class="cc-secs">0</span>s · esc to interrupt)</span></div>
          <div class="cc-input"><span class="cc-prompt">❯</span><span class="cc-typed"></span><span class="cc-caret"></span></div>
          <div class="cc-menu" hidden></div>
          <div class="cc-hint"><span>? for shortcuts</span></div>
        </div>`;
      this.log = stage.querySelector('.cc-log');
      clearInterval(spinTimer);
      let g = 0;
      spinTimer = setInterval(() => {
        const el = stage.querySelector('.cc-glyph'), secs = stage.querySelector('.cc-secs');
        if (el) el.textContent = SPIN[g++ % SPIN.length];
        if (secs && playing && !stage.querySelector('.cc-spin').hidden && g % 7 === 0) secs.textContent = +secs.textContent + 1;
      }, 140);
    },
    scroll() { this.log.scrollTop = this.log.scrollHeight; },
    add(html) { this.log.insertAdjacentHTML('beforeend', html); this.scroll(); },
    type(st, done) {
      const text = st.text;
      const typed = stage.querySelector('.cc-typed'), menu = stage.querySelector('.cc-menu');
      const render = s => mentions(s).map(x => x.startsWith('@') ? `<span class="cc-at">${esc(x)}</span>` : esc(x)).join('');
      let k = 0;
      const tick = () => {
        if (!playing) { timer = setTimeout(tick, 120); return; }
        k = Math.min(text.length, k + 2);
        const s = text.slice(0, k);
        typed.innerHTML = render(s);
        if (s.startsWith('/cl')) { menu.hidden = false; menu.innerHTML = slashMenu('cc'); }
        if (k < text.length) { timer = setTimeout(tick, instant ? 0 : 24); return; }
        timer = setTimeout(() => {
          menu.hidden = true; typed.innerHTML = '';
          this.add(`<div class="cc-user"><span class="cc-prompt">❯</span>${render(text)}</div>`);
          done();
        }, instant ? 0 : 400);
      };
      tick();
    },
    think(text) { const s = stage.querySelector('.cc-spin'); s.hidden = false; s.querySelector('.cc-spin-t').textContent = text + '…'; s.querySelector('.cc-secs').textContent = 0; },
    idle() { stage.querySelector('.cd-spin') && (stage.querySelector('.cd-spin').hidden = true); stage.querySelector('.cc-spin') && (stage.querySelector('.cc-spin').hidden = true); },
    tool(st) {
      const out = st.out.map((l, n) => `<div class="cc-out">${n ? '     ' : '  ⎿  '}${esc(l)}</div>`).join('') +
        (st.more ? `<div class="cc-out">     … +${st.more} lines (ctrl+o to expand)</div>` : '');
      this.add(`<div class="cc-tool"><span class="${st.ok ? 'cc-green' : 'cc-red'}">⏺</span> <b>${esc(st.name)}</b>(${esc(st.arg)})</div>${out}`);
    },
    clin(text) { this.add(`<div class="cc-out cc-clin">  ⎿  Stop hook · <span class="clin">/Clin</span> ${inline(text)}</div>`); },
    assistant(text, done) {
      this.add(`<div class="cc-asst"><span>⏺</span><div class="cc-text"></div></div>`);
      stream(this.log.lastElementChild.querySelector('.cc-text'), text, () => this.scroll(), done);
    },
  };

  // ---------------------------------------------------------------- riproduzione
  function next() {
    if (!playing) { timer = setTimeout(next, 150); return; }
    if (i >= data.steps.length) {
      view.idle(); playing = false; btn.textContent = 'Riproduci'; root.classList.add('ended'); return;
    }
    const st = data.steps[i++];
    bar.style.width = `${(i / data.steps.length) * 100}%`;
    const go = ms => { timer = setTimeout(next, instant ? 0 : ms); };
    if (st.type === 'user') { view.idle(); view.type(st, () => go(500)); }
    else if (st.type === 'think') { view.think(st.text); go(1300); }
    else if (st.type === 'tool') { view.tool(st); go(st.ok ? 700 : 900); }
    else if (st.type === 'clin') { view.clin(st.text); go(1300); }
    else if (st.type === 'assistant') { view.idle(); view.assistant(st.text, () => go(900)); }
    else go(0);
  }
  function restart() { clearTimeout(timer); i = 0; bar.style.width = '0'; view.build(); }
  function play() {
    const fresh = i === 0 || i >= data.steps.length;
    if (i >= data.steps.length) restart();
    playing = true; root.classList.remove('ended'); btn.textContent = 'Pausa';
    if (fresh) { clearTimeout(timer); next(); }
  }
  function pause() { playing = false; btn.textContent = 'Riprendi'; }
  function select(name) {
    tabs.forEach(t => t.setAttribute('aria-selected', String(t.dataset.view === name)));
    view = name === 'terminal' ? terminal : desktop;
    playing = false;
    restart();
    if (instant) { playing = true; next(); }
    else if (started) play();
  }

  btn.addEventListener('click', () => (playing ? pause() : play()));
  again.addEventListener('click', () => { playing = false; restart(); play(); });
  tabs.forEach(t => t.addEventListener('click', () => select(t.dataset.view)));

  fetch('demo.json').then(r => r.json()).then(d => {
    data = d;
    root.querySelector('.demo-meta').textContent = d.meta;
    instant = still.matches;                            // nessuna animazione: sessione completa, subito
    select('desktop');
    if (instant) return;
    new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !started) { started = true; play(); }
      else if (!e.isIntersecting && playing) pause();
    }, { threshold: .3 }).observe(root);
  });
})();
