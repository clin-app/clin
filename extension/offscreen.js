// Clin - motore dell'estensione (documento offscreen): lo stesso motore Python dell'app,
// eseguito con Pyodide. Riceve testi e file dalla pagina della chat tramite il service worker
// e restituisce il testo con i segnaposto. Nessuna connessione di rete.

let py = null, fs = null, pdfjs = null, booting = null, step = "", activeTabId = null, nerMod = null;

function report(msg, pct) {
  step = msg;
  if (!activeTabId) return;
  try {
    chrome.runtime.sendMessage({ target: "background", op: "progress", tabId: activeTabId, step: msg, pct }).catch(() => {});
  } catch (_) {}
}

async function boot() {
  if (py) return;
  report("Avvio del motore locale…", 10);
  if (!booting) booting = (async () => {
    const { loadPyodide } = await import("./vendor/pyodide/pyodide.mjs");
    const pyodide = await loadPyodide({ indexURL: new URL("vendor/pyodide/", location.href).href });
    for (const f of ["anonymize_engine.py", "clin_text.py", "tabular_engine.py", "clin_ocr.py", "clin_llm.py", "clin_lingue.py", "clin_web.py"]) {
      pyodide.FS.writeFile(f, await (await fetch(`py/${f}`)).text());
    }
    pyodide.runPython("import sys; sys.path.insert(0, '.')");
    py = pyodide.pyimport("clin_web");
    fs = pyodide.FS;
    self.__pyodide = pyodide;
  })();
  await booting;
}

// GLiNER nel browser (ner.js): i nomi senza etichetta trovati dal modello passano al motore Python,
// che li verifica (compaiono nel testo, non sono eponimi ne' termini clinici) come sul computer
let nerNote = "";
async function withNer(texts) {
  try {
    report("Analisi nomi con modello GLiNER locale…", 62);
    const ner = nerMod || (nerMod = await import("./ner.js"));
    const found = await ner.entities(texts.filter(Boolean));
    py.set_ner(found ? JSON.stringify(found) : "");
    if (found) {
      nerNote = "";
    } else {
      const st = ner.status ? ner.status() : { state: "missing", progress: 0 };
      if (st.state === "downloading") {
        nerNote = `Download una tantum del modello GLiNER in corso (${st.progress}%): intanto anonimizzazione attiva con le regole locali.`;
      } else {
        nerNote = "Modello GLiNER non ancora pronto: nomi senza etichetta riconosciuti solo dal contesto.";
      }
    }
  } catch (err) {
    console.error(err);
    py.set_ner("");
    nerNote = "GLiNER non disponibile in questo momento: nomi senza etichetta riconosciuti solo dal contesto.";
  }
}

const bytes = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));

async function pdfPages(data) {
  if (!pdfjs) {
    pdfjs = await import("./vendor/pdfjs/pdf.min.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "vendor/pdfjs/pdf.worker.min.mjs";
  }
  const doc = await pdfjs.getDocument({ data, isEvalSupported: false }).promise;
  const pages = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const content = await (await doc.getPage(i)).getTextContent();
    pages.push(content.items.map((it) => it.str + (it.hasEOL ? "\n" : " ")).join(""));
  }
  await doc.destroy();
  return pages;
}

function viaFS(data, ext, fn) {
  const path = "/tmp/documento" + ext;  // il nome originale del file non viene usato
  fs.writeFile(path, data);
  try { return fn(path); } finally { fs.unlink(path); }
}

function loadScript(src) {
  return new Promise((ok, ko) => {
    const s = document.createElement("script");
    s.src = src; s.onload = ok; s.onerror = () => ko(new Error("script " + src));
    document.head.appendChild(s);
  });
}

// OCR: fino a OCR_MAX worker Tesseract in parallelo (le pagine scansionate di un PDF si leggono insieme).
// Il primo nasce al primo uso, gli altri solo quando ci sono piu' pagine in attesa che worker.
const OCR_MAX = Math.max(1, Math.min(3, Math.floor((navigator.hardwareConcurrency || 2) / 2)));
let tessSched = null, tessBoot = null, tessWorkers = 0, tessPending = 0, tessGrowing = null;

