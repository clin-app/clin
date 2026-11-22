// Clin - motore dell'estensione (documento offscreen): lo stesso motore Python dell'app,
// eseguito con Pyodide. Riceve testi e file dalla pagina della chat tramite il service worker
// e restituisce il testo con i segnaposto. Nessuna connessione di rete.

let py = null, fs = null, pdfjs = null, tess = null, booting = null;

async function boot() {
  if (py) return;
  if (!booting) booting = (async () => {
    const { loadPyodide } = await import("./vendor/pyodide/pyodide.mjs");
    const pyodide = await loadPyodide({ indexURL: new URL("vendor/pyodide/", location.href).href });
    for (const f of ["anonymize_engine.py", "clin_text.py", "tabular_engine.py", "clin_ocr.py", "clin_llm.py", "clin_web.py"]) {
      pyodide.FS.writeFile(f, await (await fetch(`py/${f}`)).text());
    }
    pyodide.runPython("import sys; sys.path.insert(0, '.')");
    py = pyodide.pyimport("clin_web");
    fs = pyodide.FS;
  })();
  await booting;
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

async function ocr(data, type) {
  if (!tess) {
    await loadScript("vendor/tess/tesseract.min.js");
    const base = new URL("vendor/tess/", location.href).href;
    tess = await self.Tesseract.createWorker("ita", 1, {
      workerPath: base + "worker.min.js", corePath: base, langPath: base.replace(/\/$/, ""),
      workerBlobURL: false, gzip: true, cacheMethod: "none",
    });
  }
  const bitmap = await createImageBitmap(new Blob([data], { type }), { imageOrientation: "from-image" });
  const scale = Math.min(1, 2200 / Math.max(bitmap.width, bitmap.height));
  const canvas = new OffscreenCanvas(Math.round(bitmap.width * scale), Math.round(bitmap.height * scale));
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const { data: res } = await tess.recognize(await canvas.convertToBlob());
  return res.text || "";
}

async function anonymize(items, previous) {
  await boot();
  const bundle = [], tables = [], notes = [];
  let n = 0;
  const many = items.length > 1;
  for (const it of items) {
    n++;
    const title = it.kind === "testo incollato" ? "Testo incollato" : `Documento ${n} (${it.kind})`;
    if (it.text !== undefined) { bundle.push({ titolo: title, pagine: [it.text] }); continue; }
    const data = bytes(it.data);
    const ext = (it.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
    if (it.kind === "PDF") bundle.push({ titolo: title, pagine: await pdfPages(data) });
    else if (it.kind === "foto") { bundle.push({ titolo: title, pagine: [await ocr(data, it.type)] }); notes.push(`${title}: letto con OCR, da verificare.`); }
    else if (it.kind === "tabella") tables.push({ title, data, ext });
    else bundle.push({ titolo: title, pagine: [viaFS(data, ext, (p) => py.extract(p))] });
  }
  let mapping = { ...previous }, text = "";
  if (bundle.length) {
    const res = JSON.parse(py.run_bundle(JSON.stringify(bundle), 10, JSON.stringify(mapping)));
    text = res.text; mapping = { ...mapping, ...res.mapping }; notes.push(...(res.notes || []));
  }
  for (const t of tables) {
    const res = JSON.parse(viaFS(t.data, t.ext, (p) => py.run_file(p, 10, JSON.stringify(mapping))));
    text += (text ? "\n\n" : "") + (many ? `### ${t.title}\n` : "") + res.text;
    mapping = { ...mapping, ...res.mapping };
  }
  return { text, mapping, notes };
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.target !== "offscreen") return false;
  (async () => {
    try {
      if (msg.op === "anonymize") reply(await anonymize(msg.items, msg.previous || {}));
      else if (msg.op === "restore") { await boot(); reply({ text: py.restore(msg.text, JSON.stringify(msg.mapping || {})) }); }
      else reply({ error: "operazione sconosciuta" });
    } catch (err) {
      console.error(err);
      reply({ error: String(err.message || err) });
    }
  })();
  return true;
});

boot();  // il motore si prepara subito, cosi' la prima richiesta e' veloce
