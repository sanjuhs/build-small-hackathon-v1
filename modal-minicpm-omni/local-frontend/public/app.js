const $ = (selector) => document.querySelector(selector);

const els = {
  remote: $("#remote-url"),
  saveRemote: $("#save-remote"),
  refresh: $("#refresh-status"),
  wake: $("#warm-health"),
  stop: $("#stop-modal"),
  openRemote: $("#open-remote"),
  health: $("#metric-health"),
  worker: $("#metric-worker"),
  queue: $("#metric-queue"),
  latency: $("#metric-latency"),
  inspector: $("#inspector"),
  log: $("#event-log"),
  clearLog: $("#clear-log"),
  wsState: $("#ws-state"),
  emptyState: $("#empty-state"),
  messages: $("#messages"),
  form: $("#chat-form"),
  system: $("#system-prompt"),
  prompt: $("#prompt"),
  recordAudio: $("#record-audio"),
  imagePicker: $("#image-picker"),
  toggleCamera: $("#toggle-camera"),
  capturePhoto: $("#capture-photo"),
  recordVideo: $("#record-video"),
  clearChat: $("#clear-chat"),
  captureStatus: $("#capture-status"),
  cameraStage: $("#camera-stage"),
  cameraPreview: $("#camera-preview"),
  fileInput: $("#file-input"),
  attachments: $("#attachments"),
  streaming: $("#streaming"),
  tts: $("#tts"),
  stopSpeech: $("#stop-speech"),
  maxTokens: $("#max-tokens"),
  temperature: $("#temperature"),
  topP: $("#top-p"),
  send: $("#send-chat"),
  template: $("#message-template"),
};

let defaultRemote = "";
let attachments = [];
let attachmentUrls = new Map();
let transcript = [];
let activeSocket = null;
let audioPlayer;
let audioRecorder = null;
let audioChunks = [];
let audioStream = null;
let cameraStream = null;
let videoRecorder = null;
let videoChunks = [];
let captureStatusTimer = null;

const TRANSCRIPT_LIMIT = 24;
const MAX_TOTAL_ATTACHMENT_BYTES = 35 * 1024 * 1024;
const CHAT_TIMEOUT_MS = 180_000;

async function init() {
  try {
    const config = await fetchJson("/api/config");
    defaultRemote = config.defaultRemote || defaultRemote;
  } catch (error) {
    logEvent("config", error.message, "error");
  }

  const urlRemote = new URLSearchParams(window.location.search).get("remote");
  els.remote.value = urlRemote || defaultRemote;
  localStorage.setItem("minicpm_modal_remote", els.remote.value);
  wireEvents();
  updateRemoteLinks();
  setMetrics("Not checked", "Not checked", "Not checked", "Idle");
  els.inspector.textContent = JSON.stringify(
    {
      remote: currentRemote(),
      note: "Use Wake or Refresh when you want to start or inspect the Modal app.",
    },
    null,
    2,
  );
  logEvent("ready", "local chat loaded");
}

