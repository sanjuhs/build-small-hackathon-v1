const state = {
  history: [],
  activeTab: "chat",
  chatAbort: null,
  pdfAbort: null,
};

const els = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  modelInput: document.getElementById("modelInput"),
  maxTokens: document.getElementById("maxTokens"),
  temperature: document.getElementById("temperature"),
  refreshStatus: document.getElementById("refreshStatus"),
  tabs: [...document.querySelectorAll(".tab")],
  panels: {
    chat: document.getElementById("chatPanel"),
    pdf: document.getElementById("pdfPanel"),
    stats: document.getElementById("statsPanel"),
  },
  imageInput: document.getElementById("imageInput"),
  imagePreview: document.getElementById("imagePreview"),
  chatPrompt: document.getElementById("chatPrompt"),
  runChat: document.getElementById("runChat"),
  clearChat: document.getElementById("clearChat"),
  chatOutput: document.getElementById("chatOutput"),
  chatMetrics: document.getElementById("chatMetrics"),
  pdfInput: document.getElementById("pdfInput"),
  pdfMaxPages: document.getElementById("pdfMaxPages"),
  pdfDpi: document.getElementById("pdfDpi"),
  pdfPrompt: document.getElementById("pdfPrompt"),
  runPdf: document.getElementById("runPdf"),
  pdfSummary: document.getElementById("pdfSummary"),
  pdfPages: document.getElementById("pdfPages"),
  historyTable: document.getElementById("historyTable"),
  clearStats: document.getElementById("clearStats"),
};

init();

function init() {
  lucide.createIcons();
  bindTabs();
  bindFiles();
  els.refreshStatus.addEventListener("click", refreshStatus);
  els.runChat.addEventListener("click", runChat);
  els.clearChat.addEventListener("click", clearChat);
  els.runPdf.addEventListener("click", runPdf);
  els.clearStats.addEventListener("click", () => {
    state.history = [];
    renderHistory();
  });
  refreshStatus();
  renderMetrics(els.chatMetrics, null);
  renderHistory();
}

function bindTabs() {
  for (const tab of els.tabs) {
    tab.addEventListener("click", () => {
      state.activeTab = tab.dataset.tab;
      for (const item of els.tabs) item.classList.toggle("active", item === tab);
      for (const [name, panel] of Object.entries(els.panels)) panel.classList.toggle("active", name === state.activeTab);
      lucide.createIcons();
    });
  }
}

function bindFiles() {
  els.imageInput.addEventListener("change", () => {
    const file = els.imageInput.files?.[0];
    if (!file) return;
    els.imagePreview.src = URL.createObjectURL(file);
    els.imagePreview.classList.add("visible");
  });
  els.pdfInput.addEventListener("change", () => {
    const file = els.pdfInput.files?.[0];
    els.pdfSummary.textContent = file ? `Ready: ${file.name}` : "No PDF selected.";
  });
}

async function refreshStatus() {
  setStatus("Checking Ollama...", "warn");
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    const version = data.version?.version || "unknown";
    const running = data.ps?.models?.[0];
    if (data.defaultModel) els.modelInput.value = els.modelInput.value || data.defaultModel;
    setStatus(running ? `Ollama ${version}; warm ${formatBytes(running.size_vram)}` : `Ollama ${version}; model idle`, "ok");
  } catch {
    setStatus("Ollama unavailable", "bad");
  }
}

function setStatus(text, tone) {
  els.statusText.textContent = text;
  els.statusDot.className = `status-dot ${tone === "ok" ? "ok" : tone === "bad" ? "bad" : ""}`;
}

async function runChat() {
  if (state.chatAbort) state.chatAbort.abort();
  const abort = new AbortController();
  state.chatAbort = abort;
  els.chatOutput.textContent = "";
  renderMetrics(els.chatMetrics, { state: "running" });

  const form = new FormData();
  form.set("message", els.chatPrompt.value);
  form.set("model", els.modelInput.value.trim());
  form.set("temperature", els.temperature.value);
  form.set("max_tokens", els.maxTokens.value);
  const image = els.imageInput.files?.[0];
  if (image) form.set("image", image);

  let finalStats = null;
  const started = performance.now();
  try {
    await readNdjson(fetch("/api/chat", { method: "POST", body: form, signal: abort.signal }), (event) => {
      if (event.type === "token") {
        els.chatOutput.textContent += event.text;
        els.chatOutput.scrollTop = els.chatOutput.scrollHeight;
        renderMetrics(els.chatMetrics, { ttftMs: event.ttftMs, elapsedMs: event.elapsedMs, state: "streaming" });
      } else if (event.type === "done") {
        finalStats = event.stats;
        renderMetrics(els.chatMetrics, finalStats);
      } else if (event.type === "error") {
        els.chatOutput.textContent += `\n[error] ${event.message}`;
      }
    });
  } finally {
    state.chatAbort = null;
    if (finalStats) addHistory("Image/chat", finalStats, `${els.chatOutput.textContent.length} chars`);
    else renderMetrics(els.chatMetrics, { totalMs: Math.round(performance.now() - started), state: "stopped" });
    refreshStatus();
  }
}

function clearChat() {
  if (state.chatAbort) state.chatAbort.abort();
  els.chatOutput.textContent = "";
  els.imageInput.value = "";
  els.imagePreview.removeAttribute("src");
  els.imagePreview.classList.remove("visible");
  renderMetrics(els.chatMetrics, null);
}

