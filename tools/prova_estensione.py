"""
Prova dell'estensione dentro Chromium, su una finta pagina di chat con dati inventati:
incolla (passaggio diretto e finestra di controllo), PDF dal selettore di file, interruttori,
parola aggiunta, consegna al sito, pannello con la risposta ripristinata, Esc.

    python3 tools/prova_estensione.py [--dark]

Lavora su una copia temporanea di extension/dist in cui la pagina di prova (localhost) e'
tra i siti ammessi e lo shadow DOM e' aperto, cosi' Playwright puo' leggere l'interfaccia.
Richiede Playwright con Chromium e PyMuPDF. Gli screenshot restano nella cartella temporanea.
"""
import asyncio, functools, http.server, json, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
SP = Path(tempfile.mkdtemp(prefix="clin-prova-"))
subprocess.run(["cp", "-Rc", str(ROOT / "extension" / "dist"), str(SP / "ext")], check=False)  # copia istantanea su APFS
if not (SP / "ext").exists():
    shutil.copytree(ROOT / "extension" / "dist", SP / "ext")
m = json.loads((SP / "ext" / "manifest.json").read_text())
m["content_scripts"][0]["matches"].append("http://localhost/*")
(SP / "ext" / "manifest.json").write_text(json.dumps(m))
c = (SP / "ext" / "content.js").read_text(encoding="utf-8")
assert 'mode: "closed"' in c
(SP / "ext" / "content.js").write_text(c.replace('mode: "closed"', 'mode: "open"'), encoding="utf-8")
(SP / "site").mkdir()
DARK = "--dark" in sys.argv
(SP / "site" / "index.html").write_text(f'''<!doctype html><meta charset="utf-8"><title>chat di prova</title>
<body style="margin:0;font:16px system-ui;background:{"#1e1f20" if DARK else "#fff"};color:{"#eee" if DARK else "#111"}">
<main style="max-width:760px;margin:40px auto;padding:0 20px"><h2>Chat di prova</h2>
<div data-message-author-role="assistant"><div class="markdown">Il paziente [PAZIENTE_1] va rivalutato tra 7 giorni.</div></div>
<form style="margin-top:40px"><textarea id="t" style="width:100%;height:160px;font:inherit"></textarea>
<input type="file" id="f" multiple></form></main></body>''', encoding="utf-8")
import fitz
doc = fitz.open()
for n in range(2):
    y = 72
    for line in ["OSPEDALE SAN GIOVANNI - U.O. Medicina Interna", "LETTERA DI DIMISSIONE", "",
                 "Paziente: Mario Rossi, nato il 12/03/1958 a Torino", "Codice fiscale: RSSMRA58C12L219X   Tel. 333 1234567",
                 "Residente in via Garibaldi 14, 10122 Torino", "", "Ricoverato dal 02/11/2026 al 09/11/2026 per polmonite lobare destra.",
                 "Emoglobina 13,5 g/dL, PCR 4,2 mg/dL.", "Il sig. Rossi viene dimesso in buone condizioni generali.", "", "Dott.ssa Giulia Bianchi"]:
        (doc.new_page() if y == 72 else doc[-1]).insert_text((72, y), line, fontsize=11); y += 22
doc.save(SP / "site" / "lettera.pdf")
EXT = str(SP / "ext")
PAGE = "index.html"
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SP / "site"))
h.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8799), h)
threading.Thread(target=srv.serve_forever, daemon=True).start()
TXT = "Paziente Mario Rossi, nato il 12/03/1958, CF RSSMRA58C12L219X. Visitato dalla Dott.ssa Giulia Bianchi per dispnea. Tel 333 1234567. Emoglobina 13,5 g/dL. " * 3

