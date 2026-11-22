'use strict';
/* Sfondo della hero in ASCII: un campo vettoriale rado, a scacchiera, che deriva lentamente
   ed e' attraversato da impulsi verso destra, come un flusso di dati. Disegno per righe e
   livelli di intensita': poche chiamate fillText per fotogramma. Fermo con "riduci movimento"
   e fuori schermo. */
(() => {
  const hero = document.querySelector('.hero');
  const cv = document.querySelector('.hero-ascii');
  if (!hero || !cv) return;
  const ctx = cv.getContext('2d');
  const still = matchMedia('(prefers-reduced-motion: reduce)');
    const LEVELS = [.14, .24, .38, .6];                  // opacita' dei quattro livelli del campo
  const FS = 12, LH = 15;
  let W = 0, H = 0, cols = 0, rows = 0, cw = 7.2, raf = 0, last = 0, visible = true;

  function resize() {
    const dpr = Math.min(2, devicePixelRatio || 1);
    W = hero.clientWidth; H = hero.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = `500 ${FS}px ui-monospace, "SF Mono", Menlo, monospace`;
    ctx.textBaseline = 'top';
    cw = ctx.measureText('0').width;
    cols = Math.ceil(W / cw) + 1; rows = Math.ceil(H / LH) + 1;
  }

  function frame(now) {
    const t = now / 1000;
    ctx.clearRect(0, 0, W, H);
    const lines = LEVELS.map(() => []);
    for (let r = 0; r < rows; r++) {
      const buf = LEVELS.map(() => new Array(cols).fill(' '));
      for (let c = 0; c < cols; c++) {
        if ((c + r) % 2) continue;                                                            // griglia rada, a scacchiera
        // campo vettoriale che deriva lentamente: direzione della corrente in ogni punto
        const a = Math.sin(c * .045 + t * .15) * 1.1 + Math.cos(r * .07 - t * .11) * .9 + Math.sin((c + r) * .021) * .6;
        // impulso che attraversa il campo verso destra: il "flusso" dei dati
        const pulse = Math.max(0, Math.sin(c * .06 - t * 1.4 + Math.sin(r * .08) * 1.2)) ** 6;
        const m = .35 + .35 * Math.sin(r * .05 + c * .02 + t * .2) + .9 * pulse;
        if (m < .3) continue;
        const lv = Math.min(3, Math.floor((m - .3) * 3.2));
        const q = ((Math.round(a / (Math.PI / 4)) % 4) + 4) % 4;
        buf[lv][c] = m < .42 ? '·' : '─╲│╱'[q];
      }
      buf.forEach((b, k) => lines[k].push(b.join('')));
    }
    lines.forEach((rowsTxt, k) => {
      ctx.fillStyle = `rgba(212, 240, 107, ${LEVELS[k]})`;
      rowsTxt.forEach((s, r) => ctx.fillText(s, 0, r * LH));
    });
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (now - last < 1000 / 24) return;               // 24 fotogrammi al secondo bastano
    last = now;
    frame(now);
  }
  function start() { if (!raf && visible && !still.matches && !document.hidden) raf = requestAnimationFrame(loop); }
  function stop() { cancelAnimationFrame(raf); raf = 0; }

  resize();
  frame(12000);
  addEventListener('resize', () => { resize(); frame(performance.now()); });
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop(); }).observe(hero);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  still.addEventListener('change', () => (still.matches ? stop() : start()));
  start();
})();