function wireEvents() {
  els.saveRemote.addEventListener("click", () => {
    const remote = normalizeRemote(els.remote.value);
    els.remote.value = remote;
    localStorage.setItem("minicpm_modal_remote", remote);
    updateRemoteLinks();
    logEvent("remote", remote);
  });

  els.remote.addEventListener("change", () => els.saveRemote.click());
  els.refresh.addEventListener("click", refreshStatus);
  els.wake.addEventListener("click", wakeRemote);
  els.stop.addEventListener("click", stopModal);
  els.tts.addEventListener("change", updateSpeechControls);
  els.stopSpeech.addEventListener("click", stopSpeaking);
  els.recordAudio.addEventListener("click", toggleAudioRecording);
  els.imagePicker.addEventListener("click", () => els.fileInput.click());
  els.toggleCamera.addEventListener("click", toggleCamera);
  els.capturePhoto.addEventListener("click", capturePhoto);
  els.recordVideo.addEventListener("click", toggleVideoRecording);
  els.clearChat.addEventListener("click", clearChatSession);
  els.clearLog.addEventListener("click", () => {
    els.log.innerHTML = "";
  });

  els.fileInput.addEventListener("change", () => {
    attachments = [...attachments, ...Array.from(els.fileInput.files || [])];
    els.fileInput.value = "";
    renderAttachments();
  });

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendChat().catch((error) => {
      appendMessage("error", error.message, "Error");
      setWsState("Error", "error");
      logEvent("chat error", error.message, "error");
      els.send.disabled = false;
      updateEmptyState();
    });
  });

  els.prompt.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });
  els.prompt.addEventListener("input", autosizePrompt);

  els.streaming.checked = true;
  updateSpeechControls();
  updateCaptureControls();
  autosizePrompt();
  window.addEventListener("beforeunload", () => {
    stopAudioTracks();
    stopCameraTracks();
    revokeAllAttachmentUrls();
  });
}

function normalizeRemote(value) {
  const url = new URL(value || defaultRemote);
  url.hash = "";
  url.search = "";
  return url.toString().replace(/\/$/, "");
}

function currentRemote() {
  return normalizeRemote(els.remote.value);
}

function updateRemoteLinks() {
  const remote = currentRemote();
  els.openRemote.href = remote;
  document.querySelectorAll("[data-remote-path]").forEach((link) => {
    link.href = remote + link.dataset.remotePath;
  });
}

function wsUrl(path) {
  const url = new URL(currentRemote());
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = path;
  url.searchParams.set("client_surface", "local_cockpit");
  url.searchParams.set("page_route", "local_cockpit");
  return url.toString();
}

async function modalGet(path) {
  return fetchJson(`/api/proxy?remote=${encodeURIComponent(currentRemote())}&path=${encodeURIComponent(path)}`);
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
    const message = payload.error || payload.detail || response.statusText;
    throw new Error(message);
  }
  return payload;
}

async function refreshStatus() {
  updateRemoteLinks();
  const started = performance.now();
  setMetrics("Checking", "Checking", "Checking", "...");
  logEvent("status", "refresh started");

  try {
    const health = await modalGet("/health");
    const [statusResult, workersResult, queueResult, appsResult] = await Promise.allSettled([
      modalGet("/status"),
      modalGet("/workers"),
      modalGet("/api/queue"),
      modalGet("/api/apps"),
    ]);

    const status = settledValue(statusResult);
    const workers = settledValue(workersResult);
    const queue = settledValue(queueResult);
    const apps = settledValue(appsResult);
    const latency = Math.round(performance.now() - started);

    els.health.textContent = health.status || "OK";
    els.worker.textContent = status
      ? `${status.idle_workers ?? 0} idle / ${status.busy_workers ?? 0} busy`
      : "Unknown";
    els.queue.textContent = status ? `${status.queue_length ?? 0} waiting` : "Unknown";
    els.latency.textContent = `${latency} ms`;
    els.inspector.textContent = JSON.stringify({ health, status, workers, queue, apps }, null, 2);
    logEvent("status", "remote responded");
  } catch (error) {
    setMetrics("Offline", "Unknown", "Unknown", "Failed");
    els.inspector.textContent = JSON.stringify({ error: error.message }, null, 2);
    logEvent("status", error.message, "error");
  }
}

function settledValue(result) {
  return result.status === "fulfilled" ? result.value : { error: result.reason.message };
}

function setMetrics(health, worker, queue, latency) {
  els.health.textContent = health;
  els.worker.textContent = worker;
  els.queue.textContent = queue;
  els.latency.textContent = latency;
}

function autosizePrompt() {
  els.prompt.style.height = "auto";
  els.prompt.style.height = `${Math.min(180, Math.max(26, els.prompt.scrollHeight))}px`;
}

