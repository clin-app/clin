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
  // contenitori delle risposte (dal piu' specifico); se nessuno corrisponde si usa un criterio generale
  const ANSWERS = [
    "[data-message-author-role='assistant']", "[data-response-body]", "[data-testid='assistant-message']",
    ".font-claude-response", "message-content", "model-response",
  ];
  const MARKDOWN = ".standard-markdown, .markdown, [data-testid='chatgpt-writing-block']";
  const PH = /\[[A-Z_]+_\d+\]|\b[A-Z]{2,4}-\d{4}\b/;
  let active = true, noteSent = false, busy = false, passing = false;

  const send = (msg) => chrome.runtime.sendMessage({ target: "background", ...msg });

  // ---------------------------------------------------------------- interfaccia (shadow DOM chiuso)
  const host = document.createElement("clin-panel");
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }
      .pill { position: fixed; right: 18px; bottom: 18px; z-index: 2147483646; display: flex; align-items: center; gap: 0;
              height: 44px; padding: 0 5px; border: 0; border-radius: 22px; background: #101411; color: #fff;
              font-size: 13px; font-weight: 600; letter-spacing: -.01em; cursor: pointer;
              box-shadow: 0 8px 24px rgba(16,20,17,.28), 0 0 0 1px rgba(255,255,255,.06) inset;
              transition: gap .2s, padding .2s, background .2s, opacity .2s; opacity: .92; }
      .pill:hover, .pill.busy, .pill.open { gap: 10px; padding: 0 16px 0 5px; opacity: 1; }
      .logo { position: relative; flex: none; width: 34px; height: 34px; display: grid; place-items: center; }
      .logo svg { width: 34px; height: 34px; display: block; }
      .lbl { max-width: 0; overflow: hidden; white-space: nowrap; transition: max-width .25s; }
      .pill:hover .lbl, .pill.busy .lbl, .pill.open .lbl { max-width: 180px; }
      .state { position: absolute; right: -1px; bottom: -1px; width: 11px; height: 11px; border-radius: 50%;
               background: #7fcf8a; box-shadow: 0 0 0 2px #101411; }
      .pill.off { background: #3d423e; }
      .pill.off .state { background: #9ba19c; }
      .pill.off .logo svg { filter: grayscale(1); opacity: .7; }
      .ring { position: absolute; inset: -3px; border-radius: 50%; border: 2px solid transparent; border-top-color: #d4f06b; display: none; animation: spin .9s linear infinite; }
      .pill.busy .ring { display: block; }
      @keyframes spin { to { transform: rotate(360deg); } }
      .panel { position: fixed; right: 18px; bottom: 72px; z-index: 2147483647; width: min(420px, calc(100vw - 36px));
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
      .toast { position: fixed; right: 18px; bottom: 72px; z-index: 2147483647; max-width: 360px; padding: 10px 14px;
               border-radius: 14px; background: #101411; color: #fff; font-size: 13px; line-height: 1.45;
               box-shadow: 0 10px 30px rgba(0,0,0,.25); }
      .toast.err { background: #c8312f; }
    </style>
    <button class="pill" part="pill" title="Clin: anonimizzazione locale">
      <span class="logo"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16" fill="#d4f06b"/><g transform="rotate(-8 16 16)"><path d="M10.2 7.5h8.6l4.2 4.2v12.1a1.4 1.4 0 0 1-1.4 1.4H10.2a1.4 1.4 0 0 1-1.4-1.4V8.9a1.4 1.4 0 0 1 1.4-1.4z" fill="#101411"/><path d="M18.6 7.5v4.4h4.4" fill="#3c7a4b"/><rect x="11.3" y="13.6" width="9.4" height="1.5" rx=".75" fill="#d4f06b"/><rect x="11.3" y="17" width="9.4" height="3" rx="1" fill="#d4f06b"/><rect x="11.3" y="21.8" width="5.6" height="1.5" rx=".75" fill="#d4f06b"/></g></svg><span class="state"></span><span class="ring"></span></span>
      <span class="lbl">/Clin attivo</span>
    </button>
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
    pill.classList.toggle("open", !panel.hidden);
    $(".lbl").textContent = busy ? "/Clin al lavoro…" : active ? "/Clin attivo" : "/Clin in pausa";
    $(".on").checked = active;
  }
  async function refresh() {
    const s = await send({ op: "status" }).catch(() => null);
    if (s?.ok) { active = s.attivo; $(".n").textContent = s.n ? `${s.n} segnaposto in memoria.` : ""; }
    render();
  }

  pill.addEventListener("click", () => { panel.hidden = !panel.hidden; toastEl.hidden = true; refresh(); if (!panel.hidden) restoreLast(); });
  $(".x").addEventListener("click", () => { panel.hidden = true; render(); });
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
  $(".sel").addEventListener("click", () => { mode = "sel"; restore(lastSelection || "Selezionare prima un testo nella chat."); });
  $(".last").addEventListener("click", restoreLast);

  // testo della risposta: solo i blocchi di contenuto, senza ragionamento ne' etichette nascoste
  function answerText(el) {
    const blocks = [...el.querySelectorAll(MARKDOWN)].filter((b) => !b.parentElement.closest(MARKDOWN));
    if (blocks.length) return blocks.map((b) => b.innerText.trim()).join("\n\n");
    return el.innerText.replace(/^\s*\S+ (ha detto|ha risposto|said|says):?\s*\n/i, "");
  }
  const isUser = (el) => el.innerText.includes(NOTE.slice(0, 40)) || el.closest("[data-message-author-role='user'],[data-testid='user-message'],user-query");
  function lastAnswer() {
    for (const sel of ANSWERS) {
      const all = [...document.querySelectorAll(sel)].filter((e) => !isUser(e));
      if (all.length) return answerText(all[all.length - 1]);
    }
    // criterio generale: l'ultimo blocco di testo con segnaposto che non sia il messaggio inviato
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let last = null, n;
    while ((n = walker.nextNode())) if (PH.test(n.nodeValue) && !n.parentElement.closest("[contenteditable='true'],textarea")) last = n;
    let el = last?.parentElement;
    while (el?.parentElement && el.parentElement !== document.body && !isUser(el.parentElement)
           && el.parentElement.innerText.length < 20000) el = el.parentElement;
    return el && !isUser(el) ? answerText(el) : "";
  }
  async function restore(text) {
    if (!text.trim()) { out.textContent = "Nessuna risposta trovata: selezionare il testo nella chat."; return; }
    const r = await send({ op: "restore", text }).catch(() => null);
    out.textContent = r?.ok ? r.text : "Ripristino non riuscito.";
  }
  let mode = "last", lastShown = "", watchTimer = 0;
  function restoreLast() { mode = "last"; const t = lastAnswer(); lastShown = t; restore(t); }
  new MutationObserver(() => {
    if (panel.hidden || mode !== "last") return;
    clearTimeout(watchTimer);
    watchTimer = setTimeout(() => { const t = lastAnswer(); if (t !== lastShown) { lastShown = t; restore(t); } }, 900);
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });

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
    if (/\.(xlsx|xlsm)$/.test(name)) return "Excel";
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

  // input file del sito a cui consegnare i documenti coperti
  function fileInput(preferred) {
    if (preferred && document.contains(preferred)) return preferred;
    const all = [...document.querySelectorAll("input[type='file']")];
    return all.find((i) => !i.accept || /pdf|\*|application/.test(i.accept)) || all[0] || null;
  }

  function deliver(files, origin) {
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    passing = true;
    try {
      const input = origin.kind === "input" ? fileInput(origin.input) : fileInput(null);
      if (input) {
        input.files = dt.files;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      const t = origin.target && document.contains(origin.target) ? origin.target : composer();
      if (!t) return false;
      for (const type of ["dragenter", "dragover", "drop"]) t.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
      return true;
    } finally {
      passing = false;
    }
  }

  async function handleFiles(files, origin) {
    const items = [], refused = [];
    for (const f of files) {
      const kind = kindOf(f);
      if (!kind) { refused.push(f.name); continue; }
      items.push({ kind, name: f.name, type: f.type, data: b64(await f.arrayBuffer()) });
    }
    if (refused.length) toast(`Non inviati (formato non supportato): ${refused.join(", ")}`, true, 8000);
    if (!items.length) return;
    busy = true; render();
    toast(`/Clin · copertura dei dati in ${items.length === 1 ? "1 file" : items.length + " file"}…`, false, 60000);
    try {
      const r = await send({ op: "redact", items });
      if (!r?.ok) throw new Error(r?.error || "motore non disponibile");
      const out = r.files.map((f) => new File([Uint8Array.from(atob(f.data), (c) => c.charCodeAt(0))], f.name, { type: f.type }));
      if (!deliver(out, origin)) throw new Error("allegato non accettato dal sito");
      if (!noteSent) {  // la nota sui segnaposto, una volta per pagina
        const el = composer();
        if (el) { noteSent = true; insert(el, NOTE.trim() + " "); }
      }
      const extra = r.notes?.length ? " " + r.notes.join(" ") : "";
      toast(`/Clin · allegat${out.length === 1 ? "o 1 file" : "i " + out.length + " file"} con i dati coperti: ${out.map((f) => f.name).join(", ")}.${extra} Controllare prima di inviare.`, false, 9000);
    } catch (err) {
      console.error("[Clin]", err);
      toast(`/Clin: copertura non riuscita (${err.message}). Nessun file è stato inviato alla chat.`, true, 10000);
    } finally {
      busy = false; render();
    }
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
      let body = (filled ? "\n\n" : "") + prefix + r.text.replace(/\n{3,}/g, "\n\n");
      if (el.isContentEditable) body = body.replace(/\n\n/g, "\n");
      insert(el, body);
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
    if (passing || !active || !editable(e.target.closest?.("[contenteditable='true'],textarea,input") || e.target)) return;
    const dt = e.clipboardData;
    if (!dt) return;
    const files = [...(dt.files || [])];
    const text = files.length ? "" : dt.getData("text/plain");
    if (!files.length && !text) return;
    stop(e);
    if (files.length) handleFiles(files, { kind: "paste", target: e.target });
    else handle({ text }, e.target.closest?.("[contenteditable='true'],textarea,input") || e.target);
  }, true);

  // trascinamento di file sulla chat
  window.addEventListener("drop", (e) => {
    if (passing || !active || !e.dataTransfer?.files?.length) return;
    const files = [...e.dataTransfer.files], target = e.target;
    stop(e);
    for (const t of ["dragleave", "dragend"]) {
      try { target.dispatchEvent(new DragEvent(t, { bubbles: true, cancelable: true, dataTransfer: new DataTransfer() })); } catch (_) {}
    }
    handleFiles(files, { kind: "drop", target });
  }, true);

  // graffetta / "Carica file": il file non arriva al sito (alcuni siti ascoltano "input", altri "change")
  const onPick = (e) => {
    const input = e.target;
    if (passing || !active || input?.tagName !== "INPUT" || input.type !== "file" || !input.files?.length) return;
    stop(e);
    const files = [...input.files];
    input.value = "";
    handleFiles(files, { kind: "input", input });
  };
  window.addEventListener("input", onPick, true);
  window.addEventListener("change", onPick, true);
})();
