// Clin - service worker dell'estensione.
// Tiene la tabella dei segnaposto in chrome.storage.session (solo in memoria, cancellata
// alla chiusura del browser, invisibile ai siti) e inoltra il lavoro al documento offscreen,
// dove gira il motore (Pyodide + GLiNER). Mantiene vivo il service worker durante le
// elaborazioni lunghe (PDF/OCR) e inoltra lo stato di avanzamento alla scheda.

const MAP_KEY = "map";

async function ensureEngine() {
  if (await chrome.offscreen.hasDocument()) return;
  try {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["WORKERS"],
      justification: "Motore di anonimizzazione locale (Python/WebAssembly)",
    });
  } catch (err) {
    if (!String(err).includes("single offscreen")) throw err;  // gia' in creazione
  }
}

async function getMap() {
  return (await chrome.storage.session.get(MAP_KEY))[MAP_KEY] || {};
}

async function engine(op, payload) {
  await ensureEngine();
  // In Manifest V3 il service worker puo' essere sospeso dopo ~30s di attesa:
  // un ping periodico all'API Chrome lo mantiene attivo finche' offscreen non risponde.
  const keepAlive = setInterval(() => {
    try { chrome.runtime.getPlatformInfo(() => {}); } catch (_) {}
  }, 15000);
  try {
    for (let i = 0; i < 6; i++) {  // il documento appena creato puo' non ascoltare ancora
      const res = await chrome.runtime.sendMessage({ target: "offscreen", op, ...payload }).catch(() => null);
      if (res) return res;
      await new Promise((r) => setTimeout(r, 350));
    }
    throw new Error("motore non disponibile");
  } finally {
    clearInterval(keepAlive);
  }
}

let queue = Promise.resolve();
function serialized(fn) {
  const next = queue.then(fn, fn);
  queue = next.catch(() => {});
  return next;
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!msg || msg.target !== "background" || sender.id !== chrome.runtime.id) return false;
  if (msg.op === "progress") {
    if (msg.tabId) {
      chrome.tabs.sendMessage(msg.tabId, {
        target: "content",
        op: "progress",
        step: msg.step || "",
        pct: typeof msg.pct === "number" ? msg.pct : null,
      }).catch(() => {});
    }
    return false;
  }
  const tabId = sender.tab?.id || null;
  (async () => {
    try {
      if (msg.op === "anonymize") {
        const res = await serialized(async () => {
          const map = await getMap();
          const r = await engine("anonymize", { job: msg.job, items: msg.items, previous: map, review: msg.review, tabId });
          if (r.error) throw new Error(r.error);
          await chrome.storage.session.set({ [MAP_KEY]: { ...(await getMap()), ...r.mapping } });
          return r;
        });
        reply({ ok: true, text: res.text, count: Object.keys(res.mapping || {}).length, notes: res.notes || [], found: res.found || [] });
      } else if (msg.op === "redact") {
        const res = await serialized(async () => {
          const map = await getMap();
          const { book = {} } = await chrome.storage.session.get("book");
          const r = await engine("redact", { job: msg.job, items: msg.items, previous: map, book, review: msg.review, tabId });
          if (r.error) throw new Error(r.error);
          await chrome.storage.session.set({ [MAP_KEY]: { ...(await getMap()), ...r.mapping }, book: r.book });
          return r;
        });
        reply({ ok: true, files: res.files, notes: res.notes || [], found: res.found || [] });
      } else if (msg.op === "restore") {
        const res = await engine("restore", { text: msg.text, mapping: await getMap() });
        if (res.error) throw new Error(res.error);
        reply({ ok: true, text: res.text });
      } else if (msg.op === "status") {
        const { attivo = true } = await chrome.storage.local.get("attivo");
        // stato del motore senza crearlo: se il documento offscreen non c'e' ancora, e' "in avvio"
        const st = (await chrome.offscreen.hasDocument())
          ? await chrome.runtime.sendMessage({ target: "offscreen", op: "state" }).catch(() => null) : null;
        reply({ ok: true, attivo, n: Object.keys(await getMap()).length,
                engine: Boolean(st?.engine), ner: st?.ner || { state: "loading", progress: 0 } });
      } else if (msg.op === "toggle") {
        await chrome.storage.local.set({ attivo: !!msg.attivo });
        reply({ ok: true });
      } else if (msg.op === "forget") {
        await serialized(() => chrome.storage.session.remove([MAP_KEY, "book"]));
        reply({ ok: true });
      } else if (msg.op === "release") {
        if (await chrome.offscreen.hasDocument()) {
          await chrome.runtime.sendMessage({ target: "offscreen", op: "release", job: msg.job }).catch(() => {});
        }
        reply({ ok: true });
      } else if (msg.op === "font") {
        const buf = new Uint8Array(await (await fetch(chrome.runtime.getURL("fonts/AlbertSans.woff2"))).arrayBuffer());
        let bin = "";
        for (let i = 0; i < buf.length; i += 0x2000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x2000));
        reply({ ok: true, data: btoa(bin) });
      } else if (msg.op === "warmup") {
        await ensureEngine();
        reply({ ok: true });
      }
    } catch (err) {
      reply({ ok: false, error: String(err.message || err) });
    }
  })();
  return true;  // risposta asincrona
});

// clic sull'icona: apre il pannello di Clin nella scheda della chat; sulle altre pagine
// (dove Clin non lavora) mostra una finestrella con l'elenco delle chat supportate
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) return;
  try {
    await chrome.tabs.sendMessage(tab.id, { target: "content", op: "panel" });
  } catch (_) {
    await chrome.action.setPopup({ tabId: tab.id, popup: "popup.html" });
    try { await chrome.action.openPopup(); } catch (_) {}  // Chrome < 127: si apre al clic successivo
  }
});
