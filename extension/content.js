// Clin - nella pagina della chat (ChatGPT, Claude, Gemini...).
//
// Quando Clin e' attivo, testo incollato, file trascinati e file scelti vengono fermati PRIMA
// che il sito li riceva: si anonimizzano sul computer e si aprono nella finestra di revisione
// (anteprima reale del documento a sinistra, dati coperti a destra). Solo con «Inserisci nella
// chat» entrano nel sito. Un testo breve in cui non c'e' nulla da coprire passa senza domande.
// Tutta l'interfaccia vive in uno shadow DOM chiuso: la pagina non puo' leggere i dati reali.
(() => {
  if (window.__clin) return;
  window.__clin = true;

  const COMPOSER = [
    "#prompt-textarea", "div.ProseMirror[contenteditable='true']", "rich-textarea .ql-editor",
    "[contenteditable='true'][role='textbox']", "textarea", "[contenteditable='true']",
  ];
  const ANSWERS = [
    "[data-message-author-role='assistant']", "[data-response-body]", "[data-testid='assistant-message']",
    ".font-claude-response", "message-content", "model-response",
  ];
  const MARKDOWN = ".standard-markdown, .markdown, [data-testid='chatgpt-writing-block']";
  const PH = /\[[A-Z_]+_\d+\]|\b[A-Z]{2,4}-\d{4}\b/;
  const QUIET_MAX = 400;  // caratteri: sotto questa soglia un testo senza dati personali entra senza revisione
  let active = true, busy = false, passing = false;

  const send = (msg) => chrome.runtime.sendMessage({ target: "background", ...msg });

  // ---------------------------------------------------------------- icone e disegni
  const ico = (d, extra = "") => `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${extra}<path d="${d}"/></svg>`;
  const I = {
    x: ico("M6 6l12 12M18 6L6 18"),
    up: ico("M12 16V4m0 0L8 8m4-4l4 4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"),
    down: ico("M12 4v12m0 0l-4-4m4 4l4-4M4 20h16"),
    lock: ico("M8 11V8a4 4 0 018 0v3", '<rect x="5" y="11" width="14" height="9" rx="2"/>'),
    copy: ico("M5 15V6a2 2 0 012-2h8", '<rect x="9" y="9" width="11" height="11" rx="2"/>'),
    prev: ico("M15 6l-6 6 6 6"),
    next: ico("M9 6l6 6-6 6"),
    plus: ico("M12 5v14M5 12h14"),
    minus: ico("M5 12h14"),
    file: ico("M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8zM14 3v5h5"),
    text: ico("M5 6h14M5 12h14M5 18h9"),
    arrow: ico("M4 12h15m0 0l-5-5m5 5l-5 5"),
  };
  const LOGO = `<svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16" fill="#d4f06b"/><g transform="rotate(-8 16 16)"><path d="M10.2 7.5h8.6l4.2 4.2v12.1a1.4 1.4 0 0 1-1.4 1.4H10.2a1.4 1.4 0 0 1-1.4-1.4V8.9a1.4 1.4 0 0 1 1.4-1.4z" fill="#101411"/><path d="M18.6 7.5v4.4h4.4" fill="#3c7a4b"/><rect x="11.3" y="13.6" width="9.4" height="1.5" rx=".75" fill="#d4f06b"/><rect x="11.3" y="17" width="9.4" height="3" rx="1" fill="#d4f06b"/><rect x="11.3" y="21.8" width="5.6" height="1.5" rx=".75" fill="#d4f06b"/></g></svg>`;
  // pila isometrica di fogli (lo stesso disegno dei diagrammi del sito)
  const stack = (n = 5) => {
    let p = "";
    for (let k = n - 1; k >= 0; k--) p += `<path d="M24 ${1.5 + k * 5}l21 10.5-21 10.5L3 ${12 + k * 5}z"/>`;
    return `<svg class="stk" viewBox="0 0 48 ${24 + (n - 1) * 5}" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
  };

  // ---------------------------------------------------------------- interfaccia (shadow DOM chiuso)
  const host = document.createElement("clin-panel");
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      .app { --bg: #fff; --bg2: #f5f6f3; --bg3: #ebede7; --line: #e2e5dd; --ink: #101411; --ink2: #4a504b; --ink3: #767c77;
             --acc: #d4f06b; --on-acc: #101411; --green: #2e6b3c; --green-bg: #e9f4ec; --warn: #9a5407; --warn-bg: #fff3df; --warn-line: #f1d9ad;
             --err: #c0302e; --blue: #3c7a4b; --blue-bg: #f1f9d2; --mark-bg: #101411; --mark-ink: #d4f06b;
             --shadow: 0 24px 64px rgba(16,20,17,.24), 0 2px 8px rgba(16,20,17,.08);
             font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color: var(--ink); letter-spacing: -.005em; }
      .app.dark { --bg: #181b19; --bg2: #212622; --bg3: #2b312d; --line: #353c37; --ink: #f1f3ee; --ink2: #bcc1bb; --ink3: #8a908a;
                  --green: #8fd39b; --green-bg: #1d2e22; --warn: #f0b765; --warn-bg: #33290f; --warn-line: #5a4517;
                  --err: #ff8a85; --blue: #d4f06b; --blue-bg: #283016; --mark-bg: #d4f06b; --mark-ink: #101411;
                  --shadow: 0 24px 64px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.06); }
      * { box-sizing: border-box; font-family: inherit; }
      [hidden] { display: none !important; }
      .i { width: 18px; height: 18px; flex: none; display: block; }
      .logo { width: 28px; height: 28px; flex: none; display: block; }
      button { font: inherit; color: inherit; border: 0; background: none; padding: 0; cursor: pointer; }
      button:focus-visible, input:focus-visible, .dz:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }
      @keyframes rise { from { opacity: 0; transform: translateY(8px) scale(.985); } to { opacity: 1; transform: none; } }
      @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
      @keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
      @media (prefers-reduced-motion: reduce) { * { animation-duration: .01ms !important; transition-duration: .01ms !important; } }

      /* ---------------- pulsanti */
      .b { display: inline-flex; align-items: center; justify-content: center; gap: 7px; height: 36px; padding: 0 14px; border-radius: 10px;
           background: var(--bg2); color: var(--ink); font-size: 13.5px; font-weight: 600; white-space: nowrap; transition: background .15s, opacity .15s; }
      .b:hover { background: var(--bg3); }
      .b.pri { background: var(--ink); color: var(--bg); }
      .b.pri:hover { opacity: .88; }
      .b:disabled { opacity: .45; cursor: default; }
      .b kbd { font: 600 11px/1 inherit; padding: 3px 5px; border-radius: 5px; background: rgba(127,127,127,.28); }
      .ib { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; color: var(--ink2); transition: background .15s; }
      .ib:hover { background: var(--bg2); color: var(--ink); }
      .ib:disabled { opacity: .35; cursor: default; }
      .lnk { color: var(--ink3); font-size: 12.5px; text-decoration: underline; text-underline-offset: 2px; }
      .lnk:hover { color: var(--ink); }

      /* ---------------- pulsante fisso */
      .fab { position: fixed; right: 16px; bottom: 16px; z-index: 2147483646; display: flex; align-items: center; height: 40px; padding: 0 6px;
             border-radius: 20px; background: #101411; color: #fff; font-size: 13px; font-weight: 600;
             box-shadow: 0 6px 20px rgba(16,20,17,.3), inset 0 0 0 1px rgba(255,255,255,.08); transition: padding .2s, background .2s; }
      .fab-m { position: relative; display: grid; place-items: center; width: 28px; height: 28px; }
      .fab-d { position: absolute; right: -2px; bottom: -2px; width: 10px; height: 10px; border-radius: 50%; background: #7fcf8a; box-shadow: 0 0 0 2px #101411; }
      .fab-r { position: absolute; inset: -4px; border-radius: 50%; border: 2px solid transparent; border-top-color: #d4f06b; animation: spin .8s linear infinite; display: none; }
      .fab-l { max-width: 0; overflow: hidden; white-space: nowrap; transition: max-width .25s, margin .25s; }
      .fab:hover, .fab.busy, .fab.off, .fab.say { padding-right: 14px; }
      .fab:hover .fab-l, .fab.busy .fab-l, .fab.off .fab-l, .fab.say .fab-l { max-width: 240px; margin-left: 9px; }
      .fab.busy .fab-r { display: block; }
      .fab.off { background: #4a4f4b; }
      .fab.off .fab-d { background: #f0b765; box-shadow: 0 0 0 2px #4a4f4b; }
      .fab.off .logo { filter: grayscale(1); opacity: .75; }

      .toast { position: fixed; right: 16px; bottom: 66px; z-index: 2147483647; max-width: min(400px, calc(100vw - 32px)); display: flex; align-items: center; gap: 10px;
               padding: 10px 12px 10px 14px; border-radius: 12px; background: #101411; color: #fff; font-size: 13px; line-height: 1.4;
               box-shadow: 0 10px 30px rgba(0,0,0,.3); animation: rise .2s ease-out; }
      .toast.err { background: #b32b29; }
      .t-act { flex: none; height: 28px; padding: 0 10px; border-radius: 8px; background: #d4f06b; color: #101411; font-size: 12.5px; font-weight: 600; }

      /* ---------------- pannello */
      .pop { position: fixed; right: 16px; bottom: 66px; z-index: 2147483647; width: min(380px, calc(100vw - 32px)); max-height: min(620px, calc(100vh - 90px));
             display: flex; flex-direction: column; border-radius: 16px; background: var(--bg); border: 1px solid var(--line); box-shadow: var(--shadow);
             overflow: hidden; animation: rise .18s ease-out; }
      .pop-h { display: flex; align-items: center; gap: 10px; padding: 14px 12px 12px 14px; }
      .ttl { flex: 1; min-width: 0; display: grid; }
      .ttl b { font-size: 15px; font-weight: 650; }
      .ttl span { font-size: 12.5px; color: var(--ink3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .sw { appearance: none; -webkit-appearance: none; flex: none; position: relative; width: 38px; height: 22px; margin: 0; border-radius: 11px; background: var(--bg3); cursor: pointer; transition: background .18s; }
      .sw::after { content: ""; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .18s; }
      .sw:checked { background: #3c7a4b; }
      .sw:checked::after { transform: translateX(16px); }
      .pop-b { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 12px; padding: 0 14px 14px; overflow: auto; }
      .dz { display: flex; align-items: center; gap: 12px; width: 100%; padding: 12px 14px; border-radius: 12px; text-align: left;
            border: 1.5px dashed var(--line); background: var(--bg2); transition: border-color .15s, background .15s; }
      .dz:hover { border-color: var(--blue); background: var(--blue-bg); }
      .dz .i { width: 22px; height: 22px; color: var(--blue); }
      .dz b { display: block; font-size: 13.5px; font-weight: 600; }
      .dz small { display: block; font-size: 12px; color: var(--ink3); }
      .seg { display: flex; gap: 2px; padding: 3px; border-radius: 10px; background: var(--bg2); }
      .seg button { flex: 1; height: 30px; border-radius: 8px; font-size: 12.5px; font-weight: 600; color: var(--ink3); }
      .seg button.on { background: var(--bg); color: var(--ink); box-shadow: 0 1px 3px rgba(0,0,0,.12); }
      .seg i { font-style: normal; font-weight: 500; opacity: .7; }
      .tab { display: flex; flex-direction: column; gap: 10px; min-height: 0; }
      .hint { margin: 0; font-size: 12.5px; color: var(--ink3); }
      .out { min-height: 96px; max-height: 240px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; padding: 10px 12px; border-radius: 10px;
             background: var(--bg2); font-size: 13.5px; line-height: 1.5; user-select: text; }
      .out.empty { color: var(--ink3); }
      .row { display: flex; flex-wrap: wrap; gap: 8px; }
      .row .b { flex: 1; }
      .sent { display: grid; gap: 6px; max-height: 300px; overflow: auto; }
      .sc { display: grid; grid-template-columns: 40px 1fr auto; align-items: center; gap: 10px; padding: 7px 8px; border-radius: 10px; background: var(--bg2); text-align: left; width: 100%; }
      .sc:hover { background: var(--bg3); }
      .sc-t { width: 40px; height: 50px; border-radius: 6px; object-fit: cover; background: var(--bg3); display: grid; place-items: center; color: var(--ink3); border: 1px solid var(--line); }
      .sc-n { font-weight: 600; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .sc-m { font-size: 12px; color: var(--ink3); }
      .pop-f { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; border-top: 1px solid var(--line); font-size: 12.5px; color: var(--ink3); }
      .eng { display: flex; align-items: center; gap: 7px; min-width: 0; }
      .eng i { flex: none; width: 7px; height: 7px; border-radius: 50%; background: #e0a53a; }
      .eng.ok i { background: #3c9a55; }

      /* ---------------- finestra di revisione */
      .ov { position: fixed; inset: 0; z-index: 2147483647; display: grid; place-items: center; padding: 16px; background: rgba(16,20,17,.5);
            backdrop-filter: blur(3px); -webkit-backdrop-filter: blur(3px); animation: fade .15s ease-out; }
      .dlg { position: relative; display: flex; flex-direction: column; width: min(1080px, 100%); height: min(780px, 100%); border-radius: 18px;
             background: var(--bg); border: 1px solid var(--line); box-shadow: var(--shadow); overflow: hidden; animation: rise .22s cubic-bezier(.2,.8,.2,1); }
      .dlg.text { width: min(900px, 100%); height: min(640px, 100%); }
      .dlg:focus { outline: none; }
      .dlg-h { flex: none; display: flex; align-items: center; gap: 10px; padding: 14px 12px 14px 16px; border-bottom: 1px solid var(--line); }
      .local { flex: none; display: inline-flex; align-items: center; gap: 6px; height: 26px; padding: 0 10px 0 8px; border-radius: 13px; background: var(--green-bg); color: var(--green); font-size: 12px; font-weight: 600; }
      .local .i { width: 14px; height: 14px; }
      .upd { flex: none; height: 2px; margin-bottom: -2px; position: relative; z-index: 3; overflow: hidden; visibility: hidden; }
      .upd::after { content: ""; display: block; width: 30%; height: 100%; background: var(--blue); animation: slide 1s ease-in-out infinite; }
      .dlg.updating .upd { visibility: visible; }
      .dlg.updating .side, .dlg.updating .pv { opacity: .6; transition: opacity .15s; }

      .load { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 22px; padding: 24px; text-align: center; }
      .pipe { display: flex; align-items: center; gap: 14px; color: var(--ink3); }
      .pipe figure { margin: 0; display: grid; justify-items: center; gap: 8px; width: 112px; padding: 14px 8px 12px; border-radius: 14px; font-size: 12px; font-weight: 600; transition: background .3s, color .3s; }
      .pipe .stk { width: 48px; }
      .stk path { fill: var(--bg); }
      .pipe figure.on .stk path { fill: var(--acc); }
      .pipe figure.on { background: var(--acc); color: var(--on-acc); }
      .pipe figure.on .stk { animation: bob 1.2s ease-in-out infinite; }
      .pipe figure.done { color: var(--ink); }
      .pipe .i { width: 20px; height: 20px; opacity: .6; }
      .load-t b { display: block; font-size: 15px; font-weight: 600; }
      .load-t span { font-size: 13px; color: var(--ink3); }
      .bar { width: min(320px, 80%); height: 4px; border-radius: 2px; background: var(--bg3); overflow: hidden; }
      .bar div { height: 100%; width: 8%; border-radius: 2px; background: var(--blue); transition: width .4s cubic-bezier(.2,.8,.2,1); }
      .load.fail .pipe, .load.fail .bar { display: none; }
      .load.fail .load-t b { color: var(--err); }

      .dlg-b { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 340px; }
      .pv { min-width: 0; min-height: 0; display: flex; flex-direction: column; background: var(--bg2); }
      .pv-bar { flex: none; display: flex; align-items: center; gap: 4px; padding: 8px 10px; border-bottom: 1px solid var(--line); background: var(--bg); min-height: 49px; }
      .pv-k { margin: 0 6px; font-size: 12px; font-weight: 600; color: var(--ink3); text-transform: uppercase; letter-spacing: .05em; }
      .ft { display: flex; gap: 2px; min-width: 0; overflow: auto; }
      .ft button { height: 30px; max-width: 180px; padding: 0 10px; border-radius: 8px; font-size: 12.5px; font-weight: 600; color: var(--ink3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; }
      .ft button.on { background: var(--bg2); color: var(--ink); }
      .sp { flex: 1; }
      .pg { font-size: 12.5px; font-weight: 600; color: var(--ink2); font-variant-numeric: tabular-nums; padding: 0 2px; white-space: nowrap; }
      .stage { flex: 1; min-height: 0; overflow: auto; padding: 18px; text-align: center; }
      .stage img { display: inline-block; max-width: none; height: auto; background: #fff; border-radius: 4px; box-shadow: 0 2px 14px rgba(0,0,0,.16); }
      .txt { flex: 1; min-height: 0; overflow: auto; margin: 0; padding: 20px 22px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.65; user-select: text; background: var(--bg); }
      mark { background: var(--mark-bg); color: var(--mark-ink); border-radius: 5px; padding: 1px 5px; font: 600 .86em/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: nowrap; }

      .side { min-height: 0; display: flex; flex-direction: column; border-left: 1px solid var(--line); }
      .cnt { flex: none; display: flex; align-items: baseline; gap: 8px; padding: 16px 16px 4px; }
      .cnt b { font-size: 30px; font-weight: 650; letter-spacing: -.03em; line-height: 1; }
      .cnt span { font-size: 13.5px; color: var(--ink2); }
      .cnt-s { flex: none; margin: 0; padding: 0 16px 10px; font-size: 12.5px; color: var(--ink3); }
      .cnt-s.w { color: var(--warn); font-weight: 600; }
      .list { flex: 1; min-height: 0; overflow: auto; padding: 0 10px 8px; }
      .gk { position: sticky; top: 0; z-index: 1; margin: 0; padding: 10px 6px 4px; background: var(--bg); font-size: 11.5px; font-weight: 600; color: var(--ink3); text-transform: uppercase; letter-spacing: .05em; }
      .it { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 8px; padding: 7px 6px; border-radius: 9px; cursor: pointer; }
      .it:hover { background: var(--bg2); }
      .it-v { font-size: 13.5px; font-weight: 550; overflow-wrap: anywhere; }
      .it-p { font: 600 11px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; padding: 2px 6px; border-radius: 5px; background: var(--mark-bg); color: var(--mark-ink); white-space: nowrap; max-width: 130px; overflow: hidden; text-overflow: ellipsis; }
      .it .sw { width: 32px; height: 18px; border-radius: 9px; }
      .it .sw::after { width: 14px; height: 14px; }
      .it .sw:checked::after { transform: translateX(14px); }
      .it.off { background: var(--warn-bg); box-shadow: inset 0 0 0 1px var(--warn-line); }
      .it.off .it-p { background: transparent; color: var(--warn); }
      .none { margin: 8px 6px; font-size: 13px; color: var(--ink3); }
      .add { flex: none; display: flex; gap: 6px; padding: 10px 12px; border-top: 1px solid var(--line); }
      .add input { flex: 1; min-width: 0; height: 36px; padding: 0 12px; border-radius: 10px; border: 1px solid var(--line); background: var(--bg); color: var(--ink); font-size: 13.5px; }
      .add input::placeholder { color: var(--ink3); }
      .notes { flex: none; margin: 0; padding: 0 14px 10px; font-size: 12px; color: var(--ink3); }
      .selb { position: fixed; z-index: 2; height: 32px; padding: 0 12px; border-radius: 9px; background: var(--ink); color: var(--bg); font-size: 12.5px; font-weight: 600; box-shadow: 0 6px 18px rgba(0,0,0,.28); }

      .dlg-f { flex: none; display: flex; align-items: center; gap: 8px; padding: 12px 14px 12px 16px; border-top: 1px solid var(--line); }
      .st { flex: 1; min-width: 0; margin: 0; font-size: 12.5px; color: var(--ink3); }
      .st.err { color: var(--err); font-weight: 600; }
      .go { min-width: 190px; height: 40px; }

      /* ---------------- anteprima a schermo intero (documenti gia' inviati) */
      .lb { position: fixed; inset: 0; z-index: 2147483647; display: flex; flex-direction: column; background: rgba(12,15,13,.9); color: #fff; animation: fade .15s ease-out; }
      .lb-h { display: flex; align-items: center; gap: 8px; padding: 12px 14px 12px 18px; }
      .lb-h b { flex: 1; min-width: 0; font-size: 14.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .lb-h .ib { color: #fff; }
      .lb-h .ib:hover { background: rgba(255,255,255,.14); }
      .lb-h .pg { color: #fff; }
      .lb-b { flex: 1; min-height: 0; overflow: auto; padding: 8px 18px 24px; text-align: center; }
      .lb-b img { width: min(920px, 100%); height: auto; border-radius: 6px; background: #fff; }
      .lb-b .txt { display: inline-block; width: min(820px, 100%); text-align: left; border-radius: 12px; color: var(--ink); }

      @media (max-width: 820px) {
        .dlg-b { grid-template-columns: 1fr; grid-template-rows: minmax(0, 1fr) minmax(0, 1fr); }
        .side { border-left: 0; border-top: 1px solid var(--line); }
        .local { display: none; }
        .go { min-width: 0; flex: 1; }
        .go kbd { display: none; }
        .pipe figure { width: 88px; }
      }
    </style>

    <div class="app">
      <button class="fab" type="button" aria-label="Apri Clin">
        <span class="fab-m">${LOGO}<span class="fab-d"></span><span class="fab-r"></span></span>
        <span class="fab-l">Clin attivo</span>
      </button>

      <div class="toast" role="status" hidden><span class="t-msg"></span><button class="t-act" type="button" hidden></button></div>

      <section class="pop" role="dialog" aria-label="Clin" hidden>
        <header class="pop-h">
          ${LOGO}
          <div class="ttl"><b>Clin</b><span class="pop-s">Protezione attiva</span></div>
          <input type="checkbox" class="sw on" role="switch" aria-label="Protezione attiva" checked>
          <button class="ib pop-x" type="button" aria-label="Chiudi">${I.x}</button>
        </header>
        <div class="pop-b">
          <button class="dz" type="button">${I.up}<span><b>Scegli o trascina un file</b><small>PDF, foto, Word, Excel, CSV, testo · letto solo su questo computer</small></span></button>
          <input type="file" class="pick" multiple accept="image/*,application/pdf,.pdf,.docx,.xlsx,.xlsm,.csv,.tsv,.txt,.md" hidden>
          <nav class="seg">
            <button type="button" class="on" data-tab="ans">Risposta con i dati reali</button>
            <button type="button" data-tab="sent">Inviati <i class="sent-n">0</i></button>
          </nav>
          <div class="tab tab-ans">
            <div class="out empty"></div>
            <div class="row">
              <button class="b pri copy" type="button">${I.copy}Copia</button>
              <button class="b last" type="button">Ultima risposta</button>
              <button class="b sel" type="button">Selezione</button>
            </div>
            <p class="hint">I nomi veri compaiono solo qui: la pagina della chat non può leggerli.</p>
          </div>
          <div class="tab tab-sent" hidden><div class="sent"></div></div>
        </div>
        <footer class="pop-f">
          <span class="eng"><i></i><span class="eng-t">Motore in avvio…</span></span>
          <button class="lnk forget" type="button">Dimentica tutto</button>
        </footer>
      </section>

      <div class="ov" hidden>
        <section class="dlg" role="dialog" aria-modal="true" aria-label="Controlla prima di inviare" tabindex="-1">
          <header class="dlg-h">
            ${LOGO}
            <div class="ttl"><b>Controlla prima di inviare</b><span class="dlg-s"></span></div>
            <span class="local">${I.lock}Solo su questo computer</span>
            <button class="ib dlg-x" type="button" aria-label="Annulla e chiudi">${I.x}</button>
          </header>
          <div class="upd"></div>
          <div class="load">
            <div class="pipe">
              <figure class="p1">${stack(5)}<figcaption>Documento</figcaption></figure>${I.arrow}
              <figure class="p2">${stack(5)}<figcaption>Motore locale</figcaption></figure>${I.arrow}
              <figure class="p3">${stack(5)}<figcaption>Copia anonima</figcaption></figure>
            </div>
            <div class="load-t"><b class="load-step">Avvio del motore locale…</b><span class="load-sub">Nessun dato lascia questo computer</span></div>
            <div class="bar"><div></div></div>
          </div>
          <div class="dlg-b" hidden>
            <div class="pv"></div>
            <aside class="side">
              <div class="cnt"><b>0</b><span>dati coperti</span></div>
              <p class="cnt-s"></p>
              <div class="list"></div>
              <p class="notes" hidden></p>
              <form class="add"><input class="word" placeholder="Manca qualcosa? Scrivilo qui" autocomplete="off" aria-label="Parola o nome da coprire"><button class="b" type="submit">Copri</button></form>
            </aside>
          </div>
          <footer class="dlg-f">
            <p class="st" aria-live="polite"></p>
            <button class="b cancel" type="button">Annulla</button>
            <button class="b retry" type="button" hidden>Riprova</button>
            <button class="b dl" type="button" hidden>${I.down}Scarica</button>
            <button class="b pri go" type="button" disabled>Inserisci nella chat <kbd>⌘↵</kbd></button>
          </footer>
        </section>
        <button class="selb" type="button" hidden>Copri la selezione</button>
      </div>

      <div class="lb" hidden>
        <div class="lb-h">
          <b class="lb-t"></b>
          <button class="ib lb-prev" type="button" aria-label="Pagina precedente">${I.prev}</button>
          <span class="pg lb-pg"></span>
          <button class="ib lb-next" type="button" aria-label="Pagina successiva">${I.next}</button>
          <button class="ib lb-dl" type="button" aria-label="Scarica">${I.down}</button>
          <button class="ib lb-x" type="button" aria-label="Chiudi">${I.x}</button>
        </div>
        <div class="lb-b"></div>
      </div>
    </div>`;

  const $ = (s) => root.querySelector(s);
  const app = $(".app"), fab = $(".fab"), pop = $(".pop"), toastEl = $(".toast"), out = $(".out");
  const ov = $(".ov"), dlg = $(".dlg"), lb = $(".lb");
  const sentDocs = [];  // documenti e testi inviati da questa scheda (solo in memoria)
  if (!/Mac|iPhone|iPad/.test(navigator.platform)) $(".go kbd").textContent = "Ctrl ↵";

  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function svg(markup) { const t = document.createElement("template"); t.innerHTML = markup; return t.content.firstChild; }

  const ensureMounted = () => {
    if (!host.isConnected) (document.body || document.documentElement).appendChild(host);
  };

  // chiaro o scuro come la pagina della chat (che puo' differire dal tema del sistema)
  function theme() {
    let dark = matchMedia("(prefers-color-scheme: dark)").matches;
    try {
      const m = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g);
      if (m && m.length >= 3 && (m[3] === undefined || +m[3] > 0.5)) dark = 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2] < 128;
    } catch (_) {}
    app.classList.toggle("dark", dark);
  }

  let toastTimer = 0, toastAction = null;
  function toast(msg, err = false, ms = 5000, action = null) {
    ensureMounted();
    $(".t-msg").textContent = msg;
    toastEl.classList.toggle("err", err);
    toastAction = action;
    const act = $(".t-act");
    act.hidden = !action;
    if (action) act.textContent = action.label;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; toastAction = null; }, ms);
  }
  $(".t-act").addEventListener("click", () => {
    const fn = toastAction?.fn;
    toastEl.hidden = true; toastAction = null;
    if (fn) fn();
  });

  // messaggio breve accanto al pulsante (senza toast): "Nessun dato personale", "Rilascia qui"...
  let sayTimer = 0, said = "";
  function say(text, ms = 1800) {
    said = text;
    clearTimeout(sayTimer);
    if (ms) sayTimer = setTimeout(() => { said = ""; render(); }, ms);
    render();
  }

  function render() {
    fab.classList.toggle("off", !active);
    fab.classList.toggle("busy", busy);
    fab.classList.toggle("say", Boolean(said));
    $(".fab-l").textContent = busy ? "Clin al lavoro…" : said || (active ? "Clin attivo" : "Clin in pausa: nulla viene coperto");
    $(".on").checked = active;
    $(".pop-s").textContent = active ? "Protezione attiva su questa chat" : "In pausa: testi e file passano in chiaro";
  }

  let pollTimer = 0;
  async function refresh() {
    const s = await send({ op: "status" }).catch(() => null);
    if (s?.ok) {
      active = s.attivo;
      const ner = s.ner?.state;
      const ready = s.engine && ner === "ready";
      $(".eng").classList.toggle("ok", ready);
      $(".eng-t").textContent = !s.engine ? "Motore in avvio…"
        : ner === "ready" ? `Motore pronto${s.n ? ` · ${s.n} segnaposto` : ""}`
        : ner === "downloading" ? `Modello dei nomi: download ${s.ner.progress}%`
        : ner === "loading" ? "Modello dei nomi in caricamento…"
        : "Attivo con le regole (modello dei nomi assente)";
      clearTimeout(pollTimer);
      if (!pop.hidden && (!s.engine || ner === "loading" || ner === "downloading")) pollTimer = setTimeout(refresh, 1500);
    }
    render();
  }

  function downloadFileObj(f) {
    const blob = new Blob([Uint8Array.from(atob(f.data), (c) => c.charCodeAt(0))], { type: f.type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = f.name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  function appendHighlighted(container, text) {
    let last = 0;
    for (const m of text.matchAll(/\[[A-Z_]+_\d+\]/g)) {
      container.append(document.createTextNode(text.slice(last, m.index)), el("mark", "", m[0]));
      last = m.index + m[0].length;
    }
    container.append(document.createTextNode(text.slice(last)));
  }

  // ---------------------------------------------------------------- anteprima a schermo intero
  let lbState = null;
  function drawLightbox() {
    const { title, pages, text, file, pageIdx } = lbState;
    $(".lb-t").textContent = title;
    const many = pages.length > 1;
    $(".lb-prev").hidden = $(".lb-next").hidden = $(".lb-pg").hidden = !many;
    $(".lb-dl").hidden = !file;
    const body = $(".lb-b");
    if (pages.length) {
      $(".lb-pg").textContent = `${pageIdx + 1} / ${pages.length}`;
      $(".lb-prev").disabled = pageIdx <= 0;
      $(".lb-next").disabled = pageIdx >= pages.length - 1;
      const img = el("img");
      img.src = pages[pageIdx]; img.alt = `${title}, pagina ${pageIdx + 1}`;
      body.replaceChildren(img);
    } else {
      const box = el("div", "txt");
      appendHighlighted(box, text || "Nessuna anteprima disponibile per questo file.");
      body.replaceChildren(box);
    }
    body.scrollTop = 0;
  }
  function openLightbox({ title, pages = [], text = "", file = null }) {
    ensureMounted(); theme();
    lbState = { title, pages, text, file, pageIdx: 0 };
    lb.hidden = false;
    drawLightbox();
  }
  const closeLightbox = () => { lb.hidden = true; lbState = null; };
  $(".lb-x").addEventListener("click", closeLightbox);
  $(".lb-prev").addEventListener("click", () => { lbState.pageIdx--; drawLightbox(); });
  $(".lb-next").addEventListener("click", () => { lbState.pageIdx++; drawLightbox(); });
  $(".lb-dl").addEventListener("click", () => { if (lbState?.file) downloadFileObj(lbState.file); });
  lb.addEventListener("click", (e) => { if (e.target === lb || e.target === $(".lb-b")) closeLightbox(); });

  // ---------------------------------------------------------------- pannello
  function showTab(which) {
    for (const b of root.querySelectorAll(".seg button")) b.classList.toggle("on", b.dataset.tab === which);
    $(".tab-ans").hidden = which !== "ans";
    $(".tab-sent").hidden = which !== "sent";
  }
  $(".seg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) showTab(b.dataset.tab); });

  function drawSent() {
    $(".sent-n").textContent = sentDocs.length;
    const list = $(".sent");
    list.replaceChildren();
    if (!sentDocs.length) {
      list.append(el("p", "hint", "Ancora nulla. I file e i testi anonimizzati inviati da questa scheda restano qui, per rivedere che cosa ha ricevuto l’IA."));
      return;
    }
    for (const d of sentDocs) {
      const card = el("button", "sc");
      card.type = "button";
      let thumb;
      if (d.pages?.length) { thumb = el("img", "sc-t"); thumb.src = d.pages[0]; thumb.alt = ""; }
      else { thumb = el("span", "sc-t"); thumb.append(svg(d.file ? I.file : I.text)); }
      const info = el("span");
      info.append(el("span", "sc-n", d.title), el("span", "sc-m", [d.time, d.pages?.length ? `${d.pages.length} pag.` : "", `${d.count} dati coperti`].filter(Boolean).join(" · ")));
      info.style.display = "grid"; info.style.minWidth = "0";
      card.append(thumb, info);
      card.addEventListener("click", () => openLightbox(d));
      list.append(card);
    }
  }
  function remember(entry) {
    sentDocs.unshift(entry);
    if (sentDocs.length > 20) sentDocs.length = 20;
    drawSent();
  }

  function showOut(text, empty = false) { out.textContent = text; out.classList.toggle("empty", empty); $(".copy").disabled = empty; }
  function openPanel() {
    ensureMounted(); theme();
    pop.hidden = false; toastEl.hidden = true;
    refresh(); drawSent(); restoreLast();
  }
  const closePanel = () => { pop.hidden = true; clearTimeout(pollTimer); };
  fab.addEventListener("click", () => (pop.hidden ? openPanel() : closePanel()));
  $(".pop-x").addEventListener("click", closePanel);
  $(".on").addEventListener("change", async (e) => { active = e.target.checked; render(); await send({ op: "toggle", attivo: active }).catch(() => {}); });
  $(".dz").addEventListener("click", () => $(".pick").click());
  $(".pick").addEventListener("change", (e) => {
    const files = [...(e.target.files || [])];
    e.target.value = "";
    if (!files.length) return;
    closePanel();
    handleFiles(captureFiles(files), { kind: "drop", target: composer() });
  });
  $(".forget").addEventListener("click", async () => {
    await send({ op: "forget" }).catch(() => {});
    sentDocs.length = 0; drawSent();
    showOut("Segnaposto e documenti inviati dimenticati.", true);
    refresh();
  });
  $(".copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(out.textContent); toast("Copiato con i dati reali: si può incollare nella cartella clinica."); }
    catch (_) { toast("Copia non riuscita: selezionare il testo nel pannello e copiarlo.", true); }
  });
  let lastSelection = "";
  document.addEventListener("selectionchange", () => {
    const t = String(getSelection() || "");
    if (t.trim()) lastSelection = t;
  });
  $(".sel").addEventListener("click", () => { mode = "sel"; restore(lastSelection, "Selezionare prima un testo nella chat, poi premere «Selezione»."); });
  $(".last").addEventListener("click", restoreLast);

  function answerText(el) {
    const blocks = [...el.querySelectorAll(MARKDOWN)].filter((b) => !b.parentElement.closest(MARKDOWN));
    if (blocks.length) return blocks.map((b) => b.innerText.trim()).join("\n\n");
    return el.innerText.replace(/^\s*\S+ (ha detto|ha risposto|said|says):?\s*\n/i, "");
  }
  const isUser = (el) => el.closest("[data-message-author-role='user'],[data-testid='user-message'],user-query");
  function lastAnswer() {
    for (const sel of ANSWERS) {
      const all = [...document.querySelectorAll(sel)].filter((e) => !isUser(e));
      if (all.length) return answerText(all[all.length - 1]);
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let last = null, n;
    while ((n = walker.nextNode())) if (PH.test(n.nodeValue) && !n.parentElement.closest("[contenteditable='true'],textarea")) last = n;
    let el = last?.parentElement;
    while (el?.parentElement && el.parentElement !== document.body && !isUser(el.parentElement)
           && el.parentElement.innerText.length < 20000) el = el.parentElement;
    return el && !isUser(el) ? answerText(el) : "";
  }
  async function restore(text, emptyMsg = "Quando l’IA risponde, qui compare la risposta con i nomi e i dati veri.") {
    if (!text.trim()) { showOut(emptyMsg, true); return; }
    const r = await send({ op: "restore", text }).catch(() => null);
    if (r?.ok) showOut(r.text); else showOut("Ripristino non riuscito: ricaricare la pagina e riprovare.", true);
  }
  let mode = "last", lastShown = "", watchTimer = 0;
  function restoreLast() { mode = "last"; const t = lastAnswer(); lastShown = t; restore(t); }
  new MutationObserver(() => {
    if (pop.hidden || mode !== "last") return;
    clearTimeout(watchTimer);
    watchTimer = setTimeout(() => { const t = lastAnswer(); if (t !== lastShown) { lastShown = t; restore(t); } }, 900);
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
    if (!msg || msg.target !== "content") return;
    if (msg.op === "panel") { openPanel(); reply({ ok: true }); }
    else if (msg.op === "progress" && rv) setProgress(msg.step, msg.pct);
  });

  const mount = () => { ensureMounted(); refresh(); send({ op: "warmup" }).catch(() => {}); };
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
  // i tasti premuti dentro Clin non devono arrivare alle scorciatoie della pagina
  for (const t of ["keydown", "keyup", "keypress"]) host.addEventListener(t, (e) => e.stopPropagation());

  // ---------------------------------------------------------------- intercettazione e consegna
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
    for (let i = 0; i < bytes.length; i += 0x2000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x2000));
    return btoa(s);
  }

  const MAX_FILE_BYTES = 35 * 1024 * 1024;

  function acceptsFile(input, wantImage) {
    const acc = (input.accept || "").trim();
    if (!acc || /\*\/\*/.test(acc)) return true;
    if (wantImage) return /image|\.(png|jpe?g|webp)/i.test(acc);
    return /pdf|application|word|sheet|csv|text|\.(pdf|docx|xlsx|csv|txt|md)/i.test(acc);
  }

  function fileInput(preferred, wantImage = false) {
    if (preferred && document.contains(preferred) && acceptsFile(preferred, wantImage)) return preferred;
    const comp = composer();
    const scopes = [
      comp?.closest?.("form, input-area-v2, [data-testid='composer-background'], main"),
      document,
    ].filter(Boolean);
    for (const scope of scopes) {
      const all = [...scope.querySelectorAll("input[type='file']")];
      const match = all.find((i) => !i.disabled && acceptsFile(i, wantImage));
      if (match) return match;
    }
    return null;
  }

  function dropZone(originTarget) {
    const comp = composer();
    const candidates = [
      originTarget && document.contains(originTarget) ? originTarget : null,
      document.querySelector("[xapfileselectordropzone]"),
      comp?.closest?.("input-area-v2, uploader, .input-area-container, [data-testid='composer-background'], form"),
      comp,
      document.querySelector("main"),
      document.body,
    ].filter(Boolean);
    return candidates[0] || null;
  }

  function makeDT(files) {
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    return dt;
  }

  async function deliver(files, origin) {
    const allImages = files.length > 0 && files.every((f) => (f.type || "").startsWith("image/"));
    passing = true;
    try {
      if (origin.kind === "input" && origin.input && document.contains(origin.input)) {
        origin.input.files = makeDT(files).files;
        origin.input.dispatchEvent(new Event("input", { bubbles: true }));
        origin.input.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      const comp = composer();
      if (origin.kind === "paste" && comp) {
        comp.focus();
        const ev = new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: makeDT(files) });
        comp.dispatchEvent(ev);
        if (ev.defaultPrevented) return true;
      }
      const input = fileInput(origin.input, allImages);
      if (input) {
        input.files = makeDT(files).files;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      if (comp) {
        comp.focus();
        const ev = new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: makeDT(files) });
        comp.dispatchEvent(ev);
        if (ev.defaultPrevented) return true;
      }
      const zone = dropZone(origin.target);
      if (!zone) return false;
      zone.dispatchEvent(new DragEvent("dragenter", { bubbles: true, cancelable: true, dataTransfer: makeDT(files) }));
      await new Promise((r) => setTimeout(r, 60));
      zone.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: makeDT(files) }));
      zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: makeDT(files) }));
      return true;
    } finally {
      passing = false;
    }
  }
  function readViaFileReader(file) {
    return new Promise((ok, ko) => {
      const fr = new FileReader();
      fr.onload = () => ok(fr.result);
      fr.onerror = () => ko(fr.error || new Error("FileReader error"));
      fr.readAsArrayBuffer(file);
    });
  }
  function readViaEntry(entry) {
    return new Promise((ok, ko) => {
      if (!entry || !entry.isFile) { ko(new Error("non è un file")); return; }
      entry.file((f) => f.arrayBuffer().then(ok, () => readViaFileReader(f).then(ok, ko)), ko);
    });
  }
  function captureFiles(files, entries = []) {
    return files.map((f, idx) => {
      const kind = kindOf(f);
      const ok = Boolean(kind && f.size <= MAX_FILE_BYTES);
      const entry = entries[idx] || null;
      const buf = ok
        ? f.arrayBuffer().catch(() => readViaFileReader(f)).catch((e) => (entry ? readViaEntry(entry) : Promise.reject(e)))
        : null;
      return { file: f, kind, buf };
    });
  }
  function readItems(captured) {
    const refused = [], tooLarge = [];
    const list = captured.map((c) => (c && "buf" in c ? c : { file: c, kind: kindOf(c), buf: null }));
    return Promise.all(list.map(async ({ file: f, kind, buf }) => {
      if (!kind) { refused.push(f.name); return null; }
      if (f.size > MAX_FILE_BYTES) { tooLarge.push(f.name); return null; }
      const ab = await (buf || f.arrayBuffer());
      return { kind, name: f.name, type: f.type, data: b64(ab) };
    })).then((items) => {
      if (refused.length) toast(`Non inviati (formato non supportato): ${refused.join(", ")}`, true, 8000);
      if (tooLarge.length) toast(`Non inviati (file oltre 35 MB): ${tooLarge.join(", ")}`, true, 8000);
      return items.filter(Boolean);
    });
  }

  // ---------------------------------------------------------------- revisione prima dell'invio
  // tipo di segnaposto -> titolo del gruppo nell'elenco (nell'ordine in cui compaiono)
  const KINDS = {
    PAZIENTE: "Pazienti", PERSONA: "Persone", MEDICO: "Medici", OPERATORE: "Operatori sanitari",
    DATA_NASCITA: "Date di nascita", DATA: "Date", CONTATTO: "Recapiti", INDIRIZZO: "Indirizzi",
    ID: "Documenti d’identità", ID_CLINICO: "Codici clinici", STRUTTURA: "Strutture sanitarie",
    PROVENIENZA: "Provenienza", IBAN: "Dati bancari", DOCUMENTO: "Documenti", DATO: "Aggiunti da te",
  };
  const ORDER = Object.keys(KINDS);
  const kindOf_ = (ph) => { const m = /^\[([A-Z_]+)_\d+\]$/.exec(ph); return m ? m[1] : "CODICE"; };
  const kindTitle = (k) => KINDS[k] || (k === "CODICE" ? "Codici" : k.charAt(0) + k.slice(1).toLowerCase().replace(/_/g, " "));
  const addList = [];  // parole aggiunte a mano: valgono per tutta la sessione della scheda
  let rv = null, rerunTimer = 0;

  function setProgress(stepText, pct) {
    if (stepText) $(".load-step").textContent = stepText;
    if (typeof pct !== "number") return;
    const p = Math.max(5, Math.min(100, Math.round(pct)));
    $(".bar div").style.width = p + "%";
    const stage = p < 60 ? 1 : p < 92 ? 2 : 3;  // lettura, riconoscimento, copia anonima
    [".p1", ".p2", ".p3"].forEach((s, i) => {
      $(s).classList.toggle("on", i + 1 === stage);
      $(s).classList.toggle("done", i + 1 < stage);
    });
  }

  function status(msg, err = false) { const s = $(".st"); s.textContent = msg; s.classList.toggle("err", err); }

  function openDialog() {
    ensureMounted(); theme();
    closePanel(); toastEl.hidden = true;
    dlg.classList.toggle("text", rv.op === "anonymize");
    dlg.classList.remove("updating");
    $(".dlg-s").textContent = rv.label;
    $(".load").hidden = false; $(".load").classList.remove("fail");
    $(".load-sub").textContent = "Nessun dato lascia questo computer";
    $(".dlg-b").hidden = true;
    $(".dl").hidden = $(".retry").hidden = $(".selb").hidden = true;
    $(".go").disabled = true;
    status("");
    setProgress("Avvio del motore locale…", 8);
    ov.hidden = false;
    dlg.focus();
  }

  async function startReview(op, items, label, finish, quiet = false) {
    ensureMounted();
    if (rv) {
      toast("Concludere prima la revisione aperta di Clin.", true);
      return;
    }
    rv = { op, items, label, finish, quiet, job: crypto.randomUUID(), delivered: false,
           keep: new Set(), kept: new Map(), result: null, fileIdx: 0, pageIdx: 0, zoom: 100 };
    if (!quiet) openDialog();
    await rerun();
  }

  function sendWithTimeout(msg, ms = 300000) {
    return Promise.race([
      send(msg),
      new Promise((_, rej) => setTimeout(() => rej(new Error("tempo massimo superato")), ms)),
    ]);
  }

  // i file viaggiano una volta sola per revisione: le spunte successive mandano solo le scelte
  async function callEngine(mine) {
    const base = { op: mine.op, job: mine.job, review: { keep: [...mine.keep], add: addList } };
    let r = await sendWithTimeout(mine.delivered ? base : { ...base, items: mine.items });
    if (!r?.ok && r?.error === "job-missing") r = await sendWithTimeout({ ...base, items: mine.items });
    if (r?.ok) mine.delivered = true;
    return r;
  }

  async function rerun() {
    if (!rv) return;
    const mine = rv;
    busy = true; render();
    $(".go").disabled = true;
    $(".retry").hidden = true;
    status("");
    if (mine.result) dlg.classList.add("updating");
    try {
      const r = await callEngine(mine);
      if (rv !== mine) return;
      if (!r?.ok) throw new Error(r?.error || "motore non disponibile");
      mine.result = r;
      if (mine.quiet && ov.hidden && !(r.found || []).length) {  // nulla da coprire: entra senza domande
        say("Nessun dato personale");
        await commit();
        return;
      }
      if (ov.hidden) openDialog();
      $(".load").hidden = true;
      $(".dlg-b").hidden = false;
      dlg.classList.remove("updating");
      drawReview();
      $(".go").disabled = false;
      $(".dl").hidden = mine.op !== "redact" || !r.files?.length;
    } catch (err) {
      if (rv !== mine) return;
      if (ov.hidden) openDialog();
      dlg.classList.remove("updating");
      const msg = String(err?.message || err);
      const reload = /Extension context invalidated|message port closed/i.test(msg);
      const text = reload ? "Clin è stato aggiornato: ricaricare questa pagina e riprovare."
        : `Anonimizzazione non riuscita (${msg}).`;
      if (mine.result) status(`${text} Nulla è stato inviato.`, true);
      else {
        $(".load").classList.add("fail");
        $(".load-step").textContent = text;
        $(".load-sub").textContent = "Nulla è stato inviato alla chat.";
      }
      $(".retry").hidden = reload;
    } finally {
      busy = false; render();
    }
  }
  // piu' spunte ravvicinate diventano una sola rielaborazione
  function queueRerun() {
    clearTimeout(rerunTimer);
    dlg.classList.add("updating");
    $(".go").disabled = true;
    rerunTimer = setTimeout(rerun, 220);
  }

  function drawPreview() {
    const pv = $(".pv"), r = rv.result;
    const bar = el("div", "pv-bar");
    pv.replaceChildren(bar);
    $(".selb").hidden = true;
    const textBox = (text) => {
      const box = el("div", "txt");
      appendHighlighted(box, text.replace(/\n{3,}/g, "\n\n"));
      return box;
    };
    if (rv.op === "anonymize") {
      bar.append(el("p", "pv-k", "Ciò che entra nella chat"));
      pv.append(textBox(r.text || ""));
      return;
    }
    const files = r.files || [];
    if (!files.length) return;
    rv.fileIdx = Math.min(rv.fileIdx, files.length - 1);
    const f = files[rv.fileIdx], pages = f.pages || [];
    rv.pageIdx = Math.min(rv.pageIdx, Math.max(0, pages.length - 1));
    if (files.length > 1) {
      const ft = el("div", "ft");
      files.forEach((fi, idx) => {
        const b = el("button", idx === rv.fileIdx ? "on" : "", fi.name);
        b.type = "button"; b.title = fi.name;
        b.addEventListener("click", () => { rv.fileIdx = idx; rv.pageIdx = 0; drawPreview(); });
        ft.append(b);
      });
      bar.append(ft);
    } else {
      bar.append(el("p", "pv-k", "Ciò che riceve l’IA"));
    }
    bar.append(el("span", "sp"));
    const ib = (icon, label, fn, disabled = false) => {
      const b = el("button", "ib"); b.type = "button"; b.setAttribute("aria-label", label); b.title = label;
      b.append(svg(icon)); b.disabled = disabled; b.addEventListener("click", fn);
      return b;
    };
    if (pages.length) {
      if (pages.length > 1) {
        bar.append(
          ib(I.prev, "Pagina precedente", () => { rv.pageIdx--; drawPreview(); }, rv.pageIdx <= 0),
          el("span", "pg", `${rv.pageIdx + 1} / ${pages.length}`),
          ib(I.next, "Pagina successiva", () => { rv.pageIdx++; drawPreview(); }, rv.pageIdx >= pages.length - 1),
        );
      }
      bar.append(
        ib(I.minus, "Riduci", () => { rv.zoom = Math.max(50, rv.zoom - 25); drawPreview(); }, rv.zoom <= 50),
        el("span", "pg", `${rv.zoom}%`),
        ib(I.plus, "Ingrandisci", () => { rv.zoom = Math.min(250, rv.zoom + 25); drawPreview(); }, rv.zoom >= 250),
      );
      const stage = el("div", "stage"), img = el("img");
      img.src = pages[rv.pageIdx];
      img.alt = `${f.name}, pagina ${rv.pageIdx + 1}`;
      img.style.width = rv.zoom + "%";
      stage.append(img);
      pv.append(stage);
    } else {
      pv.append(textBox(f.previewText || "Anteprima non disponibile per questo file: i dati elencati a destra sono stati coperti."));
    }
  }

  function drawReview() {
    const r = rv.result;
    const groups = new Map();  // segnaposto -> valori originali
    for (const [ph, orig] of r.found || []) {
      if (!groups.has(ph)) groups.set(ph, new Set());
      groups.get(ph).add(orig);
    }
    const kept = [...rv.kept].filter(([ph]) => !groups.has(ph));
    $(".cnt b").textContent = groups.size;
    $(".cnt span").textContent = groups.size === 1 ? "dato coperto" : "dati coperti";
    const cs = $(".cnt-s");
    cs.classList.toggle("w", kept.length > 0);
    cs.textContent = kept.length ? `${kept.length} ${kept.length === 1 ? "lasciato" : "lasciati"} in chiaro per tua scelta`
      : groups.size ? "Spegnere un interruttore per lasciare un dato in chiaro." : "";
    drawPreview();

    const rows = [...[...groups].map(([ph, o]) => [ph, o, true]), ...kept.map(([ph, o]) => [ph, o, false])];
    const rank = (ph) => { const i = ORDER.indexOf(kindOf_(ph)); return i < 0 ? ORDER.length : i; };
    rows.sort((a, b) => rank(a[0]) - rank(b[0]));
    const list = $(".list");
    list.replaceChildren();
    let current = null;
    for (const [ph, originals, on] of rows) {
      const k = kindOf_(ph);
      if (k !== current) { current = k; list.append(el("p", "gk", kindTitle(k))); }
      const lab = el("label", "it" + (on ? "" : " off"));
      const cb = el("input", "sw"); cb.type = "checkbox"; cb.checked = on;
      cb.setAttribute("aria-label", `Coprire ${[...originals].join(", ")}`);
      cb.addEventListener("change", () => toggle(ph, originals, cb.checked, lab));
      lab.append(el("span", "it-v", [...originals].join(" · ")), el("span", "it-p", on ? ph : "in chiaro"), cb);
      list.append(lab);
    }
    if (!rows.length) list.append(el("p", "none", "Nessun dato personale riconosciuto. Se ne manca uno, scriverlo qui sotto."));
    const notes = $(".notes");
    notes.hidden = !r.notes?.length;
    notes.textContent = (r.notes || []).join(" ");
  }

  function toggle(ph, originals, on, row) {
    if (!rv) return;
    row.classList.toggle("off", !on);
    if (on) {
      rv.kept.delete(ph);
      for (const o of originals) rv.keep.delete(o);
    } else {
      rv.kept.set(ph, originals);
      for (const o of originals) {
        rv.keep.add(o);
        const i = addList.findIndex((a) => a.toLowerCase() === o.toLowerCase());
        if (i >= 0) addList.splice(i, 1);
      }
    }
    queueRerun();
  }

  function addWord(word) {
    word = (word || "").replace(/\s+/g, " ").trim();
    if (!rv || word.length < 2) return;
    if (/\[[A-Z_]+_\d+\]/.test(word)) { status("Selezionare solo testo in chiaro, non un segnaposto.", true); return; }
    if (!addList.some((a) => a.toLowerCase() === word.toLowerCase())) addList.push(word);
    for (const o of [...rv.keep]) if (o.toLowerCase() === word.toLowerCase()) rv.keep.delete(o);
    $(".word").value = "";
    $(".selb").hidden = true;
    queueRerun();
  }

  function closeReview() {
    clearTimeout(rerunTimer);
    if (rv) send({ op: "release", job: rv.job }).catch(() => {});
    rv = null;
    ov.hidden = true;
    $(".pv").replaceChildren(); $(".list").replaceChildren();  // i dati reali non restano nel DOM
  }
  async function commit() {
    if (!rv?.result) return;
    const { result, finish } = rv;
    closeReview();
    try { await finish(result); }
    catch (err) { console.error("[Clin]", err); toast(`Inserimento non riuscito (${err.message}). Nulla è stato inviato alla chat.`, true, 10000); }
  }
  const cancel = () => { if (rv) { closeReview(); toast("Annullato: nulla è stato inserito nella chat."); } };

  $(".retry").addEventListener("click", () => { if (!rv) return; if (!rv.result) openDialog(); rerun(); });
  $(".add").addEventListener("submit", (e) => { e.preventDefault(); addWord($(".word").value); });
  $(".cancel").addEventListener("click", cancel);
  $(".dlg-x").addEventListener("click", cancel);
  $(".go").addEventListener("click", commit);
  $(".dl").addEventListener("click", () => {
    if (!rv?.result?.files?.length) return;
    for (const f of rv.result.files) downloadFileObj(f);
    status("File anonimizzato salvato nei Download.");
  });
  // testo selezionato nell'anteprima -> pulsante «Copri la selezione» accanto alla selezione
  const selectionIn = () => (root.getSelection ? root.getSelection() : getSelection());
  $(".pv").addEventListener("mouseup", () => setTimeout(() => {
    const sel = selectionIn(), text = String(sel || "").trim(), btn = $(".selb");
    if (!rv || text.length < 2 || text.length > 80 || !sel.rangeCount) { btn.hidden = true; return; }
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    if (!rect.width) { btn.hidden = true; return; }
    btn.textContent = `Copri «${text.length > 28 ? text.slice(0, 27) + "…" : text}»`;
    btn.dataset.word = text;
    btn.style.left = Math.max(8, Math.min(innerWidth - 240, rect.left)) + "px";
    btn.style.top = Math.min(innerHeight - 44, rect.bottom + 6) + "px";
    btn.hidden = false;
  }));
  $(".selb").addEventListener("click", (e) => addWord(e.currentTarget.dataset.word));
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!lb.hidden) closeLightbox();
      else if (rv && !ov.hidden) cancel();
      else if (!pop.hidden) closePanel();
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && rv && !ov.hidden && !$(".go").disabled) {
      e.preventDefault();
      commit();
    }
  });

  const nowTime = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const countOf = (r) => new Set((r.found || []).map((x) => x[0])).size;

  async function handleFiles(files, origin) {
    try {
      const items = await readItems(files);
      if (!items.length) return;
      const label = items.length === 1 ? items[0].name : `${items.length} file`;
      await startReview("redact", items, label, async (r) => {
        const out = r.files.map((f) => new File([Uint8Array.from(atob(f.data), (c) => c.charCodeAt(0))], f.name, { type: f.type }));
        if (!(await deliver(out, origin))) throw new Error("allegato non accettato dal sito");
        const count = countOf(r), time = nowTime();
        const entries = r.files.map((f) => ({ title: f.name, pages: f.pages || [], text: f.previewText || "", file: f, count, time }));
        for (const e of [...entries].reverse()) remember(e);
        toast(out.length === 1 ? `Allegato con i dati coperti: ${out[0].name}` : `Allegati ${out.length} file con i dati coperti.`,
              false, 8000, { label: "Rivedi", fn: () => openLightbox(entries[0]) });
      });
    } catch (err) {
      console.warn("[Clin handleFiles]", err);
      const raw = String(err?.message || err);
      const msg = /could not be found|NotFoundError/i.test(raw)
        ? "Chrome non lascia leggere i file trascinati dalla barra dei download: aprire Clin e usare «Scegli o trascina un file», oppure trascinarlo dalla cartella."
        : `Impossibile leggere il file (${raw}).`;
      toast(msg, true, 9000);
    }
  }

  async function handle({ text = "" }, target) {
    try {
      if (!text.trim()) return;
      const items = [{ kind: "testo incollato", text }];
      await startReview("anonymize", items, "Testo incollato", (r) => {
        const el = target && editable(target) && document.contains(target) ? target : composer();
        if (!el) throw new Error("campo della chat non trovato");
        const filled = (el.value ?? el.innerText ?? "").trim().length > 0;
        let body = (filled ? "\n\n" : "") + r.text.replace(/\n{3,}/g, "\n\n");
        if (el.isContentEditable) body = body.replace(/\n\n/g, "\n");
        insert(el, body);
        const count = countOf(r);
        if (!count) return;  // testo senza dati personali: nessuna traccia, nessun avviso
        const entry = { title: "Testo incollato", pages: [], text: r.text, file: null, count, time: nowTime() };
        remember(entry);
        toast(`Testo inserito: ${count} ${count === 1 ? "dato coperto" : "dati coperti"}.`, false, 6000, { label: "Rivedi", fn: () => openLightbox(entry) });
      }, text.length <= QUIET_MAX);
    } catch (err) {
      console.warn("[Clin handle]", err);
      toast(`Errore di Clin (${err?.message || err}). Nulla è stato inviato.`, true, 8000);
    }
  }

  const stop = (e) => { e.preventDefault(); e.stopImmediatePropagation(); e.stopPropagation(); };
  const inClin = (e) => e.target === host || e.composedPath?.().includes(host);

  function droppedFiles(dt) {
    if (!dt) return [];
    if (dt.files && dt.files.length) return [...dt.files];
    if (dt.items && dt.items.length) {
      return [...dt.items].filter((it) => it.kind === "file").map((it) => it.getAsFile()).filter(Boolean);
    }
    return [];
  }
  function droppedEntries(dt) {
    if (!dt?.items?.length) return [];
    return [...dt.items].filter((it) => it.kind === "file").map((it) => {
      try { return it.webkitGetAsEntry ? it.webkitGetAsEntry() : null; } catch (_) { return null; }
    });
  }

  window.addEventListener("paste", (e) => {
    if (passing || !active || inClin(e)) return;
    const ed = e.target?.closest?.("[contenteditable],textarea,input") || (editable(e.target) ? e.target : null);
    if (ed && ed.tagName === "INPUT" && !/^(text|search)$/.test(ed.type)) return;
    const dt = e.clipboardData;
    if (!dt) return;
    const files = droppedFiles(dt);
    const text = files.length ? "" : dt.getData("text/plain");
    if (!files.length && !text) return;
    const captured = files.length ? captureFiles(files) : [];
    stop(e);
    const target = editable(ed) ? ed : composer();
    if (captured.length) handleFiles(captured, { kind: "paste", target: target || e.target });
    else handle({ text }, target);
  }, true);

  // mentre un file viene trascinato sulla pagina, il pulsante dice che cosa succedera' al rilascio
  window.addEventListener("dragover", (e) => {
    if (!active || rv || !e.dataTransfer?.types?.includes("Files")) return;
    if (inClin(e)) e.preventDefault();  // il pannello di Clin accetta il rilascio
    say("Rilascia: Clin copre i dati prima dell’invio", 700);
  }, true);

  window.addEventListener("drop", (e) => {
    if (passing || !active) return;
    const files = droppedFiles(e.dataTransfer);
    if (!files.length) return;
    const captured = captureFiles(files, droppedEntries(e.dataTransfer));
    const mine = inClin(e);  // rilasciato sul pannello di Clin: il file va consegnato al campo della chat
    const target = mine ? composer() : e.target;
    stop(e);
    if (mine) closePanel();
    else for (const t of ["dragleave", "dragend"]) {
      try { target.dispatchEvent(new DragEvent(t, { bubbles: true, cancelable: true, dataTransfer: new DataTransfer() })); } catch (_) {}
    }
    handleFiles(captured, { kind: "drop", target });
  }, true);

  const onPick = (e) => {
    const input = e.target;
    if (passing || !active || input?.tagName !== "INPUT" || input.type !== "file" || !input.files?.length) return;
    stop(e);
    const captured = captureFiles([...input.files]);
    input.value = "";
    handleFiles(captured, { kind: "input", input });
  };
  window.addEventListener("input", onPick, true);
  window.addEventListener("change", onPick, true);
})();
