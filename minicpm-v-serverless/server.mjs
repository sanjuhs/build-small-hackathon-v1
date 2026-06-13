import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const publicDir = resolve(__dirname, "public");
loadEnvFile(resolve(__dirname, ".env"));

const config = {
  apiBase: normalizeBaseUrl(process.env.MINICPM_V_API_BASE || "https://api.modelbest.cn/v1"),
  apiKey: process.env.MINICPM_V_API_KEY || "",
  model: process.env.MINICPM_V_MODEL || "MiniCPM-V-4.6-Instruct",
  thinkingModel: process.env.MINICPM_V_THINKING_MODEL || "MiniCPM-V-4.6-Thinking",
  port: Number(process.env.PORT || getArg("--port") || 5176),
  maxBodyBytes: Number(process.env.MAX_BODY_BYTES || 28 * 1024 * 1024),
};

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

function getArg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : null;
}

function loadEnvFile(path) {
  if (!existsSync(path)) return;
  const content = readFileSync(path, "utf8");
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    if (process.env[key] !== undefined) continue;
    process.env[key] = rawValue.replace(/^['"]|['"]$/g, "");
  }
}

function normalizeBaseUrl(value) {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("MINICPM_V_API_BASE must use http or https");
  }
  url.hash = "";
  url.search = "";
  return url.toString().replace(/\/$/, "");
}

function sendJson(res, status, payload) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  res.end(JSON.stringify(payload, null, 2));
}

async function readJsonBody(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.byteLength;
    if (total > config.maxBodyBytes) {
      throw new Error(`Request body is too large. Limit is ${Math.round(config.maxBodyBytes / 1024 / 1024)} MB.`);
    }
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  return raw ? JSON.parse(raw) : {};
}

function publicConfig() {
  return {
    apiBase: config.apiBase,
    apiKeyConfigured: Boolean(config.apiKey),
    model: config.model,
    thinkingModel: config.thinkingModel,
    defaultModel: config.model,
    supportedInputs: ["text", "image"],
    note: "MiniCPM-V 4.6 serverless docs support text-only and vision-language image requests through Chat Completions.",
  };
}

function validateImageDataUrl(image) {
  if (!image || typeof image.dataUrl !== "string") {
    throw new Error("Each image must include a dataUrl.");
  }
  if (!/^data:image\/(png|jpe?g|webp);base64,/i.test(image.dataUrl)) {
    throw new Error("Images must be PNG, JPEG, or WebP data URLs.");
  }
}

function buildMessages(body) {
  const prompt = String(body.prompt || "").trim();
  const images = Array.isArray(body.images) ? body.images : [];
  if (!prompt && images.length === 0) {
    throw new Error("Send text, at least one image, or both.");
  }
  if (images.length > 6) {
    throw new Error("Send up to six images per request for reliable serverless latency.");
  }

  const messages = [];
  const system = String(body.system || "").trim();
  if (system) messages.push({ role: "system", content: system });

  const history = Array.isArray(body.history) ? body.history.slice(-12) : [];
  for (const item of history) {
    if (!item || !["user", "assistant"].includes(item.role)) continue;
    const content = String(item.content || "").trim();
    if (content) messages.push({ role: item.role, content });
  }

  const content = [];
  if (prompt) content.push({ type: "text", text: prompt });
  for (const image of images) {
    validateImageDataUrl(image);
    content.push({ type: "image_url", image_url: { url: image.dataUrl } });
  }

  messages.push({ role: "user", content: content.length === 1 && prompt && images.length === 0 ? prompt : content });
  return messages;
}

async function callMiniCpmV(body) {
  if (!config.apiKey) {
    throw new Error("MINICPM_V_API_KEY is not configured. Copy .env.example to .env and add a ModelBest/OpenBMB API key.");
  }

  const model = String(body.model || config.model);
  const payload = {
    model,
    messages: buildMessages(body),
    max_tokens: Number(body.max_tokens || 768),
    temperature: Number(body.temperature ?? 0.2),
    stream: false,
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Number(body.timeout_ms || 120_000));
  try {
    const response = await fetch(`${config.apiBase}/chat/completions`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        authorization: `Bearer ${config.apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const text = await response.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text };
    }

    if (!response.ok) {
      const message = data.error?.message || data.error || data.detail || response.statusText;
      const error = new Error(message);
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    const answer = data.choices?.[0]?.message?.content || "";
    return {
      ok: true,
      model: data.model || model,
      text: normalizeResponseText(answer),
      usage: data.usage || null,
      raw: data,
    };
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("MiniCPM-V request timed out. Try fewer images or a smaller image.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function normalizeResponseText(text) {
  if (typeof text !== "string") return "";
  return text.replace(/(?<!\\)\\n/g, "\n");
}

async function serveStatic(res, pathname) {
  const requested = pathname === "/" ? "/index.html" : pathname;
  const safePath = normalize(decodeURIComponent(requested)).replace(/^(\.\.[/\\])+/, "");
  const filePath = resolve(join(publicDir, safePath));

  if (!filePath.startsWith(publicDir)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  try {
    const body = await readFile(filePath);
    res.writeHead(200, {
      "content-type": mimeTypes[extname(filePath)] || "application/octet-stream",
      "cache-control": "no-store",
    });
    res.end(body);
  } catch {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
  }
}

createServer(async (req, res) => {
  const requestUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

  try {
    if (requestUrl.pathname === "/api/config") {
      return sendJson(res, 200, publicConfig());
    }
    if (requestUrl.pathname === "/api/health") {
      return sendJson(res, 200, { ok: true, ...publicConfig() });
    }
    if (requestUrl.pathname === "/api/chat" && req.method === "POST") {
      const body = await readJsonBody(req);
      const result = await callMiniCpmV(body);
      return sendJson(res, 200, result);
    }
    if (requestUrl.pathname === "/api/chat") {
      return sendJson(res, 405, { error: "Use POST" });
    }
    return serveStatic(res, requestUrl.pathname);
  } catch (error) {
    return sendJson(res, error.status || 500, {
      ok: false,
      error: error.message,
      upstream: error.payload,
    });
  }
}).listen(config.port, () => {
  console.log(`MiniCPM-V serverless chat: http://localhost:${config.port}`);
  console.log(`Upstream API base: ${config.apiBase}`);
  console.log(`Model: ${config.model}`);
});
