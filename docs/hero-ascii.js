'use strict';
/* Sfondo della hero: retino a pixel (dithering), quadratini su quattro toni che sfumano da una
   luce in alto a destra verso il buio dove sta il testo. La luce oscilla lentamente e i pixel
   "respirano". Disegno raggruppato per tono (un solo fill per livello). Fermo con
   "riduci movimento" e quando la hero non e' visibile. */
(() => {
  const hero = document.querySelector('.hero');
  const cv = document.querySelector('.hero-ascii');
  if (!hero || !cv) return;
  const ctx = cv.getContext('2d');
  const still = matchMedia('(prefers-reduced-motion: reduce)');
  // toni dal piu' scuro al piu' chiaro (verde Clin; per il blu: '#16223a','#22406e','#3b67a8','#6f9be0','#b6d0f5')
  const TONES = ['#0f2117', '#1c3d27', '#2f6a3f', '#6aa452', '#d4f06b'];
  let W = 0, H = 0, S = 10, cols = 0, rows = 0, noise = null, raf = 0, last = 0, visible = true;

  // rumore stabile per cella: lo stesso pixel cambia tono sempre allo stesso modo
  function hash(i) { i = Math.imul(i ^ 0x9e3779b9, 0x85ebca6b); i ^= i >>> 13; i = Math.imul(i, 0xc2b2ae35); return ((i ^ (i >>> 16)) >>> 0) / 4294967296; }

  function resize() {
    const dpr = Math.min(2, devicePixelRatio || 1);
    W = hero.clientWidth; H = hero.clientHeight;
    S = W < 600 ? 8 : W < 1100 ? 10 : 12;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(W / S); rows = Math.ceil(H / S);
    noise = new Float32Array(cols * rows * 2);
    for (let k = 0; k < cols * rows; k++) { noise[2 * k] = hash(k * 2 + 1); noise[2 * k + 1] = hash(k * 2 + 7) * Math.PI * 2; }
  }

  function frame(now) {
    const t = now / 1000;
    const mobile = W < 900;
    // luce: in alto a destra sul computer, in alto sul telefono (il testo sta in basso)
    const lx = mobile ? .62 + .12 * Math.sin(t * .13) : .86 + .06 * Math.sin(t * .11);
    const ly = mobile ? -.05 : .05 + .05 * Math.cos(t * .09);
    const paths = TONES.map(() => new Path2D());
    const g = S - 1;                                       // un filo di fuga fra i quadratini
    for (let r = 0; r < rows; r++) {
      const ny = r / rows;
      for (let c = 0; c < cols; c++) {
        const nx = c / cols;
        // distanza dalla luce, allungata in diagonale come un fascio
        const dx = (nx - lx) * (mobile ? 1.1 : 1), dy = (ny - ly) * (mobile ? .8 : 1.25);
        let b = 1 - Math.sqrt(dx * dx + dy * dy) * (mobile ? 1.05 : 1.15);
        b += .08 * Math.sin(nx * 9 + ny * 5 + t * .25);    // morbide onde di luce
        const k = 2 * (r * cols + c);
        const v = b + (noise[k] - .5) * .55 + .06 * Math.sin(t * .8 + noise[k + 1]);
        if (v < .08) continue;                              // nessun pixel: resta lo sfondo
        const lv = Math.min(4, Math.floor(v * 5));
        paths[lv].rect(c * S, r * S, g, g);
      }
    }
    ctx.clearRect(0, 0, W, H);
    paths.forEach((p, i) => { ctx.fillStyle = TONES[i]; ctx.fill(p); });
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (now - last < 1000 / 15) return;                     // 15 fotogrammi al secondo bastano
    last = now;
    frame(now);
  }
  function start() { if (!raf && visible && !still.matches && !document.hidden) raf = requestAnimationFrame(loop); }
  function stop() { cancelAnimationFrame(raf); raf = 0; }

  resize();
  frame(8000);
  let rt = 0;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { resize(); frame(performance.now()); }, 120); });
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop(); }).observe(hero);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  still.addEventListener('change', () => (still.matches ? stop() : start()));
  start();
})();
