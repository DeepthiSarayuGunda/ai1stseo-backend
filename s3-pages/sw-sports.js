/* AI1stSEO Sports — Service Worker for Offline Mode
   Caches last viewed scores and pages so users with no connection see last known data */
const CACHE_NAME = 'ai1stseo-sports-v1';
const STATIC_ASSETS = [
  '/directory-sports.html',
  '/directory-sport.html',
  '/cricket-tips.html',
  '/a11y-sports.css',
  '/a11y-sports.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  // Network-first for API calls, cache-first for static assets
  if (event.request.url.includes('/api/') || event.request.url.includes('thesportsdb.com')) {
    event.respondWith(
      fetch(event.request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      }).catch(() => caches.match(event.request))
    );
  } else {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      }))
    );
  }
});
