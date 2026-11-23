// Clin - nella pagina della chat (ChatGPT, Claude, Gemini...).
//
// Quando Clin e' attivo, testo incollato, file trascinati e file scelti vengono fermati PRIMA
// che il sito li riceva: si anonimizzano sul computer, si aprono nella barra di revisione
// (con anteprima visiva reale dei PDF/foto, zoom, 2 colonne stile desktop, collassabile)
// e solo con «Inserisci nella chat» entrano nel sito. I documenti inviati restano
// consultabili in anteprima dal pannello /Clin per tutta la sessione della scheda.
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
  let active = true, busy = false, passing = false;

  const send = (msg) => chrome.runtime.sendMessage({ target: "background", ...msg });

  // ---------------------------------------------------------------- interfaccia (shadow DOM chiuso)
  const host = document.createElement("clin-panel");
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }
      [hidden] { display: none !important; }
      .pill { position: fixed; right: 18px; bottom: 18px; z-index: 2147483646; display: flex; align-items: center; gap: 0;
              height: 44px; padding: 0 5px; border: 0; border-radius: 22px; background: #101411; color: #fff;
              font-size: 13px; font-weight: 600; letter-spacing: -.01em; cursor: pointer;
              box-shadow: 0 8px 24px rgba(16,20,17,.28), 0 0 0 1px rgba(255,255,255,.06) inset;
              transition: gap .2s, padding .2s, background .2s, opacity .2s; opacity: .94; }
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
      @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
      @keyframes pulse { 0%, 100% { opacity: .45; } 50% { opacity: .9; } }

      .panel { position: fixed; right: 18px; bottom: 72px; z-index: 2147483647; width: min(440px, calc(100vw - 36px));
               max-height: min(660px, calc(100vh - 100px)); display: flex; flex-direction: column; gap: 10px; padding: 16px;
               border-radius: 20px; background: #fff; color: #101411; box-shadow: 0 18px 50px rgba(0,0,0,.22); font-size: 14px; }
      .head { display: flex; align-items: center; gap: 10px; }
      .head b { font-size: 15px; }
      .head .tag, .rv-head .tag, .lb-head .tag { padding: 3px 9px; border-radius: 999px; background: #d4f06b; color: #101411; font-size: 12px; font-weight: 700; letter-spacing: -.01em; }
      .head button { margin-left: auto; }
      label.sw { display: flex; align-items: center; gap: 8px; color: #3d423e; font-size: 13px; }
      .muted { color: #6a706b; font-size: 12.5px; line-height: 1.45; margin: 0; }
      .p-tabs { display: flex; gap: 4px; padding: 4px; border-radius: 999px; background: #f0f2ec; }
      .p-tabs button { flex: 1; padding: 7px 10px; font-size: 12.5px; background: transparent; color: #5c625d; }
      .p-tabs button.on { background: #fff; color: #101411; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
      .out { flex: 1; min-height: 120px; overflow: auto; white-space: pre-wrap; padding: 10px 12px; border-radius: 12px;
             background: #f3f4f1; font-size: 13.5px; line-height: 1.5; }
      .sent-list { flex: 1; min-height: 120px; max-height: 340px; overflow: auto; display: grid; gap: 8px; align-content: start; }
      .sent-card { display: grid; grid-template-columns: 48px 1fr auto; align-items: center; gap: 10px; padding: 8px 10px;
                   border-radius: 13px; background: #f6f7f4; border: 1px solid #eceee9; }
      .sent-thumb { width: 48px; height: 60px; border-radius: 8px; background: #e5e8e0; object-fit: cover; border: 1px solid #dde0d8; cursor: pointer; display: grid; place-items: center; font-size: 20px; }
      .sent-info { min-width: 0; }
      .sent-name { font-weight: 600; font-size: 13px; color: #101411; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .sent-meta { font-size: 11.5px; color: #6a706b; margin-top: 2px; }
      .sent-act { display: flex; gap: 4px; }
      .sent-act button { padding: 6px 10px; font-size: 12px; }

      .row { display: flex; flex-wrap: wrap; gap: 8px; }
      button { border: 0; border-radius: 999px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
               background: #f3f4f1; color: #101411; transition: background .15s, transform .08s, color .15s; }
      button:hover { background: #e8ebe4; }
      button:active { transform: scale(.98); }
      button.dark { background: #101411; color: #fff; }
      button.dark:hover { background: #262c28; }
      button.x { padding: 5px 10px; background: transparent; font-size: 18px; line-height: 1; color: #4c524d; }
      button.x:hover { background: #f3f4f1; color: #101411; }

      .toast { position: fixed; right: 18px; bottom: 72px; z-index: 2147483647; max-width: 400px; padding: 10px 14px;
               border-radius: 14px; background: #101411; color: #fff; font-size: 13px; line-height: 1.45;
               box-shadow: 0 10px 30px rgba(0,0,0,.25); display: flex; align-items: center; gap: 10px; }
      .toast.err { background: #c8312f; }
      .toast .t-act { flex: none; padding: 5px 10px; font-size: 12px; background: #d4f06b; color: #101411; border-radius: 999px; }

      /* ---------------- barra di revisione (stile desktop a 2 colonne, espandibile e collassabile) */
      .rev { position: fixed; top: 10px; right: 10px; bottom: 10px; z-index: 2147483647; width: min(460px, calc(100vw - 20px));
             display: flex; flex-direction: column; border-radius: 22px; background: rgba(255,255,255,.98); color: #101411;
             backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
             border: 1px solid rgba(16,20,17,.08); box-shadow: -14px 12px 48px rgba(16,20,17,.22); font-size: 14px;
             transform: translateX(calc(100% + 28px)); opacity: 0; pointer-events: none; visibility: hidden;
             transition: transform .36s cubic-bezier(.16, 1, .3, 1), opacity .24s ease, width .28s cubic-bezier(.16, 1, .3, 1), visibility 0s linear .36s; }
      .rev.wide { width: min(980px, calc(100vw - 24px)); }
      .rev.open { transform: translateX(0); opacity: 1; pointer-events: auto; visibility: visible;
                  transition: transform .36s cubic-bezier(.16, 1, .3, 1), opacity .24s ease, width .28s cubic-bezier(.16, 1, .3, 1), visibility 0s linear 0s; }
      .rev.collapsed { transform: translateX(calc(100% + 28px)); opacity: 0; pointer-events: none; visibility: hidden;
                       transition: transform .3s cubic-bezier(.4, 0, .2, 1), opacity .2s ease, visibility 0s linear .3s; }

      .rv-tab { position: fixed; right: 0; top: 50%; z-index: 2147483647; display: flex; align-items: center; gap: 8px;
                padding: 10px 14px 10px 12px; border-radius: 16px 0 0 16px; background: #101411; color: #fff;
                box-shadow: -8px 8px 28px rgba(16,20,17,.26); font-size: 13px; font-weight: 600;
                transform: translate(110%, -50%); opacity: 0; pointer-events: none; visibility: hidden;
                transition: transform .32s cubic-bezier(.16, 1, .3, 1), opacity .2s ease, background .15s, visibility 0s linear .32s; }
      .rv-tab.show { transform: translate(0, -50%); opacity: 1; pointer-events: auto; visibility: visible;
                     transition: transform .32s cubic-bezier(.16, 1, .3, 1), opacity .2s ease, background .15s, visibility 0s linear 0s; }
      .rv-tab:hover { background: #1e2621; }
      .rv-tab .arr { font-size: 15px; color: #d4f06b; line-height: 1; }
      .rv-tab .badge { padding: 2px 7px; border-radius: 999px; background: #d4f06b; color: #101411; font-size: 11.5px; font-weight: 700; }
      .rv-tab .spin-sm { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(255,255,255,.25); border-top-color: #d4f06b; animation: spin .8s linear infinite; display: none; }
      .rv-tab.loading .spin-sm { display: block; }
      .rv-tab.loading .badge { display: none; }

      .rv-head { display: flex; align-items: center; gap: 8px; padding: 13px 14px 11px 16px; border-bottom: 1px solid #eceee9; flex: none; }
      .rv-head b { font-size: 15px; letter-spacing: -.01em; }
      .rv-head-act { margin-left: auto; display: flex; align-items: center; gap: 4px; }
      .rv-icobtn { width: 32px; height: 32px; padding: 0; display: grid; place-items: center; border-radius: 10px;
                   background: #f3f4f1; color: #2b312d; font-size: 15px; line-height: 1; }
      .rv-icobtn:hover { background: #e6e9e2; color: #101411; }

      .rv-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 16px 0; flex: none; }
      .rv-sum { margin: 0; color: #3d423e; font-size: 13px; line-height: 1.4; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .rv-sum strong { color: #101411; }
      .rv-local { flex: none; display: inline-flex; align-items: center; gap: 5px; padding: 3px 8px; border-radius: 999px;
                  background: #eef6ef; color: #2e6b3c; font-size: 11.5px; font-weight: 600; }
      .rv-local::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: #3c7a4b; }

      .rv-loader { margin: 12px 16px 0; padding: 16px; border-radius: 16px; background: #f6f7f4; border: 1px solid #eceee9; display: none; flex-direction: column; gap: 12px; }
      .rv-loader.show { display: flex; }
      .rv-ld-top { display: flex; align-items: center; gap: 12px; }
      .rv-spin { flex: none; width: 28px; height: 28px; border-radius: 50%; border: 3px solid #e4e7df; border-top-color: #101411; border-right-color: #3c7a4b; animation: spin .75s linear infinite; }
      .rv-ld-txt { flex: 1; min-width: 0; }
      .rv-ld-step { font-size: 13.5px; font-weight: 600; color: #101411; margin: 0; }
      .rv-ld-sub { font-size: 12px; color: #6a706b; margin: 2px 0 0; }
      .rv-ld-pct { font-size: 12.5px; font-weight: 700; color: #2e6b3c; font-variant-numeric: tabular-nums; }
      .rv-bar { height: 7px; border-radius: 999px; background: #e5e8e0; overflow: hidden; }
      .rv-bar-fill { height: 100%; width: 12%; border-radius: 999px; background: linear-gradient(90deg, #3c7a4b, #9fd94b, #d4f06b);
                     background-size: 200% 100%; animation: shimmer 1.8s linear infinite; transition: width .35s cubic-bezier(.16, 1, .3, 1); }
      .rv-skels { display: grid; gap: 8px; margin-top: 2px; }
      .rv-skel { height: 42px; border-radius: 12px; background: #ebede7; animation: pulse 1.3s ease-in-out infinite; }
      .rv-skel:nth-child(2) { animation-delay: .15s; opacity: .75; }
      .rv-skel:nth-child(3) { animation-delay: .3s; opacity: .55; }

      .rv-updating { margin: 8px 16px 0; padding: 7px 12px; border-radius: 10px; background: #eef6ef; color: #2e6b3c;
                     font-size: 12.5px; font-weight: 600; display: none; align-items: center; gap: 8px; flex: none; }
      .rv-updating.show { display: flex; }
      .rv-updating .u-spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(46,107,60,.25); border-top-color: #2e6b3c; animation: spin .75s linear infinite; }

      /* corpo: 1 colonna stretta, 2 colonne affiancate quando .rev.wide */
      .rv-body { flex: 1; min-height: 0; overflow: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 14px; }
      .rv-body.hide { display: none; }
      .rev.wide .rv-body { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(300px, .85fr); gap: 16px; overflow: hidden; padding: 12px 16px; }
      .rv-pane-doc, .rv-pane-ctrl { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
      .rev.wide .rv-pane-doc, .rev.wide .rv-pane-ctrl { overflow: auto; padding-right: 2px; }

      .rv-k { margin: 0 0 6px; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: #6a706b; }
      .rv-prev { max-height: 240px; overflow: auto; white-space: pre-wrap; padding: 12px 13px; border-radius: 14px; background: #f6f7f4;
                 border: 1px solid #eceee9; font-size: 13px; line-height: 1.55; user-select: text; }
      .rev.wide .rv-prev { flex: 1; max-height: none; }
      .rv-prev mark { background: #101411; color: #d4f06b; border-radius: 5px; padding: 1px 4px; font-weight: 600; font-size: 12px; }

      /* visualizzatore pagine PDF/foto */
      .doc-viewer { display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0; }
      .doc-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 12px; background: #f3f4f1; }
      .doc-bar .doc-ftabs { display: flex; gap: 4px; flex-wrap: wrap; }
      .doc-bar .ftab { padding: 4px 9px; font-size: 12px; border-radius: 8px; background: transparent; color: #5c625d; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .doc-bar .ftab.on { background: #fff; color: #101411; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
      .doc-bar .doc-nav { margin-left: auto; display: flex; align-items: center; gap: 4px; }
      .doc-bar .navbtn { padding: 4px 9px; font-size: 12px; border-radius: 8px; background: #fff; color: #101411; }
      .doc-bar .navbtn:disabled { opacity: .4; cursor: default; }
      .doc-bar .pg-lbl { font-size: 12px; font-weight: 600; color: #3d423e; padding: 0 4px; font-variant-numeric: tabular-nums; }
      .doc-stage { flex: 1; min-height: 220px; max-height: 360px; overflow: auto; border-radius: 14px; background: #e8ebe4;
                   border: 1px solid #dde0d8; padding: 10px; display: flex; justify-content: center; align-items: flex-start; }
      .rev.wide .doc-stage { max-height: none; min-height: 340px; }
      .doc-stage img { display: block; width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 16px rgba(0,0,0,.14); cursor: zoom-in; transition: width .15s; background: #fff; }
      .doc-hint { font-size: 11.5px; color: #6a706b; margin: 0; text-align: center; }

      .rv-list { display: grid; gap: 6px; }
      .rv-item { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 13px;
                 background: #f6f7f4; border: 1px solid transparent; cursor: pointer; transition: background .15s, border-color .15s; }
      .rv-item:hover { background: #eff1ec; border-color: #e1e4dc; }
      .rv-item input { width: 18px; height: 18px; margin: 0; accent-color: #3c7a4b; cursor: pointer; }
      .rv-item .v { min-width: 0; overflow-wrap: anywhere; font-weight: 600; font-size: 13px; color: #101411; }
      .rv-item .c { display: block; font-weight: 400; font-size: 11.5px; color: #6a706b; margin-top: 1px; }
      .rv-item .ph { padding: 3px 7px; border-radius: 7px; background: #101411; color: #d4f06b; font-size: 11px; font-weight: 600; white-space: nowrap; }
      .rv-item.off { background: #fff6e8; border-color: #f3dfbd; }
      .rv-item.off .v { text-decoration: line-through; text-decoration-color: rgba(16,20,17,.35); color: #5c5140; }
      .rv-item.off .ph { background: #b8640a; color: #fff; }

      .rv-add { display: flex; gap: 6px; }
      .rv-add input { flex: 1; min-width: 0; padding: 9px 13px; border: 1px solid #dde0d8; border-radius: 999px; font-size: 13.5px; background: #fff; color: #101411; }
      .rv-add input:focus { outline: 2px solid #3c7a4b; outline-offset: 1px; border-color: transparent; }

      .rv-foot { margin-top: auto; flex: none; display: grid; gap: 8px; padding: 12px 16px 14px; border-top: 1px solid #eceee9; background: rgba(255,255,255,.94); border-radius: 0 0 22px 22px; }
      .rv-foot-row { display: flex; gap: 8px; }
      .rv-foot .go { flex: 1; min-height: 44px; font-size: 14px; background: #101411; color: #fff; }
      .rv-foot .go:hover:not(:disabled) { background: #222b25; }
      .rv-foot .go:disabled { background: #e9ebe6; color: #9ba19c; cursor: default; transform: none; }
      .rv-foot .rv-dl { min-height: 44px; padding: 0 14px; background: #eef6ef; color: #2e6b3c; }
      .rv-foot .rv-dl:hover { background: #dff0e2; }
      .rv-foot .rv-cancel { min-height: 44px; padding: 0 16px; }
      .rv-foot .rv-retry { min-height: 40px; background: #d4f06b; color: #101411; display: none; }
      .rv-foot .rv-retry.show { display: block; }
      .rv-st { margin: 0; min-height: 1.1em; font-size: 12.5px; color: #6a706b; text-align: center; }
      .rv-st.err { color: #c8312f; font-weight: 500; }

      /* lightbox schermo intero per anteprima documento (prima e dopo l'invio) */
      .lb { position: fixed; inset: 0; z-index: 2147483647; background: rgba(16,20,17,.84); backdrop-filter: blur(8px);
            display: flex; flex-direction: column; padding: 18px; color: #fff; }
      .lb-head { display: flex; align-items: center; gap: 10px; max-width: 1100px; width: 100%; margin: 0 auto 12px; }
      .lb-head b { font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .lb-act { margin-left: auto; display: flex; align-items: center; gap: 6px; }
      .lb-act button { background: rgba(255,255,255,.14); color: #fff; padding: 7px 12px; font-size: 13px; }
      .lb-act button:hover { background: rgba(255,255,255,.24); }
      .lb-act .lb-pg { font-size: 13px; font-weight: 600; padding: 0 6px; }
      .lb-body { flex: 1; min-height: 0; overflow: auto; display: flex; justify-content: center; align-items: flex-start; padding: 6px; }
      .lb-body img { max-width: 100%; width: min(920px, 100%); height: auto; border-radius: 10px; box-shadow: 0 20px 60px rgba(0,0,0,.45); background: #fff; }
      .lb-body .lb-txt { max-width: 820px; width: 100%; background: #fff; color: #101411; padding: 20px 24px; border-radius: 14px; white-space: pre-wrap; line-height: 1.6; font-size: 14px; }
      .lb-body .lb-txt mark { background: #101411; color: #d4f06b; border-radius: 4px; padding: 1px 4px; font-weight: 600; }

      @media (max-width: 880px) {
        .rev.wide { width: calc(100vw - 20px); }
        .rev.wide .rv-body { display: flex; flex-direction: column; overflow: auto; }
      }
    </style>

    <button class="pill" part="pill" title="Clin: anonimizzazione locale">
      <span class="logo"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16" fill="#d4f06b"/><g transform="rotate(-8 16 16)"><path d="M10.2 7.5h8.6l4.2 4.2v12.1a1.4 1.4 0 0 1-1.4 1.4H10.2a1.4 1.4 0 0 1-1.4-1.4V8.9a1.4 1.4 0 0 1 1.4-1.4z" fill="#101411"/><path d="M18.6 7.5v4.4h4.4" fill="#3c7a4b"/><rect x="11.3" y="13.6" width="9.4" height="1.5" rx=".75" fill="#d4f06b"/><rect x="11.3" y="17" width="9.4" height="3" rx="1" fill="#d4f06b"/><rect x="11.3" y="21.8" width="5.6" height="1.5" rx=".75" fill="#d4f06b"/></g></svg><span class="state"></span><span class="ring"></span></span>
      <span class="lbl">/Clin attivo</span>
    </button>
    <div class="toast" hidden><span class="t-msg"></span><button class="t-act" type="button" hidden>Vedi anteprima</button></div>

    <button class="rv-tab" type="button" title="Riapri la revisione di Clin">
      <span class="arr" aria-hidden="true">«</span>
      <span>/Clin</span>
      <span class="spin-sm" aria-hidden="true"></span>
      <span class="badge">0</span>
    </button>

    <aside class="rev" aria-label="Revisione dei dati coperti">
      <div class="rv-head">
        <span class="tag">/Clin</span>
        <b>Controlla prima di inviare</b>
        <div class="rv-head-act">
          <button class="rv-icobtn rv-wide" type="button" title="Espandi / riduci vista a 2 colonne">⤢</button>
          <button class="rv-icobtn rv-col" type="button" title="Riduci a icona lateralmente">»</button>
          <button class="rv-icobtn rv-x" type="button" title="Annulla e chiudi">×</button>
        </div>
      </div>

      <div class="rv-meta">
        <p class="rv-sum"></p>
        <span class="rv-local">Locale</span>
      </div>

      <div class="rv-loader">
        <div class="rv-ld-top">
          <div class="rv-spin" aria-hidden="true"></div>
          <div class="rv-ld-txt">
            <p class="rv-ld-step">Avvio del motore locale…</p>
            <p class="rv-ld-sub">Nessun dato lascia questo computer</p>
          </div>
          <span class="rv-ld-pct">10%</span>
        </div>
        <div class="rv-bar"><div class="rv-bar-fill"></div></div>
        <div class="rv-skels"><div class="rv-skel"></div><div class="rv-skel"></div><div class="rv-skel"></div></div>
      </div>

      <div class="rv-updating"><span class="u-spin" aria-hidden="true"></span><span class="u-txt">Aggiornamento anteprima…</span></div>

      <div class="rv-body hide">
        <div class="rv-pane-doc">
          <div class="rv-preview"></div>
        </div>
        <div class="rv-pane-ctrl">
          <div>
            <p class="rv-k">Dati coperti · togliere la spunta per lasciarli in chiaro</p>
            <div class="rv-list"></div>
          </div>
          <div>
            <p class="rv-k">Manca qualcosa? Coprire anche</p>
            <div class="rv-add"><input class="rv-word" placeholder="Parola o nome da coprire" autocomplete="off"><button class="rv-plus" type="button">Aggiungi</button></div>
            <p class="muted rv-selhint" style="margin-top:6px">Oppure selezionare la parola nell'anteprima e premere «Copri selezione».</p>
            <div class="row" style="margin-top:6px"><button class="rv-sel" type="button">Copri selezione</button></div>
          </div>
        </div>
      </div>

      <div class="rv-foot">
        <button class="rv-retry" type="button">Riprova</button>
        <div class="rv-foot-row">
          <button class="dark go" type="button" disabled>Inserisci nella chat</button>
          <button class="rv-dl" type="button" hidden title="Salva i file anonimizzati sul computer">Scarica</button>
          <button class="rv-cancel" type="button">Annulla</button>
        </div>
        <p class="rv-st" aria-live="polite"></p>
      </div>
    </aside>

    <div class="lb" hidden>
      <div class="lb-head">
        <span class="tag">/Clin</span>
        <b class="lb-title">Anteprima documento anonimizzato</b>
        <div class="lb-act">
          <button class="lb-prev" type="button">‹</button>
          <span class="lb-pg">1 / 1</span>
          <button class="lb-next" type="button">›</button>
          <button class="lb-dl" type="button" hidden>Scarica</button>
          <button class="lb-close" type="button">Chiudi ×</button>
        </div>
      </div>
      <div class="lb-body"></div>
    </div>

    <div class="panel" hidden>
      <div class="head"><span class="tag">/Clin</span><b>Anonimizzazione locale</b><button class="x" title="Chiudi">×</button></div>
      <label class="sw"><input type="checkbox" class="on" checked> Anonimizzare testi e file incollati o trascinati</label>
      <div class="row"><button class="dark pick-btn" type="button">📎 Carica file da anonimizzare</button><input type="file" class="pick-in" multiple accept="image/*,application/pdf,.pdf,.docx,.xlsx,.xlsm,.csv,.tsv,.txt,.md" hidden></div>
      <div class="p-tabs">
        <button type="button" class="ptab-ans on">Risposte IA</button>
        <button type="button" class="ptab-sent">Inviati (0)</button>
      </div>
      <div class="p-sec-ans" style="display:flex;flex-direction:column;gap:8px;flex:1;min-height:0">
        <p class="muted"><b>Risposta con i dati reali</b> · selezionare un testo nella chat oppure usare l'ultima risposta.</p>
        <div class="row"><button class="last">Ultima risposta</button><button class="sel">Testo selezionato</button></div>
        <div class="out">Le risposte dell'IA compariranno qui con i nomi veri, visibili solo a te.</div>
        <div class="row"><button class="dark copy">Copia con i dati reali</button><button class="forget">Dimentica</button></div>
      </div>
      <div class="p-sec-sent" hidden style="display:flex;flex-direction:column;gap:8px;flex:1;min-height:0">
        <p class="muted">Anteprima esatta dei documenti e testi anonimizzati inviati in questa chat.</p>
        <div class="sent-list"></div>
      </div>
      <p class="muted n"></p>
    </div>`;

  const $ = (s) => root.querySelector(s);
  const pill = $(".pill"), panel = $(".panel"), toastEl = $(".toast"), out = $(".out");
  let toastTimer = 0, toastAction = null;
  const sentDocs = [];  // storico documenti/testi inviati in questa scheda

  const ensureMounted = () => {
    if (!host.isConnected) (document.body || document.documentElement).appendChild(host);
  };

  function toast(msg, err = false, ms = 5000, action = null) {
    ensureMounted();
    $(".t-msg").textContent = msg;
    toastEl.classList.toggle("err", err);
    toastAction = action;
    const actBtn = $(".t-act");
    actBtn.hidden = !action;
    if (action?.label) actBtn.textContent = action.label;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; toastAction = null; }, ms);
  }
  $(".t-act").addEventListener("click", () => {
    const fn = toastAction?.fn;
    toastEl.hidden = true; toastAction = null;
    if (fn) fn();
  });

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
    renderSentList();
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

  // ---------------- Lightbox a schermo intero (anteprima prima e dopo l'invio)
  const lb = $(".lb");
  let lbState = null;
  function renderLightbox() {
    if (!lbState) return;
    const { title, pages, text, file, pageIdx } = lbState;
    $(".lb-title").textContent = title;
    const body = $(".lb-body");
    body.replaceChildren();
    const hasPages = pages && pages.length > 0;
    $(".lb-prev").hidden = $(".lb-next").hidden = $(".lb-pg").hidden = !hasPages || pages.length <= 1;
    $(".lb-dl").hidden = !file;
    if (hasPages) {
      $(".lb-pg").textContent = `${pageIdx + 1} / ${pages.length}`;
      $(".lb-prev").disabled = pageIdx <= 0;
      $(".lb-next").disabled = pageIdx >= pages.length - 1;
      const img = document.createElement("img");
      img.src = pages[pageIdx];
      img.alt = `${title} - pagina ${pageIdx + 1}`;
      body.append(img);
    } else {
      const box = el("div", "lb-txt");
      appendHighlighted(box, text || "(Nessuna anteprima testuale disponibile)");
      body.append(box);
    }
  }
  function openLightbox({ title, pages = [], text = "", file = null, pageIdx = 0 }) {
    ensureMounted();
    lbState = { title, pages, text, file, pageIdx };
    lb.hidden = false;
    renderLightbox();
  }
  $(".lb-close").addEventListener("click", () => { lb.hidden = true; lbState = null; });
  $(".lb-prev").addEventListener("click", () => { if (lbState && lbState.pageIdx > 0) { lbState.pageIdx--; renderLightbox(); } });
  $(".lb-next").addEventListener("click", () => { if (lbState && lbState.pageIdx < lbState.pages.length - 1) { lbState.pageIdx++; renderLightbox(); } });
  $(".lb-dl").addEventListener("click", () => { if (lbState?.file) downloadFileObj(lbState.file); });
  lb.addEventListener("click", (e) => { if (e.target === lb || e.target === $(".lb-body")) { lb.hidden = true; lbState = null; } });

  // ---------------- Pannello pillola (Risposte IA + Inviati)
  function switchPanelTab(which) {
    const isSent = which === "sent";
    $(".ptab-ans").classList.toggle("on", !isSent);
    $(".ptab-sent").classList.toggle("on", isSent);
    $(".p-sec-ans").hidden = isSent;
    $(".p-sec-sent").hidden = !isSent;
    if (isSent) renderSentList();
  }
  $(".ptab-ans").addEventListener("click", () => switchPanelTab("ans"));
  $(".ptab-sent").addEventListener("click", () => switchPanelTab("sent"));

  function renderSentList() {
    $(".ptab-sent").textContent = `Inviati (${sentDocs.length})`;
    const list = $(".sent-list");
    list.replaceChildren();
    if (!sentDocs.length) {
      list.append(el("p", "muted", "Nessun documento inviato in questa chat. I file e testi anonimizzati compariranno qui per rivederli in qualsiasi momento."));
      return;
    }
    for (const d of sentDocs) {
      const card = el("div", "sent-card");
      if (d.pages?.length) {
        const img = document.createElement("img");
        img.className = "sent-thumb"; img.src = d.pages[0]; img.alt = d.title;
        img.addEventListener("click", () => openLightbox(d));
        card.append(img);
      } else {
        const ic = el("div", "sent-thumb", d.file ? "📄" : "📝");
        ic.addEventListener("click", () => openLightbox(d));
        card.append(ic);
      }
      const info = el("div", "sent-info");
      info.append(el("div", "sent-name", d.title));
      const metaParts = [d.time];
      if (d.pages?.length) metaParts.push(`${d.pages.length} pag.`);
      metaParts.push(`${d.count} dati coperti`);
      info.append(el("div", "sent-meta", metaParts.join(" · ")));
      const act = el("div", "sent-act");
      const btnPrev = el("button", "dark", "Vedi");
      btnPrev.addEventListener("click", () => openLightbox(d));
      act.append(btnPrev);
      if (d.file) {
        const btnDl = el("button", "", "⬇");
        btnDl.title = "Scarica file anonimizzato";
        btnDl.addEventListener("click", () => downloadFileObj(d.file));
        act.append(btnDl);
      }
      card.append(info, act);
      list.append(card);
    }
  }

  pill.addEventListener("click", () => { panel.hidden = !panel.hidden; toastEl.hidden = true; refresh(); if (!panel.hidden) restoreLast(); });
  $(".x").addEventListener("click", () => { panel.hidden = true; render(); });
  $(".on").addEventListener("change", async (e) => { active = e.target.checked; await send({ op: "toggle", attivo: active }); render(); });
  $(".pick-btn").addEventListener("click", () => $(".pick-in").click());
  $(".pick-in").addEventListener("change", (e) => {
    const files = [...(e.target.files || [])];
    e.target.value = "";
    if (!files.length) return;
    panel.hidden = true; render();
    handleFiles(captureFiles(files), { kind: "drop", target: composer() });
  });
  $(".forget").addEventListener("click", async () => { await send({ op: "forget" }); sentDocs.length = 0; out.textContent = "Segnaposto e storico dimenticati."; refresh(); });
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
    if (!msg || msg.target !== "content") return;
    if (msg.op === "panel") { panel.hidden = false; refresh(); restoreLast(); }
    else if (msg.op === "progress" && rv) { setProgress(msg.step, msg.pct); }
  });

  const mount = () => { ensureMounted(); refresh(); send({ op: "warmup" }).catch(() => {}); };
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);

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

  // ---------------------------------------------------------------- revisione prima dell'invio
  const KIND_LABEL = {
    PAZIENTE: "Paziente", PERSONA: "Persona", MEDICO: "Medico", OPERATORE: "Operatore sanitario",
    DATA_NASCITA: "Nascita", DATA: "Data", CONTATTO: "Recapito", ID: "Documento d'identità",
    ID_CLINICO: "Codice clinico", STRUTTURA: "Struttura sanitaria", PROVENIENZA: "Provenienza",
    IBAN: "Dati bancari", DOCUMENTO: "Documento", DATO: "Aggiunto da te",
  };
  const kindOfPh = (ph) => { const m = /^\[([A-Z_]+)_\d+\]$/.exec(ph); return m ? (KIND_LABEL[m[1]] || m[1]) : "Codice"; };
  const addList = [];
  let rv = null, collapsed = false, wideMode = false;
  const rev = $(".rev"), rvTab = $(".rv-tab"), rvLoader = $(".rv-loader"), rvBody = $(".rv-body"), rvUpd = $(".rv-updating"), rvRetry = $(".rv-retry");

  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  function appendHighlighted(container, text) {
    let last = 0;
    for (const m of text.matchAll(/\[[A-Z_]+_\d+\]/g)) {
      container.append(document.createTextNode(text.slice(last, m.index)), el("mark", "", m[0]));
      last = m.index + m[0].length;
    }
    container.append(document.createTextNode(text.slice(last)));
  }

  function setProgress(stepText, pct) {
    if (stepText) {
      $(".rv-ld-step").textContent = stepText;
      $(".u-txt").textContent = stepText;
    }
    if (typeof pct === "number") {
      const p = Math.max(5, Math.min(100, Math.round(pct)));
      $(".rv-ld-pct").textContent = p + "%";
      $(".rv-bar-fill").style.width = p + "%";
    }
  }

  function setWide(val) {
    wideMode = !!val;
    rev.classList.toggle("wide", wideMode);
    $(".rv-wide").textContent = wideMode ? "⤡" : "⤢";
    $(".rv-wide").title = wideMode ? "Riduci a colonna singola" : "Espandi vista a 2 colonne";
  }

  function setCollapsed(val) {
    collapsed = !!val;
    if (!rv) {
      rev.classList.remove("open", "collapsed");
      rvTab.classList.remove("show", "loading");
      return;
    }
    rev.classList.toggle("open", !collapsed);
    rev.classList.toggle("collapsed", collapsed);
    rvTab.classList.toggle("show", collapsed);
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

  function rvStatus(msg, err = false) { const el = $(".rv-st"); el.textContent = msg; el.classList.toggle("err", err); }

  async function startReview(op, items, label, finish) {
    ensureMounted();
    if (rv) {
      if (collapsed) setCollapsed(false);
      toast("Concludere prima la revisione aperta nel pannello di Clin.", true);
      return;
    }
    rv = { op, items, label, finish, keep: new Set(), kept: new Map(), result: null, fileIdx: 0, pageIdx: 0, zoom: 100 };
    panel.hidden = true; toastEl.hidden = true;
    $(".rv-sum").textContent = label;
    $(".rv-preview").replaceChildren(); $(".rv-list").replaceChildren();
    const isText = op === "anonymize";
    $(".rv-sel").hidden = $(".rv-selhint").hidden = !isText;
    $(".rv-dl").hidden = true;
    // Per i documenti (PDF/foto/Word) apriamo subito in vista ampia a 2 colonne stile desktop
    setWide(!isText && window.innerWidth >= 960);
    rvRetry.classList.remove("show");
    rvBody.classList.add("hide");
    rvLoader.classList.add("show");
    rvUpd.classList.remove("show");
    setProgress("Avvio del motore locale…", 8);
    setCollapsed(false);
    await rerun();
  }

  function sendWithTimeout(msg, ms = 120000) {
    return Promise.race([
      send(msg),
      new Promise((_, rej) => setTimeout(() => rej(new Error("tempo massimo superato: riprovare o ricaricare la scheda")), ms)),
    ]);
  }

  async function rerun() {
    if (!rv) return;
    const mine = rv;
    const firstLoad = !mine.result;
    busy = true; render();
    rvTab.classList.add("loading");
    rvRetry.classList.remove("show");
    $(".go").disabled = true;
    if (firstLoad) {
      rvLoader.classList.add("show");
      rvBody.classList.add("hide");
      setProgress("Avvio del motore locale…", 10);
      rvStatus("");
    } else {
      rvUpd.classList.add("show");
      $(".u-txt").textContent = "Aggiornamento anteprima…";
      rvStatus("");
    }
    try {
      const r = await sendWithTimeout({ op: mine.op, items: mine.items, review: { keep: [...mine.keep], add: addList } });
      if (rv !== mine) return;
      if (!r?.ok) throw new Error(r?.error || "motore non disponibile (ricaricare la pagina se hai aggiornato l'estensione)");
      mine.result = r;
      setProgress("Pronto.", 100);
      rvLoader.classList.remove("show");
      rvUpd.classList.remove("show");
      rvBody.classList.remove("hide");
      drawReview();
      $(".go").disabled = false;
      $(".rv-dl").hidden = mine.op !== "redact" || !(r.files && r.files.length);
      rvStatus("");
    } catch (err) {
      if (rv === mine) {
        rvLoader.classList.remove("show");
        rvUpd.classList.remove("show");
        rvRetry.classList.add("show");
        const msg = String(err?.message || err);
        const hint = /Extension context invalidated/i.test(msg)
          ? "Estensione aggiornata: ricarica questa pagina (Cmd+R / F5) e riprova."
          : `Anonimizzazione non riuscita (${msg}). Nulla è stato inviato alla chat.`;
        rvStatus(hint, true);
      }
    } finally {
      busy = false; render();
      rvTab.classList.remove("loading");
    }
  }

  function drawDocViewer(pv, files) {
    if (!files.length) return;
    rv.fileIdx = Math.min(rv.fileIdx, files.length - 1);
    const f = files[rv.fileIdx];
    const pages = f.pages || [];
    rv.pageIdx = Math.min(rv.pageIdx, Math.max(0, pages.length - 1));

    const wrap = el("div", "doc-viewer");
    wrap.append(el("p", "rv-k", "Anteprima documento anonimizzato"));

    const bar = el("div", "doc-bar");
    const ftabs = el("div", "doc-ftabs");
    files.forEach((fi, idx) => {
      const b = el("button", "ftab" + (idx === rv.fileIdx ? " on" : ""), fi.name);
      b.type = "button"; b.title = fi.name;
      b.addEventListener("click", () => { rv.fileIdx = idx; rv.pageIdx = 0; drawDocViewer(pv, files); });
      ftabs.append(b);
    });
    bar.append(ftabs);

    const nav = el("div", "doc-nav");
    if (pages.length) {
      if (pages.length > 1) {
        const prev = el("button", "navbtn", "‹"); prev.type = "button"; prev.disabled = rv.pageIdx <= 0;
        prev.addEventListener("click", () => { rv.pageIdx--; drawDocViewer(pv, files); });
        const next = el("button", "navbtn", "›"); next.type = "button"; next.disabled = rv.pageIdx >= pages.length - 1;
        next.addEventListener("click", () => { rv.pageIdx++; drawDocViewer(pv, files); });
        nav.append(prev, el("span", "pg-lbl", `${rv.pageIdx + 1}/${pages.length}`), next);
      }
      const zmOut = el("button", "navbtn", "−"); zmOut.type = "button"; zmOut.title = "Riduci zoom";
      zmOut.addEventListener("click", () => { rv.zoom = Math.max(80, rv.zoom - 25); drawDocViewer(pv, files); });
      const zmIn = el("button", "navbtn", "+"); zmIn.type = "button"; zmIn.title = "Aumenta zoom";
      zmIn.addEventListener("click", () => { rv.zoom = Math.min(225, rv.zoom + 25); drawDocViewer(pv, files); });
      const full = el("button", "navbtn", "Schermo intero"); full.type = "button";
      full.addEventListener("click", () => openLightbox({ title: f.name, pages, file: f, pageIdx: rv.pageIdx }));
      nav.append(zmOut, zmIn, full);
    } else if (f.previewText) {
      const full = el("button", "navbtn", "Espandi"); full.type = "button";
      full.addEventListener("click", () => openLightbox({ title: f.name, text: f.previewText, file: f }));
      nav.append(full);
    }
    bar.append(nav);
    wrap.append(bar);

    if (pages.length) {
      const stage = el("div", "doc-stage");
      const img = document.createElement("img");
      img.src = pages[rv.pageIdx];
      img.alt = `${f.name} - pagina ${rv.pageIdx + 1}`;
      img.style.width = rv.zoom + "%";
      img.addEventListener("click", () => openLightbox({ title: f.name, pages, file: f, pageIdx: rv.pageIdx }));
      stage.append(img);
      wrap.append(stage, el("p", "doc-hint", "Clicca sull'immagine per ingrandirla · Togli una spunta a destra per aggiornare subito il documento."));
    } else if (f.previewText) {
      const box = el("div", "rv-prev");
      appendHighlighted(box, f.previewText);
      wrap.append(box);
    }
    if (rv.result?.notes?.length) wrap.append(el("p", "muted", rv.result.notes.join(" ")));
    pv.replaceChildren(wrap);
  }

  function drawReview() {
    const r = rv.result;
    const groups = new Map();
    for (const [ph, orig] of r.found || []) {
      if (!groups.has(ph)) groups.set(ph, new Set());
      groups.get(ph).add(orig);
    }
    const n = groups.size;
    $(".rv-tab .badge").textContent = `${n} ${n === 1 ? "dato" : "dati"}`;
    const sum = $(".rv-sum");
    sum.replaceChildren(el("strong", "", `${n} ${n === 1 ? "dato coperto" : "dati coperti"}`), document.createTextNode(` · ${rv.label}`));

    const pv = $(".rv-preview");
    pv.replaceChildren();
    if (rv.op === "anonymize") {
      pv.append(el("p", "rv-k", "Anteprima di ciò che entra nella chat"));
      const box = el("div", "rv-prev");
      appendHighlighted(box, (r.text || "").replace(/\n{3,}/g, "\n\n"));
      pv.append(box);
    } else {
      drawDocViewer(pv, r.files || []);
    }

    const list = $(".rv-list");
    list.replaceChildren();
    const row = (ph, originals, on) => {
      const lab = el("label", "rv-item" + (on ? "" : " off"));
      const cb = el("input"); cb.type = "checkbox"; cb.checked = on;
      const v = el("span", "v", [...originals].join(" · "));
      v.append(el("span", "c", on ? kindOfPh(ph) : `${kindOfPh(ph)} · resterà in chiaro`));
      lab.append(cb, v, el("span", "ph", on ? ph : "in chiaro"));
      cb.addEventListener("change", () => toggle(ph, originals, cb.checked));
      list.append(lab);
    };
    for (const [ph, originals] of groups) row(ph, originals, true);
    for (const [ph, originals] of rv.kept) if (!groups.has(ph)) row(ph, originals, false);
    if (!list.children.length) list.append(el("p", "muted", "Nessun dato personale riconosciuto. Se ne manca qualcuno, aggiungerlo qui sotto."));
  }

  function toggle(ph, originals, on) {
    if (!rv) return;
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
    rerun();
  }

  function addWord(word) {
    word = (word || "").replace(/\s+/g, " ").trim();
    if (!rv || word.length < 2) return;
    if (/\[[A-Z_]+_\d+\]/.test(word)) { rvStatus("Selezionare solo testo in chiaro, non un segnaposto.", true); return; }
    if (!addList.some((a) => a.toLowerCase() === word.toLowerCase())) addList.push(word);
    for (const o of [...rv.keep]) if (o.toLowerCase() === word.toLowerCase()) rv.keep.delete(o);
    $(".rv-word").value = "";
    rerun();
  }

  function closeReview() {
    rv = null;
    collapsed = false;
    rev.classList.remove("open", "collapsed");
    rvTab.classList.remove("show", "loading");
    rvLoader.classList.remove("show");
    rvUpd.classList.remove("show");
    rvRetry.classList.remove("show");
    rvStatus("");
  }

  $(".rv-wide").addEventListener("click", () => setWide(!wideMode));
  $(".rv-col").addEventListener("click", () => setCollapsed(true));
  rvTab.addEventListener("click", () => setCollapsed(false));
  rvRetry.addEventListener("click", () => rerun());
  $(".rv-plus").addEventListener("click", () => addWord($(".rv-word").value));
  $(".rv-word").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addWord(e.target.value); } });
  $(".rv-sel").addEventListener("click", () => {
    const sel = (root.getSelection ? root.getSelection() : getSelection());
    addWord(String(sel || ""));
  });
  const cancel = () => { if (rv) { closeReview(); toast("/Clin · annullato: nulla è stato inserito nella chat."); } };
  $(".rv-cancel").addEventListener("click", cancel);
  $(".rv-x").addEventListener("click", cancel);
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!lb.hidden) { lb.hidden = true; lbState = null; }
      else if (rv) cancel();
    }
  });
  $(".rv-dl").addEventListener("click", () => {
    if (!rv?.result?.files?.length) return;
    for (const f of rv.result.files) downloadFileObj(f);
    toast("/Clin · file anonimizzato salvato nei Download.");
  });
  $(".go").addEventListener("click", async () => {
    if (!rv?.result) return;
    const { result, finish } = rv;
    closeReview();
    try { await finish(result); }
    catch (err) { console.error("[Clin]", err); toast(`/Clin: inserimento non riuscito (${err.message}). Nulla è stato inviato alla chat.`, true, 10000); }
  });

  function nowTime() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

  async function handleFiles(files, origin) {
    try {
      const items = await readItems(files);
      if (!items.length) return;
      const label = items.length === 1 ? items[0].name : `${items.length} file`;
      await startReview("redact", items, label, async (r) => {
        const out = r.files.map((f) => new File([Uint8Array.from(atob(f.data), (c) => c.charCodeAt(0))], f.name, { type: f.type }));
        if (!(await deliver(out, origin))) throw new Error("allegato non accettato dal sito");
        const count = new Set((r.found || []).map((x) => x[0])).size;
        const firstEntry = {
          title: r.files[0].name, pages: r.files[0].pages || [], text: r.files[0].previewText || "",
          file: r.files[0], count, time: nowTime(),
        };
        for (const f of r.files) {
          sentDocs.unshift({ title: f.name, pages: f.pages || [], text: f.previewText || "", file: f, count, time: nowTime() });
        }
        if (sentDocs.length > 20) sentDocs.length = 20;
        renderSentList();
        toast(
          `/Clin · allegat${out.length === 1 ? "o 1 file" : "i " + out.length + " file"} con i dati coperti: ${out.map((f) => f.name).join(", ")}.`,
          false, 9000,
          { label: "Vedi anteprima", fn: () => openLightbox(firstEntry) },
        );
      });
    } catch (err) {
      console.warn("[Clin handleFiles]", err);
      const raw = String(err?.message || err);
      const msg = /could not be found|NotFoundError/i.test(raw)
        ? "Chrome blocca la lettura dei file trascinati dalla bolla dei Download: clicca sulla pillola /Clin › «Carica file da anonimizzare» oppure trascinalo dal Finder."
        : `impossibile leggere il file (${raw}).`;
      toast(`/Clin: ${msg}`, true, 9000);
    }
  }

  async function handle({ files = [], text = "" }, target) {
    try {
      const items = await readItems(files);
      const fileCount = items.length;
      if (text.trim()) items.push({ kind: "testo incollato", text });
      if (!items.length) return;
      const label = fileCount ? `${fileCount === 1 ? "1 file" : fileCount + " file"}${text.trim() ? " e testo incollato" : ""}` : "testo incollato";
      await startReview("anonymize", items, label, (r) => {
        const el = target && editable(target) && document.contains(target) ? target : composer();
        if (!el) throw new Error("campo della chat non trovato");
        const filled = (el.value ?? el.innerText ?? "").trim().length > 0;
        let body = (filled ? "\n\n" : "") + r.text.replace(/\n{3,}/g, "\n\n");
        if (el.isContentEditable) body = body.replace(/\n\n/g, "\n");
        insert(el, body);
        const count = new Set((r.found || []).map((x) => x[0])).size;
        const entry = { title: label, pages: [], text: r.text, file: null, count, time: nowTime() };
        sentDocs.unshift(entry);
        if (sentDocs.length > 20) sentDocs.length = 20;
        renderSentList();
        toast("/Clin · testo anonimizzato inserito.", false, 7000, { label: "Vedi anteprima", fn: () => openLightbox(entry) });
      });
    } catch (err) {
      console.warn("[Clin handle]", err);
      toast(`/Clin: errore (${err?.message || err}).`, true, 8000);
    }
  }

  const stop = (e) => { e.preventDefault(); e.stopImmediatePropagation(); e.stopPropagation(); };

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
    if (passing || !active || e.target === host || e.composedPath?.().includes(host)) return;
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

  window.addEventListener("drop", (e) => {
    if (passing || !active) return;
    const files = droppedFiles(e.dataTransfer);
    if (!files.length) return;
    const captured = captureFiles(files, droppedEntries(e.dataTransfer));
    const target = e.target;
    stop(e);
    for (const t of ["dragleave", "dragend"]) {
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