function updateEmptyState() {
  els.emptyState.hidden = els.messages.children.length > 0;
}

async function wakeRemote() {
  const started = performance.now();
  logEvent("wake", "health check started");
  els.health.textContent = "Waking";
  try {
    const health = await modalGet("/health");
    els.health.textContent = health.status || "OK";
    els.latency.textContent = `${Math.round(performance.now() - started)} ms`;
    logEvent("wake", "ready");
  } catch (error) {
    els.health.textContent = "Failed";
    logEvent("wake", error.message, "error");
  }
}

async function stopModal() {
  if (!window.confirm("Terminate running Modal containers for this app now?")) return;
  logEvent("stop", "container stop requested");
  els.stop.disabled = true;
  try {
    const result = await fetchJson("/local/stop", { method: "POST" });
    logEvent("stop", `${result.stopped_count ?? 0} container(s) stopped`);
    setMetrics("No warm container", "No warm container", "Not checked", "Idle");
    setWsState("Idle", "");
  } catch (error) {
    logEvent("stop", error.message, "error");
  } finally {
    els.stop.disabled = false;
  }
}

function mediaCaptureSupported() {
  return Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
}

function updateCaptureControls() {
  const supported = mediaCaptureSupported();
  const audioRecording = audioRecorder?.state === "recording";
  const videoRecording = videoRecorder?.state === "recording";
  const cameraOn = Boolean(cameraStream);

  els.recordAudio.disabled = !supported || videoRecording;
  els.recordAudio.textContent = audioRecording ? "Stop" : "Voice";
  els.recordAudio.classList.toggle("recording", audioRecording);
  els.toggleCamera.disabled = !navigator.mediaDevices?.getUserMedia || videoRecording;
  els.toggleCamera.textContent = cameraOn ? "Close" : "Camera";
  els.capturePhoto.disabled = !cameraOn || videoRecording;
  els.recordVideo.disabled = !supported || !cameraOn || audioRecording;
  els.clearChat.disabled = audioRecording || videoRecording;
  els.recordVideo.textContent = videoRecording ? "Stop" : "Record clip";
  els.recordVideo.classList.toggle("recording", videoRecording);

  if (!supported) {
    els.captureStatus.textContent = "Capture unsupported";
  } else if (audioRecording) {
    els.captureStatus.textContent = "Recording audio";
  } else if (videoRecording) {
    els.captureStatus.textContent = "Recording video";
  } else if (cameraOn) {
    els.captureStatus.textContent = "Camera ready";
  } else {
    els.captureStatus.textContent = "Ready";
  }
}

function flashCaptureStatus(text) {
  window.clearTimeout(captureStatusTimer);
  els.captureStatus.textContent = text;
  captureStatusTimer = window.setTimeout(updateCaptureControls, 2400);
}

async function toggleAudioRecording() {
  if (audioRecorder?.state === "recording") {
    audioRecorder.stop();
    return;
  }

  if (!mediaCaptureSupported()) {
    logEvent("capture", "MediaRecorder is not available in this browser", "error");
    return;
  }

  try {
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    const mimeType = pickMimeType(["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]);
    audioChunks = [];
    audioRecorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : undefined);
    audioRecorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) audioChunks.push(event.data);
    });
    audioRecorder.addEventListener("stop", () => {
      const type = audioRecorder.mimeType || "audio/webm";
      const blob = new Blob(audioChunks, { type });
      stopAudioTracks();
      audioRecorder = null;
      audioChunks = [];
      if (blob.size > 0) {
        addBlobAttachment(blob, `voice-${timestampSlug()}.${extensionForMime(type, "webm")}`);
      }
      updateCaptureControls();
      if (blob.size > 0) flashCaptureStatus("Voice note ready");
    });
    audioRecorder.start();
    logEvent("capture", "audio recording started");
    updateCaptureControls();
  } catch (error) {
    stopAudioTracks();
    logEvent("capture", error.message, "error");
    updateCaptureControls();
  }
}

