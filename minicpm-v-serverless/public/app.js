const $ = (selector) => document.querySelector(selector);

const els = {
  status: $("#status-pill"),
  newChat: $("#new-chat"),
  apiBase: $("#api-base"),
  apiKeyState: $("#api-key-state"),
  modelSelect: $("#model-select"),
  system: $("#system-prompt"),
  maxTokens: $("#max-tokens"),
  temperature: $("#temperature"),
  inspector: $("#inspector"),
  empty: $("#empty-state"),
  messages: $("#messages"),
  form: $("#chat-form"),
  cameraStage: $("#camera-stage"),
  cameraPreview: $("#camera-preview"),
  capturePhoto: $("#capture-photo"),
  closeCamera: $("#close-camera"),
  attachments: $("#attachments"),
  prompt: $("#prompt"),
  imageInput: $("#image-input"),
  pickImages: $("#pick-images"),
  openCamera: $("#open-camera"),
  mediaStatus: $("#media-status"),
  send: $("#send-chat"),
  template: $("#message-template"),
};

let images = [];
let imageUrls = new Map();
let history = [];
let cameraStream = null;

const MAX_IMAGES = 6;
const MAX_TOTAL_IMAGE_BYTES = 18 * 1024 * 1024;

init().catch((error) => {
  setStatus("Error", "error");
  appendMessage("error", error.message, "Error");
});

async function init() {
  wireEvents();
  await loadConfig();
  autosizePrompt();
}

function wireEvents() {
  els.newChat.addEventListener("click", clearChat);
  els.pickImages.addEventListener("click", () => els.imageInput.click());
  els.imageInput.addEventListener("change", () => {
    addImageFiles(Array.from(els.imageInput.files || [])).catch((error) => {
      appendMessage("error", error.message, "Image error");
    });
    els.imageInput.value = "";
  });
  els.openCamera.addEventListener("click", openCamera);
  els.capturePhoto.addEventListener("click", capturePhoto);
  els.closeCamera.addEventListener("click", closeCamera);
  els.prompt.addEventListener("input", autosizePrompt);
  els.prompt.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });
  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendChat().catch((error) => {
      setStatus("Error", "error");
      appendMessage("error", error.message, "Error");
      els.send.disabled = false;
    });
  });
  window.addEventListener("beforeunload", () => {
    closeCamera();
    revokeAllImageUrls();
  });
}

async function loadConfig() {
  const config = await fetchJson("/api/config");
  els.apiBase.textContent = config.apiBase || "Unknown";
  els.apiKeyState.textContent = config.apiKeyConfigured ? "Configured" : "Missing";
  els.modelSelect.innerHTML = "";
  addModelOption(config.model, "Instruct");
  addModelOption(config.thinkingModel, "Thinking");
  els.inspector.textContent = JSON.stringify(config, null, 2);
  setStatus(config.apiKeyConfigured ? "Ready" : "Needs key", config.apiKeyConfigured ? "ready" : "error");
}

function addModelOption(value, label) {
  if (!value) return;
  const option = document.createElement("option");
  option.value = value;
  option.textContent = `${label}: ${value}`;
  els.modelSelect.append(option);
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { raw: text };
  }
  if (!response.ok) {
    throw new Error(payload.error || payload.detail || response.statusText);
  }
  return payload;
}

function setStatus(text, variant = "") {
  els.status.textContent = text;
  els.status.className = `pill ${variant}`.trim();
}

function autosizePrompt() {
  els.prompt.style.height = "auto";
  els.prompt.style.height = `${Math.min(180, Math.max(28, els.prompt.scrollHeight))}px`;
}

async function addImageFiles(files) {
  const accepted = files.filter((file) => file.type.startsWith("image/"));
  if (accepted.length !== files.length) {
    throw new Error("MiniCPM-V serverless chat only accepts images here. Use PNG, JPEG, or WebP.");
  }
  const next = [...images, ...accepted];
  validateImages(next);
  images = next;
  renderImages();
  flashMediaStatus(`${accepted.length} image${accepted.length === 1 ? "" : "s"} ready`);
}

function validateImages(files) {
  if (files.length > MAX_IMAGES) {
    throw new Error(`Send up to ${MAX_IMAGES} images per request.`);
  }
  const total = files.reduce((sum, file) => sum + file.size, 0);
  if (total > MAX_TOTAL_IMAGE_BYTES) {
    throw new Error("That image batch is too large. Try fewer or smaller images.");
  }
}

function imageUrl(file) {
  if (!imageUrls.has(file)) {
    imageUrls.set(file, URL.createObjectURL(file));
  }
  return imageUrls.get(file);
}

function revokeImageUrl(file) {
  const url = imageUrls.get(file);
  if (url) URL.revokeObjectURL(url);
  imageUrls.delete(file);
}

function revokeAllImageUrls() {
  images.forEach(revokeImageUrl);
  imageUrls = new Map();
}