PASTE = """(t) => { const el = document.querySelector('#t'); el.focus(); const dt = new DataTransfer(); dt.setData('text/plain', t);
  el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }"""

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="clin-t-"), headless=True, channel="chromium",
            viewport={"width": 1320, "height": 860}, args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"])
        sw = ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event("serviceworker")
        page = await ctx.new_page()
        logs = []
        page.on("console", lambda m: logs.append(m.text))
        await page.goto(f"http://localhost:8799/{PAGE}")
        ep = await ctx.new_page(); await ep.goto(sw.url.rsplit("/", 1)[0] + "/manifest.json")
        t0 = time.time()
        while True:
            st = await ep.evaluate("chrome.runtime.sendMessage({target:'offscreen', op:'state'}).catch(e => ({err: String(e)}))")
            if st and st.get("engine") and st.get("ner", {}).get("state") == "ready": break
            if time.time() - t0 > 120: print("TIMEOUT state", st); break
            await asyncio.sleep(1)
        print("motore pronto in %.1fs" % (time.time() - t0), st)
        await page.bring_to_front()
        # A: testo breve senza dati -> entra senza revisione
        await page.evaluate(PASTE, "riassumi in tre punti")
        await page.wait_for_function("document.querySelector('#t').value.includes('riassumi')", timeout=60000)
        print("A ok: passaggio diretto, dialog nascosto =", await page.locator(".ov").is_hidden())
        await page.evaluate("document.querySelector('#t').value=''")
        # B: testo clinico -> revisione
        t = time.time(); await page.evaluate(PASTE, TXT)
        await page.locator(".dlg-b").wait_for(state="visible", timeout=120000)
        print("B revisione testo in %.2fs" % (time.time() - t), "righe:", await page.locator(".it").count(), "| contatore:", await page.locator(".cnt b").inner_text())
        print("  gruppi:", await page.locator(".gk").all_inner_texts())
        print("  righe:", await page.locator(".it").all_inner_texts())
        await page.screenshot(path=str(SP / "shot_text_.png"))
        t = time.time(); await page.locator(".it .sw").first.click()
        await page.wait_for_function("document.querySelector('clin-panel').shadowRoot.querySelector('.it.off .it-p')?.textContent === 'in chiaro' && !document.querySelector('clin-panel').shadowRoot.querySelector('.dlg').classList.contains('updating')", timeout=60000)
        print("  spunta tolta, rielaborato in %.2fs" % (time.time() - t), "|", await page.locator(".cnt-s").inner_text())
        await page.locator(".go").click()
        v = await page.evaluate("document.querySelector('#t').value")
        print("  inserito:", v[:150].replace("\n", " "))
        assert "[" in v and "RSSMRA58C12L219X" not in v
        await page.evaluate("document.querySelector('#t').value=''")
        await asyncio.sleep(.3)
        # C: PDF dal selettore file della pagina
        t = time.time(); await page.set_input_files("#f", str(SP / "site" / "lettera.pdf"))
        await page.locator(".dlg-b").wait_for(state="visible", timeout=180000)
        print("C revisione PDF in %.2fs" % (time.time() - t), "righe:", await page.locator(".it").count(), "| pagine:", await page.locator(".pv .pg").first.inner_text())
        print("  righe:", await page.locator(".it").all_inner_texts())
        await page.screenshot(path=str(SP / "shot_pdf_.png"))
        t = time.time(); await page.locator(".it .sw").nth(1).click()
        await page.wait_for_function("document.querySelector('clin-panel').shadowRoot.querySelector('.it.off .it-p')?.textContent === 'in chiaro' && !document.querySelector('clin-panel').shadowRoot.querySelector('.dlg').classList.contains('updating')", timeout=120000)
        print("  spunta PDF rielaborata in %.2fs" % (time.time() - t))
        await page.locator(".word").fill("polmonite"); await page.locator(".add .b").click()
        await page.wait_for_function("[...document.querySelector('clin-panel').shadowRoot.querySelectorAll('.it-v')].some(e => /polmonite/i.test(e.textContent))", timeout=120000)
        print("  parola aggiunta ok")
        await page.locator(".go").click()
        await page.wait_for_function("document.querySelector('#f').files.length === 1", timeout=30000)
        print("  consegnato:", await page.evaluate("[...document.querySelector('#f').files].map(f => f.name + ' ' + f.size)"))
        await asyncio.sleep(.5)
        await page.screenshot(path=str(SP / "shot_toast_.png"))
        # D: pannello
        await page.locator(".fab").click(); await asyncio.sleep(2.5)
        print("D pannello:", (await page.locator(".out").inner_text())[:90], "|", await page.locator(".pop-s").inner_text())
        await page.screenshot(path=str(SP / "shot_panel_.png"))
        await page.locator(".seg button").nth(1).click(); await asyncio.sleep(.3)
        await page.screenshot(path=str(SP / "shot_sent_.png"))
        print("  inviati:", await page.locator(".sc").count())
        # E: stretto
        await page.locator(".pop-x").click()
        await page.set_viewport_size({"width": 700, "height": 800})
        await page.evaluate(PASTE, TXT)
        await page.locator(".dlg-b").wait_for(state="visible", timeout=120000)
        await page.screenshot(path=str(SP / "shot_narrow_.png"))
        await page.keyboard.press("Escape"); await asyncio.sleep(.3)
        print("E Esc chiude:", await page.locator(".ov").is_hidden())
        errs = [l for l in logs if "Clin" in l or "rror" in l]
        print("console:", errs[:8])
        print("screenshot in", SP)
        await ctx.close()
asyncio.run(main())