async function toggleCamera() {
  if (cameraStream) {
    stopCameraTracks();
    updateCaptureControls();
    return;
  }

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    els.cameraPreview.srcObject = cameraStream;
    els.cameraStage.hidden = false;
    await els.cameraPreview.play();
    logEvent("capture", "camera opened");
  } catch (error) {
    stopCameraTracks();
    logEvent("capture", error.message, "error");
  } finally {
    updateCaptureControls();
  }
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
  addBlobAttachment(blob, `photo-${timestampSlug()}.jpg`, "image/jpeg");
  logEvent("capture", "photo attached");
  flashCaptureStatus("Image ready");
}

function toggleVideoRecording() {
  if (videoRecorder?.state === "recording") {
    videoRecorder.stop();
    return;
  }
  if (!cameraStream || !mediaCaptureSupported()) return;

  try {
    const mimeType = pickMimeType([
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ]);
    videoChunks = [];
    videoRecorder = new MediaRecorder(cameraStream, mimeType ? { mimeType } : undefined);
    videoRecorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) videoChunks.push(event.data);
    });
    videoRecorder.addEventListener("stop", () => {
      const type = videoRecorder.mimeType || "video/webm";
      const blob = new Blob(videoChunks, { type });
      videoRecorder = null;
      videoChunks = [];
      if (blob.size > 0) {
        addBlobAttachment(blob, `clip-${timestampSlug()}.${extensionForMime(type, "webm")}`);
        logEvent("capture", "video attached");
      }
      updateCaptureControls();
      if (blob.size > 0) flashCaptureStatus("Video ready");
    });
    videoRecorder.start();
    logEvent("capture", "video recording started");
  } catch (error) {
    videoRecorder = null;
    videoChunks = [];
    logEvent("capture", error.message, "error");
  } finally {
    updateCaptureControls();
  }
}

function addBlobAttachment(blob, name, explicitType = blob.type) {
  const file = new File([blob], name, {
    type: explicitType || blob.type || "application/octet-stream",
    lastModified: Date.now(),
  });
  attachments = [...attachments, file];
  renderAttachments();
}

function getAttachmentUrl(file) {
  if (!attachmentUrls.has(file)) {
    attachmentUrls.set(file, URL.createObjectURL(file));
  }
  return attachmentUrls.get(file);
}

function revokeAttachmentUrl(file) {
  const url = attachmentUrls.get(file);
  if (url) URL.revokeObjectURL(url);
  attachmentUrls.delete(file);
}

function revokeAllAttachmentUrls() {
  attachments.forEach(revokeAttachmentUrl);
  attachmentUrls = new Map();
}

function clearAttachments() {
  revokeAllAttachmentUrls();
  attachments = [];
  renderAttachments();
}

function stopAudioTracks() {
  audioStream?.getTracks().forEach((track) => track.stop());
  audioStream = null;
}

function stopCameraTracks() {
  if (videoRecorder?.state === "recording") {
    videoRecorder.stop();
  }
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  els.cameraPreview.pause();
  els.cameraPreview.srcObject = null;
  els.cameraStage.hidden = true;
}

function clearChatSession() {
  transcript = [];
  clearAttachments();
  els.messages.innerHTML = "";
  els.prompt.value = "";
  autosizePrompt();
  stopSpeaking();
  updateEmptyState();
  logEvent("session", "cleared");
}

function pickMimeType(types) {
  return types.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionForMime(type, fallback) {
  if (/mp4/i.test(type)) return "mp4";
  if (/mpeg/i.test(type)) return "mp3";
  if (/jpeg/i.test(type)) return "jpg";
  if (/png/i.test(type)) return "png";
  if (/webm/i.test(type)) return "webm";
  return fallback;
}

function timestampSlug() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "");
}

