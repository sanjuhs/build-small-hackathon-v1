# MiniCPM-V Serverless Vision Chat

This is a separate local app for calling MiniCPM-V through a serverless OpenAI-compatible API.

I verified the current OpenBMB serverless vision release as `MiniCPM-V-4.6`, not `MiniCPM-V-5`. The app defaults to `MiniCPM-V-4.6-Instruct` and keeps the model configurable for a future V5 endpoint.

## Files

- `server.mjs` - local proxy that keeps the API key out of browser JavaScript.
- `public/` - browser chat UI for text + image requests.
- `API.md` - upstream and local API specs.
- `.env.example` - environment template.

## Configure

```bash
cd minicpm-v-serverless
cp .env.example .env
```

Then edit `.env`:

```bash
MINICPM_V_API_BASE=https://api.modelbest.cn/v1
MINICPM_V_API_KEY=your_key_here
MINICPM_V_MODEL=MiniCPM-V-4.6-Instruct
MINICPM_V_THINKING_MODEL=MiniCPM-V-4.6-Thinking
PORT=5176
```

OpenBMB's API docs currently mention a public trial key. You can use that for quick testing or replace it with your own key.

## Run

```bash
node server.mjs
```

Then open:

```text
http://localhost:5176
```

## What Works Here

- Text-only prompts.
- Image upload: PNG, JPEG, WebP.
- Multiple images per turn.
- Camera snapshot to image.
- Instruct and Thinking model modes.

## What This App Intentionally Does Not Do

This app does not send audio or video. The verified serverless MiniCPM-V API docs describe text-only and vision-language image requests for Chat Completions. Video understanding exists in MiniCPM-V 4.6 model/runtime docs, but it is not part of the simple serverless Chat Completions API spec I found.

## Sources

- Hugging Face: https://huggingface.co/openbmb/MiniCPM-V-4.6
- API docs: https://github.com/OpenBMB/MiniCPM-V/blob/main/docs/api.md
