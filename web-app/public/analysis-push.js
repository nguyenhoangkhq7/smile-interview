self.addEventListener('push', event => {
  if (!event.data) return;
  const { sessionId, jobId } = event.data.json();
  if (typeof sessionId !== 'string' || typeof jobId !== 'string') return;
  const query = new URLSearchParams({ sessionId, jobId });
  event.waitUntil(self.registration.showNotification('Phân tích CV/JD đã hoàn tất', {
    body: 'Nhấn để xem kết quả của bạn trong Smile Interview.',
    icon: '/logo.png',
    tag: 'analysis-' + jobId,
    data: { path: '/interview/new?' + query },
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = new URL(event.notification.data.path, self.location.origin);
  if (url.origin !== self.location.origin || url.pathname !== '/interview/new') return;
  event.waitUntil((async () => {
    const tabs = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = tabs.find(tab => tab.url === url.href);
    if (existing) await existing.focus();
    else await self.clients.openWindow(url.href);
  })());
});
