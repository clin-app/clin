// Orientamento delle foto e delle scansioni prima dell'OCR. Una carta d'identita' fotografata di lato
// letta cosi' com'e' produce frammenti senza senso, e i dati personali restano scoperti. Se la prima lettura
// e' poco affidabile si rileggono le altre tre rotazioni (in parallelo) e si tiene la piu' leggibile;
// i riquadri delle parole tornano nelle coordinate dell'immagine originale.

// punteggio: caratteri alfanumerici pesati per la confidenza di Tesseract; le parole incerte contano poco
export function ocrScore(data) {
  let good = 0, total = 0;
  const words = data.words || (data.blocks || []).flatMap((b) => b.paragraphs.flatMap((p) => p.lines.flatMap((l) => l.words)));
  for (const w of words) {
    const n = (w.text.match(/[\p{L}\p{N}]/gu) || []).length;
    total += n;
    good += n * (w.confidence / 100) * (w.confidence >= 55 ? 1 : 0.25);
  }
  return { score: good, mean: total ? good / total : 0 };
}

function rotated(canvas, deg) {
  const W = canvas.width, H = canvas.height, swap = deg % 180 !== 0;
  const c = document.createElement("canvas");
  c.width = swap ? H : W; c.height = swap ? W : H;
  const m = new DOMMatrix().translate(c.width / 2, c.height / 2).rotate(deg).translate(-W / 2, -H / 2);
  const ctx = c.getContext("2d");
  ctx.setTransform(m);
  ctx.drawImage(canvas, 0, 0);
  return { c, back: m.inverse() };
}

// { data, back, deg }: back riporta un punto della lettura scelta nell'immagine originale (null se 0 gradi)
export async function readOriented(canvas, recognize) {
  const first = await recognize(canvas);
  let best = { data: first, back: null, deg: 0, ...ocrScore(first) };
  if (best.mean >= 0.72 && best.score >= 40) return best;      // lettura gia' buona: nessun costo in piu'
  const tries = await Promise.all([90, 270, 180].map(async (deg) => {
    const { c, back } = rotated(canvas, deg);
    try { const data = await recognize(c); return { data, back, deg, ...ocrScore(data) }; }
    finally { c.width = c.height = 0; }
  }));
  for (const t of tries) if (t.score > best.score * 1.25) best = t;  // margine: nel dubbio resta com'e'
  return best;
}

// riquadro [x0, y0, x1, y1] della lettura ruotata nelle coordinate dell'immagine originale
export function boxBack(bbox, back) {
  if (!back) return [bbox.x0, bbox.y0, bbox.x1, bbox.y1];
  const pts = [[bbox.x0, bbox.y0], [bbox.x1, bbox.y0], [bbox.x0, bbox.y1], [bbox.x1, bbox.y1]]
    .map(([x, y]) => back.transformPoint(new DOMPoint(x, y)));
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

// parole della lettura raggruppate in righe visive (stessa altezza, da sinistra a destra), nel verso di
// lettura scelto. Tesseract su moduli e documenti d'identita' mette spesso etichetta e valore, o le parole
// di un indirizzo, in blocchi diversi: un indirizzo spezzato su tre righe non si riconosce piu'.
export function visualLines(data) {
  const words = data.words || (data.blocks || []).flatMap((b) => b.paragraphs.flatMap((p) => p.lines.flatMap((l) => l.words)));
  const rows = [];
  for (const w of [...words].sort((a, b) => (a.bbox.y0 + a.bbox.y1) - (b.bbox.y0 + b.bbox.y1))) {
    const mid = (w.bbox.y0 + w.bbox.y1) / 2, h = Math.max(1, w.bbox.y1 - w.bbox.y0);
    const last = rows[rows.length - 1];
    if (last) {
      const lmid = last.reduce((s, x) => s + (x.bbox.y0 + x.bbox.y1) / 2, 0) / last.length;
      const lh = last.reduce((s, x) => s + x.bbox.y1 - x.bbox.y0, 0) / last.length;
      if (Math.abs(mid - lmid) <= 0.5 * Math.max(h, lh)) { last.push(w); continue; }
    }
    rows.push([w]);
  }
  return rows.map((r) => r.sort((a, b) => a.bbox.x0 - b.bbox.x0));
}
