const VERSION = 'scrollforge-shell-v5';
const SHELL = ['./', './index.html', './tokens.css', './app.js', './manifest.json', './icon.svg', './icon-192.png', './icon-512.png', './apple-touch-icon.png', './data/feed.json'];
const KATEX_FONTS = [
  'KaTeX_AMS-Regular', 'KaTeX_Caligraphic-Bold', 'KaTeX_Caligraphic-Regular',
  'KaTeX_Fraktur-Bold', 'KaTeX_Fraktur-Regular', 'KaTeX_Main-Bold',
  'KaTeX_Main-BoldItalic', 'KaTeX_Main-Italic', 'KaTeX_Main-Regular',
  'KaTeX_Math-BoldItalic', 'KaTeX_Math-Italic', 'KaTeX_SansSerif-Bold',
  'KaTeX_SansSerif-Italic', 'KaTeX_SansSerif-Regular', 'KaTeX_Script-Regular',
  'KaTeX_Size1-Regular', 'KaTeX_Size2-Regular', 'KaTeX_Size3-Regular',
  'KaTeX_Size4-Regular', 'KaTeX_Typewriter-Regular'
];
const KATEX = [
  'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css',
  'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js',
  'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js',
  ...KATEX_FONTS.map(name => 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/fonts/' + name + '.woff2')
];
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await Promise.all(SHELL.map(url => cache.add(url).catch(() => null)));
    await Promise.all(KATEX.map(url => cache.add(new Request(url, { mode: 'cors' })).catch(() => null)));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('scrollforge-') && key !== VERSION).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.hostname === 'api.github.com') return;
  if (url.origin === self.location.origin) {
    if (url.pathname.endsWith('/data/feed.json')) {
      event.respondWith((async () => {
        const cache = await caches.open(VERSION);
        try {
          const response = await fetch(request);
          if (response.ok) await cache.put(request, response.clone());
          return response;
        } catch (_) {
          return (await cache.match(request)) || new Response('{"error":"No cached feed is available."}', { status: 503, headers: { 'Content-Type': 'application/json' } });
        }
      })());
      return;
    }
    if (request.mode === 'navigate') {
      event.respondWith((async () => {
        try { return await fetch(request); }
        catch (_) { return (await caches.match('./index.html')) || Response.error(); }
      })());
      return;
    }
    event.respondWith((async () => (await caches.match(request)) || fetch(request))());
    return;
  }
  if (url.hostname === 'cdn.jsdelivr.net' && url.pathname.includes('/katex@0.16.11/')) {
    event.respondWith((async () => {
      const cache = await caches.open(VERSION);
      const cached = await cache.match(request);
      if (cached) return cached;
      try { const response = await fetch(request); if (response.ok) cache.put(request, response.clone()); return response; }
      catch (_) { return Response.error(); }
    })());
  }
});
