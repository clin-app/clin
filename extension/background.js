// Clin - service worker dell'estensione.
// Tiene la tabella dei segnaposto in chrome.storage.session (solo in memoria, cancellata
// alla chiusura del browser, invisibile ai siti) e inoltra il lavoro al documento offscreen,
// dove gira il motore (Pyodide). Nessuna richiesta di rete: connect-src 'self'.

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
  for (let i = 0; i < 3; i++) {  // il documento appena creato puo' non ascoltare ancora
    const res = await chrome.runtime.sendMessage({ target: "offscreen", op, ...payload }).catch(() => null);
    if (res) return res;
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error("motore non disponibile");
}

let queue = Promise.resolve();
function serialized(fn) {
  const next = queue.then(fn, fn);
  queue = next.catch(() => {});
  return next;
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!msg || msg.target !== "background" || sender.id !== chrome.runtime.id) return false;
  (async () => {
    try {
      if (msg.op === "anonymize") {
        const res = await serialized(async () => {
          const map = await getMap();
          const r = await engine("anonymize", { items: msg.items, previous: map });
          if (r.error) throw new Error(r.error);
          await chrome.storage.session.set({ [MAP_KEY]: { ...(await getMap()), ...r.mapping } });
          return r;
        });
        reply({ ok: true, text: res.text, count: Object.keys(res.mapping || {}).length, notes: res.notes || [] });
      } else if (msg.op === "redact") {
        const res = await serialized(async () => {
          const map = await getMap();
          const { book = {} } = await chrome.storage.session.get("book");
          const r = await engine("redact", { items: msg.items, previous: map, book });
          if (r.error) throw new Error(r.error);
          await chrome.storage.session.set({ [MAP_KEY]: { ...(await getMap()), ...r.mapping }, book: r.book });
          return r;
        });
        reply({ ok: true, files: res.files, notes: res.notes || [] });
      } else if (msg.op === "restore") {
        const res = await engine("restore", { text: msg.text, mapping: await getMap() });
        if (res.error) throw new Error(res.error);
        reply({ ok: true, text: res.text });
      } else if (msg.op === "status") {
        const { attivo = true } = await chrome.storage.local.get("attivo");
        reply({ ok: true, attivo, n: Object.keys(await getMap()).length });
      } else if (msg.op === "toggle") {
        await chrome.storage.local.set({ attivo: !!msg.attivo });
        reply({ ok: true });
      } else if (msg.op === "forget") {
        await serialized(() => chrome.storage.session.remove([MAP_KEY, "book"]));
        reply({ ok: true });
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

// clic sull'icona: apre il pannello di Clin nella scheda della chat
chrome.action.onClicked.addListener((tab) => {
  if (tab.id) chrome.tabs.sendMessage(tab.id, { target: "content", op: "panel" }).catch(() => {});
});