function renderAttachments() {
  els.attachments.innerHTML = "";
  attachments.forEach((file, index) => {
    const kind = file.type.split("/")[0] || "file";
    const item = document.createElement("article");
    item.className = `attachment ${kind}`;
    const url = getAttachmentUrl(file);
    const size = file.size < 1024 * 1024
      ? `${Math.round(file.size / 1024)} KB`
      : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

    const preview = document.createElement("div");
    preview.className = "attachment-preview";
    if (file.type.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = url;
      img.alt = "";
      preview.append(img);
    } else if (file.type.startsWith("audio/")) {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = url;
      preview.append(audio);
    } else if (file.type.startsWith("video/")) {
      const video = document.createElement("video");
      video.controls = true;
      video.muted = true;
      video.src = url;
      preview.append(video);
    } else {
      preview.textContent = kind.toUpperCase();
    }

    const meta = document.createElement("div");
    meta.className = "attachment-meta";
    const title = document.createElement("strong");
    title.textContent = kind === "audio" ? "Voice note" : kind === "image" ? "Image" : kind === "video" ? "Video" : "File";
    const detail = document.createElement("span");
    detail.textContent = `${file.name} · ${size}`;
    meta.append(title, detail);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.title = "Remove";
    remove.addEventListener("click", () => {
      const [removed] = attachments.splice(index, 1);
      if (removed) revokeAttachmentUrl(removed);
      renderAttachments();
    });
    item.append(preview, meta, remove);
    els.attachments.append(item);
  });
}

async function sendChat() {
  if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
    activeSocket.close();
  }

  const userText = els.prompt.value.trim();
  if (audioRecorder?.state === "recording" || videoRecorder?.state === "recording") {
    throw new Error("Stop the active recording before sending.");
  }
  if (!userText && attachments.length === 0) return;
  validateAttachmentsForTurn(attachments);

  els.send.disabled = true;
  setWsState("Preparing", "live");
  els.streaming.checked = true;

  const content = await buildUserContent(userText, attachments);
  const displayedInput = buildDisplayedInput(userText, attachments);
  appendMessage("user", displayedInput, "You");
  els.prompt.value = "";
  autosizePrompt();
  clearAttachments();

  const assistant = appendMessage("assistant", "", "MiniCPM-o 4.5");
  const assistantText = assistant.querySelector(".message-text");
  let finalText = "";

  const messages = [];
  const systemPrompt = els.system.value.trim();
  if (systemPrompt) messages.push({ role: "system", content: systemPrompt });
  messages.push(...transcript.slice(-TRANSCRIPT_LIMIT), { role: "user", content });

  const payload = {
    messages,
    streaming: true,
    generation: {
      max_new_tokens: numberValue(els.maxTokens, 512),
      temperature: numberValue(els.temperature, 0.7),
      top_p: numberValue(els.topP, 0.8),
    },
    tts: {
      enabled: false,
      mode: "text_only",
    },
    image: {
      max_slice_nums: null,
      use_image_id: true,
    },
    omni_mode: false,
    enable_thinking: false,
  };

  logEvent("chat", `opening ${wsUrl("/ws/chat")}`);
  setWsState("Connecting", "live");

  await new Promise((resolve, reject) => {
    const socket = new WebSocket(wsUrl("/ws/chat"));
    activeSocket = socket;
    const started = performance.now();
    let settled = false;
    const timeout = window.setTimeout(() => {
      fail(new Error("MiniCPM did not finish this turn. Try a smaller media message or one attachment at a time."));
    }, CHAT_TIMEOUT_MS);

    const finish = () => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      resolve();
    };

    const fail = (error) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      updateMeta(assistant, "Error");
      assistantText.textContent = "";
      setWsState("Error", "error");
      try {
        socket.close();
      } catch {}
      reject(error);
    };

    socket.addEventListener("open", () => {
      setWsState("Streaming", "live");
      socket.send(JSON.stringify(payload));
      logEvent("chat", "payload sent");
    });

    socket.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "prefill_done") {
        updateMeta(assistant, `Prefill ${msg.input_tokens ?? "?"} tokens`);
        return;
      }
      if (msg.type === "chunk") {
        if (msg.text_delta) {
          finalText += msg.text_delta;
          assistantText.textContent = finalText;
          scrollMessages();
        }
        if (msg.audio_data) audioPlayer.enqueue(msg.audio_data);
        return;
      }
      if (msg.type === "done") {
        finalText = msg.text || finalText;
        assistantText.textContent = finalText || "[done]";
        const elapsed = Math.round(performance.now() - started);
        updateMeta(
          assistant,
          `${msg.input_tokens ?? "?"} in / ${msg.generated_tokens ?? "?"} out / ${elapsed} ms`,
        );
        if (msg.audio_data) audioPlayer.enqueue(msg.audio_data);
        transcript.push(
          { role: "user", content: compactUserText(userText, displayedInput) },
          { role: "assistant", content: finalText || "[no text]" },
        );
        transcript = transcript.slice(-TRANSCRIPT_LIMIT);
        setWsState("Done", "live");
        logEvent("chat", "done");
        if (els.tts.checked) speakText(finalText);
        socket.close();
        finish();
        return;
      }
      if (msg.type === "error") {
        fail(new Error(humanizeRemoteError(msg.error || "Remote chat error")));
        return;
      }
      logEvent("chat event", JSON.stringify(msg));
    });

    socket.addEventListener("error", () => {
      fail(new Error("WebSocket error"));
    });

    socket.addEventListener("close", () => {
      if (!settled && els.wsState.textContent !== "Done") {
        fail(new Error("The remote connection closed before MiniCPM returned an answer."));
      }
    });
  });

  els.send.disabled = false;
  await refreshStatus();
}

