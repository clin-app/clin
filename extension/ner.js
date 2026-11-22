// Clin - GLiNER nel browser: lo stesso modello del servizio locale su computer
// (urchade/gliner_multi_pii-v1, esportato in ONNX), eseguito con onnxruntime-web in WebAssembly.
// Trova i nomi e gli indirizzi senza etichetta ("Elira Shehu, 45enne, giunge in PS").
// Nessuna rete: modello, tokenizer e runtime sono dentro l'estensione.

const BASE = new URL("vendor/gliner/", location.href).href;
const LABELS = ["person", "address"];
const CHUNK = 1200, OVERLAP = 120;   // caratteri: il modello legge al massimo 384 token per volta
let model = null, loading = null, missing = false;

export async function available() {
  if (missing) return false;
  try { return (await fetch(BASE + "model/model.onnx", { method: "HEAD" })).ok; }
  catch (_) { missing = true; return false; }
}

async function load() {
  if (model) return model;
  if (!loading) loading = (async () => {
    const { Gliner } = await import("./vendor/gliner/gliner.mjs");
    const { env } = await import("./vendor/gliner/transformers.min.js");
    env.allowRemoteModels = false;      // il tokenizer si legge solo dall'estensione
    env.allowLocalModels = true;
    env.localModelPath = BASE;
    env.useBrowserCache = false;
    const ort = (await import("./vendor/gliner/ort.wasm.min.mjs")).default;
    ort.env.wasm.numThreads = 1;        // documento offscreen: senza SharedArrayBuffer
    ort.env.wasm.proxy = false;
    const g = new Gliner({
      tokenizerPath: "model",
      onnxSettings: { modelPath: BASE + "model/model.onnx", executionProvider: "wasm", wasmPaths: BASE, multiThread: false },
      transformersSettings: { allowLocalModels: true, useBrowserCache: false },
      maxWidth: 12,
    });
    await g.initialize();
    model = g;
    return g;
  })();
  try { return await loading; } catch (err) { loading = null; throw err; }
}

function chunks(text) {
  const out = [];
  for (let start = 0; start < text.length; ) {
    let end = Math.min(text.length, start + CHUNK);
    if (end < text.length) {  // si taglia su uno spazio, mai a meta' di una parola
      const cut = text.lastIndexOf(" ", end);
      if (cut > start + CHUNK / 2) end = cut;
    }
    out.push(text.slice(start, end));
    if (end >= text.length) break;
    start = Math.max(end - OVERLAP, start + 1);
  }
  return out;
}

// [(valore, "PERSONA" | "INDIRIZZO")] per tutti i testi; null se il modello non c'e'
export async function entities(texts) {
  if (!(await available())) return null;
  const g = await load();
  const found = new Map();
  const parts = texts.flatMap((t) => chunks(t)).filter((t) => t.trim().length >= 8);
  for (let i = 0; i < parts.length; i += 4) {
    const res = await g.inference({ texts: parts.slice(i, i + 4), entities: LABELS, flatNer: true, threshold: 0.5 });
    for (const list of res) for (const e of list) {
      const value = (e.spanText || "").trim();
      if (value) found.set(value + "|" + e.label, [value, e.label === "person" ? "PERSONA" : "INDIRIZZO"]);
    }
  }
  return [...found.values()];
}

export const ready = () => available().then((ok) => (ok ? load().then(() => true) : false));
