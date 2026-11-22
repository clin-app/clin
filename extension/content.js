// Clin - nella pagina della chat (ChatGPT, Claude, Gemini...).
//
// Quando Clin e' attivo, testo incollato, file trascinati e file scelti con la graffetta
// vengono fermati PRIMA che il sito li riceva: si anonimizzano sul computer e nel campo
// della chat entra solo il testo con i segnaposto. Le risposte si rileggono con i dati
// reali nel pannello di Clin, dentro uno shadow DOM chiuso: il sito non puo' leggerle.
(() => {
  if (window.__clin) return;
  window.__clin = true;

  const NOTE = "Nota: i dati personali sono sostituiti da segnaposto tra parentesi quadre " +
    "(es. [PAZIENTE_1]) e codici come PAZ-0001. Riportali esattamente così nella risposta.\n\n";
  const COMPOSER = [
    "#prompt-textarea", "div.ProseMirror[contenteditable='true']", "rich-textarea .ql-editor",
    "[contenteditable='true'][role='textbox']", "textarea", "[contenteditable='true']",
  ];
  const ANSWERS = [
    "[data-message-author-role='assistant']", "[data-testid='assistant-message']",
    ".font-claude-response", ".font-claude-message", "message-content", "model-response",
  ];
  let active = true, noteSent = false, busy = false;

  const send = (msg) => chrome.runtime.sendMessage({ target: "background", ...msg });

  // ---------------------------------------------------------------- interfaccia (shadow DOM chiuso)
  const host = document.createElement("clin-panel");
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }
      .pill { position: fixed; right: 18px; bottom: 18px; z-index: 2147483646; display: flex; align-items: center; gap: 8px;
              padding: 8px 14px 8px 10px; border: 0; border-radius: 999px; background: #d4f06b; color: #101411;
              font-size: 13px; font-weight: 600; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.18); }
      .pill.off { background: #e9ebe6; color: #6a706b; }
      .dot { width: 8px; height: 8px; border-radius: 50%; background: #3c7a4b; }
      .pill.off .dot { background: #9ba19c; }
      .pill.busy .dot { animation: p 1s infinite; }
      @keyframes p { 50% { opacity: .2; } }
      .panel { position: fixed; right: 18px; bottom: 64px; z-index: 2147483647; width: min(420px, calc(100vw - 36px));
               max-height: min(640px, calc(100vh - 100px)); display: flex; flex-direction: column; gap: 10px; padding: 16px;
               border-radius: 18px; background: #fff; color: #101411; box-shadow: 0 18px 50px rgba(0,0,0,.25); font-size: 14px; }
      .panel[hidden], .toast[hidden] { display: none; }
      .head { display: flex; align-items: center; gap: 10px; }
      .head b { font-size: 15px; }
      .head .tag { padding: 2px 8px; border-radius: 999px; background: #d4f06b; font-size: 12px; font-weight: 600; }
      .head button { margin-left: auto; }
      label.sw { display: flex; align-items: center; gap: 8px; color: #3d423e; }
      .muted { color: #6a706b; font-size: 12.5px; line-height: 1.45; margin: 0; }
      .out { flex: 1; min-height: 120px; overflow: auto; white-space: pre-wrap; padding: 10px 12px; border-radius: 12px;
             background: #f3f4f1; font-size: 13.5px; line-height: 1.5; }
      .row { display: flex; flex-wrap: wrap; gap: 8px; }
      button { border: 0; border-radius: 999px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
               background: #f3f4f1; color: #101411; }
      button.dark { background: #101411; color: #fff; }
      button.x { padding: 4px 10px; background: transparent; font-size: 18px; line-height: 1; }
      .toast { position: fixed; right: 18px; bottom: 64px; z-index: 2147483647; max-width: 360px; padding: 10px 14px;
               border-radius: 14px; background: #101411; color: #fff; font-size: 13px; line-height: 1.45;
               box-shadow: 0 10px 30px rgba(0,0,0,.25); }
      .toast.err { background: #c8312f; }
    </style>
    <button class="pill" part="pill"><span class="dot"></span><span class="lbl">/Clin attivo</span></button>
    <div class="toast" hidden></div>
    <div class="panel" hidden>
      <div class="head"><span class="tag">/Clin</span><b>Anonimizzazione locale</b><button class="x" title="Chiudi">×</button></div>
      <label class="sw"><input type="checkbox" class="on" checked> Anonimizzare testi e file incollati o trascinati in questa chat</label>
      <p class="muted">Tutto avviene su questo computer. Nella chat arrivano solo segnaposto come [PAZIENTE_1]. La tabella dei segnaposto resta in memoria e si cancella chiudendo il browser.</p>
      <p class="muted"><b>Risposta con i dati reali</b> · selezionare un testo nella chat oppure usare l'ultima risposta.</p>
      <div class="row"><button class="last">Ultima risposta</button><button class="sel">Testo selezionato</button></div>
      <div class="out">Le risposte dell'IA compariranno qui con i nomi veri, visibili solo a te.</div>
      <div class="row"><button class="dark copy">Copia con i dati reali</button><button class="forget">Dimentica i segnaposto</button></div>
      <p class="muted n"></p>
    </div>`;
  const $ = (s) => root.querySelector(s);
  const pill = $(".pill"), panel = $(".panel"), toastEl = $(".toast"), out = $(".out");
  let toastTimer = 0;

  function toast(msg, err = false, ms = 5000) {
    toastEl.textContent = msg;
    toastEl.classList.toggle("err", err);
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, ms);
  }
  function render() {
    pill.classList.toggle("off", !active);
    pill.classList.toggle("busy", busy);
    $(".lbl").textContent = busy ? "/Clin al lavoro…" : active ? "/Clin attivo" : "/Clin in pausa";
    $(".on").checked = active;
  }
  async function refresh() {
    const s = await send({ op: "status" }).catch(() => null);
    if (s?.ok) { active = s.attivo; $(".n").textContent = s.n ? `${s.n} segnaposto in memoria.` : ""; }
    render();
  }

  pill.addEventListener("click", () => { panel.hidden = !panel.hidden; toastEl.hidden = true; refresh(); if (!panel.hidden) restoreLast(); });
  $(".x").addEventListener("click", () => { panel.hidden = true; });
  $(".on").addEventListener("change", async (e) => { active = e.target.checked; await send({ op: "toggle", attivo: active }); render(); });
  $(".forget").addEventListener("click", async () => { await send({ op: "forget" }); out.textContent = "Segnaposto dimenticati."; refresh(); });
  $(".copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(out.textContent); toast("Copiato con i dati reali: si può incollare nella cartella clinica."); }
    catch (_) { toast("Copia non riuscita: selezionare il testo nel pannello.", true); }
  });
  let lastSelection = "";
  document.addEventListener("selectionchange", () => {
    const t = String(getSelection() || "");
    if (t.trim()) lastSelection = t;
  });
  $(".sel").addEventListener("click", () => restore(lastSelection || "Selezionare prima un testo nella chat."));
  $(".last").addEventListener("click", restoreLast);

  function lastAnswer() {
    for (const sel of ANSWERS) {
      const all = document.querySelectorAll(sel);
      // senza l'etichetta per lettori di schermo ("Gemini ha detto", "ChatGPT said")
      if (all.length) return all[all.length - 1].innerText.replace(/^\s*\S+ (ha detto|said):?\s*\n/i, "");
    }
    return "";
  }
  async function restore(text) {
    if (!text.trim()) { out.textContent = "Nessuna risposta trovata: selezionare il testo nella chat."; return; }
    const r = await send({ op: "restore", text }).catch(() => null);
    out.textContent = r?.ok ? r.text : "Ripristino non riuscito.";
  }
  function restoreLast() { restore(lastAnswer()); }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.target === "content" && msg.op === "panel") { panel.hidden = false; refresh(); restoreLast(); }
  });

  const mount = () => { (document.body || document.documentElement).appendChild(host); refresh(); send({ op: "warmup" }).catch(() => {}); };
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);

  // ---------------------------------------------------------------- intercettazione
  const editable = (el) => el && (el.isContentEditable || el.tagName === "TEXTAREA" ||
                                   (el.tagName === "INPUT" && /^(text|search)$/.test(el.type)));
  function composer() {
    const a = document.activeElement;
    if (editable(a)) return a;
    for (const sel of COMPOSER) { const el = document.querySelector(sel); if (el) return el; }
    return null;
  }

  function insert(el, text) {
    el.focus();
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      const s = el.selectionStart ?? el.value.length, e = el.selectionEnd ?? el.value.length;
      setter.call(el, el.value.slice(0, s) + text + el.value.slice(e));
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    // editor ProseMirror/Quill: l'inserimento come digitazione resta compatibile con il sito
    if (!document.execCommand("insertText", false, text)) {
      el.dispatchEvent(new InputEvent("beforeinput", { inputType: "insertText", data: text, bubbles: true, cancelable: true }));
    }
  }

  function kindOf(file) {
    const name = (file.name || "").toLowerCase();
    if (file.type.startsWith("image/") || /\.(jpe?g|png|heic|webp)$/.test(name)) return "foto";
    if (file.type === "application/pdf" || name.endsWith(".pdf")) return "PDF";
    if (name.endsWith(".docx")) return "Word";
    if (/\.(csv|tsv)$/.test(name)) return "tabella";
    if (/\.(txt|md)$/.test(name)) return "testo";
    return null;
  }

  function b64(buf) {
    const bytes = new Uint8Array(buf);
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }

  async function handle({ files = [], text = "" }, target) {
    const items = [];
    const refused = [];
    for (const f of files) {
      const kind = kindOf(f);
      if (!kind) { refused.push(f.name); continue; }
      items.push({ kind, name: f.name, type: f.type, data: b64(await f.arrayBuffer()) });
    }
    if (text.trim()) items.push({ kind: "testo incollato", text });
    if (refused.length) toast(`Non inviati (formato non supportato, Excel: salvarlo come CSV): ${refused.join(", ")}`, true, 8000);
    if (!items.length) return;
    busy = true; render();
    try {
      const r = await send({ op: "anonymize", items });
      if (!r?.ok) throw new Error(r?.error || "motore non disponibile");
      const el = target && document.contains(target) ? target : composer();
      if (!el) throw new Error("campo della chat non trovato");
      const prefix = noteSent ? "" : NOTE;
      noteSent = true;
      const filled = (el.value ?? el.innerText ?? "").trim().length > 0;
      insert(el, (filled ? "\n\n" : "") + prefix + r.text);
      const docs = files.length ? `${files.length === 1 ? "1 file" : files.length + " file"} anonimizzat${files.length === 1 ? "o" : "i"}` : "Testo anonimizzato";
      toast(`/Clin · ${docs} sul computer: nella chat entrano solo segnaposto. Controllare prima di inviare.`);
    } catch (err) {
      toast(`/Clin: anonimizzazione non riuscita (${err.message}). Nulla è stato inviato alla chat.`, true, 9000);
    } finally {
      busy = false; render();
    }
  }

  const stop = (e) => { e.preventDefault(); e.stopImmediatePropagation(); e.stopPropagation(); };

  // incolla: testo e immagini dagli appunti
  window.addEventListener("paste", (e) => {
    if (!active || !editable(e.target.closest?.("[contenteditable='true'],textarea,input") || e.target)) return;
    const dt = e.clipboardData;
    if (!dt) return;
    const files = [...(dt.files || [])];
    const text = files.length ? "" : dt.getData("text/plain");
    if (!files.length && !text) return;
    stop(e);
    handle({ files, text }, e.target.closest?.("[contenteditable='true'],textarea,input") || e.target);
  }, true);

  // trascinamento di file sulla chat
  window.addEventListener("drop", (e) => {
    if (!active || !e.dataTransfer?.files?.length) return;
    stop(e);
    handle({ files: [...e.dataTransfer.files] }, null);
  }, true);

  // graffetta / "Carica file": il file non arriva al sito (alcuni siti ascoltano "input", altri "change")
  const onPick = (e) => {
    const input = e.target;
    if (!active || input?.tagName !== "INPUT" || input.type !== "file" || !input.files?.length) return;
    stop(e);
    const files = [...input.files];
    input.value = "";
    handle({ files }, null);
  };
  window.addEventListener("input", onPick, true);
  window.addEventListener("change", onPick, true);
})();