function humanizeRemoteError(message) {
  if (/Sizes of tensors must match/i.test(message)) {
    return "The remote model rejected that request shape. Streaming mode is now locked on; try sending it again.";
  }
  return message;
}

function updateSpeechControls() {
  const supported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  els.tts.disabled = !supported;
  els.stopSpeech.disabled = !supported || !window.speechSynthesis.speaking;
  if (!supported) {
    els.tts.checked = false;
    els.tts.closest("label").title = "This browser does not expose speech playback.";
  }
}

function speakText(text) {
  const clean = (text || "").trim();
  if (!clean || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.volume = 1;
  utterance.onstart = updateSpeechControls;
  utterance.onend = updateSpeechControls;
  utterance.onerror = updateSpeechControls;
  window.speechSynthesis.speak(utterance);
  updateSpeechControls();
}

function stopSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  updateSpeechControls();
}

function numberValue(input, fallback) {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function setWsState(text, variant) {
  els.wsState.textContent = text;
  els.wsState.className = `pill ${variant || ""}`.trim();
}

function appendMessage(role, text, meta) {
  const node = els.template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".avatar").textContent = role === "assistant" ? "M" : role === "user" ? "U" : "!";
  node.querySelector(".message-meta").textContent = meta;
  node.querySelector(".message-text").textContent = text;
  els.messages.append(node);
  updateEmptyState();
  scrollMessages();
  return node;
}

function updateMeta(messageNode, text) {
  messageNode.querySelector(".message-meta").textContent = text;
}

function scrollMessages() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function buildDisplayedInput(text, files) {
  const names = files.map((file) => {
    if (file.type.startsWith("audio/")) return "[Voice note]";
    if (file.type.startsWith("image/")) return "[Image attached]";
    if (file.type.startsWith("video/")) return "[Video attached]";
    return `[${file.type || "file"}: ${file.name}]`;
  });
  return [text, ...names].filter(Boolean).join("\n");
}

function compactUserText(text, displayedInput) {
  return text || displayedInput || "[media input]";
}

