# MiniCPM-V Serverless API Spec

This folder targets the OpenBMB / ModelBest MiniCPM-V serverless Chat Completions API.

Current verified serverless vision model:

- `MiniCPM-V-4.6-Instruct`
- `MiniCPM-V-4.6-Thinking`

I did not find an official `MiniCPM-V-5` vision endpoint yet. The app keeps `MINICPM_V_MODEL` configurable so it can be changed later without touching UI code.

Sources:

- Hugging Face model card: https://huggingface.co/openbmb/MiniCPM-V-4.6
- OpenBMB API docs: https://github.com/OpenBMB/MiniCPM-V/blob/main/docs/api.md

## Upstream API

```text
Base URL: https://api.modelbest.cn/v1
Endpoint: POST /chat/completions
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

### Text Request

```json
{
  "model": "MiniCPM-V-4.6-Instruct",
  "messages": [
    {
      "role": "user",
      "content": "Introduce yourself in one sentence."
    }
  ]
}
```

### Vision Request

Images are passed as base64 data URLs in OpenAI-compatible `image_url` content parts.

```json
{
  "model": "MiniCPM-V-4.6-Instruct",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Describe this image."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,<BASE64_IMAGE>"
          }
        }
      ]
    }
  ]
}
```

## Local Wrapper

The local server is intentionally tiny. It keeps the API key out of browser JavaScript and normalizes responses for the UI.

### `GET /api/config`

Returns public config only. The API key is never returned.

```json
{
  "apiBase": "https://api.modelbest.cn/v1",
  "apiKeyConfigured": true,
  "model": "MiniCPM-V-4.6-Instruct",
  "thinkingModel": "MiniCPM-V-4.6-Thinking",
  "supportedInputs": ["text", "image"]
}
```

### `GET /api/health`

Same config plus `ok: true`.

### `POST /api/chat`

Request:

```json
{
  "model": "MiniCPM-V-4.6-Instruct",
  "system": "You are a precise vision assistant.",
  "prompt": "What is in this screenshot?",
  "images": [
    {
      "name": "screenshot.png",
      "type": "image/png",
      "dataUrl": "data:image/png;base64,..."
    }
  ],
  "history": [
    {
      "role": "user",
      "content": "Previous question"
    },
    {
      "role": "assistant",
      "content": "Previous answer"
    }
  ],
  "max_tokens": 768,
  "temperature": 0.2
}
```

Response:

```json
{
  "ok": true,
  "model": "MiniCPM-V-4.6-Instruct",
  "text": "The image shows...",
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 45,
    "total_tokens": 168
  },
  "raw": {}
}
```

Errors:

```json
{
  "ok": false,
  "error": "MINICPM_V_API_KEY is not configured..."
}
```

## Limits Chosen For The Local UI

- Inputs: text plus PNG/JPEG/WebP images.
- Max images per request: `6`.
- Max total image payload before base64: `18 MB`.
- Video/audio are not exposed in this app because the current serverless API docs only specify text and image Chat Completions for MiniCPM-V 4.6.
