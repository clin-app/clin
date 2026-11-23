// Clin - GLiNER nel browser: lo stesso modello del servizio locale su computer
// (urchade/gliner_multi_pii-v1, esportato in ONNX), eseguito con onnxruntime-web in WebAssembly.
// Trova i nomi e gli indirizzi senza etichetta ("Elira Shehu, 45enne, giunge in PS").
// Se model.onnx e' incluso nell'estensione (build locale/GitHub) non fa alcuna richiesta di rete;
// nella build per il Chrome Web Store lo scarica una sola volta da GitHub Releases, ne verifica
// l'impronta SHA-256 e lo salva nella Cache API del browser per funzionare poi 100% offline.

const BASE = new URL("vendor/gliner/", location.href).href;
const CACHE_NAME = "clin-gliner-v1";
const REMOTE_URL = "https://github.com/clin-app/clin/releases/download/modello-gliner-v1/model.onnx";
const REMOTE_SHA256 = "559ae3e5c5303b008796a4543b315a66812c9458f4c8196bc91de291c2db716e";
const LABELS = ["person", "address"];
const CHUNK = 1200, OVERLAP = 120;   // caratteri: il modello legge al massimo 384 token per volta

let model = null, loading = null, localOk = null, tokenizerOk = null;
let downloading = null, downloadProgress = 0, downloadError = "";

async function hasLocalModel() {
  if (localOk !== null) return localOk;
  try { localOk = (await fetch(BASE + "model/model.onnx", { method: "HEAD" })).ok; }
  catch (_) { localOk = false; }
  return localOk;
}

async function hasTokenizer() {
  if (tokenizerOk !== null) return tokenizerOk;
  try { tokenizerOk = (await fetch(BASE + "model/tokenizer.json", { method: "HEAD" })).ok; }
  catch (_) { tokenizerOk = false; }
  return tokenizerOk;
}

async function getCachedResponse() {
  if (typeof caches === "undefined") return null;
  try {
    const cache = await caches.open(CACHE_NAME);
    return (await cache.match(REMOTE_URL)) || null;
  } catch (_) {
    return null;
  }
}