async function addOcrWorker() {
  const base = new URL("vendor/tess/", location.href).href;
  const w = await self.Tesseract.createWorker("ita", 1, {
    workerPath: base + "worker.min.js", corePath: base, langPath: base.replace(/\/$/, ""),
    workerBlobURL: false, gzip: true, cacheMethod: "none",
  });
  tessSched.addWorker(w);
  tessWorkers++;
}

async function recognize(image) {
  await (tessBoot || (tessBoot = (async () => {
    await loadScript("vendor/tess/tesseract.min.js");
    tessSched = self.Tesseract.createScheduler();
    await addOcrWorker();
  })()));
  tessPending++;
  if (tessPending > tessWorkers && tessWorkers < OCR_MAX && !tessGrowing) {
    tessGrowing = addOcrWorker().catch((err) => console.error(err)).finally(() => { tessGrowing = null; });
  }
  try { return (await tessSched.addJob("recognize", image)).data; }
  finally { tessPending--; }
}

async function ocr(data, type) {
  const bitmap = await createImageBitmap(new Blob([data], { type }), { imageOrientation: "from-image" });
  const scale = Math.min(1, 2200 / Math.max(bitmap.width, bitmap.height));
  const canvas = new OffscreenCanvas(Math.round(bitmap.width * scale), Math.round(bitmap.height * scale));
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return (await recognize(await canvas.convertToBlob())).text || "";
}

