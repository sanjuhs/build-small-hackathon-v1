import { execFile } from "node:child_process";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const publicDir = resolve(__dirname, "public");
loadEnvFile(resolve(__dirname, ".env"));
const defaultRemote = process.env.MINICPM_MODAL_URL || "";
const appName = process.env.MINICPM_MODAL_APP || "minicpm-omni-45";
const port = Number(process.env.PORT || getArg("--port") || 5174);

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

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload, null, 2);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  res.end(body);
}

function execModal(args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile("modal", args, { timeout: 120_000, ...options }, (error, stdout, stderr) => {
      if (error) {
        error.stdout = stdout;
        error.stderr = stderr;
        reject(error);
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

function normalizeRemote(value) {
  const url = new URL(value || defaultRemote);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("Remote endpoint must use http or https");
  }
  url.hash = "";
  url.search = "";
  return url.toString().replace(/\/$/, "");
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks);
}

async function proxyModal(req, res, requestUrl) {
  const remote = normalizeRemote(requestUrl.searchParams.get("remote"));
  const modalPath = requestUrl.searchParams.get("path") || "/health";
  if (!modalPath.startsWith("/") || modalPath.startsWith("//")) {
    return sendJson(res, 400, { error: "Proxy path must start with a single /" });
  }

  const target = new URL(remote + modalPath);
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await readBody(req);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5 * 60 * 1000);

  try {
    const response = await fetch(target, {
      method: req.method,
      body,
      signal: controller.signal,
      headers: {
        accept: req.headers.accept || "application/json,text/plain,*/*",
        "content-type": req.headers["content-type"] || "application/json",
      },
    });

    const responseBody = Buffer.from(await response.arrayBuffer());
    res.writeHead(response.status, {
      "content-type": response.headers.get("content-type") || "application/octet-stream",
      "cache-control": "no-store",
      "x-modal-proxy-target": target.origin,
    });
    res.end(responseBody);
  } catch (error) {
    sendJson(res, 502, {
      error: error.name === "AbortError" ? "Modal request timed out" : error.message,
      remote,
      path: modalPath,
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function stopModalContainers(res) {
  try {
    const appsResult = await execModal(["app", "list", "--json"]);
    const apps = JSON.parse(appsResult.stdout || "[]");
    const deployedApp = apps.find((app) => app.description === appName && app.state === "deployed");
    if (!deployedApp) {
      return sendJson(res, 404, {
        ok: false,
        appName,
        error: "No deployed Modal app found. Run modal deploy to recreate it.",
      });
    }

    const containersResult = await execModal([
      "container",
      "list",
      "--json",
      "--app-id",
      deployedApp.app_id,
    ]);
    const containers = JSON.parse(containersResult.stdout || "[]");
    const stopped = [];
    for (const container of containers) {
      const containerId = container.container_id || container.id;
      if (!containerId) continue;
      const result = await execModal(["container", "stop", containerId, "--yes"]);
      stopped.push({ container_id: containerId, stdout: result.stdout, stderr: result.stderr });
    }

    sendJson(res, 200, {
      ok: true,
      app_id: deployedApp.app_id,
      stopped_count: stopped.length,
      stopped,
    });
  } catch (error) {
    sendJson(res, 500, {
      ok: false,
      command: "modal app list/container list/container stop",
      error: error.message,
      stdout: error.stdout,
      stderr: error.stderr,
    });
  }
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
      return sendJson(res, 200, { defaultRemote, appName });
    }
    if (requestUrl.pathname === "/api/proxy") {
      return proxyModal(req, res, requestUrl);
    }
    if (requestUrl.pathname === "/local/stop" && req.method === "POST") {
      return stopModalContainers(res);
    }
    if (requestUrl.pathname === "/local/stop") {
      return sendJson(res, 405, { error: "Use POST" });
    }
    return serveStatic(res, requestUrl.pathname);
  } catch (error) {
    return sendJson(res, 500, { error: error.message });
  }
}).listen(port, () => {
  console.log(`MiniCPM local chat UI: http://localhost:${port}`);
  console.log(`Default Modal endpoint: ${defaultRemote}`);
});
