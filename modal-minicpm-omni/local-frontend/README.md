# Local MiniCPM Omni Chat

This is a local-only ChatGPT-style browser UI for the deployed MiniCPM-o 4.5 Modal Gateway.

It uses:

- A tiny Node server for static files.
- `/api/proxy` to call Modal REST endpoints without browser CORS issues.
- Direct browser WebSocket access to the Modal Gateway's `/ws/chat` endpoint.
- A local-only `/local/stop` endpoint that stops currently running Modal containers for this app while preserving the deployment.

No Hugging Face token is needed by this frontend.

Opening the local page does not automatically wake the Modal GPU. Use `Wake`, `Refresh`, or send a chat message when you want to start the remote container.

## Environment

The local frontend reads `modal-minicpm-omni/local-frontend/.env` directly:

```bash
MINICPM_MODAL_URL=https://sanjuhs123--minicpm-omni-demo.modal.run
MINICPM_MODAL_APP=minicpm-omni-45
PORT=5174
```

The browser uses that Modal URL by default on every reload. A `?remote=...` query parameter can override it for one page load.

## Run

From the repository root:

```bash
node modal-minicpm-omni/local-frontend/server.mjs --port 5174
```

Then open:

```text
http://localhost:5174
```

Override the remote Modal URL for the server process:

```bash
MINICPM_MODAL_URL="https://your-modal-endpoint.modal.run" \
node modal-minicpm-omni/local-frontend/server.mjs --port 5174
```

## How It Talks To Modal

REST status calls go through the local server:

```text
Browser -> localhost:5174/api/proxy -> Modal /health, /status, /workers, /api/queue, /api/apps
```

Chat uses the official Gateway WebSocket:

```text
Browser -> wss://...modal.run/ws/chat
```

The local chat composer can attach:

- Text typed into the prompt.
- Uploaded images, audio files, and videos.
- Recorded mic audio, converted to 16 kHz mono PCM before sending.
- Camera snapshots as JPEG images.
- Short camera clips as WebM videos.

For reliability on the local turn-based `/ws/chat` endpoint, keep each message to one video or one voice/audio note, up to four images, and a modest total media size. Multiple videos plus separate audio in one turn can stall or close before an answer. Use the official `/omni` or `/audio_duplex` pages for live audio+video interaction.

The Gateway currently fails for `streaming=false` text chat with a tensor-size error, so the local chat UI keeps streaming enabled. The `Speak` control is browser-local speech playback of the final assistant text; it does not ask Modal to synthesize audio.

The local chat UI keeps the latest 24 text turns in the request history. Raw audio/video/image payloads are sent for their own turn but are summarized in later history so long sessions do not balloon indefinitely.

The full-duplex audio/video modes are still best tested with the official remote pages for now:

```text
/omni
/audio_duplex
/realtime
/mobile
```

Those pages already contain the microphone, camera, WebSocket, and playback machinery from the upstream demo.

## Cost Control

With the Modal app configured as `min_containers=0` and `scaledown_window=60`, idle containers should scale down automatically. The `Stop Containers` button is a manual local kill switch for currently running containers. It does not delete the deployment or the model Volume.

## Troubleshooting

If the page stays on `Unknown` with an empty Inspector after reload, the browser is probably not running this app's JavaScript. Check for a port collision:

```bash
lsof -nP -iTCP:5174 -sTCP:LISTEN
```

There should be only one `node modal-minicpm-omni/local-frontend/server.mjs` process. This page now loads `/app.js?v=media-guard-20260614` to avoid stale browser cache, and the server sends `cache-control: no-store`.