async function anonymize(items, previous) {
  await boot();
  report("Lettura del contenuto…", 22);
  const bundle = [], tables = [], notes = [];
  let n = 0;
  const many = items.length > 1;
  for (const it of items) {
    n++;
    const title = it.kind === "testo incollato" ? "Testo incollato" : `Documento ${n} (${it.kind})`;
    if (it.text !== undefined) { bundle.push({ titolo: title, pagine: [it.text] }); continue; }
    const data = it.bytes;
    const ext = (it.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
    // testo estratto una volta per revisione: a ogni spunta cambia solo la copertura
    if (it.kind === "PDF") bundle.push({ titolo: title, pagine: it.pages || (it.pages = await pdfPages(data.slice())) });
    else if (it.kind === "foto") { bundle.push({ titolo: title, pagine: [it.ocrText ?? (it.ocrText = await ocr(data, it.type))], ocr: true }); notes.push(`${title}: letto con OCR, da verificare.`); }
    else if (it.kind === "tabella") tables.push({ title, data, ext });
    else bundle.push({ titolo: title, pagine: [viaFS(data, ext, (p) => py.extract(p))] });
  }
  let mapping = { ...previous }, text = "";
  try {
    await withNer(bundle.flatMap((b) => b.pagine).concat(tables.map((t) => viaFS(t.data, t.ext, (p) => py.table_text(p)))));
    report("Applicazione segnaposto…", 84);
    if (nerNote) notes.push(nerNote);
    if (bundle.length) {
      const res = JSON.parse(py.run_bundle(JSON.stringify(bundle), 10, JSON.stringify(mapping)));
      text = res.text; mapping = { ...mapping, ...res.mapping }; notes.push(...(res.notes || []));
    }
    for (const t of tables) {
      const res = JSON.parse(viaFS(t.data, t.ext, (p) => py.run_file(p, 10, JSON.stringify(mapping))));
      text += (text ? "\n\n" : "") + (many ? `### ${t.title}\n` : "") + res.text;
      mapping = { ...mapping, ...res.mapping };
    }
  } finally {
    py.set_ner("");
  }
  return { text, mapping, notes };
}

// ------------------------------------------------------------------ file con i dati coperti
// L'IA riceve il documento stesso (PDF, foto, Word, Excel, CSV), con ogni dato personale coperto
// da un riquadro che riporta il segnaposto. I PDF hanno anche un livello di testo invisibile,
// gia' anonimizzato, che i modelli leggono come il testo di un PDF qualsiasi.

const SCALE = 2;  // risoluzione delle pagine ridisegnate (144 dpi)
let wheels = false;

async function excelReady() {
  if (wheels) return;
  const base = new URL("vendor/wheels/", location.href).href;
  await self.__pyodide.loadPackage([base + "et_xmlfile-2.0.0-py3-none-any.whl", base + "openpyxl-3.1.5-py2.py3-none-any.whl"]);
  wheels = true;
}

// segmenti di testo di una pagina: { str, box: [x0, y0, x1, y1] in pixel della tela }
async function pdfSegments(page, viewport) {
  const content = await page.getTextContent();
  const segs = [];
  for (const it of content.items) {
    if (!it.str) { if (it.hasEOL && segs.length) segs[segs.length - 1].eol = true; continue; }
    const [a, b, c, d, e, f] = it.transform;
    const h = it.height || Math.hypot(c, d);
    const vertPdf = Math.abs(b) > Math.abs(a);
    const pdfRect = vertPdf
      ? [e - h * 0.9, f, e + h * 0.25, f + (b >= 0 ? 1 : -1) * it.width]
      : [e, f - h * 0.22, e + (a >= 0 ? 1 : -1) * it.width, f + h * 0.9];
    const r = viewport.convertToViewportRectangle(pdfRect);
    const box = [Math.min(r[0], r[2]), Math.min(r[1], r[3]), Math.max(r[0], r[2]), Math.max(r[1], r[3])];
    segs.push({ str: it.str, box, vertical: (box[3] - box[1]) > (box[2] - box[0]) * 1.5 && it.str.length > 1, eol: it.hasEOL });
  }
  return segs;
}

async function ocrSegments(canvas) {
  const data = await recognize(canvas);
  const segs = [];
  for (const block of data.blocks || []) for (const para of block.paragraphs || []) for (const line of para.lines || []) {
    line.words.forEach((w, i) => segs.push({ str: w.text, box: [w.bbox.x0, w.bbox.y0, w.bbox.x1, w.bbox.y1], eol: i === line.words.length - 1 }));
  }
  return segs;
}

function joinSegs(segs) {
  let text = "", cp = 0;
  for (const sg of segs) {
    sg.chars = Array.from(sg.str);
    sg.start = cp;
    text += sg.str;
    cp += sg.chars.length;
    sg.end = cp;
    text += sg.eol ? "\n" : " ";
    cp += 1;
  }
  return text;
}

// copre gli intervalli sulla tela e calcola il testo anonimizzato di ogni segmento
function cover(ctx, segs, spans) {
  // posizione di un carattere (indice code-point) nel segmento: larghezze misurate
  const xAt = (sg, k) => {
    const chars = sg.chars || Array.from(sg.str);
    const w = sg.box[2] - sg.box[0];
    if (k <= 0) return sg.box[0];
    if (k >= chars.length) return sg.box[2];
    ctx.font = `${Math.max(8, sg.box[3] - sg.box[1])}px Helvetica, Arial, sans-serif`;
    const full = ctx.measureText(sg.str).width || 1;
    return sg.box[0] + w * ctx.measureText(chars.slice(0, k).join("")).width / full;
  };
  for (const [s, e, ph] of spans) {
    // rettangoli del dato, uniti riga per riga
    const lines = [];
    for (const sg of segs) {
      if (sg.end <= s || sg.start >= e) continue;
      const chars = sg.chars || Array.from(sg.str);
      const a = Math.max(s, sg.start) - sg.start, b = Math.min(e, sg.end) - sg.start;
      let r;
      if (sg.vertical) {
        const w = sg.box[2] - sg.box[0], totalH = sg.box[3] - sg.box[1], slack = w * 0.2;
        const y0 = sg.box[1] + totalH * (a / Math.max(1, chars.length)) - slack;
        const y1 = sg.box[1] + totalH * (b / Math.max(1, chars.length)) + slack;
        r = [sg.box[0] - 2, Math.min(y0, y1), sg.box[2] + 2, Math.max(y0, y1)];
        lines.push(r);
      } else {
        const h = sg.box[3] - sg.box[1], slack = h * 0.18;  // margine: nessuna lettera deve restare visibile
        r = [xAt(sg, a) - slack, sg.box[1] - 2, xAt(sg, b) + slack, sg.box[3] + 2];
        const line = lines.find((l) => Math.abs((l[1] + l[3]) / 2 - (r[1] + r[3]) / 2) < h * 0.6);
        if (line) { line[0] = Math.min(line[0], r[0]); line[1] = Math.min(line[1], r[1]); line[2] = Math.max(line[2], r[2]); line[3] = Math.max(line[3], r[3]); }
        else lines.push(r);
      }
      sg.out = sg.out ?? chars.slice();
      for (let k = a; k < b; k++) sg.out[k] = "";
      if (s >= sg.start) sg.out[a] = ph;  // testo del livello invisibile: il segnaposto al posto del dato
    }
    lines.forEach((r, i) => {
      const [x0, y0, x1, y1] = r, h = y1 - y0;
      const vertBox = h > (x1 - x0) * 1.8;
      if (vertBox) {
        ctx.fillStyle = "#101411";
        ctx.fillRect(x0, y0, x1 - x0, h);
        return;
      }
      let size = Math.min(h * 0.72, 30);
      ctx.font = `700 ${size}px Helvetica, Arial, sans-serif`;
      let tw = ctx.measureText(ph).width;
      if (i === 0 && tw > x1 - x0 - 4) {  // si riduce fino a 9 px, poi il riquadro si allarga quanto serve
        size = Math.max(9, size * (x1 - x0 - 4) / tw);
        ctx.font = `700 ${size}px Helvetica, Arial, sans-serif`;
        tw = ctx.measureText(ph).width;
      }
      const right = i === 0 ? Math.max(x1, x0 + tw + 6) : x1;
      ctx.fillStyle = "#101411";
      ctx.fillRect(x0, y0, right - x0, h);
      if (i === 0) {  // il segnaposto, leggibile anche dai modelli che guardano l'immagine
        ctx.fillStyle = "#d4f06b";
        ctx.textBaseline = "middle";
        ctx.fillText(ph, x0 + 3, (y0 + y1) / 2);
      }
    });
  }
  for (const sg of segs) sg.anon = sg.out ? sg.out.join("") : sg.str;
}

// ---- PDF minimo: pagine come immagini JPEG + testo invisibile (Helvetica, WinAnsi)
const CP1252 = { 0x20AC: 0x80, 0x201A: 0x82, 0x201E: 0x84, 0x2026: 0x85, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97 };
function pdfString(str) {
  let out = "";
  for (const ch of str) {
    let c = ch.codePointAt(0);
    c = CP1252[c] ?? (c < 256 ? c : 0x3F);
    out += c === 0x28 || c === 0x29 || c === 0x5C ? "\\" + String.fromCharCode(c) : c < 32 || c > 126 ? "\\" + c.toString(8).padStart(3, "0") : String.fromCharCode(c);
  }
  return "(" + out + ")";
}
function buildPdf(pages) {
  const enc = new TextEncoder(), chunks = [], offsets = [];
  let pos = 0;
  const push = (x) => { const b = typeof x === "string" ? enc.encode(x) : x; chunks.push(b); pos += b.length; };
  const obj = (n, body, stream) => {
    offsets[n] = pos;
    push(`${n} 0 obj\n${body}\n`);
    if (stream) { push("stream\n"); push(stream); push("\nendstream\n"); }
    push("endobj\n");
  };
  push("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
  const n = pages.length, kids = pages.map((_, i) => `${4 + i * 3} 0 R`).join(" ");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, `<< /Type /Pages /Kids [${kids}] /Count ${n} >>`);
  obj(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  pages.forEach((p, i) => {
    const pn = 4 + i * 3;
    let text = "BT 3 Tr\n";
    for (const t of p.texts) {
      if (!t.str.trim()) continue;
      text += `/F1 ${t.size.toFixed(2)} Tf 1 0 0 1 ${t.x.toFixed(2)} ${t.y.toFixed(2)} Tm ${pdfString(t.str)} Tj\n`;
    }
    text += "ET\n";
    const content = enc.encode(`q ${p.w.toFixed(2)} 0 0 ${p.h.toFixed(2)} 0 0 cm /Im0 Do Q\n` + text);
    obj(pn, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${p.w.toFixed(2)} ${p.h.toFixed(2)}] /Resources << /Font << /F1 3 0 R >> /XObject << /Im0 ${pn + 1} 0 R >> >> /Contents ${pn + 2} 0 R >>`);
    obj(pn + 1, `<< /Type /XObject /Subtype /Image /Width ${p.iw} /Height ${p.ih} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${p.jpeg.length} >>`, p.jpeg);
    obj(pn + 2, `<< /Length ${content.length} >>`, content);
  });
  const xref = pos, total = 4 + n * 3;
  let x = `xref\n0 ${total}\n0000000000 65535 f \n`;
  for (let i = 1; i < total; i++) x += String(offsets[i]).padStart(10, "0") + " 00000 n \n";
  push(x + `trailer\n<< /Size ${total} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  const out = new Uint8Array(pos);
  let o = 0;
  for (const c of chunks) { out.set(c, o); o += c.length; }
  return out;
}

const jpegOf = async (canvas, q = 0.88) => new Uint8Array(await (await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", q))).arrayBuffer());

function previewDataUrl(canvas) {
  const maxW = 1100;
  if (canvas.width <= maxW) return canvas.toDataURL("image/jpeg", 0.78);
  const scale = maxW / canvas.width;
  const c = document.createElement("canvas");
  c.width = Math.round(canvas.width * scale);
  c.height = Math.round(canvas.height * scale);
  c.getContext("2d").drawImage(canvas, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.78);
}

// Pagine lette (tela pulita + segmenti di testo) conservate per la durata della revisione, fino a
// CACHE_PAGES pagine: togliere una spunta ricalcola solo la copertura, non rilegge il documento.
const CACHE_PAGES = 24;

function copyCanvas(src) {
  const c = document.createElement("canvas");
  c.width = src.width; c.height = src.height;
  c.getContext("2d").drawImage(src, 0, 0);
  return c;
}

async function readPdf(data) {
  if (!pdfjs) {
    pdfjs = await import("./vendor/pdfjs/pdf.min.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "vendor/pdfjs/pdf.worker.min.mjs";
  }
  const doc = await pdfjs.getDocument({ data: data.slice(), isEvalSupported: false }).promise;
  const pages = [], scans = [];
  let read = 0;
  for (let i = 1; i <= doc.numPages; i++) {
    report(`Lettura PDF (pagina ${i} di ${doc.numPages})…`, 18 + Math.round(((i - 1) / Math.max(1, doc.numPages)) * 38));
    const page = await doc.getPage(i);
    const vp1 = page.getViewport({ scale: 1 }), vp = page.getViewport({ scale: SCALE });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(vp.width); canvas.height = Math.ceil(vp.height);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    step = "render " + i;
    // "print": niente requestAnimationFrame, che nei documenti nascosti non scatta mai
    await page.render({ canvasContext: ctx, viewport: vp, intent: "print" }).promise;
    step = "testo " + i;
    const p = { canvas, segs: await pdfSegments(page, vp), w: vp1.width, h: vp1.height, ocrUsed: false };
    if (!p.segs.some((s) => s.str.trim())) {  // scansione: OCR in parallelo, mentre si leggono le altre pagine
      p.ocrUsed = true;
      scans.push(ocrSegments(canvas).then((segs) => {
        p.segs = segs;
        report(`OCR delle pagine scansionate (${++read} di ${scans.length})…`, 58);
      }));
    }
    pages.push(p);
  }
  await Promise.all(scans);
  await doc.destroy();
  for (const p of pages) p.text = joinSegs(p.segs);
  return pages;
}

async function redactPdf(data, state, slot) {
  const pages = slot.pdf || await readPdf(data);
  const keep = pages.length <= CACHE_PAGES;
  if (keep) slot.pdf = pages;
  await withNer(pages.map((p) => p.text));
  report("Copertura dati sensibili nel PDF…", 80);
  const plan = JSON.parse(py.plan_pages(
    JSON.stringify(pages.map((p) => p.text)),
    JSON.stringify(state.map),
    JSON.stringify(pages.map((p) => p.ocrUsed)),
  ));
  state.map = { ...state.map, ...plan.mapping };
  report("Creazione PDF protetto…", 92);
  const out = [], previews = [];
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    const canvas = keep ? copyCanvas(p.canvas) : p.canvas;  // la tela pulita resta per la prossima spunta
    for (const sg of p.segs) sg.out = undefined;
    cover(canvas.getContext("2d"), p.segs, plan.spans[i]);
    const texts = p.segs.map((sg) => {
      const hpx = sg.box[3] - sg.box[1];
      return { str: sg.anon, x: sg.box[0] / SCALE, y: p.h - sg.box[3] / SCALE + hpx * 0.2 / SCALE, size: Math.max(4, hpx * 0.8 / SCALE) };
    });
    previews.push(previewDataUrl(canvas));
    out.push({ w: p.w, h: p.h, iw: canvas.width, ih: canvas.height, jpeg: await jpegOf(canvas), texts });
    canvas.width = canvas.height = 0;  // libera subito la memoria della copia
  }
  return { bytes: buildPdf(out), ocr: pages.some((p) => p.ocrUsed), previews };
}

async function redactImage(data, type, state, slot) {
  if (!slot.img) {
    report("Lettura testo dalla foto (OCR)…", 32);
    const bitmap = await createImageBitmap(new Blob([data], { type }), { imageOrientation: "from-image" });
    const scale = Math.min(1, 2400 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);  // ridisegnata: niente EXIF (posizione, data, dispositivo)
    bitmap.close();
    const segs = await ocrSegments(canvas);
    slot.img = { canvas, segs, text: joinSegs(segs) };
  }
  const { segs, text } = slot.img;
  const canvas = copyCanvas(slot.img.canvas);
  await withNer([text]);
  const plan = JSON.parse(py.plan_pages(JSON.stringify([text]), JSON.stringify(state.map), JSON.stringify([true])));
  state.map = { ...state.map, ...plan.mapping };
  for (const sg of segs) sg.out = undefined;
  cover(canvas.getContext("2d"), segs, plan.spans[0]);
  return { bytes: await jpegOf(canvas), previews: [previewDataUrl(canvas)] };
}

function viaFSout(data, ext, fn) {
  const inp = "/tmp/in" + ext, out = "/tmp/out" + ext;
  fs.writeFile(inp, data);
  try { const r = fn(inp, out); return { r, bytes: fs.readFile(out) }; }
  finally { for (const f of [inp, out]) try { fs.unlink(f); } catch (_) {} }
}

const b64of = (u8) => { let s = ""; for (let i = 0; i < u8.length; i += 0x2000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x2000)); return btoa(s); };

async function redact(items, state) {
  await boot();
  const files = [], notes = [];
  try {
    for (const it of items) {
      const data = it.bytes, slot = it.slot || (it.slot = {});
      const dot = it.name.lastIndexOf(".");
      const stem = dot > 0 ? it.name.slice(0, dot) : it.name, ext = dot > 0 ? it.name.slice(dot).toLowerCase() : "";
      let out, type = it.type || "application/octet-stream", outExt = ext, pages = [], previewText = "";
      if (it.kind === "PDF") {
        const r = await redactPdf(data, state, slot);
        out = r.bytes; type = "application/pdf"; pages = r.previews || [];
        if (r.ocr) notes.push(`${it.name}: pagine scansionate lette con OCR, verificare.`);
      } else if (it.kind === "foto") {
        const r = await redactImage(data, it.type, state, slot);
        out = r.bytes; type = "image/jpeg"; outExt = ".jpg"; pages = r.previews || [];
        notes.push(`${it.name}: letta con OCR, verificare.`);
      } else if (it.kind === "Word") {
        await withNer([viaFS(data, ext, (p) => py.extract(p))]);
        const { r, bytes: b } = viaFSout(data, ext, (i, o) => py.redact_docx(i, o, JSON.stringify(state.map)));
        state.map = { ...state.map, ...JSON.parse(r).mapping }; out = b;
        try { previewText = viaFS(b, ext, (p) => py.extract(p)).slice(0, 12000); } catch (_) {}
      } else if (it.kind === "tabella" || it.kind === "Excel") {
        if (it.kind === "Excel") await excelReady();
        await withNer([viaFS(data, ext, (p) => py.table_text(p))]);
        const { r, bytes: b } = viaFSout(data, ext, (i, o) => py.redact_table(i, o, JSON.stringify(state.book || {}), JSON.stringify(state.map)));
        const res = JSON.parse(r);
        state.book = res.book; state.map = { ...state.map, ...res.mapping }; out = b;
        try { previewText = viaFS(b, ext, (p) => py.table_text(p)).slice(0, 12000); } catch (_) {}
      } else {  // testo semplice: stesso file, con i segnaposto
        const text = new TextDecoder().decode(data);
        await withNer([text]);
        const res = JSON.parse(py.run_bundle(JSON.stringify([{ titolo: "", pagine: [text] }]), 10, JSON.stringify(state.map)));
        state.map = { ...state.map, ...res.mapping }; out = new TextEncoder().encode(res.text);
        previewText = (res.text || "").slice(0, 12000);
      }
      if (nerNote && !notes.includes(nerNote)) notes.push(nerNote);
      const name = py.safe_name(stem, JSON.stringify(state.map)) + outExt;
      files.push({ name, type, data: b64of(out), pages, previewText });
    }
  } finally {
    py.set_ner("");
  }
  return { files, mapping: state.map, book: state.book || {}, notes };
}

let job = null;  // revisione in corso: { id, items } con i file gia' decodificati e le pagine lette

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.target !== "offscreen") return false;
  (async () => {
    try {
      if (msg.op === "anonymize" || msg.op === "redact") {
        // scelte del pannello di revisione: valori lasciati in chiaro e parole da coprire in piu'
        // i file arrivano una volta sola per revisione (job): le spunte successive mandano solo le scelte
        let items;
        if (msg.items) {
          items = msg.items.map((it) => (it.data === undefined ? it : { ...it, data: undefined, bytes: bytes(it.data) }));
          job = msg.job ? { id: msg.job, items } : null;
        } else if (job && job.id === msg.job) {
          items = job.items;
        } else {
          reply({ error: "job-missing" });
          return;
        }
        activeTabId = msg.tabId || null;
        await boot();
        const rv = msg.review || {};
        py.review(JSON.stringify(rv.keep || []), JSON.stringify(rv.add || []));
        try {
          const res = msg.op === "anonymize"
            ? await anonymize(items, msg.previous || {})
            : await redact(items, { map: msg.previous || {}, book: msg.book || {} });
          res.found = JSON.parse(py.review_found());
          report("Pronto.", 100);
          reply(res);
        } finally {
          py.review_end();
          activeTabId = null;
        }
      }
      else if (msg.op === "release") { if (job && job.id === msg.job) job = null; reply({}); }
      else if (msg.op === "state") reply({ engine: Boolean(py), ner: nerMod ? nerMod.status() : { state: "loading", progress: 0 }, threads: self.crossOriginIsolated });
      else if (msg.op === "debug") reply({ step });
      else if (msg.op === "restore") { await boot(); reply({ text: py.restore(msg.text, JSON.stringify(msg.mapping || {})) }); }
      else reply({ error: "operazione sconosciuta" });
    } catch (err) {
      console.error(err);
      reply({ error: String(err.message || err) });
    }
  })();
  return true;
});

boot().then(() => import("./ner.js")).then((ner) => (nerMod = ner).ready()).catch((err) => console.error(err));  // motore e modello pronti subito
