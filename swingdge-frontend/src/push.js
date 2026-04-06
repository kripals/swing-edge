/**
 * PWA Push Notification registration (Phase 4 — stub).
 *
 * Full implementation requires:
 *   1. Generate VAPID keys (backend): `pywebpush vapid --gen`
 *   2. Add VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to backend .env
 *   3. Add POST /api/push/subscribe endpoint (saves PushSubscription to DB)
 *   4. Backend calls webpush() when sending alerts
 *   5. Set VITE_VAPID_PUBLIC_KEY in frontend .env
 *
 * To enable: call registerPush() after user logs in.
 */

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY

/**
 * Register for push notifications.
 * No-ops silently if VAPID key is not configured or browser doesn't support push.
 */
export async function registerPush() {
  if (!VAPID_PUBLIC_KEY) return
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return

  try {
    const reg = await navigator.serviceWorker.ready
    const existing = await reg.pushManager.getSubscription()
    if (existing) return  // already subscribed

    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: _urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
    })

    // Send subscription to backend
    await fetch('/api/push/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('swingdge_token')}`,
      },
      body: JSON.stringify(subscription.toJSON()),
    })
  } catch {
    // Push registration failure is non-critical — Telegram is primary channel
  }
}

/**
 * Unregister push notifications.
 */
export async function unregisterPush() {
  if (!('serviceWorker' in navigator)) return
  try {
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.getSubscription()
    if (sub) await sub.unsubscribe()
  } catch {
    // ignore
  }
}

// ── Helper ────────────────────────────────────────────────────────────────────

function _urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)))
}