function clearImages() {
  revokeAllImageUrls();
  images = [];
  renderImages();
}

function renderImages() {
  els.attachments.innerHTML = "";
  images.forEach((file, index) => {
    const card = document.createElement("article");
    card.className = "attachment";

    const img = document.createElement("img");
    img.src = imageUrl(file);
    img.alt = "";

    const footer = document.createElement("div");
    footer.className = "attachment-footer";
    const name = document.createElement("strong");
    name.textContent = "Image";
    const detail = document.createElement("span");
    detail.textContent = `${file.name} · ${formatSize(file.size)}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      const [removed] = images.splice(index, 1);
      if (removed) revokeImageUrl(removed);
      renderImages();
    });

    footer.append(name, detail, remove);
    card.append(img, footer);
    els.attachments.append(card);
  });
}

function formatSize(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function openCamera() {
  if (cameraStream) return;
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
    });
    els.cameraPreview.srcObject = cameraStream;
    els.cameraStage.hidden = false;
    await els.cameraPreview.play();
    flashMediaStatus("Camera ready");
  } catch (error) {
    closeCamera();
    throw new Error(`Camera failed: ${error.message}`);
  }
}

function closeCamera() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  els.cameraPreview.pause();
  els.cameraPreview.srcObject = null;
  els.cameraStage.hidden = true;
}

async function capturePhoto() {
  if (!cameraStream || !els.cameraPreview.videoWidth) return;
  const canvas = document.createElement("canvas");
  canvas.width = els.cameraPreview.videoWidth;
  canvas.height = els.cameraPreview.videoHeight;
  const context = canvas.getContext("2d");
  context.drawImage(els.cameraPreview, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
  if (!blob) return;
  const file = new File([blob], `camera-${timestampSlug()}.jpg`, {
    type: "image/jpeg",
    lastModified: Date.now(),
  });
  await addImageFiles([file]);
}

async function sendChat() {
  const prompt = els.prompt.value.trim();
  if (!prompt && images.length === 0) return;
  validateImages(images);

  els.send.disabled = true;
  setStatus("Thinking");

  const imagePayload = await Promise.all(
    images.map(async (file) => ({
      name: file.name,
      type: file.type,
      dataUrl: await fileToDataUrl(file),
    })),
  );

  const userText = buildUserText(prompt, images);
  appendMessage("user", userText, "You");
  els.prompt.value = "";
  autosizePrompt();
  clearImages();

  const assistantNode = appendMessage("assistant", "", "MiniCPM-V");
  const assistantText = assistantNode.querySelector(".message-text");
  updateEmptyState();

  const payload = {
    prompt,
    images: imagePayload,
    history,
    system: els.system.value,
    model: els.modelSelect.value,
    max_tokens: Number(els.maxTokens.value || 768),
    temperature: Number(els.temperature.value || 0.2),
  };

  const started = performance.now();
  try {
    const result = await fetchJson("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    assistantText.textContent = result.text || "[no text returned]";
    updateMeta(assistantNode, `${result.model || "MiniCPM-V"} · ${Math.round(performance.now() - started)} ms`);
    history.push(
      { role: "user", content: userText },
      { role: "assistant", content: result.text || "[no text returned]" },
    );
    history = history.slice(-12);
    els.inspector.textContent = JSON.stringify({ usage: result.usage, model: result.model }, null, 2);
    setStatus("Ready", "ready");
  } catch (error) {
    assistantText.textContent = error.message;
    assistantNode.classList.add("error");
    updateMeta(assistantNode, "Error");
    setStatus("Error", "error");
  } finally {
    els.send.disabled = false;
  }
}

function buildUserText(prompt, files) {
  const media = files.map(() => "[Image attached]");
  return [prompt, ...media].filter(Boolean).join("\n");
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error || new Error("Failed to read image"));
    reader.readAsDataURL(file);
  });
}

function appendMessage(role, text, meta) {
  const node = els.template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".avatar").textContent = role === "assistant" ? "V" : role === "user" ? "U" : "!";
  node.querySelector(".message-meta").textContent = meta;
  node.querySelector(".message-text").textContent = text;
  els.messages.append(node);
  updateEmptyState();
  scrollMessages();
  return node;
}

function updateMeta(node, text) {
  node.querySelector(".message-meta").textContent = text;
}

function updateEmptyState() {
  els.empty.hidden = els.messages.children.length > 0;
}

function scrollMessages() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function clearChat() {
  history = [];
  clearImages();
  closeCamera();
  els.messages.innerHTML = "";
  els.prompt.value = "";
  autosizePrompt();
  updateEmptyState();
  setStatus("Ready", "ready");
}

function flashMediaStatus(text) {
  els.mediaStatus.textContent = text;
  window.setTimeout(() => {
    els.mediaStatus.textContent = "Ready";
  }, 2200);
}

function timestampSlug() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "");
}
