'use strict';
/* Figure in caratteri: piccoli solidi (fogli impilati, archivio, lucchetto) disegnati
   con un raymarching a bassa risoluzione e resi come testo, dal carattere piu' leggero al piu' denso.
   Ruotano piano; in basso sfumano nello sfondo. Si muovono solo quando sono visibili e restano
   ferme con "riduci movimento".
   Uso: <canvas class="ascii-fig" data-shape="fogli|archivio|lucchetto" data-tone="light|dark"> */
(() => {
  const figs = [...document.querySelectorAll('canvas.ascii-fig')];
  if (!figs.length) return;
  const still = matchMedia('(prefers-reduced-motion: reduce)');
  const RAMP = " .'`-:;~=+*!?/|1iltjxzvnuJYCLQ0OZmwqpdbkhao#MW&8%B@";
  const len3 = (x, y, z) => Math.sqrt(x * x + y * y + z * z);

  function roundBox(x, y, z, bx, by, bz, r) {
    const qx = Math.abs(x) - bx + r, qy = Math.abs(y) - by + r, qz = Math.abs(z) - bz + r;
    return len3(Math.max(qx, 0), Math.max(qy, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qy, qz), 0) - r;
  }
  function cyl(x, y, z, r, h, e) {                         // cilindro verticale con spigolo arrotondato
    const dx = Math.hypot(x, z) - r + e, dy = Math.abs(y) - h + e;
    return Math.min(Math.max(dx, dy), 0) + Math.hypot(Math.max(dx, 0), Math.max(dy, 0)) - e;
  }

  const SHAPES = {
    fogli: { size: 1.75, tilt: .42, turn: .5, sdf(x, y, z) {          // tre fogli sospesi, come nello schema del sito
      let d = 9;
      for (let i = 0; i < 3; i++) d = Math.min(d, roundBox(x, y - (i - 1) * 1.0, z, 1.0, .05, .7, .045));
      return d;
    } },
    archivio: { size: 1.5, tilt: .42, turn: 0, sdf(x, y, z) {        // tre dischi: un archivio di dati
      let d = 9;
      for (let i = 0; i < 3; i++) d = Math.min(d, cyl(x, y - (i - 1) * .62, z, .95, .24, .07));
      return d;
    } },
    lucchetto: { size: 1.45, tilt: .18, turn: .4, sdf(x, y, z) {
      const body = roundBox(x, y + .38, z, .82, .6, .34, .16);
      const R = .5, ly = y - .25;                           // arco con due gambe
      const arc = ly > 0 ? Math.hypot(Math.hypot(x, ly) - R, z) : Math.hypot(Math.abs(x) - R, z, Math.max(-ly - .5, 0));
      return Math.min(body, arc - .15);
    } },
  };

  function setup(cv) {
    const shape = SHAPES[cv.dataset.shape] || SHAPES.fogli;
    const dark = cv.dataset.tone === 'dark';
    const ctx = cv.getContext('2d');
    const st = { cv, ctx, shape, dark, cols: 0, rows: 0, cw: 0, ch: 0, fs: 11, visible: false, seed: Math.random() * 6 };
    st.resize = () => {
      const dpr = Math.min(2, devicePixelRatio || 1);
      const W = cv.clientWidth, H = cv.clientHeight;
      if (!W || !H) return;
      st.fs = W < 320 ? 8 : 10;
      st.cw = st.fs * .62; st.ch = st.fs * 1.18;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      st.W = W; st.H = H; st.cols = Math.floor(W / st.cw); st.rows = Math.floor(H / st.ch);
    };
    st.resize();
    return st;
  }

  function draw(st, t) {
    const { ctx, shape, cols, rows, cw, ch, W, H } = st;
    if (!cols) return;
    if (H < 120) { ctx.clearRect(0, 0, W, H); return; }    // spazio troppo piccolo: meglio nessuna figura
    const scale = Math.min(W, H) / (2 * shape.size) * 1.08;  // pixel per unita'
    const a = (shape.turn ?? 0) + .55 * Math.sin(t * .28 + st.seed),   // oscilla: la figura non si mostra mai di taglio
      ca = Math.cos(a), sa = Math.sin(a);
    const ct = Math.cos(shape.tilt), stl = Math.sin(shape.tilt);
    // luce dall'alto a sinistra, davanti (gia' nello spazio dell'oggetto ruotato si usa la vista)
    const L = [-.35, .85, .4], ln = len3(...L); L[0] /= ln; L[1] /= ln; L[2] /= ln;
    const ox = (W - cols * cw) / 2, oy = (H - rows * ch) / 2;
    ctx.clearRect(0, 0, W, H);
    ctx.font = `500 ${st.fs}px ui-monospace, "SF Mono", Menlo, monospace`;
    ctx.textBaseline = 'top';
    const col = st.dark ? '212,240,107' : '23,61,38';
    // dalla vista allo spazio dell'oggetto: inclinazione attorno a X, poi rotazione attorno a Y
    const toObj = (x, y, z) => {
      const y1 = y * ct + z * stl, z1 = -y * stl + z * ct;   // si guarda dall'alto
      return [x * ca + z1 * sa, y1, -x * sa + z1 * ca];
    };
    const f = (x, y, z) => { const p = toObj(x, y, z); return shape.sdf(p[0], p[1], p[2]); };
    const lim = shape.size * 1.25;
    for (let r = 0; r < rows; r++) {
      const v = -((r + .5) * ch + oy - H / 2) / scale;
      const fade = Math.min(1, Math.max(0, (rows - r) / (rows * .38)));   // sfuma in basso
      for (let c = 0; c < cols; c++) {
        const u = ((c + .5) * cw + ox - W / 2) / scale;
        if (u * u + v * v > lim * lim) continue;
        let z = lim, hit = false, steps = 0;
        for (let i = 0; i < 44; i++) {                      // proiezione ortogonale, raggio verso -z
          const d = f(u, v, z);
          steps = i;
          if (d < .006) { hit = true; break; }
          z -= d;
          if (z < -lim) break;
        }
        if (!hit) continue;
        const e = .012;
        let nx = f(u + e, v, z) - f(u - e, v, z), ny = f(u, v + e, z) - f(u, v - e, z), nz = f(u, v, z + e) - f(u, v, z - e);
        const nl = len3(nx, ny, nz) || 1; nx /= nl; ny /= nl; nz /= nl;
        let lum = .14 + .86 * Math.max(0, nx * L[0] + ny * L[1] + nz * L[2]);
        lum += .18 * Math.pow(1 - Math.abs(nz), 3);         // bordo: le sagome restano leggibili
        lum *= 1 - Math.min(.3, steps / 100);               // raggi che sfiorano altre superfici: piu' scuri, separano i piani
        lum = Math.min(1, lum);
        // un po' di grana: celle vicine con la stessa luce non hanno tutte lo stesso carattere
        const jit = ((Math.imul(c * 73856093 ^ r * 19349663, 2654435761) >>> 0) % 3) - 1;
        const k = Math.max(1, Math.min(RAMP.length - 1, 1 + Math.floor(lum * (RAMP.length - 2)) + jit));
        const al = (.28 + .72 * lum) * fade;
        if (al < .04) continue;
        ctx.fillStyle = `rgba(${col},${al.toFixed(2)})`;
        ctx.fillText(RAMP[k], ox + c * cw, oy + r * ch);
      }
    }
  }

  const states = figs.map(setup);
  let raf = 0, last = 0;
  function loop(now) {
    raf = 0;
    if (now - last >= 1000 / 18) {                          // 18 fotogrammi al secondo bastano
      last = now;
      states.forEach(s => s.visible && draw(s, now / 1000));
    }
    if (!still.matches && !document.hidden && states.some(s => s.visible)) raf = requestAnimationFrame(loop);
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(loop); };
  const io = new IntersectionObserver(es => es.forEach(e => {
    const s = states.find(x => x.cv === e.target);
    s.visible = e.isIntersecting;
    if (s.visible) { if (!s.cols) s.resize(); draw(s, performance.now() / 1000); kick(); }
  }));
  states.forEach(s => io.observe(s.cv));
  // si ridisegna anche quando il canvas cambia dimensione (es. menu che si apre)
  const ro = new ResizeObserver(es => es.forEach(e => {
    const s = states.find(x => x.cv === e.target);
    s.resize(); if (s.visible) draw(s, performance.now() / 1000);
  }));
  states.forEach(s => ro.observe(s.cv));
  document.addEventListener('visibilitychange', kick);
  still.addEventListener('change', kick);
})();