async function runPdf() {
  const file = els.pdfInput.files?.[0];
  if (!file) {
    els.pdfSummary.textContent = "Choose a PDF first.";
    return;
  }
  if (state.pdfAbort) state.pdfAbort.abort();
  const abort = new AbortController();
  state.pdfAbort = abort;
  els.pdfPages.innerHTML = "";
  els.pdfSummary.textContent = "Rendering and transcribing locally...";

  const form = new FormData();
  form.set("file", file);
  form.set("model", els.modelInput.value.trim());
  form.set("prompt", els.pdfPrompt.value);
  form.set("dpi", els.pdfDpi.value);
  form.set("max_pages", els.pdfMaxPages.value);
  form.set("temperature", "0");
  form.set("max_tokens", els.maxTokens.value);

  const pages = new Map();
  try {
    await readNdjson(fetch("/api/pdf", { method: "POST", body: form, signal: abort.signal }), (event) => {
      if (event.type === "pdf_start") {
        els.pdfSummary.textContent = `${event.filename}: ${event.pagesPlanned}/${event.pagesTotal} pages at ${event.dpi} DPI`;
      } else if (event.type === "page_start") {
        const card = createPageCard(event);
        pages.set(event.page, card);
        els.pdfPages.appendChild(card.root);
      } else if (event.type === "token") {
        const card = pages.get(event.page);
        if (card) {
          card.output.textContent += event.text;
          card.metrics.textContent = `TTFT ${event.ttftMs ?? "-"} ms · ${event.elapsedMs} ms`;
          card.output.scrollTop = card.output.scrollHeight;
        }
      } else if (event.type === "done" && event.page) {
        const card = pages.get(event.page);
        if (card) {
          card.stats = event.stats;
          card.metrics.textContent = metricSummary(event.stats);
          addHistory(`PDF page ${event.page}`, event.stats, `${event.stats.chars} chars`);
        }
      } else if (event.type === "page_done") {
        const card = pages.get(event.page);
        if (card) card.output.textContent = event.text || card.output.textContent;
      } else if (event.type === "pdf_done") {
        els.pdfSummary.textContent = `Done: ${event.pages.length} pages in ${event.totalMs} ms`;
        addHistory("PDF total", { totalMs: event.totalMs, chars: event.text.length }, `${event.pages.length} pages`);
      } else if (event.type === "error" || event.type === "page_error") {
        els.pdfSummary.textContent = event.message || "PDF run hit an error.";
      }
    });
  } finally {
    state.pdfAbort = null;
    refreshStatus();
  }
}

function createPageCard(event) {
  const root = document.createElement("article");
  root.className = "page-card";
  const img = document.createElement("img");
  img.src = event.preview;
  img.alt = `PDF page ${event.page}`;
  const text = document.createElement("div");
  text.className = "page-text";
  const header = document.createElement("header");
  const title = document.createElement("span");
  title.textContent = `Page ${event.page}`;
  const metrics = document.createElement("span");
  metrics.textContent = `Rendered ${event.renderMs} ms`;
  const output = document.createElement("pre");
  output.textContent = "";
  header.append(title, metrics);
  text.append(header, output);
  root.append(img, text);
  return { root, output, metrics, stats: null };
}

async function readNdjson(fetchPromise, onEvent) {
  const response = await fetchPromise;
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}

function renderMetrics(container, stats) {
  const items = [
    ["TTFT", stats?.ttftMs ?? stats?.state ?? "-"],
    ["Total", stats?.totalMs ?? stats?.elapsedMs ?? "-"],
    ["Prompt tokens", stats?.promptEvalCount ?? "-"],
    ["Eval tokens", stats?.evalCount ?? "-"],
    ["Load", stats?.loadMs ?? "-"],
    ["Prompt eval", stats?.promptEvalMs ?? "-"],
    ["Eval", stats?.evalMs ?? "-"],
    ["Chars", stats?.chars ?? "-"],
  ];
  container.innerHTML = items.map(([label, value]) => {
    const display = typeof value === "number" && !label.toLowerCase().includes("tokens") && label !== "Chars"
      ? `${value} ms`
      : String(value);
    return `<div class="metric"><span>${label}</span><strong>${escapeHtml(display)}</strong></div>`;
  }).join("");
}

function metricSummary(stats) {
  return `TTFT ${stats.ttftMs ?? "-"} ms · total ${stats.totalMs ?? "-"} ms · ${stats.chars ?? 0} chars`;
}

function addHistory(kind, stats, note) {
  state.history.unshift({
    kind,
    note,
    ttftMs: stats.ttftMs ?? "-",
    totalMs: stats.totalMs ?? "-",
    promptEvalCount: stats.promptEvalCount ?? "-",
    evalCount: stats.evalCount ?? "-",
    evalMs: stats.evalMs ?? "-",
    chars: stats.chars ?? "-",
  });
  state.history = state.history.slice(0, 80);
  renderHistory();
}

function renderHistory() {
  const rows = [
    ["Run", "TTFT", "Total", "Prompt tok", "Eval tok", "Eval", "Output"],
    ...state.history.map((item) => [
      `${item.kind}${item.note ? ` · ${item.note}` : ""}`,
      msCell(item.ttftMs),
      msCell(item.totalMs),
      item.promptEvalCount,
      item.evalCount,
      msCell(item.evalMs),
      item.chars,
    ]),
  ];
  els.historyTable.innerHTML = rows.map((row, index) => {
    return `<div class="history-row ${index === 0 ? "header" : ""}">${row.map((cell) => `<span>${escapeHtml(cell)}</span>`).join("")}</div>`;
  }).join("");
}

function msCell(value) {
  return typeof value === "number" ? `${value} ms` : String(value);
}

function formatBytes(value) {
  const num = Number(value || 0);
  if (num <= 0) return "0 B";
  if (num > 1024 * 1024 * 1024) return `${(num / 1024 / 1024 / 1024).toFixed(2)} GB`;
  return `${Math.round(num / 1024 / 1024)} MB`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