async function sha256Hex(buffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

function startDownload() {
  if (downloading) return downloading;
  downloadProgress = 0;
  downloadError = "";
  downloading = (async () => {
    try {
      const resp = await fetch(REMOTE_URL, { credentials: "omit", cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status} scaricando model.onnx`);
      const total = Number(resp.headers.get("content-length")) || 0;
      let bytes;
      if (resp.body && total > 0) {
        bytes = new Uint8Array(total);
        const reader = resp.body.getReader();
        let received = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (received + value.length > bytes.length) {
            const grown = new Uint8Array(received + value.length);
            grown.set(bytes.subarray(0, received));
            bytes = grown;
          }
          bytes.set(value, received);
          received += value.length;
          downloadProgress = Math.min(99, Math.round((received / total) * 100));
        }
        if (received < bytes.length) bytes = bytes.subarray(0, received);
      } else {
        bytes = new Uint8Array(await resp.arrayBuffer());
        downloadProgress = 99;
      }
      const actual = await sha256Hex(bytes);
      if (actual !== REMOTE_SHA256) {
        throw new Error(`Impronta SHA-256 non valida per model.onnx (${actual})`);
      }
      if (typeof caches !== "undefined") {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(REMOTE_URL, new Response(bytes, {
          headers: { "Content-Type": "application/octet-stream", "Content-Length": String(bytes.byteLength) },
        }));
      }
      downloadProgress = 100;
      return bytes;
    } catch (err) {
      downloadError = String(err.message || err);
      console.error("[Clin GLiNER download]", err);
      throw err;
    } finally {
      downloading = null;
    }
  })();
  return downloading;
}

export function status() {
  if (model) return { state: "ready", progress: 100 };
  if (downloading) return { state: "downloading", progress: downloadProgress };
  if (loading) return { state: "loading", progress: 0 };
  if (downloadError) return { state: "error", progress: 0, error: downloadError };
  return { state: "missing", progress: 0 };
}

export async function available() {
  if (model) return true;
  if (await hasLocalModel()) return true;
  if (!(await hasTokenizer())) return false;
  return Boolean(await getCachedResponse());
}

async function resolveModelSource(preloadedBytes = null) {
  if (await hasLocalModel()) return BASE + "model/model.onnx";
  if (preloadedBytes) return preloadedBytes;
  const cached = await getCachedResponse();
  if (cached) return new Uint8Array(await cached.arrayBuffer());
  return null;
}

async function load(preloadedBytes = null) {
  if (model) return model;
  if (!loading) loading = (async () => {
    const modelSource = await resolveModelSource(preloadedBytes);
    if (!modelSource) throw new Error("model.onnx non disponibile");
    const { Gliner } = await import("./vendor/gliner/gliner.mjs");
    const { env } = await import("./vendor/gliner/transformers.min.js");
    env.allowRemoteModels = false;      // il tokenizer si legge solo dall'estensione
    env.allowLocalModels = true;
    env.localModelPath = BASE;
    env.useBrowserCache = false;
    const ort = (await import("./vendor/gliner/ort.wasm.min.mjs")).default;
    // piu' thread solo se il documento e' isolato (COOP/COEP nel manifest): altrimenti niente SharedArrayBuffer
    const threads = self.crossOriginIsolated ? Math.max(1, Math.min(4, (navigator.hardwareConcurrency || 2) - 1)) : 1;
    ort.env.wasm.numThreads = threads;
    ort.env.wasm.proxy = false;
    const g = new Gliner({
      tokenizerPath: "model",
      onnxSettings: { modelPath: modelSource, executionProvider: "wasm", wasmPaths: BASE, multiThread: false },
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

// parole tutte minuscole o tutte maiuscole con l'iniziale maiuscola ("paola de santis", "ГЛЕБ ЗАЙЦЕВ"):
// GLiNER le riconosce come nomi solo cosi'. Stessa lunghezza del testo, come clin_llm.case_normalized
const WORD = /[\p{L}]+(?:['’\-][\p{L}]+)*/gu;
function caseNormalized(text) {
  return text.replace(WORD, (w) => {
    if (w.length < 2 || !(w === w.toLowerCase() || w === w.toUpperCase())) return w;
    const c = w[0].toUpperCase() + w.slice(1).toLowerCase();
    return c.length === w.length ? c : w;
  });
}

// risultati per brano gia' analizzato: la revisione rielabora lo stesso documento a ogni spunta,
// e il modello e' la parte piu' lenta. Chiave: il brano; valore: Map("valore|etichetta" -> [valore, tipo])
const memo = new Map();
const MEMO_MAX = 1500;

// sink[i]: Map in cui finiscono le entita' del brano parts[i]
async function run(g, parts, sink, original) {
  for (let i = 0; i < parts.length; i += 4) {
    const batch = parts.slice(i, i + 4);
    const res = await g.inference({ texts: batch, entities: LABELS, flatNer: true, threshold: 0.5 });
    res.forEach((list, k) => {
      for (const e of list) {
        const value = (e.spanText || "").trim();
        if (!value) continue;
        const kind = e.label === "person" ? "PERSONA" : "INDIRIZZO";
        if (original) {  // dal testo normalizzato si torna a tutte le forme scritte nel documento
          const src = original[i + k], norm = batch[k];
          let from = 0;
          while (true) {
            const at = norm.indexOf(value, from);
            if (at < 0) break;
            const raw = src.slice(at, at + value.length);
            if (raw) sink[i + k].set(raw + "|" + e.label, [raw, kind]);
            from = at + Math.max(1, value.length);
          }
        } else {
          sink[i + k].set(value + "|" + e.label, [value, kind]);
        }
      }
    });
  }
}

// [(valore, "PERSONA" | "INDIRIZZO")] per tutti i testi; null se il modello non e' ancora pronto
export async function entities(texts) {
  if (!(await available())) {
    if (await hasTokenizer()) {
      startDownload().then((bytes) => load(bytes)).catch(() => {});
    }
    return null;
  }
  const g = await load();
  const parts = [...new Set(texts.flatMap((t) => chunks(t)).filter((t) => t.trim().length >= 8))];
  const fresh = parts.filter((p) => !memo.has(p));
  if (fresh.length) {
    const sink = fresh.map(() => new Map());
    await run(g, fresh, sink, null);
    const norm = fresh.map(caseNormalized);
    const changed = norm.map((t, i) => (t !== fresh[i] ? i : -1)).filter((i) => i >= 0);
    if (changed.length) await run(g, changed.map((i) => norm[i]), changed.map((i) => sink[i]), changed.map((i) => fresh[i]));
    if (memo.size + fresh.length > MEMO_MAX) memo.clear();
    fresh.forEach((p, i) => memo.set(p, sink[i]));
  }
  const found = new Map();
  for (const p of parts) for (const [k, v] of memo.get(p) || []) found.set(k, v);
  return [...found.values()];
}

export async function ready() {
  if (await available()) {
    await load();
    return true;
  }
  if (await hasTokenizer()) {
    const bytes = await startDownload();
    await load(bytes);
    return true;
  }
  return false;
}
