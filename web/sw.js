// Clin - service worker: funzionamento offline e ricezione dal menu Condividi (Android).
// __VERSION__ e __FILES__ vengono compilati da build.py.
const CACHE = "clin-__VERSION__";
const FILES = __FILES__;

self.addEventListener("install", (event) => {
  // cache: "reload" scavalca la cache HTTP: una nuova versione non riceve file vecchi
  event.waitUntil(caches.open(CACHE)
    .then((c) => c.addAll(FILES.map((f) => new Request(f, { cache: "reload" }))))
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("clin-") && k !== CACHE && k !== "clin-share")
                                       .map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;

  // Share Target: il file resta sul telefono, in una cache locale letta subito da app.js.
  if (event.request.method === "POST" && url.pathname.endsWith("/condividi")) {
    event.respondWith((async () => {
      const form = await event.request.formData();
      const cache = await caches.open("clin-share");
      const file = form.get("file");
      const text = [form.get("title"), form.get("text"), form.get("url")].filter(Boolean).join("\n");
      if (file && file.size) {
        await cache.put("file", new Response(file, { headers: { "X-Name": file.name || "condiviso" } }));
      }
      if (text) await cache.put("text", new Response(text));
      return Response.redirect("./?condiviso=1", 303);
    })());
    return;
  }

  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then((hit) => hit || fetch(event.request))
  );
});