function validateAttachmentsForTurn(files) {
  const videos = files.filter((file) => file.type.startsWith("video/"));
  const audios = files.filter((file) => file.type.startsWith("audio/"));
  const images = files.filter((file) => file.type.startsWith("image/"));
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);

  if (videos.length > 1) {
    throw new Error("Send one video per message for the turn-based MiniCPM endpoint. Multiple videos can hang or return no answer.");
  }
  if (audios.length > 1) {
    throw new Error("Send one voice/audio note per message. Multiple audio files can overload this endpoint.");
  }
  if (videos.length && audios.length) {
    throw new Error("For this local turn-based chat, send either a video or a voice note in one message. Use the remote Omni page for live audio+video together.");
  }
  if (images.length > 4) {
    throw new Error("Send up to four images at a time. More than that gets unreliable on this endpoint.");
  }
  if (totalBytes > MAX_TOTAL_ATTACHMENT_BYTES) {
    throw new Error("That media batch is too large for a reliable turn. Try one shorter clip or fewer attachments.");
  }
}

async function buildUserContent(text, files) {
  if (files.length === 0) return text;

  const parts = [];
  if (text) parts.push({ type: "text", text });

  for (const file of files) {
    if (file.type.startsWith("image/")) {
      parts.push({ type: "image", data: await fileToBase64(file) });
    } else if (file.type.startsWith("video/")) {
      parts.push({ type: "video", data: await fileToBase64(file), stack_frames: 1 });
    } else if (file.type.startsWith("audio/")) {
      parts.push({
        type: "audio",
        data: await audioFileToPcmBase64(file),
        sample_rate: 16000,
      });
    } else {
      logEvent("file skipped", `${file.name}: unsupported type`, "error");
    }
  }

  return parts;
}

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  return bytesToBase64(new Uint8Array(buffer));
}

async function audioFileToPcmBase64(file) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const context = new AudioContextClass();
  const input = await file.arrayBuffer();
  const decoded = await context.decodeAudioData(input.slice(0));
  await context.close();

  const targetRate = 16000;
  const frames = Math.max(1, Math.ceil(decoded.duration * targetRate));
  const offline = new OfflineAudioContext(1, frames, targetRate);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start(0);
  const rendered = await offline.startRendering();
  const mono = rendered.getChannelData(0);
  return bytesToBase64(new Uint8Array(mono.buffer.slice(0)));
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function base64ToFloat32Array(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const aligned = bytes.byteLength - (bytes.byteLength % 4);
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + aligned);
  return new Float32Array(buffer);
}

function logEvent(title, detail = "", variant = "") {
  const event = document.createElement("div");
  event.className = `event ${variant}`.trim();
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString();
  const text = document.createElement("div");
  text.textContent = detail ? `${title}: ${detail}` : title;
  event.append(time, text);
  els.log.prepend(event);
}

class PcmAudioPlayer {
  constructor(sampleRate) {
    this.sampleRate = sampleRate;
    this.context = null;
    this.nextTime = 0;
  }

  async ensure() {
    if (!this.context) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      this.context = new AudioContextClass({ sampleRate: this.sampleRate });
    }
    if (this.context.state === "suspended") {
      await this.context.resume();
    }
  }

  enqueue(base64) {
    if (!base64) return;
    this.ensure().then(() => {
      const samples = base64ToFloat32Array(base64);
      if (!samples.length) return;
      const buffer = this.context.createBuffer(1, samples.length, this.sampleRate);
      buffer.copyToChannel(samples, 0);
      const source = this.context.createBufferSource();
      source.buffer = buffer;
      source.connect(this.context.destination);
      const startAt = Math.max(this.context.currentTime + 0.02, this.nextTime);
      source.start(startAt);
      this.nextTime = startAt + buffer.duration;
    });
  }
}

audioPlayer = new PcmAudioPlayer(24000);
init();
