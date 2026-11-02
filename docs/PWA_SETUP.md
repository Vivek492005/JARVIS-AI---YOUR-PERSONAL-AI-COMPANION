# PWA Setup — JARVIS HUD on mobile (Task 7.9)

The HUD (`/hud/`) is a Progressive Web App: install it on your phone's home
screen and it behaves like a native companion app (standalone window, offline
command queue, notifications).

## 1. Serve jarvisd over HTTPS

Service workers and `beforeinstallprompt` **require HTTPS** (or localhost).
On your Windows machine, the easiest trusted-cert path is `mkcert`:

```powershell
# one-time
choco install mkcert            # or: winget install mkcert
mkcert -install                 # trust the local CA
mkcert 192.168.1.50             # your PC's LAN IP (see ipconfig)
```

Then start jarvisd with TLS (Task 2.4's `--http` plus cert flags):

```powershell
jarvis serve --http --port 8765 --tls-cert 192.168.1.50.pem --tls-key 192.168.1.50-key.pem
```

> If `--tls-cert` isn't implemented on your build yet, put Caddy/Nginx in
> front as a reverse proxy with the mkcert certs — the HUD only needs
> `https://<ip>:<port>/hud/`.

## 2. Install on the phone

1. Phone on the **same Wi-Fi**. Open Chrome → `https://192.168.1.50:8765/hud/?token=<your-token>`.
2. Accept the mkcert cert warning once (expected — it's your own CA).
3. Chrome menu → **Install app** (or tap the "Install app" button in the HUD header).
4. Grant **Notifications** when asked — confirmations and errors then pop up
   even with the phone locked (once Web Push is configured, §4).

## 3. Offline queue

If the phone loses connectivity, typed commands and haan/nahi answers are
stored in `localStorage` and sent in order when the connection returns
(`online` event). The timeline shows `queued (offline): …` entries so you
can see what will fire. The queue survives app restarts.

## 4. Push notifications (Web Push / VAPID)

In-page notifications work with zero setup while the HUD is open.
True background push needs two one-time steps on the server:

```powershell
# 1. generate VAPID keys (once)
pip install pywebpush
python -m pywebpush --generate-vapid-keys   # keep both, they're secrets

# 2. expose them to jarvisd (env, never in a file)
setx JARVIS_VAPID_PUBLIC_KEY "<public>"
setx JARVIS_VAPID_PRIVATE_KEY "<private>"
```

Then open the installed PWA once and allow notifications — the app
subscribes via `POST /api/push/subscribe` automatically on first
Notification-permission grant. From then on, `ConfirmationRequested` and
`Error` events trigger `notify_push()` on the server.

Without `pywebpush`/keys, `notify_push()` logs and returns 0 — the PWA
still works, it just can't wake a closed app.

## 5. Mobile layout notes

- The HUD is responsive down to 360 px; the orb scales, transcript and
  timeline stack.
- `prefers-reduced-motion` disables the orb animation (battery saver).
- Wake-word listening on mobile is not yet supported — use the text box
  or the mic button (STT) in the HUD.

## Needs a real device to verify

- Install prompt flow (Chrome Android / Safari iOS "Add to Home Screen").
- Offline queue flush on a real network drop.
- Background push delivery with VAPID keys.
- Layout on small screens (360×640 and notched devices).
