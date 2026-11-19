'use client';

import { useEffect, useState } from 'react';
import axiosClient from '@/lib/axiosClient';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

const api = '/api/v1/analysis-push';

export function AnalysisPushButton({ userId, analyzing }: { userId?: string; analyzing: boolean }) {
  const [key, setKey] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [asked, setAsked] = useState(false);
  const preferenceKey = 'analysis-push-prompt:' + userId;

  useEffect(() => {
    if (!userId || !window.isSecureContext || !('PushManager' in window) ||
        !('Notification' in window) || !('serviceWorker' in navigator)) return;
    const request = new AbortController();
    async function load() {
      const { data } = await axiosClient.get<{ publicKey: string }>(api + '/config', { signal: request.signal });
      if (!data.publicKey) return;
      const registration = await navigator.serviceWorker.getRegistration('/');
      const sub = await registration?.pushManager.getSubscription();
      const active = sub && (await axiosClient.post<boolean>(api + '/status', { endpoint: sub.endpoint },
        { signal: request.signal })).data;
      if (!request.signal.aborted) {
        setAsked(localStorage.getItem(preferenceKey) === 'seen');
        setEnabled(Boolean(active));
        setKey(data.publicKey);
      }
    }
    void load().catch(() => { if (!request.signal.aborted) setKey(''); });
    return () => request.abort();
  }, [userId, preferenceKey]);

  function dismissPrompt() {
    setAsked(true);
    try { localStorage.setItem(preferenceKey, 'seen'); } catch { /* Remember for this visit. */ }
  }

  async function toggle() {
    const jobId = analyzing ? new URLSearchParams(window.location.search).get('jobId') : null;
    setBusy(true);
    setMessage('');
    try {
      if (!enabled && Notification.permission !== 'granted' && await Notification.requestPermission() !== 'granted') {
        setMessage('Để nhận thông báo, hãy cho phép thông báo trong cài đặt của trang này.');
        return;
      }
      dismissPrompt();
      await navigator.serviceWorker.register('/analysis-push.js');
      const registration = await navigator.serviceWorker.ready;
      const old = await registration.pushManager.getSubscription();
      if (enabled) {
        if (old) {
          await axiosClient.delete(api, { data: { endpoint: old.endpoint } });
          await old.unsubscribe();
        }
        setEnabled(false);
        return;
      }
      // A previous account or VAPID key may have used this browser.
      if (old) await old.unsubscribe();
      const bytes = Uint8Array.from(atob(key.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
      const sub = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes });
      await axiosClient.put(api, { ...sub.toJSON(), jobId });
      setEnabled(true);
    } catch {
      setMessage('Chưa cập nhật được thông báo. Vui lòng thử lại.');
    } finally {
      dismissPrompt();
      setBusy(false);
    }
  }

  if (!key) return null;
  return <div className="mt-3 space-y-1">
    <Dialog open={analyzing && !asked && !enabled && Notification.permission !== 'denied'}
      onOpenChange={open => { if (!open) dismissPrompt(); }}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Nhận thông báo khi phân tích xong?</DialogTitle>
          <DialogDescription>Bạn có thể đóng tab. Khi có kết quả CV/JD, trình duyệt sẽ báo để bạn mở lại hồ sơ.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={dismissPrompt}>Bỏ qua</Button>
          <Button type="button" disabled={busy} onClick={toggle}>Bật thông báo</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <Button type="button" variant="outline" size="sm" disabled={busy} aria-pressed={enabled} onClick={toggle}>
      {enabled ? 'Tắt thông báo kết quả trên thiết bị này' : 'Báo cho tôi khi phân tích xong'}
    </Button>
    {message && <p role="status" className="text-sm text-muted-foreground">{message}</p>}
  </div>;
}
