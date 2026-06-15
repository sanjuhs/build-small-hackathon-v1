import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import * as CANNON from "cannon-es";
import {
  createIcons,
  Bone,
  Bot,
  Clock,
  Cloud,
  FlipVertical2,
  Flame,
  Grape,
  Hand,
  Heart,
  Magnet,
  Mic,
  MicOff,
  Minimize2,
  MessageCircle,
  MoveUp,
  Package,
  Play,
  RotateCcw,
  RotateCw,
  Route,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
  Waves,
  Zap
} from "https://cdn.jsdelivr.net/npm/lucide@0.468.0/+esm";

import { PET_LOOKS } from "./config.js";
import { ToyAudio } from "./audio.js?v=20260613-sound-recipes";
import { ToyEffects } from "./effects.js";
import { applyPetBlendshape, createPet, petPointerReaction, setPetEmotion, updatePet } from "./pet.js?v=20260614-grounded-gestures";
import { createPetBalanceRig } from "./pet_balance.js?v=20260614-locomotion4";
import { createPhysicsWorld, createToyRoom } from "./room.js?v=20260615-pet-tools1";
import { captureCameraFrame } from "./sensing.js";
import { createSenseFeeds } from "./senses.js?v=20260614-forward-view";

const LUCIDE_ICONS = {
  Bone,
  Bot,
  Clock,
  Cloud,
  FlipVertical2,
  Flame,
  Grape,
  Hand,
  Heart,
  Magnet,
  Mic,
  MicOff,
  Minimize2,
  MessageCircle,
  MoveUp,
  Package,
  Play,
  RotateCcw,
  RotateCw,
  Route,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
  Waves,
  Zap,
};

createIcons({ icons: LUCIDE_ICONS });

const TOYBOX_VERSION = document.body.dataset.toyboxVersion || "v2";
const IS_V3_MODE = TOYBOX_VERSION === "v3";
const DEFAULT_AGENT_KIND = IS_V3_MODE ? "fire_boy" : "squeaky";
const BRAIN_MODE_STORAGE_KEY = "toybox-v3-brain-mode";
const BRAIN_MODE_LABELS = {
  modal: "Modal",
  "ollama-vision": "Ollama V",
  "ollama-text": "Ollama 1B",
};

function mountV3ViewDock() {
  if (!IS_V3_MODE || document.querySelector(".v3-view-dock")) return;
  const grid = document.querySelector(".sense-grid");
  const app = document.getElementById("app");
  if (!grid || !app) return;
  const dock = document.createElement("section");
  dock.className = "v3-view-dock";
  dock.setAttribute("aria-label", "Player and Fire Boy camera views");
  dock.appendChild(grid);
  app.appendChild(dock);
}

const AGENT_SPECS = IS_V3_MODE
  ? [
    { kind: "fire_boy", label: "Fire Boy", home: new CANNON.Vec3(-0.25, 0.06, 0.24), yaw: 0.06 },
  ]
  : [
    { kind: "squeaky", label: "Squeaky", home: new CANNON.Vec3(-2.8, 0.06, 1.15), yaw: 0.38 },
    { kind: "fire_boy", label: "Fire Boy", home: new CANNON.Vec3(-0.85, 0.06, 1.55), yaw: 0.12 },
    { kind: "shark_girl", label: "Shark Girl", home: new CANNON.Vec3(1.1, 0.06, 1.35), yaw: -0.16 },
    { kind: "electraica", label: "Electraica", home: new CANNON.Vec3(2.95, 0.06, 1.05), yaw: -0.38 },
  ];

const RIG_ASSETS = {
  squeaky: "/toy-assets/generated/rigged/squeaky-rigged.glb",
  fire_boy: IS_V3_MODE ? "/fire-boy-rig/fire-boy-rigged-full.glb" : "/toy-assets/generated/rigged/fire-boy-rigged.glb",
  shark_girl: "/toy-assets/generated/rigged/shark-girl-rigged.glb",
  electraica: "/toy-assets/generated/rigged/electraica-rigged.glb",
};

const ABILITY_SETS = {
  squeaky: [
    { power: "time_freeze", label: "Freeze", icon: "clock", prompt: "Use power: time_freeze. Freeze the nearest moving toy and explain what you saw." },
    { power: "shrink", label: "Shrink", icon: "minimize-2", prompt: "Use power: shrink. Make yourself tiny for a moment." },
    { power: "rewind", label: "Rewind", icon: "rotate-ccw", prompt: "Use power: rewind. Bounce the nearest toy backward." },
    { power: "clock_bubble", label: "Bubble", icon: "sparkles", prompt: "Use power: clock_bubble. Push the nearby toys into a round second." },
  ],
  fire_boy: [
    ...(IS_V3_MODE ? [
      { power: "pick_box", label: "Pick Box", icon: "package", prompt: "Fire Boy, pick up the box." },
      { power: "run_loop", label: "Run", icon: "route", prompt: "Fire Boy, run around the toy room." },
    ] : []),
    { power: "fireball", label: "Fireball", icon: "flame", prompt: "Use power: fireball. Send a supervised warm comet at the nearest toy." },
    ...(IS_V3_MODE ? [
      { power: "baby_talk", label: "Talk", icon: "message-circle", prompt: "Fire Boy, say hello to the judges in your tiny baby voice." },
    ] : []),
    { power: "ember_jump", label: "Ember Jump", icon: "move-up", prompt: "Use power: ember_jump. Hop upward with a safe ember flourish." },
    { power: "smoke_poof", label: "Smoke", icon: "cloud", prompt: "Use power: smoke_poof. Make a soft smoke curtain around yourself." },
  ],
  shark_girl: [
    { power: "wave", label: "Wave", icon: "waves", prompt: "Use power: wave. Push the room with a plush tide." },
    { power: "bubble_lift", label: "Bubble Lift", icon: "move-up", prompt: "Use power: bubble_lift. Lift the nearest toy in a bubble." },
    { power: "tide_pull", label: "Tide Pull", icon: "magnet", prompt: "Use power: tide_pull. Pull nearby toys together with a gentle current." },
  ],
  electraica: [
    { power: "shock", label: "Shock", icon: "zap", prompt: "Use power: shock. Zap the nearest toy with manners." },
    { power: "lamp_burst", label: "Lamp Burst", icon: "sparkles", prompt: "Use power: lamp_burst. Make the lamp extremely cheerful." },
    { power: "magnet_pull", label: "Magnet", icon: "magnet", prompt: "Use power: magnet_pull. Pull shiny toys closer." },
  ],
};

const FORCE_CONTROLS = [
  { action: "lift", label: "Lift", icon: "move-up", vector: [0, 2.8, 0], message: "react to force input: the player lifted your balance body" },
  { action: "toss", label: "Toss", icon: "flip-vertical-2", vector: [2.4, 2.6, -1.6], message: "react to force input: the player tossed your balance body" },
  { action: "spin", label: "Spin", icon: "rotate-cw", vector: [1.8, 4.6, -2.2], message: "react to force input: the player spun your balance body" },
  { action: "drop", label: "Drop", icon: "move-up", vector: [0, 3.65, 0], message: "react to force input: the player dropped you from a height" },
  { action: "settle", label: "Settle", icon: "rotate-ccw", vector: [0, 0, 0], message: "react to force input: the player helped you settle upright" },
];

const RECYCLABLE_WASTE_IDS = ["crumpled-paper", "tin-can", "plastic-bottle"];
const LOW_LEVEL_INTERVAL_MS = 1800;

const dom = {
  canvas: document.getElementById("stage"),
  speech: document.getElementById("speech"),
  toast: document.getElementById("toast"),
  agentDock: document.getElementById("agentDock"),
  abilityDock: document.getElementById("abilityDock"),
  forceDock: document.getElementById("forceDock"),
  roomToolDock: document.getElementById("roomToolDock"),
  handToolButton: document.getElementById("handToolButton"),
  foodToolButton: document.getElementById("foodToolButton"),
  petToolButton: document.getElementById("petToolButton"),
  composer: document.getElementById("composer"),
  input: document.getElementById("messageInput"),
  resetButton: document.getElementById("resetButton"),
  autoButton: document.getElementById("autoButton"),
  demoButton: document.getElementById("demoButton"),
  voiceButton: document.getElementById("voiceButton"),
  micButton: document.getElementById("micButton"),
  rigButton: document.getElementById("rigButton"),
  gravityButton: document.getElementById("gravityButton"),
  modeButton: document.getElementById("modeButton"),
  brainModeControl: document.getElementById("brainModeControl"),
  effectFlash: document.getElementById("effectFlash"),
  perceptionTitle: document.getElementById("perceptionTitle"),
  perceptionReadout: document.getElementById("perceptionReadout"),
  petMeters: document.getElementById("petMeters"),
  modelStatus: document.getElementById("modelStatus"),
  agentReadout: document.getElementById("agentReadout"),
  agentLoopAccordion: document.getElementById("agentLoopAccordion"),
  agentLoopSummary: document.getElementById("agentLoopSummary"),
  modelMatrix: document.getElementById("modelMatrix"),
  judgeScorecard: document.getElementById("judgeScorecard"),
  aiEvidence: document.getElementById("aiEvidence"),
  visionBoard: document.getElementById("visionBoard"),
  brainTrace: document.getElementById("brainTrace"),
  copyBrainTraceButton: document.getElementById("copyBrainTraceButton"),
  memoryList: document.getElementById("memoryList"),
  userView: document.getElementById("userView"),
  petView: document.getElementById("petView"),
  audioBars: document.getElementById("audioBars"),
  balanceReadout: document.getElementById("balanceReadout"),
};

if (dom.agentLoopAccordion) {
  dom.agentLoopAccordion.open = !IS_V3_MODE;
}

const renderer = new THREE.WebGLRenderer({ canvas: dom.canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = IS_V3_MODE ? 1.36 : 1.12;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xfff5db, IS_V3_MODE ? 13 : 10, IS_V3_MODE ? 34 : 28);

const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
camera.position.set(IS_V3_MODE ? 5.8 : 6.4, IS_V3_MODE ? 4.2 : 4.7, IS_V3_MODE ? 7.1 : 8.4);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 1.15, 0);
controls.enableDamping = true;
controls.minDistance = 5.2;
controls.maxDistance = 12.5;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minPolarAngle = Math.PI * 0.15;

const audio = new ToyAudio();
updateVoiceButton();
updateMicButton();
const effects = new ToyEffects(scene);
const world = createPhysicsWorld();
const room = createToyRoom({ scene, world, ui: speechOnlyUi(), recordForce, variant: IS_V3_MODE ? "v3" : "v2" });
const senses = createSenseFeeds({ scene, userCamera: camera, userRenderer: renderer, dom, audio });
const gltfLoader = new GLTFLoader();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const dragPlane = new THREE.Plane();
const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const dragHit = new THREE.Vector3();
const dragOffset = new THREE.Vector3();
const dragHistory = [];
const objects = room.objects;
const forceEvents = [];
const interactions = [];
const agents = new Map();
const recycledWasteIds = new Set();
const councilVisionAgents = new Set();
let dialogueTurns = 0;
let rescueTurns = 0;

let activeKind = DEFAULT_AGENT_KIND;
let dragged = null;
let dragPointerId = null;
let hoverAgent = null;
let autoplay = !IS_V3_MODE;
let councilMode = !IS_V3_MODE;
let rigMeshesVisible = true;
let roomToolMode = "hand";
let lastPhysicsTime = performance.now();
let lastAutoAction = 0;
let lastSoundReaction = 0;
let lastRecycleCheck = 0;
let lastVisionBoardRender = 0;
let lastJudgeRender = 0;
let lastLowLevelAction = 0;
let autoIndex = 0;
let lowLevelIndex = 0;
let lowLevelActions = 0;
let modelStatus = { enabled: false, visionEnabled: false, model: "fallback-policy" };
let trainingStatus = { usableRows: 0, totalRows: 0, minRows: 20, ready: false, exists: false };
let judgeStatus = { checks: [], score: { ok: 0, warn: 0, total: 0, requiredOk: 0, requiredTotal: 0, ready: false } };
let aiEvidence = { checks: [], score: { ok: 0, warn: 0, total: 0, requiredOk: 0, requiredTotal: 0, ready: false }, metrics: {} };
let lastLoopMetric = { label: "idle", state: "warn" };
let actionSequence = 0;
let demoRunning = false;
let brainModePinned = false;
let selectedBrainMode = loadBrainMode();

function loadBrainMode() {
  try {
    const stored = localStorage.getItem(BRAIN_MODE_STORAGE_KEY);
    if (stored && Object.hasOwn(BRAIN_MODE_LABELS, stored)) {
      brainModePinned = true;
      return stored;
    }
  } catch {}
  return "modal";
}

function setBrainMode(mode) {
  if (!Object.hasOwn(BRAIN_MODE_LABELS, mode)) return;
  selectedBrainMode = mode;
  brainModePinned = true;
  try {
    localStorage.setItem(BRAIN_MODE_STORAGE_KEY, mode);
  } catch {}
  renderBrainModeControl();
  updateAgentPanel();
  showToast(`Brain: ${BRAIN_MODE_LABELS[mode]}.`);
}

function brainModeAvailable(mode) {
  if (mode === "modal") return Boolean(modelStatus.vlaRouter?.enabled || modelStatus.modalOmniEnabled || modelStatus.modalOmniConfigured);
  if (mode === "ollama-vision") {
    return Boolean(modelStatus.localOllamaAvailable && modelStatus.localOllamaVisionInstalled);
  }
  if (mode === "ollama-text") {
    return Boolean(modelStatus.localOllamaAvailable && modelStatus.localOllamaTextInstalled);
  }
  return false;
}

function brainModeTitle(mode) {
  if (mode === "modal") {
    if (modelStatus.vlaRouter?.enabled) return "Use Modal MiniCPM-V VLA router";
    return modelStatus.modalOmniConfigured ? "Use Modal MiniCPM-o" : "Modal endpoint is not configured";
  }
  if (mode === "ollama-vision") {
    if (!modelStatus.localOllamaAvailable) return `Ollama offline at ${modelStatus.localOllamaEndpoint || "localhost"}`;
    if (!modelStatus.localOllamaVisionInstalled) return `Pull ${modelStatus.localOllamaVisionModel || "MiniCPM-V"}`;
    return `Use ${modelStatus.localOllamaVisionModel}`;
  }
  if (mode === "ollama-text") {
    if (!modelStatus.localOllamaAvailable) return `Ollama offline at ${modelStatus.localOllamaEndpoint || "localhost"}`;
    if (!modelStatus.localOllamaTextInstalled) return `Pull ${modelStatus.localOllamaTextModel || "MiniCPM5"}`;
    return `Use ${modelStatus.localOllamaTextModel}`;
  }
  return "";
}

function renderBrainModeControl() {
  if (!dom.brainModeControl) return;
  for (const button of dom.brainModeControl.querySelectorAll("[data-brain-mode]")) {
    const mode = button.dataset.brainMode || "modal";
    const active = mode === selectedBrainMode;
    const available = brainModeAvailable(mode);
    button.classList.toggle("active", active);
    button.classList.toggle("warn", !available);
    button.setAttribute("aria-pressed", String(active));
    button.title = brainModeTitle(mode);
  }
  document.body.dataset.selectedBrainMode = selectedBrainMode;
}

function chooseInitialBrainMode() {
  if (modelStatus.vlaRouter?.enabled) {
    selectedBrainMode = "modal";
    brainModePinned = false;
    try {
      localStorage.setItem(BRAIN_MODE_STORAGE_KEY, "modal");
    } catch {}
    return;
  }
  if (brainModePinned) return;
  if (brainModeAvailable(selectedBrainMode)) return;
  if (brainModeAvailable("ollama-vision")) {
    selectedBrainMode = "ollama-vision";
  } else if (brainModeAvailable("ollama-text")) {
    selectedBrainMode = "ollama-text";
  }
}

for (const spec of AGENT_SPECS) {
  const pet = createPet(spec.kind, scene);
  pet.group.rotation.y = spec.yaw;
  pet.facingYaw = spec.yaw;
  pet.targetFacingYaw = spec.yaw;
  pet.group.position.set(spec.home.x, spec.home.y, spec.home.z);
  pet.group.traverse((node) => {
    if (node.isMesh) node.userData.agentKind = spec.kind;
  });
  const rig = createPetBalanceRig({ world, recordForce, home: spec.home });
  rig.setPet(pet, spec.kind);
  rig.moveTo(spec.home, { settleOnFloor: true });
  const agent = {
    ...spec,
    pet,
    rig,
    needs: { hunger: 42, curiosity: 48, energy: 74, social: 44, playfulness: 58 },
    memories: [],
    lastIntent: "waking",
    lastSpell: "",
    lastPartner: "",
    lastTrace: null,
    traceHistory: [],
    locomotion: null,
    heldObject: null,
    proceduralHitMeshes: [...pet.hitMeshes],
    rigVisual: null,
    rigHelper: null,
    rigBones: {},
    rigBoneBases: {},
    rigRetarget: null,
    rigMixer: null,
    rigActions: {},
    rigActiveClip: "",
    rigStatus: "loading",
    controlToken: 0,
    energyState: "ok",
    inFlight: false,
  };
  agents.set(spec.kind, agent);
  if (IS_V3_MODE) setProceduralPetOpacity(agent, 0.16);
  loadGeneratedRig(agent);
}

room.resetRoom();
resetRecyclingChallenge();
updateGeneratedMarker();
syncAgentDock();
setActiveAgent(activeKind);
updateModeButton();
updateRigButton();
renderRoomToolMode();
refreshModelStatus();
refreshTrainingStatus();
refreshJudgeStatus();
refreshAiEvidence();
loadMemories(activeKind);
window.setInterval(refreshJudgeStatus, 30000);
window.setInterval(refreshAiEvidence, 45000);

function speechOnlyUi() {
  return {
    showSpeech,
    flash(durationMs) {
      dom.effectFlash.classList.add("on");
      setTimeout(() => dom.effectFlash.classList.remove("on"), Math.min(durationMs, 1500));
    },
  };
}

function showSpeech(text) {
  dom.speech.textContent = text || "Tiny thought.";
  dom.speech.classList.add("visible");
  clearTimeout(showSpeech.timer);
  showSpeech.timer = setTimeout(() => dom.speech.classList.remove("visible"), 4700);
}

function showToast(text) {
  dom.toast.textContent = text;
  dom.toast.classList.add("visible");
  setTimeout(() => dom.toast.classList.remove("visible"), 2300);
}

function setRoomToolMode(mode) {
  roomToolMode = ["food", "pet"].includes(mode) ? mode : "hand";
  renderRoomToolMode();
  const messages = {
    food: "Food mode: click the floor to drop grapes.",
    pet: "Pet mode: touch or drag Fire Boy like a ragdoll.",
    hand: "Hand mode: drag toys and pet Fire Boy.",
  };
  showToast(messages[roomToolMode] || messages.hand);
}

function renderRoomToolMode() {
  if (!IS_V3_MODE) return;
  dom.handToolButton?.classList.toggle("active", roomToolMode === "hand");
  dom.foodToolButton?.classList.toggle("active", roomToolMode === "food");
  dom.petToolButton?.classList.toggle("active", roomToolMode === "pet");
  if (dom.canvas) dom.canvas.dataset.toolMode = roomToolMode;
  document.body.dataset.roomToolMode = roomToolMode;
}

function syncAgentDock() {
  if (!dom.agentDock) return;
  dom.agentDock.innerHTML = "";
  for (const spec of AGENT_SPECS) {
    const look = PET_LOOKS[spec.kind] || PET_LOOKS.squeaky;
    const button = document.createElement("button");
    button.className = "agent-button";
    button.type = "button";
    button.dataset.agent = spec.kind;
    button.innerHTML = `<span class="agent-swatch" style="background:${petHex(spec.kind, "body")}"></span><span>${look.label || spec.label}</span>`;
    dom.agentDock.appendChild(button);
  }
  dom.agentDock.classList.toggle("single", IS_V3_MODE);
}

function setActiveAgent(kind) {
  if (!agents.has(kind)) return;
  activeKind = kind;
  const agent = activeAgent();
  senses.setPet(agent.pet);
  dom.perceptionTitle.textContent = `${agent.label} sees`;
  document.querySelectorAll(".agent-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.agent === kind);
  });
  renderAbilityDock(agent);
  renderForceDock(agent);
  updateAgentPanel();
  updateModeButton();
  loadMemories(kind);
}

function renderAbilityDock(agent = activeAgent()) {
  if (!dom.abilityDock) return;
  dom.abilityDock.innerHTML = "";
  const abilities = ABILITY_SETS[agent.kind] || [];
  for (const ability of abilities) {
    const button = document.createElement("button");
    button.className = "ability-button glass";
    button.type = "button";
    button.dataset.power = ability.power;
    button.title = `${agent.label}: ${ability.label}`;
    button.innerHTML = `<i data-lucide="${ability.icon}"></i><span>${ability.label}</span>`;
    button.addEventListener("click", () => triggerAbility(agent.kind, ability));
    dom.abilityDock.appendChild(button);
  }
  createIcons({ icons: LUCIDE_ICONS });
}

function maybeRunUrlCommand() {
  if (!IS_V3_MODE) return;
  let command = "";
  try {
    command = new URLSearchParams(window.location.search).get("autocmd") || "";
  } catch {
    command = "";
  }
  command = command.replace(/\s+/g, " ").trim();
  if (!command) return;
  document.body.dataset.urlAutoCommand = command;
  setTimeout(() => {
    const agent = activeAgent();
    if (!agent?.inFlight) requestAction(agent, command);
  }, 900);
}

function maybeApplyUrlPetState() {
  if (!IS_V3_MODE) return;
  let params;
  try {
    params = new URLSearchParams(window.location.search);
  } catch {
    return;
  }
  const agent = activeAgent();
  let changed = false;
  for (const [queryKey, needKey] of [["hunger", "hunger"], ["energy", "energy"], ["playfulness", "playfulness"]]) {
    if (!params.has(queryKey)) continue;
    const value = Number(params.get(queryKey));
    if (!Number.isFinite(value)) continue;
    agent.needs[needKey] = clampNeed(value);
    changed = true;
  }
  if (changed) {
    agent.energyState = Number(agent.needs.energy || 0) > 32 ? "ok" : agent.energyState;
    renderPetMeters(agent);
    document.body.dataset.urlPetStateApplied = "true";
  }
}

function triggerAbility(kind, ability) {
  const agent = agents.get(kind);
  if (!agent || !ability) return;
  audio.unlock();
  setActiveAgent(kind);
  document.querySelectorAll(".ability-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.power === ability.power);
  });
  document.body.dataset.lastAbility = `${kind}:${ability.power}`;
  showToast(`${agent.label}: ${ability.label}`);
  requestAction(agent, ability.prompt);
}

function renderForceDock(agent = activeAgent()) {
  if (!dom.forceDock) return;
  dom.forceDock.innerHTML = "";
  for (const control of FORCE_CONTROLS) {
    const button = document.createElement("button");
    button.className = "force-button glass";
    button.type = "button";
    button.dataset.force = control.action;
    button.title = `${agent.label}: ${control.label}`;
    button.innerHTML = `<i data-lucide="${control.icon}"></i>`;
    button.addEventListener("click", () => triggerForceControl(agent.kind, control));
    dom.forceDock.appendChild(button);
  }
  createIcons({ icons: LUCIDE_ICONS });
}

function triggerForceControl(kind, control) {
  const agent = agents.get(kind);
  if (!agent || !control) return;
  audio.unlock();
  setActiveAgent(kind);
  applyAgentForceControl(agent, control);
  scheduleForceRescue(agent, control);
  document.querySelectorAll(".force-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.force === control.action);
  });
  document.body.dataset.lastForceControl = `${kind}:${control.action}`;
  showToast(`${agent.label}: ${control.label}`);
  setTimeout(() => requestAction(agent, control.message), 180);
}

function applyAgentForceControl(agent, control) {
  const position = agent.pet.group.position;
  const vec = control.vector || [0, 0, 0];
  const event = { kind: `agent-${control.action}`, objectId: `${agent.kind}-body`, impact: 0.65 };
  if (control.action === "lift") {
    agent.rig.dropFrom(new CANNON.Vec3(position.x, Math.max(2.45, position.y + 2.2), position.z));
    setPetEmotion(agent.pet, "surprised");
  } else if (control.action === "drop") {
    agent.rig.dropFrom(new CANNON.Vec3(position.x, Math.max(3.4, position.y + 3.1), position.z));
    setPetEmotion(agent.pet, "startled");
    event.impact = 0.82;
  } else if (control.action === "toss") {
    agent.rig.nudge(new CANNON.Vec3(vec[0], vec[1], vec[2]), 0.78);
    setPetEmotion(agent.pet, "dizzy");
    event.impact = 0.76;
  } else if (control.action === "spin") {
    agent.rig.twist?.(new CANNON.Vec3(vec[0], vec[1], vec[2]), 0.58);
    agent.rig.nudge(new CANNON.Vec3(0, 0.9, 0), 0.45);
    setPetEmotion(agent.pet, "dizzy");
    event.impact = 0.7;
  } else if (control.action === "settle") {
    const home = AGENT_SPECS.find((item) => item.kind === agent.kind)?.home || new CANNON.Vec3(position.x, 0.06, position.z);
    agent.rig.moveTo(home, { settleOnFloor: true });
    setPetEmotion(agent.pet, "happy");
    event.impact = 0.18;
  }
  playRigMotion(agent, rigClipForForce(control.action));
  agent.pet.animation = control.action === "settle" ? "bounce" : "startle";
  agent.pet.actionUntil = performance.now() + 1300;
  agent.lastIntent = `force ${control.action}`;
  recordForce(event);
  updateAgentPanel();
}

function loadGeneratedRig(agent) {
  const url = RIG_ASSETS[agent.kind];
  if (!url) {
    agent.rigStatus = "none";
    return;
  }
  gltfLoader.load(
    url,
    (gltf) => {
      const wrapper = new THREE.Group();
      wrapper.name = `${agent.kind}-generated-rig-wrapper`;
      const root = gltf.scene;
      root.name = `${agent.kind}-generated-rig`;
      normalizeRigModel(root, wrapper);
      const rigHitMeshes = tintRigMaterials(root, agent.kind);
      if (IS_V3_MODE && agent.kind === "fire_boy") {
        wrapper.position.set(0, -0.01, 0.02);
        wrapper.rotation.y = -0.08;
        agent.pet.hitMeshes = rigHitMeshes.length ? rigHitMeshes : agent.proceduralHitMeshes;
        setProceduralPetOpacity(agent, 0.012);
      } else {
        wrapper.position.set(0.78, 0.03, -0.7);
        wrapper.rotation.y = -0.36;
        agent.pet.hitMeshes = [...agent.proceduralHitMeshes, ...rigHitMeshes];
      }
      wrapper.visible = rigMeshesVisible;
      agent.pet.group.add(wrapper);
      setupRigAnimations(agent, root, gltf.animations || []);

      let helper = null;
      try {
        helper = new THREE.SkeletonHelper(root);
        helper.name = `${agent.kind}-skeleton-helper`;
        helper.visible = rigMeshesVisible;
        helper.material.transparent = true;
        helper.material.opacity = 0.48;
        helper.material.depthTest = false;
        helper.material.color.setHex(PET_LOOKS[agent.kind]?.power || 0x66cbd8);
        scene.add(helper);
      } catch {
        helper = null;
      }

      agent.rigVisual = wrapper;
      agent.rigHelper = helper;
      agent.rigStatus = "ready";
      playRigMotion(agent, "Idle", { immediate: true });
      updateRigButton();
      updateAgentPanel();
    },
    undefined,
    () => {
      agent.rigStatus = "missing";
      updateAgentPanel();
    },
  );
}

function normalizeRigModel(root, wrapper) {
  const box = new THREE.Box3().setFromObject(root);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const height = Math.max(0.01, size.y);
  const scale = (IS_V3_MODE ? 1.24 : 1.32) / height;
  root.scale.setScalar(scale);
  root.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
  wrapper.add(root);
}

function tintRigMaterials(root, kind) {
  const look = PET_LOOKS[kind] || PET_LOOKS.squeaky;
  const rigHitMeshes = [];
  root.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = true;
    node.receiveShadow = true;
    node.frustumCulled = false;
    node.userData.generatedRigMesh = true;
    node.userData.agentKind = kind;
    rigHitMeshes.push(node);
    const materials = Array.isArray(node.material) ? node.material : [node.material];
    const cloned = materials.map((material) => {
      const next = material?.clone ? material.clone() : new THREE.MeshStandardMaterial({ color: look.body });
      const isPrimaryV3Rig = IS_V3_MODE && kind === "fire_boy";
      next.transparent = !isPrimaryV3Rig;
      next.opacity = isPrimaryV3Rig ? 1 : 0.38;
      next.depthWrite = isPrimaryV3Rig;
      if ("roughness" in next) next.roughness = Math.min(Number(next.roughness ?? 0.7), isPrimaryV3Rig ? 0.58 : 0.74);
      if ("emissive" in next) {
        next.emissive = new THREE.Color(look.power || 0x66cbd8);
        next.emissiveIntensity = isPrimaryV3Rig ? 0.16 : 0.08;
      }
      return next;
    });
    node.material = Array.isArray(node.material) ? cloned : cloned[0];
  });
  return rigHitMeshes;
}

function setProceduralPetOpacity(agent, opacity) {
  const meshes = agent?.proceduralHitMeshes || [];
  for (const mesh of meshes) {
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const cloned = materials.map((material) => {
      const next = material?.clone ? material.clone() : material;
      if (!next) return next;
      next.transparent = opacity < 1;
      next.opacity = opacity;
      next.depthWrite = opacity > 0.2;
      return next;
    });
    mesh.material = Array.isArray(mesh.material) ? cloned : cloned[0];
  }
}

function setupRigAnimations(agent, root, clips) {
  setupRigRetargetBones(agent, root);
  agent.rigMixer = null;
  agent.rigActions = {};
  agent.rigActiveClip = "";
  if (!Array.isArray(clips) || !clips.length) return;
  agent.rigMixer = new THREE.AnimationMixer(root);
  for (const clip of clips) {
    agent.rigActions[clip.name] = agent.rigMixer.clipAction(clip);
  }
}

function playRigMotion(agent, requestedName, { immediate = false } = {}) {
  if (agent?.rigRetarget?.active && !immediate) return;
  if (!agent?.rigMixer || !agent.rigActions) return;
  const clipName = resolveRigClip(agent, requestedName);
  const next = agent.rigActions[clipName];
  if (!next || (!immediate && clipName === agent.rigActiveClip)) return;
  next.reset().setEffectiveWeight(1).play();
  if (agent.rigActiveClip && agent.rigActions[agent.rigActiveClip]) {
    agent.rigActions[agent.rigActiveClip].crossFadeTo(next, immediate ? 0.01 : 0.22, true);
  }
  agent.rigActiveClip = clipName;
  document.body.dataset.activeRigClip = clipName;
}

function resolveRigClip(agent, requestedName) {
  const actions = agent?.rigActions || {};
  if (actions[requestedName]) return requestedName;
  const lowered = String(requestedName || "").toLowerCase();
  const fallbackOrder = [
    ["sit", "Sit"],
    ["jump", "Jump"],
    ["ember", "Jump"],
    ["walk", "Walk"],
    ["run", "Run"],
    ["pickup", "Cheer"],
    ["carry", "Walk"],
    ["bring", "Walk"],
    ["throw", "Throw"],
    ["fireball", "Throw"],
    ["smoke", "Cheer"],
    ["wave", "Wave"],
    ["talk", "Wave"],
    ["dance", "Dance"],
    ["spin", "Spin"],
    ["nuzzle", "Cheer"],
    ["petted", "Cheer"],
    ["startle", "Jump"],
    ["inspect", "Wave"],
    ["read", "Sit"],
    ["eat", "Cheer"],
    ["play", "Dance"],
  ];
  for (const [needle, clip] of fallbackOrder) {
    if (lowered.includes(needle) && actions[clip]) return clip;
  }
  return actions.Idle ? "Idle" : Object.keys(actions)[0];
}

function setupRigRetargetBones(agent, root) {
  const aliases = {
    hips: ["hips"],
    spine: ["spine"],
    chest: ["chest"],
    neck: ["neck"],
    head: ["head"],
    crown: ["crown"],
    shoulderL: ["shoulderl"],
    shoulderR: ["shoulderr"],
    upperArmL: ["upperarml"],
    upperArmR: ["upperarmr"],
    lowerArmL: ["lowerarml"],
    lowerArmR: ["lowerarmr"],
    handL: ["handl"],
    handR: ["handr"],
    upperLegL: ["upperlegl"],
    upperLegR: ["upperlegr"],
    lowerLegL: ["lowerlegl"],
    lowerLegR: ["lowerlegr"],
    footL: ["footl"],
    footR: ["footr"],
  };
  const found = {};
  root.traverse((node) => {
    if (!node.isBone) return;
    const name = canonicalBoneName(node.name);
    for (const [key, names] of Object.entries(aliases)) {
      if (!found[key] && names.includes(name)) found[key] = node;
    }
  });
  agent.rigBones = found;
  agent.rigBoneBases = {};
  for (const [key, bone] of Object.entries(found)) {
    agent.rigBoneBases[key] = bone.quaternion.clone();
  }
  document.body.dataset.rigRetargetBones = String(Object.keys(found).length);
}

function canonicalBoneName(name) {
  return String(name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function startRigRetarget(agent, action = {}, skill = "") {
  const trajectory = action.debug?.mujocoPolicy?.retargetTrajectory;
  const frames = Array.isArray(trajectory?.frames) ? trajectory.frames : [];
  const jointNames = Array.isArray(trajectory?.joint_names) ? trajectory.joint_names : [];
  if (!agent?.rigBones || !frames.length || !jointNames.length) {
    document.body.dataset.rigRetargetActive = "false";
    document.body.dataset.rigRetargetReason = "missing-trajectory";
    return false;
  }
  const jointIndex = {};
  jointNames.forEach((name, index) => {
    jointIndex[name] = index;
  });
  const durationMs = Number(
    trajectory.duration_ms
      || action.interaction?.durationMs
      || (frames.length * 1000 / Number(trajectory.fps || 24)),
  );
  agent.rigRetarget = {
    active: true,
    startedAt: performance.now(),
    durationMs: THREE.MathUtils.clamp(durationMs, 900, 7200),
    frames,
    jointIndex,
    skill,
    task: trajectory.task || skill,
    source: trajectory.source || "mujoco",
  };
  for (const rigAction of Object.values(agent.rigActions || {})) rigAction.paused = true;
  document.body.dataset.rigRetargetActive = "true";
  document.body.dataset.rigRetargetSkill = skill;
  document.body.dataset.rigRetargetTask = agent.rigRetarget.task;
  document.body.dataset.rigRetargetFrames = String(frames.length);
  document.body.dataset.rigRetargetSource = agent.rigRetarget.source;
  return true;
}

function updateRigRetarget(agent, now) {
  const clip = agent?.rigRetarget;
  if (!clip?.active) return false;
  const frames = clip.frames || [];
  if (!frames.length) {
    finishRigRetarget(agent);
    return false;
  }
  const progress = THREE.MathUtils.clamp((now - clip.startedAt) / Math.max(1, clip.durationMs), 0, 1);
  const framePosition = progress * Math.max(0, frames.length - 1);
  const index = Math.min(frames.length - 1, Math.floor(framePosition));
  const nextIndex = Math.min(frames.length - 1, index + 1);
  const alpha = framePosition - index;
  const values = interpolateRetargetValues(frames[index]?.values, frames[nextIndex]?.values, alpha);
  applyRetargetPose(agent, values, clip.jointIndex, alpha);
  document.body.dataset.rigRetargetFrame = String(index);
  document.body.dataset.rigRetargetStage = frames[index]?.stage || "";
  if (progress >= 1) finishRigRetarget(agent);
  return true;
}

function interpolateRetargetValues(a = [], b = [], alpha = 0) {
  const count = Math.max(a.length || 0, b.length || 0);
  const values = new Array(count);
  for (let i = 0; i < count; i += 1) {
    const av = Number(a[i] ?? b[i] ?? 0);
    const bv = Number(b[i] ?? a[i] ?? av);
    values[i] = THREE.MathUtils.lerp(av, bv, alpha);
  }
  return values;
}

function finishRigRetarget(agent) {
  if (!agent) return;
  resetRigRetargetPose(agent);
  agent.rigRetarget = null;
  for (const rigAction of Object.values(agent.rigActions || {})) rigAction.paused = false;
  document.body.dataset.rigRetargetActive = "false";
  document.body.dataset.rigRetargetFrame = "";
  document.body.dataset.rigRetargetStage = "done";
  playRigMotion(agent, "Idle", { immediate: true });
}

function resetRigRetargetPose(agent) {
  const bases = agent?.rigBoneBases || {};
  for (const [key, bone] of Object.entries(agent?.rigBones || {})) {
    if (bases[key]) bone.quaternion.copy(bases[key]);
  }
}

function applyRetargetPose(agent, values, jointIndex) {
  const get = (name, fallback = 0) => {
    const index = jointIndex?.[name];
    return Number.isFinite(index) ? Number(values[index] ?? fallback) : fallback;
  };
  const skill = agent.rigRetarget?.skill || "";
  const t = THREE.MathUtils.clamp((performance.now() - agent.rigRetarget.startedAt) / Math.max(1, agent.rigRetarget.durationMs), 0, 1);
  const runPhase = t * Math.PI * 8;
  const berryPoseBoost = skill.includes("eat") || skill.includes("pick") ? 1 : 0;

  setRetargetEuler(agent, "hips", 0.06 * Math.sin(runPhase) * (skill.includes("run") ? 1 : 0.35), get("root_yaw") * 0.12, 0);
  setRetargetEuler(agent, "spine", -get("spine_pitch") * 0.55, 0, get("chest_yaw") * 0.22);
  setRetargetEuler(agent, "chest", 0, get("chest_yaw") * 0.45, 0);
  setRetargetEuler(agent, "neck", 0, get("neck_yaw") * 0.35, 0);
  setRetargetEuler(agent, "head", -get("head_pitch") * 0.7, get("neck_yaw") * 0.18, 0);

  setRetargetEuler(agent, "shoulderR", -get("shoulder_R_pitch") * 0.28, get("shoulder_R_yaw") * 0.18, -get("shoulder_R_roll") * 0.18);
  setRetargetEuler(agent, "upperArmR", -0.18 - get("shoulder_R_pitch") * 0.78 - berryPoseBoost * 0.25, get("shoulder_R_yaw") * 0.36, -0.20 - get("shoulder_R_roll") * 0.48);
  setRetargetEuler(agent, "lowerArmR", -get("elbow_R") * 0.72 - berryPoseBoost * 0.42, 0, get("wrist_R_roll") * 0.22);
  setRetargetEuler(agent, "handR", -get("wrist_R_pitch") * 0.62, 0, get("wrist_R_roll") * 0.5);

  setRetargetEuler(agent, "shoulderL", -get("shoulder_L_pitch") * 0.22, get("shoulder_L_yaw") * 0.16, get("shoulder_L_roll") * 0.16);
  setRetargetEuler(agent, "upperArmL", -0.14 - get("shoulder_L_pitch") * 0.72, get("shoulder_L_yaw") * 0.34, 0.18 + get("shoulder_L_roll") * 0.46);
  setRetargetEuler(agent, "lowerArmL", -get("elbow_L") * 0.68, 0, -get("wrist_L_roll") * 0.2);
  setRetargetEuler(agent, "handL", -get("wrist_L_pitch") * 0.58, 0, -get("wrist_L_roll") * 0.48);

  const runBoost = skill.includes("run") ? 1.25 : skill.includes("walk") ? 0.85 : 0.35;
  setRetargetEuler(agent, "upperLegR", -get("hip_R_pitch") * 0.92 * runBoost, get("hip_R_yaw") * 0.3, 0);
  setRetargetEuler(agent, "lowerLegR", get("knee_R") * 0.76 * runBoost, 0, 0);
  setRetargetEuler(agent, "footR", -get("ankle_R") * 0.75 * runBoost, 0, 0);
  setRetargetEuler(agent, "upperLegL", -get("hip_L_pitch") * 0.92 * runBoost, get("hip_L_yaw") * 0.3, 0);
  setRetargetEuler(agent, "lowerLegL", get("knee_L") * 0.76 * runBoost, 0, 0);
  setRetargetEuler(agent, "footL", -get("ankle_L") * 0.75 * runBoost, 0, 0);
}

function setRetargetEuler(agent, key, x = 0, y = 0, z = 0) {
  const bone = agent?.rigBones?.[key];
  const base = agent?.rigBoneBases?.[key];
  if (!bone || !base) return;
  const delta = new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z, "XYZ"));
  bone.quaternion.copy(base).multiply(delta);
}

function rigClipForAction(action = {}) {
  return [
    action.animation,
    action.power?.name,
    action.interaction?.verb,
    action.intent,
    action.emotion,
  ].filter(Boolean).join(" ");
}

function rigClipForForce(action) {
  if (action === "settle") return "Idle";
  if (action === "spin" || action === "toss") return "Spin";
  if (action === "lift" || action === "drop") return "Jump";
  return "Cheer";
}

function setRigMeshesVisible(visible) {
  rigMeshesVisible = IS_V3_MODE ? true : Boolean(visible);
  for (const agent of agents.values()) {
    if (agent.rigVisual) agent.rigVisual.visible = rigMeshesVisible;
    if (agent.rigHelper) agent.rigHelper.visible = rigMeshesVisible;
  }
  updateRigButton();
  updateAgentPanel();
}

function activeAgent() {
  return agents.get(activeKind) || agents.get(DEFAULT_AGENT_KIND) || [...agents.values()][0];
}

function pointerToNdc(event) {
  const rect = dom.canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function floorPointFromPointer() {
  if (!raycaster.ray.intersectPlane(floorPlane, dragHit)) return null;
  return clampAgentPosition(dragHit.clone()).setY(0.31);
}

function dropFoodAtPointer(event) {
  const point = floorPointFromPointer();
  if (!point) return false;
  event.preventDefault();
  const entry = room.spawnFood(point, { name: "Dropped grapes", energy: 15, nutrition: 15 });
  updateGeneratedMarker();
  effects.hearts(bodyToVector(entry.body.position).add(new THREE.Vector3(0, 0.34, 0)), 0x8c7ac0, 7);
  audio.play("soft_pop", 0.76);
  recordInteraction({ kind: "drop_food", pet: activeKind, objectId: entry.id, objectName: entry.name || entry.id });
  document.body.dataset.lastDroppedFood = entry.id;
  showToast("Dropped grapes for Fire Boy.");
  return true;
}

function onPointerDown(event) {
  audio.unlock();
  if (dragged) return;
  pointerToNdc(event);
  raycaster.setFromCamera(pointer, camera);

  if (IS_V3_MODE && roomToolMode === "food") {
    dropFoodAtPointer(event);
    return;
  }

  const agentHit = findAgentHit();
  if (IS_V3_MODE && roomToolMode === "pet") {
    const targetAgent = agentHit?.agent || activeAgent();
    const hitPoint = agentHit?.point || targetAgent.pet.group.position.clone().add(new THREE.Vector3(0, 1.05, 0.08));
    beginAgentDrag(event, targetAgent, hitPoint, { playMode: true, touchType: "pet" });
    return;
  }

  if (agentHit) {
    beginAgentDrag(event, agentHit.agent, agentHit.point);
    return;
  }

  const hits = raycaster.intersectObjects(objects.map((entry) => entry.mesh), true);
  if (!hits.length) return;
  const entry = objectEntryFromHit(hits[0].object);
  if (!entry) return;
  beginObjectDrag(event, entry, hits[0].point);
}

function beginObjectDrag(event, entry, hitPoint) {
  event.preventDefault();
  dragPointerId = event.pointerId;
  try {
    dom.canvas.setPointerCapture(dragPointerId);
  } catch {}
  const bodyPosition = bodyToVector(entry.body.position);
  dragPlane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()).normalize(), hitPoint);
  dragOffset.copy(bodyPosition).sub(hitPoint);
  dragged = {
    kind: "object",
    entry,
    originalMass: entry.body.mass,
    plane: dragPlane.clone(),
    offset: dragOffset.clone(),
  };
  dragHistory.length = 0;
  dragHistory.push({ t: performance.now(), x: bodyPosition.x, y: bodyPosition.y, z: bodyPosition.z });
  entry.body.type = CANNON.Body.KINEMATIC;
  entry.body.mass = 0;
  entry.body.updateMassProperties();
  entry.body.velocity.set(0, 0, 0);
  entry.body.angularVelocity.set(0, 0, 0);
  controls.enabled = false;
  dom.canvas.classList.add("dragging");
  startleNearbyAgents(bodyPosition, 0.25);
}

function beginAgentDrag(event, agent, hitPoint, options = {}) {
  event.preventDefault();
  setActiveAgent(agent.kind);
  stopAgentLocomotion(agent);
  dragPointerId = event.pointerId;
  try {
    dom.canvas.setPointerCapture(dragPointerId);
  } catch {}
  dragPlane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()).normalize(), hitPoint);
  dragOffset.copy(agent.pet.group.position).sub(hitPoint);
  dragged = {
    kind: "agent",
    agent,
    plane: dragPlane.clone(),
    offset: dragOffset.clone(),
    startClient: { x: event.clientX, y: event.clientY },
    startPoint: hitPoint.clone(),
    touchType: options.touchType || (event.altKey ? "poke" : "pet"),
    playMode: Boolean(options.playMode || roomToolMode === "pet"),
    lastPetTrailAt: 0,
    moved: false,
  };
  dragHistory.length = 0;
  dragHistory.push({ t: performance.now(), x: agent.pet.group.position.x, y: agent.pet.group.position.y, z: agent.pet.group.position.z });
  controls.enabled = false;
  dom.canvas.classList.add("dragging");
  setPetEmotion(agent.pet, "curious");
}

function onPointerMove(event) {
  if (dragged && event.pointerId !== dragPointerId) return;
  pointerToNdc(event);
  raycaster.setFromCamera(pointer, camera);
  if (!dragged) {
    const hit = findAgentHit();
    const nextHover = hit?.agent || null;
    if (nextHover !== hoverAgent) {
      if (hoverAgent) petPointerReaction(hoverAgent.pet, "leave");
      hoverAgent = nextHover;
      if (hoverAgent) {
        petPointerReaction(hoverAgent.pet, "hover");
        effects.stars(hoverAgent.pet.group.position.clone().add(new THREE.Vector3(0, 1.55, 0.2)), PET_LOOKS[hoverAgent.kind].power, 8);
      }
      dom.canvas.classList.toggle("pet-hover", Boolean(hoverAgent));
    }
    return;
  }
  if (dragged.kind === "agent") updateAgentDrag(event);
  else updateObjectDrag();
}

function updateObjectDrag() {
  if (!raycaster.ray.intersectPlane(dragged.plane, dragHit)) return;
  const entry = dragged.entry;
  const next = clampObjectPosition(dragHit.clone().add(dragged.offset), entry);
  entry.body.position.set(next.x, next.y, next.z);
  entry.body.velocity.set(0, 0, 0);
  entry.body.angularVelocity.set(0, 0, 0);
  dragHistory.push({ t: performance.now(), x: next.x, y: next.y, z: next.z });
  while (dragHistory.length > 6) dragHistory.shift();
}

function updateAgentDrag(event) {
  const movedPixels = Math.hypot(event.clientX - dragged.startClient.x, event.clientY - dragged.startClient.y);
  if (movedPixels > 6) dragged.moved = true;
  if (!dragged.moved) return;
  if (!raycaster.ray.intersectPlane(dragged.plane, dragHit)) return;
  const next = clampAgentPosition(dragHit.clone().add(dragged.offset));
  dragged.agent.rig.moveTo(new CANNON.Vec3(next.x, next.y, next.z));
  if (dragged.playMode) {
    const now = performance.now();
    if (now - dragged.lastPetTrailAt > 240) {
      dragged.lastPetTrailAt = now;
      petPointerReaction(dragged.agent.pet, "pet");
      dragged.agent.rig.twist(new CANNON.Vec3(0.02, 0.09, -0.03), 0.28);
      effects.hearts(dragged.agent.pet.group.position.clone().add(new THREE.Vector3(0, 1.18, 0.2)), PET_LOOKS[dragged.agent.kind].cheeks, 4);
    }
  }
  dragHistory.push({ t: performance.now(), x: next.x, y: next.y, z: next.z });
  while (dragHistory.length > 6) dragHistory.shift();
}

function onPointerUp(event) {
  if (dragged && event?.pointerId !== dragPointerId) return;
  releaseDrag(event, { throwObject: true });
}

function onPointerCancel(event) {
  if (dragged && event?.pointerId !== dragPointerId) return;
  releaseDrag(event, { throwObject: false });
}

function releaseDrag(event, { throwObject = true, skipPointerRelease = false } = {}) {
  if (!dragged) return;
  if (dragged.kind === "agent") {
    releaseAgentDrag(event, { skipPointerRelease });
    return;
  }
  const { entry, originalMass } = dragged;
  entry.body.type = CANNON.Body.DYNAMIC;
  entry.body.mass = originalMass;
  entry.body.updateMassProperties();
  entry.body.wakeUp();
  if (throwObject && dragHistory.length >= 2) {
    const first = dragHistory[0];
    const last = dragHistory[dragHistory.length - 1];
    const dt = Math.max(40, last.t - first.t);
    entry.body.velocity.set(
      ((last.x - first.x) / dt) * 560,
      THREE.MathUtils.clamp(((last.y - first.y) / dt) * 450 + 0.7, -1.7, 5.7),
      ((last.z - first.z) / dt) * 560,
    );
    recordForce({ kind: "throw", objectId: entry.id, impact: 0.78 });
    audio.play("startle", 0.8);
    startleNearbyAgents(bodyToVector(entry.body.position), 0.65);
  } else {
    entry.body.velocity.set(0, 0.2, 0);
  }
  finishPointerRelease(skipPointerRelease);
}

function releaseAgentDrag(event, { skipPointerRelease = false } = {}) {
  const agent = dragged.agent;
  const wasMoved = Boolean(dragged.moved);
  const placed = dragHistory[dragHistory.length - 1] || { x: agent.pet.group.position.x, y: agent.pet.group.position.y, z: agent.pet.group.position.z };
  if (wasMoved) {
    if (placed.y > 0.72) {
      agent.rig.dropFrom(new CANNON.Vec3(placed.x, placed.y, placed.z));
      recordForce({ kind: "agent-drop", objectId: `${agent.kind}-body`, impact: 0.72 });
      showSpeech(`${agent.label}: tiny landing protocol.`);
      audio.play("startle", 0.75);
      playRigMotion(agent, "Jump");
    } else {
      agent.rig.moveTo(new CANNON.Vec3(placed.x, 0.06, placed.z), { settleOnFloor: true });
      showSpeech(`${agent.label}: standing here now.`);
      audio.play("soft_pop", 0.72);
      playRigMotion(agent, "Walk");
    }
    const pointer = pointerSnapshot(event, new THREE.Vector3(placed.x, placed.y, placed.z));
    if (dragged.playMode) {
      petPointerReaction(agent.pet, "pet");
      effects.hearts(agent.pet.group.position.clone().add(new THREE.Vector3(0, 1.34, 0.25)), PET_LOOKS[agent.kind].cheeks, 10);
      audio.play("pet_touch", 0.86);
      audio.play("purr", 0.42);
      showSpeech(`${agent.label}: whee, gentle play.`);
      showToast("Pet/ragdoll play recorded.");
      document.body.dataset.lastPetPlay = "ragdoll-drag";
      recordInteraction({ kind: "pet_ragdoll_play", pet: agent.kind, pointer });
    } else {
      recordInteraction({ kind: "pet_move", pet: agent.kind, pointer });
    }
  } else {
    handleAgentTouch(agent, dragged.touchType, event, dragged.startPoint);
  }
  finishPointerRelease(skipPointerRelease);
}

function finishPointerRelease(skipPointerRelease) {
  if (!skipPointerRelease && dragPointerId !== null) {
    try {
      dom.canvas.releasePointerCapture(dragPointerId);
    } catch {}
  }
  dragged = null;
  dragPointerId = null;
  controls.enabled = true;
  dom.canvas.classList.remove("dragging");
}

function handleAgentTouch(agent, type, event, worldPoint) {
  petPointerReaction(agent.pet, type);
  playRigMotion(agent, type === "pet" ? "Cheer" : "Jump");
  const position = agent.pet.group.position.clone().add(new THREE.Vector3(0, 1.3, 0.35));
  effects.hearts(position, PET_LOOKS[agent.kind].cheeks, type === "pet" ? 9 : 5);
  audio.play(type === "pet" ? "pet_touch" : "startle", 0.9);
  if (type === "pet") audio.play("purr", 0.5);
  const pointerEvent = pointerSnapshot(event, worldPoint);
  recordInteraction({ kind: type, pet: agent.kind, pointer: pointerEvent });
  showSpeech(type === "pet" ? `${agent.label}: that was very kind.` : `${agent.label}: small startle.`);
  requestAction(agent, type === "pet" ? "the player gently petted you" : "the player poked you by surprise");
}

function pointerSnapshot(event, worldPoint) {
  const rect = dom.canvas.getBoundingClientRect();
  return {
    modality: event?.pointerType || "mouse",
    altKey: Boolean(event?.altKey),
    screen: {
      x: Number((((event?.clientX || 0) - rect.left) / Math.max(1, rect.width)).toFixed(3)),
      y: Number((((event?.clientY || 0) - rect.top) / Math.max(1, rect.height)).toFixed(3)),
    },
    ndc: { x: Number(pointer.x.toFixed(3)), y: Number(pointer.y.toFixed(3)) },
    world: worldPoint
      ? { x: Number(worldPoint.x.toFixed(2)), y: Number(worldPoint.y.toFixed(2)), z: Number(worldPoint.z.toFixed(2)) }
      : null,
  };
}

function isStopCommand(message = "") {
  const text = ` ${String(message).toLowerCase().replace(/[^a-z0-9]+/g, " ")} `;
  return /\b(stop|pause|idle|halt|freeze|stay)\b/.test(text) || text.includes(" hold still ");
}

function isDemandingCommand(message = "") {
  const text = String(message || "").toLowerCase();
  return /\b(run|walk|go|move|pick|grab|hold|bring|fetch|jump|dance|catch|throw|toss|play)\b/.test(text);
}

function shouldEatBeforeCommand(agent, message = "") {
  if (!IS_V3_MODE || !agent || !isDemandingCommand(message)) return false;
  if (/\b(eat|berry|berries|grape|grapes|food|snack|stop|idle|rest|sit)\b/i.test(message)) return false;
  return Number(agent.needs.energy || 0) < 35;
}

function applyCommandNeedNudges(agent, message = "") {
  if (!agent?.needs) return;
  const text = String(message || "").toLowerCase();
  let energyCost = 0;
  let playDelta = 0;
  if (/\b(run|dash|sprint|jump|dance)\b/.test(text)) {
    energyCost += 8;
    playDelta += 7;
  }
  if (/\b(walk|go|move|pick|grab|hold|bring|fetch)\b/.test(text)) {
    energyCost += 3;
  }
  if (/\b(play|catch|throw|toss|ball)\b/.test(text)) {
    energyCost += 4;
    playDelta += 10;
  }
  if (/\b(good|cute|nice|love|fun|yay|hello|hi|wave)\b/.test(text)) {
    playDelta += 6;
  }
  if (/\b(stop|idle|rest|sit|calm)\b/.test(text)) {
    energyCost = Math.max(0, energyCost - 3);
    playDelta -= 4;
  }
  if (energyCost) agent.needs.energy = clampNeed(agent.needs.energy - energyCost);
  if (playDelta) agent.needs.playfulness = clampNeed((agent.needs.playfulness ?? 50) + playDelta);
  document.body.dataset.lastNeedEnergyCost = String(energyCost);
  document.body.dataset.lastNeedPlayDelta = String(playDelta);
}

function eatBeforeCommand(agent, message = "") {
  const target = nearestEntryToAgent(agent, objects.filter((entry) => entry.consumable || entry.kind === "berry" || entry.affordances?.includes("eat")));
  if (!target) {
    showToast("Fire Boy needs energy, but no berries are available.");
    return false;
  }
  cancelAgentActions(agent);
  const actionToken = agent.controlToken;
  const action = {
    interaction: { durationMs: 2600 },
    debug: {
      clientCommand: message,
      vlaRouter: { skill: "find_and_eat_berry", policyKind: "local_energy_gate" },
      mujocoPolicy: { success: true, skill: "find_and_eat_berry" },
    },
  };
  document.body.dataset.energyGate = "eat-first";
  showToast("Fire Boy is low energy, so he eats first.");
  runVlaLiveEat(agent, target, action);
  window.setTimeout(() => {
    if (!agentActionAlive(agent, actionToken)) return;
    if (message && Number(agent.needs.energy || 0) > 10) requestAction(agent, message);
  }, 3400);
  return true;
}

async function requestAction(agent, message = "") {
  if (!agent || agent.inFlight) return;
  if (IS_V3_MODE && isStopCommand(message)) {
    performIdleStop(agent, "command_stop");
    return;
  }
  applyCommandNeedNudges(agent, message);
  if (shouldEatBeforeCommand(agent, message) && eatBeforeCommand(agent, message)) {
    updateAgentPanel();
    return;
  }
  agent.inFlight = true;
  agent.lastIntent = message ? "listening" : "watching";
  updateAgentPanel();
  const previousActive = activeAgent();
  senses.setPet(agent.pet);
  const frameMime = selectedBrainMode === "ollama-vision" ? "image/png" : "image/jpeg";
  const petFrame = senses.capturePetFrame(frameMime, 0.45);
  senses.setPet(previousActive.pet);
  const payload = {
    pet: agent.kind,
    message,
    brainMode: selectedBrainMode,
    scene: collectSceneState(agent),
    memories: agent.memories,
    forces: forceEvents.slice(-12),
    interactions: interactions.slice(-10),
    detectedObjects: detectObjects(agent),
    cameraFrame: petFrame || captureCameraFrame(renderer, frameMime, 0.45),
    cameraFrameSource: petFrame ? "agent-view" : "room-view",
    audio: senses.audioSummary(),
    cooldowns: {},
  };
  setAgentTrace(agent, compactBrainTrace(payload, null, "pending"));
  updateAgentPanel();
  const startedAt = performance.now();

  try {
    const response = await fetch("/api/pet-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const action = await response.json();
    action.debug = action.debug || {};
    action.debug.clientRoundTripMs = Number((performance.now() - startedAt).toFixed(1));
    action.debug.clientCommand = message;
    setAgentTrace(agent, compactBrainTrace(payload, action, action.debug?.policy || "model"), { remember: true });
    applyAgentAction(agent, action);
  } catch {
    showToast("The agent brain blinked; local physics stayed awake.");
    const action = fallbackClientAction(agent);
    action.debug = { ...(action.debug || {}), clientRoundTripMs: Number((performance.now() - startedAt).toFixed(1)) };
    setAgentTrace(agent, compactBrainTrace(payload, action, "client_fallback"), { remember: true });
    applyAgentAction(agent, action);
  } finally {
    agent.inFlight = false;
    updateAgentPanel();
  }
}

function setAgentTrace(agent, trace, options = {}) {
  if (!agent) return;
  agent.lastTrace = trace;
  if (!options.remember || !trace) return;
  if (!Array.isArray(agent.traceHistory)) agent.traceHistory = [];
  agent.traceHistory.push(trace);
  if (agent.traceHistory.length > 80) {
    agent.traceHistory.splice(0, agent.traceHistory.length - 80);
  }
  document.body.dataset.brainTraceHistory = String(agent.traceHistory.length);
}

function applyAgentAction(agent, action) {
  cancelAgentActions(agent);
  const emotion = action.emotion || "happy";
  const line = spokenLineForAgent(agent, action.speech || "I have a tiny plan.", action);
  const vlaLiveAction = isVlaPolicyAction(action);
  setPetEmotion(agent.pet, emotion);
  applyPetBlendshape(agent.pet, action.blendshape);
  if (vlaLiveAction) {
    agent.pet.animation = "think";
    agent.pet.actionUntil = performance.now() + 900;
    playRigMotion(agent, "Idle");
  } else {
    agent.pet.animation = action.animation || "bounce";
    agent.pet.actionUntil = performance.now() + 1900;
    playRigMotion(agent, rigClipForAction(action));
  }
  agent.lastIntent = action.intent || "playful action";
  agent.lastSpell = action.spell?.spellName || action.power?.name || "";
  showSpeech(`${agent.label}: ${line}`);
  const hasSoundRecipe = Boolean(action.soundRecipe?.tones?.length);
  audio.play(action.sound || "happy_chirp", hasSoundRecipe ? 0.44 : 0.82);
  audio.playRecipe(action.soundRecipe, 0.9);
  audio.speak(agent.kind, agent.label, line);
  const livePolicyExecuted = executeVlaLivePolicy(agent, action);
  if (vlaLiveAction && action.debug?.mujocoPolicy?.retargetTrajectory?.frames?.length) {
    hideMujocoPolicyRollout("retargeted-on-fireboy");
  } else {
    showMujocoPolicyRollout(action);
  }
  const interactionExecuted = livePolicyExecuted || executeInteraction(agent, action.interaction || {}, action);
  scheduleSocialCombo(agent, action, { livePolicyExecuted, interactionExecuted });
  applyObjectRecipe(agent, action.objectRecipe);
  const projectileLaunched = maybeLaunchFireball(agent, action);
  const executableSpell = executableSpellForAction(action, action.spell || spellFromPower(action.power, agent), { projectileLaunched });
  if (executableSpell) applySpell(agent, executableSpell);
  recordActionLoopMetrics(agent, action, { projectileLaunched });
  if (action.debug?.memoryApplied || action.intent === "memory_transfer") {
    document.body.dataset.memoryApplied = action.debug?.memoryApplied || action.intent || "memory";
  }
  if (action.debug?.visionApplied || action.intent === "vision_grounded") {
    document.body.dataset.visionApplied = action.debug?.visionApplied || action.intent || "agent-view";
    councilVisionAgents.add(agent.kind);
    document.body.dataset.councilVisionAgents = String(councilVisionAgents.size);
    document.body.dataset.councilVisionKinds = [...councilVisionAgents].join(",");
  }
  if (action.newMemory?.concept) {
    agent.memories = [...agent.memories.filter((item) => item.concept !== action.newMemory.concept), action.newMemory].slice(-8);
    document.body.dataset.lastLearnedConcept = action.newMemory.concept;
    document.body.dataset.learningScore = String(Number(document.body.dataset.learningScore || 0) + 1);
    showToast(`${agent.label} learned: ${action.newMemory.concept}`);
    loadMemories(agent.kind);
  }
  updateAgentPanel();
  refreshTrainingStatus();
  refreshAiEvidence();
}

function scheduleSocialCombo(agent, action = {}, options = {}) {
  const combo = socialComboForAction(action, agent);
  if (!agent || !combo.length) return false;
  const now = performance.now();
  const locomotionDelay = agent.locomotion?.until ? Math.max(0, agent.locomotion.until - now) : 0;
  const retargetDelay = agent.rigRetarget?.active ? Math.max(0, (agent.rigRetarget.startedAt + agent.rigRetarget.durationMs) - now) : 0;
  const interactionDelay = !options.livePolicyExecuted && action.interaction?.verb === "look_at"
    ? Math.min(850, Math.max(260, Number(action.interaction.durationMs || 900) * 0.42))
    : 0;
  const startDelay = Math.max(locomotionDelay, retargetDelay, interactionDelay, options.interactionExecuted ? 280 : 0) + 180;
  const actionToken = agent.controlToken;
  document.body.dataset.pendingSocialCombo = combo.map((item) => item.kind).join(",");
  window.setTimeout(() => {
    if (agentActionAlive(agent, actionToken)) runSocialCombo(agent, combo, actionToken);
  }, startDelay);
  return true;
}

function socialComboForAction(action = {}, agent = activeAgent()) {
  const command = String(action.debug?.clientCommand || action.debug?.originalCommand || "").toLowerCase();
  const debugCombo = String(action.debug?.postActionCombo || "").toLowerCase();
  const combo = [];
  const playful = Number(agent?.needs?.playfulness ?? 50) > 78;
  const wantsWave = debugCombo.includes("wave") || greetingCommand(command);
  const wantsDance = debugCombo.includes("dance") || danceCommand(command);
  const wantsSit = debugCombo.includes("sit") || sitCommand(command);
  const wantsThrow = debugCombo.includes("throw") || throwCommand(command);
  if (wantsSit) combo.push({ kind: "sit", clip: "Sit", durationMs: 2600 });
  if (wantsWave) combo.push({ kind: "wave", clip: "Wave", durationMs: 1700 });
  if (wantsDance) combo.push({ kind: "dance", clip: "Dance", durationMs: 2500 });
  if (wantsDance && playful) combo.push({ kind: "dance", clip: "Spin", durationMs: 1500 });
  if (wantsThrow) combo.push({ kind: "throw", clip: "Throw", durationMs: 1450 });
  return combo;
}

function greetingCommand(command) {
  if (!command) return false;
  if (/\b(walk|run|go|move|pick|grab|eat)\b/.test(command) && !/\b(wave|say hi|say hello|greet)\b/.test(command)) return false;
  return /\b(say hi|say hello|hello|hi|hey|greet|wave)\b/.test(command);
}

function danceCommand(command) {
  return /\b(dance|boogie|celebrate)\b/.test(command);
}

function sitCommand(command) {
  return (/\bsit\b/.test(command) || /\bsit down\b/.test(command) || /\btake a seat\b/.test(command)) && !/\bthrow|catch|toss\b/.test(command);
}

function throwCommand(command) {
  return /\b(throw|toss|catch)\b/.test(command) || /\bplay catch\b/.test(command);
}

function runSocialCombo(agent, combo = [], actionToken = agent?.controlToken) {
  if (!agentActionAlive(agent, actionToken) || !combo.length) return;
  const [current, ...rest] = combo;
  if (current.kind === "throw") {
    runThrowCombo(agent, current);
    if (rest.length) window.setTimeout(() => runSocialCombo(agent, rest, actionToken), Math.max(700, current.durationMs - 250));
    return;
  }
  if (current.kind === "sit") {
    runSitCombo(agent, current);
    if (rest.length) window.setTimeout(() => runSocialCombo(agent, rest, actionToken), Math.max(900, current.durationMs - 350));
    return;
  }
  stopAgentLocomotion(agent);
  if (agent.rigRetarget?.active) finishRigRetarget(agent);
  setFacingToward(agent, camera.position.clone().sub(agent.pet.group.position));
  runPetGesture(agent, current.kind, { durationMs: current.durationMs });
  playRigMotion(agent, current.clip, { immediate: true });
  const color = current.kind === "dance" ? 0xffb347 : PET_LOOKS[agent.kind].power;
  effects.stars(agent.pet.group.position.clone().add(new THREE.Vector3(0, 1.18, 0.16)), color, current.kind === "dance" ? 14 : 8);
  document.body.dataset.lastSocialCombo = current.kind;
  document.body.dataset.lastSocialComboTarget = "player-camera";
  document.body.dataset.lastLookTarget = "player-camera";
  document.body.dataset.pendingSocialCombo = rest.map((item) => item.kind).join(",");
  showToast(current.kind === "dance" ? "Fire Boy is doing the dance clip." : "Fire Boy is waving hello.");
  if (rest.length) {
    window.setTimeout(() => runSocialCombo(agent, rest, actionToken), Math.max(700, current.durationMs - 250));
  }
}

function runSitCombo(agent, current = {}) {
  stopAgentLocomotion(agent);
  if (agent.rigRetarget?.active) finishRigRetarget(agent);
  const chair = nearestEntryToAgent(agent, objects.filter((entry) => entry.kind === "chair" || entry.affordances?.includes("sit")));
  if (chair) {
    const chairPosition = bodyToVector(chair.body.position);
    const agentPosition = agent.rig.position();
    const fromChair = agentPosition.clone().sub(chairPosition);
    fromChair.y = 0;
    if (fromChair.lengthSq() < 0.01) fromChair.set(0, 0, 1);
    fromChair.normalize().multiplyScalar(0.32);
    const sitPoint = clampAgentPosition(chairPosition.clone().add(fromChair));
    agent.rig.steerTo(new CANNON.Vec3(sitPoint.x, 0.06, sitPoint.z), { settleOnFloor: true });
    document.body.dataset.lastSitTarget = chair.id;
  } else {
    document.body.dataset.lastSitTarget = "";
  }
  setFacingToward(agent, camera.position.clone().sub(agent.pet.group.position));
  runPetGesture(agent, "sit", { durationMs: current.durationMs || 2600 });
  playRigMotion(agent, "Sit", { immediate: true });
  document.body.dataset.lastSocialCombo = "sit";
  document.body.dataset.lastSocialComboTarget = document.body.dataset.lastSitTarget || "self";
  showToast(chair ? `Fire Boy is sitting by ${chair.name || chair.id}.` : "Fire Boy is sitting.");
}

function runThrowCombo(agent, current = {}) {
  stopAgentLocomotion(agent);
  if (agent.rigRetarget?.active) finishRigRetarget(agent);
  const target = agent.heldObject?.entry || nearestEntryToAgent(agent, objects.filter((entry) => entry.kind === "ball" || entry.affordances?.includes("throw") || entry.affordances?.includes("play")));
  if (!target) {
    document.body.dataset.lastThrowTarget = "";
    showToast("No throwable toy is close enough.");
    return;
  }
  setFacingToward(agent, camera.position.clone().sub(agent.pet.group.position));
  runPetGesture(agent, "throw", { durationMs: current.durationMs || 1450 });
  playRigMotion(agent, "Throw", { immediate: true });
  const actionToken = agent.controlToken;
  window.setTimeout(() => {
    if (agentActionAlive(agent, actionToken)) throwObjectTowardViewer(agent, target);
  }, 360);
  document.body.dataset.lastSocialCombo = "throw";
  document.body.dataset.lastSocialComboTarget = "player-camera";
  document.body.dataset.lastLookTarget = "player-camera";
  document.body.dataset.lastThrowTarget = target.id;
}

function throwObjectTowardViewer(agent, entry) {
  if (!agent || !entry) return;
  const hold = agent.heldObject?.entry === entry ? agent.heldObject : null;
  if (hold) agent.heldObject = null;
  document.body.dataset.heldObject = "";
  document.body.dataset.heldObjectAnchor = "";
  entry.body.type = hold?.originalType ?? CANNON.Body.DYNAMIC;
  entry.body.mass = Number.isFinite(hold?.originalMass) ? hold.originalMass : Math.max(0.5, Number(entry.body.mass || 1));
  entry.body.updateMassProperties();
  const handPosition = heldObjectWorldPosition(agent, entry);
  placeObject(entry, new CANNON.Vec3(handPosition.x, handPosition.y, handPosition.z));
  const viewer = playerCameraFloorTarget();
  const direction = viewer.clone().sub(handPosition);
  direction.y = 0;
  if (direction.lengthSq() < 0.01) direction.copy(agentForwardVector(agent));
  direction.normalize();
  const impulse = new CANNON.Vec3(direction.x * 3.4, 1.15, direction.z * 3.4);
  entry.body.applyImpulse(impulse, entry.body.position);
  entry.body.angularVelocity.set(direction.z * 6, 0.8, -direction.x * 6);
  entry.body.wakeUp();
  effects.ring(handPosition.clone().add(new THREE.Vector3(0, 0.15, 0)), PET_LOOKS[agent.kind].power, 0.8, 0.55);
  showToast(`Fire Boy threw ${entry.name || entry.id} toward you.`);
}

function executableSpellForAction(action = {}, spell = {}, options = {}) {
  if (!spell || !Array.isArray(spell.ops)) return null;
  if (options.projectileLaunched) return null;
  const verb = action.interaction?.verb || "none";
  if (!["walk", "run", "pickup", "carry", "bring", "turn", "look_at", "point", "reach", "release", "stop"].includes(verb)) return spell;
  const ops = spell.ops.filter((op) => ["spawn_particle", "set_light"].includes(op?.op));
  if (!ops.length) return null;
  return { ...spell, ops };
}

function spokenLineForAgent(agent, text, action = {}) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!IS_V3_MODE || agent.kind !== "fire_boy") return clean || "I have a tiny plan.";
  const lower = clean.toLowerCase();
  if (lower.includes("fireball") || lower.includes("comet") || lower.includes("whoosh")) return "Me make warm sparkle.";
  if (lower.includes("smoke") || lower.includes("poof") || lower.includes("mysterious")) return "Poof, hidey cloud.";
  if (lower.includes("jump") || lower.includes("hop") || lower.includes("bounce")) return "Boop, warm hop.";
  if (lower.includes("recycle") || lower.includes("tidy") || lower.includes("clean")) return "Me clean, hehe.";
  if (lower.includes("wish") || action.objectRecipe) return `Me made ${shortTraceText(action.objectRecipe?.name || "tiny toy", 20)}.`;
  if (lower.startsWith("i see")) return clean.replace(/^i see/i, "Me see").slice(0, 54);
  if (/\b(me|tiny|lil|hehe|boop|baby|warm)\b/i.test(clean) && clean.length <= 64) return clean;
  return "Me tiny Fire Boy.";
}

function applyObjectRecipe(agent, recipe) {
  if (!recipe || typeof recipe !== "object" || !recipe.id) return null;
  const duplicate = objects.find((entry) => entry.generated && (entry.id === recipe.id || (entry.name && entry.name === recipe.name)));
  if (duplicate) {
    effects.stars(bodyToVector(duplicate.body.position).add(new THREE.Vector3(0, 0.45, 0)), PET_LOOKS[agent.kind].power, 10);
    return duplicate;
  }
  const entry = room.spawnGeneratedObject(recipe, agent.pet.group.position);
  if (!entry) return null;
  updateGeneratedMarker();
  const position = bodyToVector(entry.body.position).add(new THREE.Vector3(0, 0.45, 0));
  effects.burst(position, colorNumber(recipe.accentColor || recipe.color, PET_LOOKS[agent.kind].power), 22, 0.9);
  effects.stars(position.clone().add(new THREE.Vector3(0, 0.2, 0)), colorNumber(recipe.color, PET_LOOKS[agent.kind].cheeks), 16);
  audio.play(recipe.affordances?.includes("music") ? "bulb_ping" : "soft_pop", 0.86);
  recordInteraction({ kind: "spawn_object", pet: agent.kind, objectId: entry.id, objectName: entry.name || recipe.name || "" });
  showToast(`${agent.label} wished in ${entry.name || recipe.name || entry.id}`);
  return entry;
}

function isVlaPolicyAction(action = {}) {
  return Boolean(action?.debug?.vlaRouter && action?.debug?.mujocoPolicy?.success);
}

function executeVlaLivePolicy(agent, action = {}) {
  if (!isVlaPolicyAction(action)) return false;
  const skill = vlaSkillForAction(action);
  const now = performance.now();
  document.body.dataset.vlaLiveBridge = `${skill}:started`;
  document.body.dataset.vlaLivePolicy = action.debug?.vlaRouter?.policyKind || "";
  document.body.dataset.vlaLiveDispatch = action.debug?.vlaRouterDispatchMessage || action.debug?.vlaRouter?.dispatch || "";
  startRigRetarget(agent, action, skill);

  if (skill === "run_around") {
    runVlaLiveRoute(agent, action);
    return true;
  }

  const target = resolveVlaLiveTarget(agent, action);
  if (!target) {
    document.body.dataset.vlaLiveBridge = `${skill}:no-target`;
    return false;
  }

  if (skill === "pick_up") {
    runVlaLivePickup(agent, target, action);
    return true;
  }

  if (skill === "find_and_eat_berry" || skill === "go_eat_berry") {
    runVlaLiveEat(agent, target, action);
    return true;
  }

  if (skill === "walk_to" || skill === "go_to_point") {
    runVlaLiveWalkTo(agent, target, action);
    return true;
  }

  document.body.dataset.vlaLiveBridge = `${skill || "unknown"}:fallback`;
  agent.pet.actionUntil = Math.max(agent.pet.actionUntil || 0, now + 1200);
  return false;
}

function vlaSkillForAction(action = {}) {
  return String(
    action.debug?.vlaRouter?.skill
      || action.debug?.mujocoPolicy?.skill
      || action.interaction?.verb
      || "",
  );
}

function resolveVlaLiveTarget(agent, action = {}) {
  const skill = vlaSkillForAction(action);
  const targetId = action.interaction?.targetId && action.interaction.targetId !== "self"
    ? String(action.interaction.targetId)
    : "";
  const exact = targetId ? objects.find((entry) => entry.id === targetId) : null;
  const virtualExact = targetId ? virtualTargetEntryForId(agent, targetId) : null;
  const commandTarget = commandTargetForLiveVla(agent, action, skill);
  if (commandTarget) return commandTarget;
  if (virtualExact) return virtualExact;
  if (exact) return exact;

  const edible = objects.filter((entry) => entry.consumable || entry.kind === "berry" || entry.affordances?.includes("eat"));
  if (skill === "find_and_eat_berry" || skill === "go_eat_berry") {
    return nearestEntryToAgent(agent, edible) || nearestObjectFor(agent);
  }

  if (skill === "pick_up") {
    const grabbable = objects.filter((entry) => (
      entry.kind === "berry"
      || entry.kind === "ball"
      || entry.affordances?.includes("play")
      || entry.affordances?.includes("lift")
      || entry.affordances?.includes("eat")
    ));
    return nearestEntryToAgent(agent, grabbable) || nearestObjectFor(agent);
  }

  return nearestObjectFor(agent);
}

function commandTargetForLiveVla(agent, action = {}, skill = "") {
  const command = String(action.debug?.clientCommand || action.debug?.originalCommand || "").toLowerCase();
  if (!command && skill !== "find_and_eat_berry" && skill !== "go_eat_berry") return null;
  if (/\b(me|camera|viewer|player|user|here)\b/.test(command) || /\bcome (to )?me\b/.test(command)) {
    document.body.dataset.vlaLiveGrounding = "player-camera";
    return virtualTargetEntryForId(agent, "player-camera");
  }
  const requested = requestedTargetGroups(command, skill);
  let candidates = objects.slice();
  if (requested.categories.size) {
    const matching = candidates.filter((entry) => [...requested.categories].some((group) => entryMatchesTargetGroup(entry, group)));
    if (matching.length) candidates = matching;
  }
  if (!candidates.length) return null;
  const origin = agent?.pet?.group?.position || new THREE.Vector3();
  const scored = candidates
    .map((entry) => ({
      entry,
      score: liveTargetCommandScore(entry, command, requested),
      distance: bodyToVector(entry.body.position).distanceTo(origin),
    }))
    .filter((item) => item.score > 0 || requested.categories.size || requested.colors.size)
    .sort((a, b) => b.score - a.score || a.distance - b.distance);
  const winner = scored[0]?.entry || null;
  if (winner) document.body.dataset.vlaLiveGrounding = `${winner.id}:${Math.max(0, scored[0].score).toFixed(0)}`;
  return winner;
}

const TARGET_GROUP_ALIASES = {
  berry: ["berry", "berries", "food", "snack"],
  ball: ["ball", "sphere", "orb", "round"],
  cube: ["cube", "block", "box"],
  chair: ["chair", "seat", "stool", "sit"],
  table: ["table", "desk"],
  lamp: ["lamp", "light"],
  plant: ["plant", "fern", "sprout", "pot"],
  book: ["book", "notes", "story"],
  clock: ["clock", "timer"],
  bottle: ["bottle"],
  can: ["can", "tin"],
  paper: ["paper"],
  waste: ["waste", "trash", "garbage", "peel"],
  bin: ["bin", "recycle"],
  ramp: ["ramp"],
  domino: ["domino"],
};

const TARGET_COLOR_ALIASES = {
  blue: ["blue", "cyan", "teal"],
  mint: ["mint", "green", "teal"],
  green: ["green", "mint", "leaf", "fern"],
  yellow: ["yellow", "amber", "honey", "gold", "golden"],
  orange: ["orange", "coral", "ember", "fire"],
  red: ["red", "rose", "pink"],
  purple: ["purple", "violet", "moon"],
  white: ["white", "pale", "cream"],
  black: ["black", "dark"],
  brown: ["brown", "wood", "wooden"],
};

function requestedTargetGroups(command, skill = "") {
  const terms = tokenizeTargetText(command);
  const categories = new Set();
  const colors = new Set();
  for (const [group, aliases] of Object.entries(TARGET_GROUP_ALIASES)) {
    if (aliases.some((alias) => terms.has(alias))) categories.add(group);
  }
  for (const [color, aliases] of Object.entries(TARGET_COLOR_ALIASES)) {
    if (aliases.some((alias) => terms.has(alias))) colors.add(color);
  }
  if (skill === "find_and_eat_berry" || skill === "go_eat_berry") categories.add("berry");
  return { terms, categories, colors };
}

function liveTargetCommandScore(entry, command, requested = requestedTargetGroups(command)) {
  const terms = targetTermsForEntry(entry);
  let score = 0;
  for (const word of requested.terms) {
    if (word.length >= 3 && terms.has(word)) score += 12;
  }
  for (const group of requested.categories) {
    if (entryMatchesTargetGroup(entry, group)) score += 24;
  }
  for (const color of requested.colors) {
    if (entryMatchesTargetColor(entry, color)) score += 18;
  }
  if (/\bsoft ball\b/.test(command) && terms.has("soft") && terms.has("ball")) score += 12;
  if (/\bmoon ball\b/.test(command) && terms.has("moon") && terms.has("ball")) score += 12;
  if (/\breading lamp\b/.test(command) && entry.id === "reading-lamp") score += 12;
  if (/\btea table\b/.test(command) && entry.id === "tea-table") score += 12;
  return score;
}

function entryMatchesTargetGroup(entry, group) {
  const terms = targetTermsForEntry(entry);
  const aliases = TARGET_GROUP_ALIASES[group] || [group];
  return aliases.some((alias) => terms.has(alias));
}

function entryMatchesTargetColor(entry, color) {
  const terms = targetTermsForEntry(entry);
  const aliases = TARGET_COLOR_ALIASES[color] || [color];
  return aliases.some((alias) => terms.has(alias));
}

function targetTermsForEntry(entry = {}) {
  const terms = new Set(tokenizeTargetText([
    entry.id,
    entry.kind,
    entry.name || "",
    ...(entry.tags || []),
    ...(entry.affordances || []),
  ].join(" ")));
  const kind = String(entry.kind || "").toLowerCase();
  const id = String(entry.id || "").toLowerCase();
  if (kind === "ball") addTerms(terms, "sphere orb round toy");
  if (kind === "berry") addTerms(terms, "berry berries food snack sphere round");
  if (kind === "cube") addTerms(terms, "cube block box");
  if (kind === "chair") addTerms(terms, "chair seat furniture");
  if (kind === "table") addTerms(terms, "table desk furniture");
  if (kind === "lamp") addTerms(terms, "lamp light");
  if (kind === "plant") addTerms(terms, "plant fern sprout pot green");
  if (kind === "recycle-bin") addTerms(terms, "bin recycle trash waste");
  if (id.includes("blue")) addTerms(terms, "blue cyan teal");
  if (id.includes("mint")) addTerms(terms, "mint green teal");
  if (id.includes("coral")) addTerms(terms, "coral orange red");
  if (id.includes("honey")) addTerms(terms, "honey yellow gold golden");
  if (id.includes("amber")) addTerms(terms, "amber yellow orange gold golden");
  if (id.includes("ember") || id.includes("fire")) addTerms(terms, "ember fire orange red warm");
  if (id.includes("moon")) addTerms(terms, "moon purple violet blue pale");
  if (id.includes("rose")) addTerms(terms, "rose red pink");
  if (id.includes("beach")) addTerms(terms, "beach white pale sphere orb");
  if (id.includes("reading-lamp")) addTerms(terms, "blue cyan reading lamp light");
  if (id.includes("lamp") && !id.includes("reading")) addTerms(terms, "yellow warm lamp light");
  if (id.includes("fern") || id.includes("sprout")) addTerms(terms, "green plant leaf");
  if (id.includes("paper")) addTerms(terms, "paper white waste trash sphere");
  if (id.includes("can")) addTerms(terms, "can tin metal waste");
  if (id.includes("bottle")) addTerms(terms, "bottle blue waste");
  if (id.includes("peel")) addTerms(terms, "peel banana yellow waste");
  return terms;
}

function addTerms(set, text) {
  for (const term of tokenizeTargetText(text)) set.add(term);
}

function tokenizeTargetText(value) {
  return new Set(String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").split(/\s+/).filter(Boolean));
}

function nearestEntryToAgent(agent, entries = []) {
  if (!agent || !entries.length) return null;
  const origin = agent.pet.group.position;
  return [...entries].sort((a, b) => (
    bodyToVector(a.body.position).distanceTo(origin) - bodyToVector(b.body.position).distanceTo(origin)
  ))[0] || null;
}

function runVlaLiveRoute(agent, action = {}) {
  const center = roomCenterPoint();
  const current = agent.rig.position();
  const radius = THREE.MathUtils.clamp(Number(action.debug?.vlaRouter?.params?.radius || 1.35), 0.9, 2.2);
  const direction = current.clone().sub(center);
  direction.y = 0;
  if (direction.lengthSq() < 0.01) direction.set(1, 0, 0);
  direction.normalize();
  const tangent = new THREE.Vector3(-direction.z, 0, direction.x);
  const route = [
    center.clone().add(direction.clone().multiplyScalar(radius)),
    center.clone().add(direction.clone().multiplyScalar(0.35)).add(tangent.clone().multiplyScalar(radius * 0.85)),
    center.clone().add(direction.clone().multiplyScalar(-radius * 0.9)).add(tangent.clone().multiplyScalar(radius * 0.35)),
    center.clone().add(tangent.clone().multiplyScalar(-radius * 0.9)),
    current.clone(),
  ].map((point) => clampAgentPosition(point));
  const durationMs = Number(action.interaction?.durationMs || 5200);
  startAgentLocomotion(agent, route, Math.max(3600, durationMs), { walk: false, loop: false, stopAtEnd: true, speed: 2.35 });
  document.body.dataset.vlaLiveBridge = "run_around:live-route";
  document.body.dataset.vlaLiveTarget = `${route[0].x.toFixed(2)},${route[0].z.toFixed(2)}`;
  showToast("VLA is driving Fire Boy's live run.");
}

function runVlaLiveWalkTo(agent, target, action = {}) {
  const targetPosition = bodyToVector(target.body.position);
  const approach = target.virtualDirect ? clampAgentPosition(targetPosition.clone()) : approachPointForObject(agent, target);
  const distance = agent.rig.position().distanceTo(approach);
  const shouldRun = commandRequestsRun(action);
  const durationMs = THREE.MathUtils.clamp(distance * (shouldRun ? 520 : 900), shouldRun ? 620 : 900, Number(action.interaction?.durationMs || (shouldRun ? 2600 : 3600)));
  setFacingToward(agent, targetPosition.clone().sub(agent.pet.group.position));
  startAgentLocomotion(agent, [approach], durationMs, { walk: !shouldRun, stopAtEnd: true, speed: shouldRun ? 2.22 : 1.24 });
  document.body.dataset.vlaLiveBridge = shouldRun ? "run_to:live-route" : "walk_to:live-route";
  document.body.dataset.vlaLiveTarget = target.id;
  document.body.dataset.vlaLiveTargetKind = target.kind || "";
  document.body.dataset.vlaLiveTargetPosition = `${approach.x.toFixed(2)},${approach.z.toFixed(2)}`;
  const verb = shouldRun ? "running" : "walking";
  showToast(target.id === "player-camera" ? `VLA is ${verb} Fire Boy toward the viewer.` : `VLA is ${verb} Fire Boy toward ${target.name || target.id}.`);
}

function commandRequestsRun(action = {}) {
  const command = String(action.debug?.clientCommand || action.debug?.originalCommand || action.interaction?.verb || action.intent || "").toLowerCase();
  return /\b(run|running|dash|sprint|race|zoom)\b/.test(command) || action.interaction?.verb === "run";
}

function runVlaLivePickup(agent, target, action = {}) {
  const actionToken = agent.controlToken;
  const targetPosition = bodyToVector(target.body.position);
  const approach = approachPointForObject(agent, target);
  const distance = agent.rig.position().distanceTo(approach);
  const approachMs = THREE.MathUtils.clamp(distance * 760, 640, 1900);
  setFacingToward(agent, targetPosition.clone().sub(agent.pet.group.position));
  startAgentLocomotion(agent, [approach], approachMs, { walk: true, stopAtEnd: true, speed: 1.22 });
  playRigMotion(agent, "Walk");
  document.body.dataset.vlaLiveBridge = "pick_up:approach";
  document.body.dataset.vlaLiveTarget = target.id;
  setTimeout(() => {
    if (!agentActionAlive(agent, actionToken)) return;
    if (!objects.includes(target)) return;
    setFacingToward(agent, bodyToVector(target.body.position).sub(agent.pet.group.position));
    runPetGesture(agent, "reach", { durationMs: 680 });
    playRigMotion(agent, "Cheer");
    setTimeout(() => {
      if (!agentActionAlive(agent, actionToken)) return;
      if (!objects.includes(target)) return;
      pickUpObject(agent, target, "pickup", Math.max(Number(action.interaction?.durationMs || 3600), 6400));
      runPetGesture(agent, "hold", { durationMs: 2600 });
      document.body.dataset.vlaLiveBridge = "pick_up:grasped";
    }, 520);
  }, approachMs + 120);
}

function runVlaLiveEat(agent, target, action = {}) {
  const actionToken = agent.controlToken;
  const targetPosition = bodyToVector(target.body.position);
  const approach = approachPointForObject(agent, target);
  const distance = agent.rig.position().distanceTo(approach);
  const approachMs = THREE.MathUtils.clamp(distance * 820, 760, 2300);
  setFacingToward(agent, targetPosition.clone().sub(agent.pet.group.position));
  startAgentLocomotion(agent, [approach], approachMs, { walk: true, stopAtEnd: true, speed: 1.28 });
  playRigMotion(agent, "Walk");
  document.body.dataset.vlaLiveBridge = "find_and_eat_berry:approach";
  document.body.dataset.vlaLiveTarget = target.id;
  setTimeout(() => {
    if (!agentActionAlive(agent, actionToken)) return;
    if (!objects.includes(target)) return;
    setFacingToward(agent, bodyToVector(target.body.position).sub(agent.pet.group.position));
    runPetGesture(agent, "reach", { durationMs: 620 });
    playRigMotion(agent, "Cheer");
    setTimeout(() => {
      if (!agentActionAlive(agent, actionToken)) return;
      if (!objects.includes(target)) return;
      pickUpObject(agent, target, "pickup", 2600);
      runPetGesture(agent, "hold", { durationMs: 1700 });
      document.body.dataset.vlaLiveBridge = "find_and_eat_berry:grasped";
      setTimeout(() => {
        if (!agentActionAlive(agent, actionToken)) return;
        if (!objects.includes(target)) return;
        effects.hearts(bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.24, 0)), PET_LOOKS[agent.kind].cheeks, 8);
        room.consumeObject(target.id);
        agent.heldObject = null;
        document.body.dataset.heldObject = "";
        document.body.dataset.heldObjectAnchor = "";
        agent.needs.hunger = clampNeed(agent.needs.hunger - Number(target.nutrition || 24));
        agent.needs.energy = clampNeed(agent.needs.energy + Number(target.energy || 15));
        agent.needs.playfulness = clampNeed((agent.needs.playfulness ?? 50) + 4);
        runPetGesture(agent, "hold", { durationMs: 900 });
        playRigMotion(agent, "Cheer");
        document.body.dataset.vlaLiveBridge = "find_and_eat_berry:eaten";
        document.body.dataset.lastInteractionVerb = "eat";
        recordInteraction({ kind: "vla_live_eat", pet: agent.kind, objectId: target.id });
      }, 900);
    }, 460);
  }, approachMs + 120);
}

function roomCenterPoint() {
  const candidates = objects
    .filter((entry) => ["cube", "ball", "berry"].includes(entry.kind))
    .map((entry) => bodyToVector(entry.body.position));
  if (!candidates.length) return new THREE.Vector3(0, 0.06, 0);
  const center = candidates.reduce((acc, point) => acc.add(point), new THREE.Vector3()).multiplyScalar(1 / candidates.length);
  center.y = 0.06;
  return clampAgentPosition(center);
}

function executeInteraction(agent, interaction = {}, action = {}) {
  const verb = interaction.verb || "none";
  if (verb === "none") return false;
  if (verb === "stop") {
    performIdleStop(agent, "command_stop");
    recordInteraction({ kind: verb, pet: agent.kind, objectId: interaction.targetId || "" });
    return true;
  }
  if (verb === "release") {
    releaseHeldObject(agent);
    runPetGesture(agent, "release", { durationMs: Number(interaction.durationMs || 1200) });
    recordInteraction({ kind: verb, pet: agent.kind, objectId: interaction.targetId || "" });
    return true;
  }
  if (verb === "turn") {
    turnAgent(agent, action);
    recordInteraction({ kind: verb, pet: agent.kind, objectId: interaction.targetId || "" });
    return true;
  }
  if (verb === "run" || verb === "walk") {
    const requestedDuration = Number(interaction.durationMs || 0);
    const minimumDuration = verb === "walk" ? 4200 : 3000;
    runAgentRoute(agent, Math.max(requestedDuration, minimumDuration), { walk: verb === "walk" });
    recordInteraction({ kind: verb, pet: agent.kind, objectId: interaction.targetId || "" });
    return true;
  }
  const target = objects.find((entry) => entry.id === interaction.targetId) || nearestObjectFor(agent);
  const partner = interaction.partnerPet ? findPartner(interaction.partnerPet, agent) : null;
  recordInteraction({ kind: verb, pet: agent.kind, objectId: target?.id || "", partnerPet: partner?.kind || "" });

  if (partner && ["talk", "play", "comfort", "share", "gather"].includes(verb)) {
    moveAgentNearAgent(agent, partner);
    effects.hearts(midpoint(agent.pet.group.position, partner.pet.group.position).add(new THREE.Vector3(0, 1.1, 0)), PET_LOOKS[agent.kind].cheeks, 7);
    partner.rig.nudge(new CANNON.Vec3(0.08, 0.2, 0.02), 0.45);
    agent.lastPartner = partner.kind;
    partner.lastIntent = `${verb} with ${agent.label}`;
    partner.lastPartner = agent.kind;
    document.body.dataset.socialInteractions = String(Number(document.body.dataset.socialInteractions || 0) + 1);
    schedulePartnerReply(agent, partner, verb);
    return true;
  }

  if (!target) return false;

  if (verb === "look_at") {
    const playerTarget = isPlayerFacingAction(action, interaction);
    if (playerTarget) performLookAtPlayer(agent, interaction);
    else performLookAtObject(agent, target, interaction);
    return true;
  }

  if (verb === "point") {
    performPointAtObject(agent, target, interaction);
    return true;
  }

  if (verb === "reach") {
    performReachForObject(agent, target, interaction);
    return true;
  }

  if (["pickup", "carry", "bring"].includes(verb)) {
    approachAndPickUpObject(agent, target, verb, Number(interaction.durationMs || 2400));
    return true;
  }

  moveAgentNearObject(agent, target);

  if (verb === "clean" || verb === "recycle") {
    const bin = objects.find((entry) => entry.id === "recycle-bin");
    if (bin && target.id !== "recycle-bin") {
      const dir = new CANNON.Vec3(bin.body.position.x - target.body.position.x, 1.0, bin.body.position.z - target.body.position.z);
      dir.normalize();
      target.body.applyImpulse(dir.scale(2.1), target.body.position);
      effects.stars(bodyToVector(target.body.position), 0x66cbd8, 14);
      audio.play("soft_pop", 0.68);
      if (target.recyclable && !recycledWasteIds.has(target.id)) {
        setTimeout(() => {
          const current = objects.find((entry) => entry.id === target.id);
          const currentBin = objects.find((entry) => entry.id === "recycle-bin");
          if (current && currentBin && !recycledWasteIds.has(current.id)) scoreRecycledWaste(current, bodyToVector(currentBin.body.position));
        }, 620);
      }
    }
    return true;
  }

  if (verb === "eat" && target.consumable) {
    effects.hearts(bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.24, 0)), PET_LOOKS[agent.kind].cheeks, 6);
    setTimeout(() => {
      room.consumeObject(target.id);
      if (agent.heldObject?.entry === target) agent.heldObject = null;
      document.body.dataset.heldObject = "";
      document.body.dataset.heldObjectAnchor = "";
    }, 520);
    agent.needs.hunger = clampNeed(agent.needs.hunger - Number(target.nutrition || 18));
    agent.needs.energy = clampNeed(agent.needs.energy + Number(target.energy || 15));
    agent.needs.playfulness = clampNeed((agent.needs.playfulness ?? 50) + 4);
    return true;
  }

  if (["read", "inspect", "sniff", "water", "sit", "play"].includes(verb)) {
    const position = bodyToVector(target.body.position);
    effects.stars(position.add(new THREE.Vector3(0, 0.45, 0)), PET_LOOKS[agent.kind].power, 10);
    agent.needs.curiosity = clampNeed(agent.needs.curiosity - 7);
    agent.needs.social = clampNeed(agent.needs.social - (partner ? 10 : 2));
    return true;
  }
  return false;
}

function runPetGesture(agent, animation, options = {}) {
  if (!agent?.pet) return;
  const now = performance.now();
  agent.pet.animation = animation;
  agent.pet.actionUntil = Math.max(agent.pet.actionUntil || 0, now + Math.max(500, Number(options.durationMs || 1500)));
  document.body.dataset.lastGesture = animation;
}

function turnAgent(agent, action = {}) {
  const turnToPlayer = isPlayerFacingAction(action, action.interaction || {});
  if (turnToPlayer) {
    setFacingToward(agent, camera.position.clone().sub(agent.pet.group.position));
  } else {
    const currentYaw = Number.isFinite(agent.pet.targetFacingYaw) ? agent.pet.targetFacingYaw : agent.pet.group.rotation.y;
    agent.pet.targetFacingYaw = currentYaw + Math.PI;
  }
  runPetGesture(agent, "turn", { durationMs: 1400 });
  playRigMotion(agent, "Spin");
  effects.ring(agent.pet.group.position.clone().add(new THREE.Vector3(0, 0.28, 0)), PET_LOOKS[agent.kind].power, 0.72, 0.42);
  document.body.dataset.lastTurnYaw = String(Number(agent.pet.targetFacingYaw || 0).toFixed(3));
}

function isPlayerFacingAction(action = {}, interaction = {}) {
  return action.intent === "grounded_look_at_player"
    || action.intent === "grounded_greet_player"
    || action.intent === "grounded_dance_player"
    || action.debug?.commandCoercion === "look_at_player"
    || action.debug?.commandCoercion === "greet_player"
    || action.debug?.commandCoercion === "dance_player"
    || interaction.targetId === "player-camera";
}

function performLookAtPlayer(agent, interaction = {}) {
  stopAgentLocomotion(agent);
  setFacingToward(agent, camera.position.clone().sub(agent.pet.group.position));
  runPetGesture(agent, "look", { durationMs: Number(interaction.durationMs || 1700) });
  playRigMotion(agent, "Wave");
  effects.stars(agent.pet.group.position.clone().add(new THREE.Vector3(0, 1.48, 0.24)), PET_LOOKS[agent.kind].power, 6);
  document.body.dataset.lastLookTarget = "player-camera";
}

function performLookAtObject(agent, target, interaction = {}) {
  stopAgentLocomotion(agent);
  const position = bodyToVector(target.body.position);
  setFacingToward(agent, position.clone().sub(agent.pet.group.position));
  runPetGesture(agent, "look", { durationMs: Number(interaction.durationMs || 1700) });
  playRigMotion(agent, "Wave");
  effects.stars(position.clone().add(new THREE.Vector3(0, 0.42, 0)), PET_LOOKS[agent.kind].power, 8);
  document.body.dataset.lastLookTarget = target.id;
}

function performPointAtObject(agent, target, interaction = {}) {
  stopAgentLocomotion(agent);
  const position = bodyToVector(target.body.position);
  setFacingToward(agent, position.clone().sub(agent.pet.group.position));
  runPetGesture(agent, "point", { durationMs: Number(interaction.durationMs || 1800) });
  playRigMotion(agent, "Wave");
  effects.ring(position.clone().add(new THREE.Vector3(0, 0.24, 0)), PET_LOOKS[agent.kind].power, 0.52, 0.42);
  document.body.dataset.lastPointTarget = target.id;
}

function performReachForObject(agent, target, interaction = {}) {
  const actionToken = agent.controlToken;
  const position = bodyToVector(target.body.position);
  const distance = agent.rig.position().distanceTo(position);
  const durationMs = Number(interaction.durationMs || 1900);
  const reach = () => {
    if (!objects.includes(target)) return;
    const latestPosition = bodyToVector(target.body.position);
    setFacingToward(agent, latestPosition.clone().sub(agent.pet.group.position));
    runPetGesture(agent, "reach", { durationMs });
    playRigMotion(agent, "Cheer");
    effects.stars(latestPosition.clone().add(new THREE.Vector3(0, 0.34, 0)), PET_LOOKS[agent.kind].cheeks, 6);
    document.body.dataset.lastReachTarget = target.id;
  };
  if (distance > 1.35) {
    const approach = approachPointForObject(agent, target);
    const approachMs = THREE.MathUtils.clamp(distance * 680, 420, 1200);
    setFacingToward(agent, position.clone().sub(agent.pet.group.position));
    startAgentLocomotion(agent, [approach], approachMs, { walk: true, stopAtEnd: true });
    setTimeout(() => {
      if (agentActionAlive(agent, actionToken)) reach();
    }, approachMs);
  } else {
    stopAgentLocomotion(agent);
    reach();
  }
}

function pickUpObject(agent, target, verb, durationMs = 2400) {
  const targetLabel = target.name || target.id.replace(/-/g, " ");
  const holdColor = PET_LOOKS[agent.kind].power;
  releaseHeldObject(agent, { quiet: true });
  const originalMass = target.body.mass;
  const originalType = target.body.type;
  target.body.type = CANNON.Body.KINEMATIC;
  target.body.mass = 0;
  target.body.updateMassProperties();
  target.body.velocity.set(0, 0, 0);
  target.body.angularVelocity.set(0, 0, 0);
  agent.heldObject = {
    entry: target,
    originalMass,
    originalType,
    until: performance.now() + Math.max(durationMs, verb === "pickup" ? 3600 : 2600),
    verb,
    targetLabel,
  };
  updateHeldObject(agent, performance.now(), 0, true);
  effects.stars(bodyToVector(target.body.position), holdColor, 12);
  document.body.dataset.lastPickupTarget = target.id;
  document.body.dataset.lastInteractionVerb = verb;
  playRigMotion(agent, verb === "pickup" ? "Cheer" : "Walk");
  if (verb === "carry" || verb === "bring") {
    const forward = agentForwardVector(agent);
    const side = new THREE.Vector3(forward.z, 0, -forward.x);
    const offset = verb === "bring"
      ? forward.clone().multiplyScalar(1.38)
      : forward.clone().multiplyScalar(0.92).add(side.multiplyScalar(0.72));
    const next = clampAgentPosition(agent.rig.position().add(offset));
    startAgentLocomotion(agent, [next], Math.max(1200, Math.min(durationMs, 2800)), { walk: true, stopAtEnd: true });
    setTimeout(() => releaseHeldObject(agent, { toast: `${agent.label} carried ${targetLabel}.` }), Math.min(durationMs, 3200));
  } else {
    showToast(`${agent.label} picked up ${targetLabel}.`);
  }
}

function runAgentRoute(agent, durationMs = 2600, options = {}) {
  const isWalk = Boolean(options.walk);
  const start = agent.rig.position();
  const route = [
    new THREE.Vector3(1.18, 0, 0.12),
    new THREE.Vector3(0.72, 0, -1.08),
    new THREE.Vector3(-0.92, 0, -0.74),
    new THREE.Vector3(-0.54, 0, 0.86),
    new THREE.Vector3(0.12, 0, 0.08),
  ].map((offset) => clampAgentPosition(start.clone().add(offset)));
  document.body.dataset.lastRunAround = String(Date.now());
  startAgentLocomotion(agent, route, durationMs, { walk: isWalk, loop: true });
}

function approachAndPickUpObject(agent, target, verb, durationMs = 2400) {
  const actionToken = agent.controlToken;
  const targetPosition = bodyToVector(target.body.position);
  const approach = approachPointForObject(agent, target);
  const distance = agent.rig.position().distanceTo(approach);
  const approachMs = THREE.MathUtils.clamp(distance * 720, 420, Math.min(1500, durationMs * 0.6));
  setFacingToward(agent, targetPosition.clone().sub(agent.pet.group.position));
  startAgentLocomotion(agent, [approach], approachMs + 180, { walk: true, stopAtEnd: true });
  setTimeout(() => {
    if (!agentActionAlive(agent, actionToken)) return;
    if (!objects.includes(target)) return;
    setFacingToward(agent, bodyToVector(target.body.position).sub(agent.pet.group.position));
    pickUpObject(agent, target, verb, durationMs);
  }, approachMs);
}

function startAgentLocomotion(agent, route, durationMs = 2400, options = {}) {
  const points = (Array.isArray(route) ? route : [route])
    .filter(Boolean)
    .map((point) => clampAgentPosition(point.clone ? point.clone() : new THREE.Vector3(point.x || 0, point.y || 0, point.z || 0)));
  if (!agent || !points.length) return;
  const now = performance.now();
  const walk = options.walk !== false;
  const startPosition = agent.rig.position();
  const moodSpeed = petSpeedMultiplier(agent);
  const duration = Math.max(420, durationMs / moodSpeed);
  agent.locomotion = {
    route: points,
    index: 0,
    until: now + duration,
    startPosition,
    speed: Number(options.speed || (walk ? 1.24 : 2.08)) * moodSpeed,
    walk,
    loop: Boolean(options.loop),
    stopAtEnd: options.stopAtEnd !== false,
    lastStepAt: 0,
    lastProgressAt: now,
    lastDistance: Number.POSITIVE_INFINITY,
    stuckSkips: 0,
  };
  agent.pet.animation = walk ? "walk" : "run";
  agent.pet.actionUntil = Math.max(agent.pet.actionUntil, now + duration);
  document.body.dataset.lastLocomotionStart = `${startPosition.x.toFixed(2)},${startPosition.z.toFixed(2)}`;
  document.body.dataset.lastLocomotionMode = walk ? "walk" : "run";
  document.body.dataset.lastLocomotionTravel = "0.00";
  playRigMotion(agent, walk ? "Walk" : "Run");
}

function petSpeedMultiplier(agent) {
  const playfulness = Number(agent?.needs?.playfulness ?? 50);
  const energy = Number(agent?.needs?.energy ?? 60);
  const playBoost = THREE.MathUtils.clamp(0.82 + playfulness / 180, 0.78, 1.34);
  const energyDrag = energy < 25 ? 0.72 : energy < 45 ? 0.9 : 1;
  return Number((playBoost * energyDrag).toFixed(3));
}

function updateAgentLocomotion(agent, now, dt) {
  const locomotion = agent?.locomotion;
  if (!locomotion || !locomotion.route?.length) return;
  const current = agent.rig.position();
  if (now > locomotion.until) {
    stopAgentLocomotion(agent, current);
    return;
  }
  let waypoint = locomotion.route[locomotion.index] || locomotion.route[0];
  let toWaypoint = waypoint.clone().sub(current);
  toWaypoint.y = 0;
  if (toWaypoint.length() < 0.34) {
    locomotion.index += 1;
    if (locomotion.index >= locomotion.route.length) {
      if (locomotion.loop) locomotion.index = 0;
      else {
        stopAgentLocomotion(agent, current);
        return;
      }
    }
    waypoint = locomotion.route[locomotion.index] || waypoint;
    toWaypoint = waypoint.clone().sub(current);
    toWaypoint.y = 0;
  }
  const distance = Math.max(0.001, toWaypoint.length());
  if (distance < locomotion.lastDistance - 0.08) {
    locomotion.lastDistance = distance;
    locomotion.lastProgressAt = now;
  } else if (now - locomotion.lastProgressAt > 900) {
    locomotion.stuckSkips += 1;
    locomotion.index = (locomotion.index + 1) % locomotion.route.length;
    locomotion.lastDistance = Number.POSITIVE_INFINITY;
    locomotion.lastProgressAt = now;
    document.body.dataset.lastLocomotionStuckSkips = String(locomotion.stuckSkips);
    if (!locomotion.loop && locomotion.stuckSkips > 1) {
      stopAgentLocomotion(agent, current);
    }
    return;
  }
  const direction = toWaypoint.multiplyScalar(1 / distance);
  const leadDistance = locomotion.walk ? 1.12 : 1.62;
  const lead = clampAgentPosition(current.clone().add(direction.clone().multiplyScalar(Math.min(distance, leadDistance))));
  agent.rig.steerTo(new CANNON.Vec3(lead.x, 0.06, lead.z), { settleOnFloor: true });
  agent.rig.drive(new CANNON.Vec3(direction.x, 0, direction.z), locomotion.speed, dt);
  setFacingToward(agent, direction);
  agent.pet.animation = locomotion.walk ? "walk" : "run";
  agent.pet.actionUntil = Math.max(agent.pet.actionUntil, now + 220);
  document.body.dataset.lastLocomotionPet = agent.kind;
  document.body.dataset.lastLocomotionPosition = `${current.x.toFixed(2)},${current.z.toFixed(2)}`;
  document.body.dataset.lastLocomotionTarget = `${waypoint.x.toFixed(2)},${waypoint.z.toFixed(2)}`;
  document.body.dataset.lastLocomotionMode = locomotion.walk ? "walk" : "run";
  if (locomotion.startPosition) {
    document.body.dataset.lastLocomotionTravel = current.distanceTo(locomotion.startPosition).toFixed(2);
  }
  if (now - locomotion.lastStepAt > (locomotion.walk ? 520 : 330)) {
    locomotion.lastStepAt = now;
    effects.burst(agent.pet.group.position.clone().add(new THREE.Vector3(0, 0.24, 0.2)), PET_LOOKS[agent.kind].power, locomotion.walk ? 2 : 5, locomotion.walk ? 0.18 : 0.38);
  }
}

function stopAgentLocomotion(agent, current = agent?.rig?.position?.()) {
  if (!agent) return;
  const locomotion = agent.locomotion;
  agent.locomotion = null;
  const position = current || agent.pet.group.position;
  agent.rig.steerTo(new CANNON.Vec3(position.x, 0.06, position.z), { settleOnFloor: true });
  document.body.dataset.lastLocomotionMode = "stopped";
  document.body.dataset.lastLocomotionPosition = `${position.x.toFixed(2)},${position.z.toFixed(2)}`;
  if (locomotion?.startPosition) {
    document.body.dataset.lastLocomotionTravel = position.distanceTo(locomotion.startPosition).toFixed(2);
  }
}

function cancelAgentActions(agent) {
  if (!agent) return 0;
  agent.controlToken = Number(agent.controlToken || 0) + 1;
  document.body.dataset.agentControlToken = String(agent.controlToken);
  return agent.controlToken;
}

function agentActionAlive(agent, token) {
  return Boolean(agent && Number(agent.controlToken || 0) === Number(token));
}

function performIdleStop(agent, reason = "command_stop", options = {}) {
  if (!agent) return;
  cancelAgentActions(agent);
  stopAgentLocomotion(agent);
  if (agent.rigRetarget?.active) finishRigRetarget(agent);
  agent.pet.animation = "idle";
  agent.pet.actionUntil = performance.now() + 800;
  playRigMotion(agent, "Idle", { immediate: true });
  document.body.dataset.lastStopReason = reason;
  document.body.dataset.lastGesture = "idle";
  document.body.dataset.lastSocialCombo = "";
  document.body.dataset.pendingSocialCombo = "";
  if (!options.quiet) {
    showSpeech(`${agent.label}: me stop.`);
    showToast("Fire Boy stopped and idled.");
  }
  updateAgentPanel();
}

function approachPointForObject(agent, target) {
  const targetPosition = bodyToVector(target.body.position);
  const fromTarget = agent.rig.position().sub(targetPosition);
  fromTarget.y = 0;
  if (fromTarget.lengthSq() < 0.01) fromTarget.copy(agentForwardVector(agent)).multiplyScalar(-1);
  fromTarget.normalize().multiplyScalar(Math.max(0.88, Number(target.radius || 0.36) + 0.62));
  return clampAgentPosition(targetPosition.clone().add(fromTarget));
}

function updateHeldObject(agent, now, _dt, immediate = false) {
  const hold = agent?.heldObject;
  if (!hold?.entry || !objects.includes(hold.entry)) {
    if (agent) agent.heldObject = null;
    return;
  }
  if (now > hold.until) {
    releaseHeldObject(agent);
    return;
  }
  const entry = hold.entry;
  const current = bodyToVector(entry.body.position);
  const target = heldObjectWorldPosition(agent, entry);
  const velocity = target.clone().sub(current).multiplyScalar(immediate ? 0 : 12);
  entry.body.position.set(target.x, target.y, target.z);
  entry.body.velocity.set(velocity.x, velocity.y, velocity.z);
  entry.body.angularVelocity.set(0, 0, 0);
  entry.mesh.position.copy(entry.body.position);
  entry.mesh.quaternion.copy(entry.body.quaternion);
  document.body.dataset.lastPickupTarget = entry.id;
  document.body.dataset.lastInteractionVerb = hold.verb || "pickup";
  document.body.dataset.heldObject = entry.id;
  document.body.dataset.heldObjectPosition = `${target.x.toFixed(2)},${target.y.toFixed(2)},${target.z.toFixed(2)}`;
}

function releaseHeldObject(agent, options = {}) {
  const hold = agent?.heldObject;
  if (!hold?.entry) return;
  const entry = hold.entry;
  agent.heldObject = null;
  document.body.dataset.heldObject = "";
  document.body.dataset.heldObjectAnchor = "";
  entry.body.type = hold.originalType ?? CANNON.Body.DYNAMIC;
  entry.body.mass = Number.isFinite(hold.originalMass) ? hold.originalMass : 1;
  entry.body.updateMassProperties();
  const drop = heldObjectDropPosition(agent, entry);
  placeObject(entry, new CANNON.Vec3(drop.x, drop.y, drop.z));
  const forward = agentForwardVector(agent);
  entry.body.velocity.set(forward.x * 0.55, 0.18, forward.z * 0.55);
  entry.body.wakeUp();
  effects.ring(bodyToVector(entry.body.position).add(new THREE.Vector3(0, 0.25, 0)), PET_LOOKS[agent.kind].power, 0.64, 0.56);
  if (options.toast) showToast(options.toast);
  else if (!options.quiet) showToast(`${agent.label} put down ${hold.targetLabel || entry.name || entry.id}.`);
}

function heldObjectWorldPosition(agent, entry) {
  const hands = rigHandHoldWorldPosition(agent);
  if (hands) {
    const halfY = objectHalfHeight(entry);
    hands.y = Math.max(hands.y, halfY + 0.34);
    document.body.dataset.heldObjectAnchor = "fireboy-hands";
    return hands;
  }
  const halfY = objectHalfHeight(entry);
  const local = new THREE.Vector3(0.42, Math.max(0.78, halfY + 0.68), 0.74);
  document.body.dataset.heldObjectAnchor = "pet-offset";
  return agent.pet.group.localToWorld(local);
}

function rigHandHoldWorldPosition(agent) {
  const bones = agent?.rigBones || {};
  const left = bones.handL;
  const right = bones.handR;
  if (!left && !right) return null;
  const points = [];
  if (left) points.push(left.getWorldPosition(new THREE.Vector3()));
  if (right) points.push(right.getWorldPosition(new THREE.Vector3()));
  if (!points.length) return null;
  const center = points.reduce((acc, point) => acc.add(point), new THREE.Vector3()).multiplyScalar(1 / points.length);
  const forward = agentForwardVector(agent);
  return center.add(forward.multiplyScalar(0.18)).add(new THREE.Vector3(0, 0.04, 0));
}

function heldObjectDropPosition(agent, entry) {
  const forward = agentForwardVector(agent);
  const halfY = objectHalfHeight(entry);
  return clampObjectPosition(agent.pet.group.position.clone().add(forward.multiplyScalar(0.78)).setY(Math.max(halfY + 0.08, 0.32)), entry);
}

function objectHalfHeight(entry) {
  return Number(entry?.size?.y || entry?.radius || 0.42) * 0.5;
}

function agentForwardVector(agent) {
  const yaw = Number.isFinite(agent?.pet?.facingYaw) ? agent.pet.facingYaw : agent?.pet?.group?.rotation?.y || 0;
  return new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw)).normalize();
}

function directionLabelForAgent(agent, position) {
  const toTarget = position.clone ? position.clone() : new THREE.Vector3(position.x || 0, position.y || 0, position.z || 0);
  toTarget.sub(agent?.pet?.group?.position || new THREE.Vector3());
  toTarget.y = 0;
  if (toTarget.lengthSq() < 0.001) return "here";
  toTarget.normalize();
  const forward = agentForwardVector(agent);
  const right = new THREE.Vector3(forward.z, 0, -forward.x).normalize();
  const frontDot = forward.dot(toTarget);
  const sideDot = right.dot(toTarget);
  if (frontDot > 0.72) return "front";
  if (frontDot < -0.72) return "behind";
  return sideDot > 0 ? "right" : "left";
}

function setFacingToward(agent, vector) {
  if (!agent || !vector) return;
  const x = Number(vector.x || 0);
  const z = Number(vector.z || 0);
  if (Math.hypot(x, z) < 0.001) return;
  agent.pet.targetFacingYaw = Math.atan2(x, z);
}

function applySpell(agent, spell = {}) {
  const ops = Array.isArray(spell.ops) ? spell.ops.slice(0, 5) : [];
  if (!ops.length) return;
  for (const op of ops) {
    const targets = resolveTargets(op.targetId, agent);
    if (op.op === "impulse") applyImpulse(targets, op);
    else if (op.op === "freeze") applyFreeze(targets, op);
    else if (op.op === "scale") applyScale(targets, op);
    else if (op.op === "attract") applyAttract(targets, agent, op);
    else if (op.op === "spawn_particle") applyParticles(targets, agent, op);
    else if (op.op === "set_light") applyLight(op);
    else if (op.op === "nudge_pet") applyPetNudge(targets, agent, op);
  }
}

function resolveTargets(targetId, agent) {
  if (targetId === "self") return [{ type: "agent", agent }];
  if (targetId === "all-agents") return [...agents.values()].map((item) => ({ type: "agent", agent: item }));
  if (targetId === "all-toys" || targetId === "all-moving") {
    const selected = targetId === "all-moving"
      ? objects.filter((entry) => entry.body.velocity.length() > 0.35)
      : objects;
    return selected.map((entry) => ({ type: "object", entry }));
  }
  const object = objects.find((entry) => entry.id === targetId);
  if (object) return [{ type: "object", entry: object }];
  const otherAgent = agents.get(normalizeKind(targetId));
  if (otherAgent) return [{ type: "agent", agent: otherAgent }];
  const nearest = nearestObjectFor(agent);
  return nearest ? [{ type: "object", entry: nearest }] : [{ type: "agent", agent }];
}

function applyImpulse(targets, op) {
  const vec = op.vec || [0, 2.2, 0];
  const impulse = new CANNON.Vec3(Number(vec[0] || 0), Number(vec[1] || 0), Number(vec[2] || 0));
  for (const target of targets) {
    if (target.type === "object") {
      target.entry.body.applyImpulse(impulse, target.entry.body.position);
      target.entry.body.wakeUp();
    } else {
      target.agent.rig.nudge(impulse, 0.64);
    }
    effects.stars(targetPosition(target), colorNumber(op.color, PET_LOOKS[activeKind].power), 12);
  }
}

function applyFreeze(targets, op) {
  const now = performance.now();
  const duration = Number(op.durationMs || 1300);
  for (const target of targets) {
    if (target.type !== "object") {
      setPetEmotion(target.agent.pet, "sleepy");
      continue;
    }
    const entry = target.entry;
    room.frozenBodies.set(entry.id, { until: now + duration, position: entry.body.position.clone(), quaternion: entry.body.quaternion.clone() });
    entry.body.velocity.set(0, 0, 0);
    entry.body.angularVelocity.set(0, 0, 0);
  }
  dom.effectFlash.classList.add("on");
  setTimeout(() => dom.effectFlash.classList.remove("on"), Math.min(duration, 1400));
}

function applyScale(targets, op) {
  const factor = THREE.MathUtils.clamp(Number(op.factor || 1), 0.25, 2.25);
  const duration = Number(op.durationMs || 1200);
  for (const target of targets) {
    if (target.type === "agent") {
      target.agent.pet.targetScale = factor;
      setTimeout(() => {
        target.agent.pet.targetScale = 1;
      }, duration);
    } else {
      const mesh = target.entry.mesh;
      if (!mesh.userData.originalScale) mesh.userData.originalScale = mesh.scale.clone();
      mesh.scale.copy(mesh.userData.originalScale).multiplyScalar(factor);
      setTimeout(() => {
        if (mesh.userData.originalScale) mesh.scale.copy(mesh.userData.originalScale);
      }, duration);
    }
    effects.burst(targetPosition(target), colorNumber(op.color, PET_LOOKS[activeKind].power), 14, 0.72);
  }
}

function applyAttract(targets, agent, op) {
  const center = agent.pet.group.position;
  const strength = Number(op.strength ?? 0.5);
  const radius = Number(op.radius || 4);
  const all = targets.length ? targets : objects.map((entry) => ({ type: "object", entry }));
  for (const target of all) {
    const position = targetPosition(target);
    const distance = position.distanceTo(center);
    if (distance > radius) continue;
    const dir = new THREE.Vector3().subVectors(center, position).normalize().multiplyScalar(strength);
    const impulse = new CANNON.Vec3(dir.x, Math.abs(strength) * 0.45, dir.z);
    if (target.type === "object") target.entry.body.applyImpulse(impulse, target.entry.body.position);
    else if (target.agent !== agent) target.agent.rig.nudge(impulse, 0.5);
  }
  effects.ring(center.clone().add(new THREE.Vector3(0, 0.8, 0)), colorNumber(op.color, PET_LOOKS[agent.kind].power), Math.min(radius, 4), 1.0);
}

function applyParticles(targets, agent, op) {
  const selected = targets.length ? targets.slice(0, 8) : [{ type: "agent", agent }];
  for (const target of selected) {
    const position = targetPosition(target).add(new THREE.Vector3(0, target.type === "agent" ? 1.1 : 0.35, 0));
    effects.stars(position, colorNumber(op.color, PET_LOOKS[agent.kind].power), 14);
  }
}

function applyLight(op) {
  const light = room.lights.fillLight;
  const originalIntensity = light.intensity;
  const originalColor = light.color.clone();
  light.intensity = Number(op.intensity || 72);
  if (op.color) light.color.set(colorNumber(op.color, 0xffde71));
  setTimeout(() => {
    light.intensity = originalIntensity;
    light.color.copy(originalColor);
  }, Number(op.durationMs || 420));
}

function applyPetNudge(targets, agent, op) {
  const selected = targets.some((target) => target.type === "agent") ? targets : [{ type: "agent", agent }];
  const vec = op.vec || [0, 1.4, 0];
  const impulse = new CANNON.Vec3(Number(vec[0] || 0), Number(vec[1] || 0), Number(vec[2] || 0));
  for (const target of selected) {
    if (target.type === "agent") target.agent.rig.nudge(impulse, 0.72);
  }
}

function spellFromPower(power = {}, agent) {
  const targetId = power.targetId || nearestObjectFor(agent)?.id || "all-toys";
  return {
    spellName: power.name || "tiny improvisation",
    ops: [
      { op: "spawn_particle", targetId: "self", durationMs: 900 },
      { op: "impulse", targetId, vec: [0, Number(power.strength || 0.8) * 2.2, 0], durationMs: Number(power.durationMs || 900) },
    ],
  };
}

function maybeLaunchFireball(agent, action = {}) {
  const spellText = [
    action.power?.name,
    action.spell?.spellName,
    action.intent,
    action.speech,
  ].filter(Boolean).join(" ").toLowerCase();
  if (!agent || agent.kind !== "fire_boy" || !/(fireball|fire ball|comet|warm sparkle|whoosh)/.test(spellText)) return false;
  const opTargetId = Array.isArray(action.spell?.ops)
    ? action.spell.ops.find((op) => op.targetId && !["self", "all-agents"].includes(op.targetId))?.targetId
    : "";
  const targetId = action.power?.targetId || opTargetId || "";
  const target = objects.find((entry) => entry.id === targetId) || nearestObjectFor(agent);
  if (!target) return false;

  const start = agent.pet.group.position.clone().add(new THREE.Vector3(0, 1.18, 0.24));
  const end = bodyToVector(target.body.position).add(new THREE.Vector3(0, Math.max(0.28, Number(target.size?.y || 0.4) * 0.55), 0));
  effects.projectile(start, end, 0xff704d, () => {
    const impact = bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.34, 0));
    target.body.applyImpulse(new CANNON.Vec3(1.25, 1.6, -0.95), target.body.position);
    target.body.wakeUp();
    effects.ring(impact, 0xff704d, 1.0, 0.72);
    effects.burst(impact, 0xff9b45, 18, 1.05);
    recordForce({ kind: "fireball", objectId: target.id, impact: 0.72 });
  });
  recordInteraction({ kind: "fireball_projectile", pet: agent.kind, objectId: target.id });
  document.body.dataset.lastFireballTarget = target.id;
  return true;
}

function recordActionLoopMetrics(agent, action = {}, options = {}) {
  const roundTripMs = Number(action.debug?.clientRoundTripMs || 0);
  const serverLatencyMs = Number(action.debug?.serverLatencyMs || 0);
  const stateChanges = estimateStateChanges(action) + (options.projectileLaunched ? 2 : 0);
  const functionCalls = estimateStateFunctionCalls(action) + (options.projectileLaunched ? 1 : 0);
  const tokenRate = Number(action.debug?.tokensPerSecond || action.debug?.completionTokensPerSecond || 0);
  const label = `${roundTripMs ? `${Math.round(roundTripMs)}ms` : "local"} / ${stateChanges} ops`;
  lastLoopMetric = { label, state: "ok" };
  actionSequence += 1;
  document.body.dataset.actionSequence = String(actionSequence);
  document.body.dataset.lastActionLatencyMs = String(roundTripMs || serverLatencyMs || 0);
  document.body.dataset.lastServerLatencyMs = String(serverLatencyMs || 0);
  document.body.dataset.lastStateChanges = String(stateChanges);
  document.body.dataset.lastFunctionCalls = String(functionCalls);
  document.body.dataset.lastBrainPolicy = action.debug?.policy || "unknown";
  document.body.dataset.lastInteractionVerb = action.interaction?.verb || "";
  document.body.dataset.lastActionPet = agent?.kind || "";
  document.body.dataset.lastTokenRate = tokenRate ? tokenRate.toFixed(1) : "";
}

function estimateStateChanges(action = {}) {
  const spellOps = Array.isArray(action.spell?.ops) ? action.spell.ops.length : 0;
  return [
    action.speech,
    action.emotion,
    action.animation,
    action.blendshape && Object.keys(action.blendshape).length,
    action.interaction?.verb && action.interaction.verb !== "none",
    action.objectRecipe,
    action.sound,
    action.soundRecipe,
    action.newMemory,
  ].filter(Boolean).length + spellOps;
}

function estimateStateFunctionCalls(action = {}) {
  const spellOps = Array.isArray(action.spell?.ops) ? action.spell.ops.length : 0;
  return [
    "applyAgentAction",
    action.interaction?.verb && action.interaction.verb !== "none" ? "executeInteraction" : "",
    action.objectRecipe ? "applyObjectRecipe" : "",
    action.sound ? "audio.play" : "",
    action.speech ? "audio.speak" : "",
  ].filter(Boolean).length + spellOps;
}

function fallbackClientAction(agent) {
  return {
    pet: agent.kind,
    speech: "I made a tiny local sparkle.",
    emotion: "curious",
    animation: "bounce",
    intent: "client_fallback",
    spell: { spellName: "local sparkle", ops: [{ op: "spawn_particle", targetId: "self", durationMs: 900 }] },
    sound: "soft_pop",
  };
}

function collectSceneState(agent) {
  const petPos = agent.pet.group.position;
  return {
    pet: {
      kind: agent.kind,
      emotion: agent.pet.emotion,
      hovered: agent.pet.hovered,
      recentlyTouched: performance.now() - (agent.pet.lastPettedAt || 0) < 2500,
      needs: { ...agent.needs },
      balance: agent.rig.state(),
    },
    agents: [...agents.values()].filter((item) => item !== agent).map((item) => ({
      pet: item.kind,
      label: item.label,
      emotion: item.pet.emotion,
      lastIntent: item.lastIntent,
      distanceToPet: Number(item.pet.group.position.distanceTo(petPos).toFixed(2)),
      position: vectorPayload(item.pet.group.position),
    })),
    viewer: playerCameraVirtualTarget(agent)?.scene || null,
    objects: objects.map((entry) => {
      const pos = entry.body.position;
      const speed = entry.body.velocity.length();
      const distanceToPet = new THREE.Vector3(pos.x, pos.y, pos.z).distanceTo(petPos);
      return {
        id: entry.id,
        kind: entry.kind,
        name: entry.name || "",
        generated: Boolean(entry.generated),
        position: { x: Number(pos.x.toFixed(2)), y: Number(pos.y.toFixed(2)), z: Number(pos.z.toFixed(2)) },
        x: Number(pos.x.toFixed(2)),
        y: Number(pos.y.toFixed(2)),
        z: Number(pos.z.toFixed(2)),
        speed: Number(speed.toFixed(2)),
        distanceToPet: Number(distanceToPet.toFixed(2)),
        moving: speed > 0.5,
        affordances: Array.isArray(entry.affordances) ? entry.affordances.slice(0, 6) : [],
        tags: sceneTagsForEntry(entry),
        nutrition: Number(entry.nutrition || 0),
        readable: Boolean(entry.readable),
        comfort: Number(entry.comfort || 0),
        social: Number(entry.social || 0),
      };
    }).concat(virtualSceneObjects(agent)),
  };
}

function virtualSceneObjects(agent) {
  const target = playerCameraVirtualTarget(agent);
  return target ? [target.scene] : [];
}

function virtualTargetEntries(agent) {
  const target = playerCameraVirtualTarget(agent);
  return target ? [target.entry] : [];
}

function virtualTargetEntryForId(agent, id) {
  const cleanId = String(id || "");
  return virtualTargetEntries(agent).find((entry) => entry.id === cleanId) || null;
}

function playerCameraVirtualTarget(agent) {
  if (!agent?.pet?.group) return null;
  const position = playerCameraFloorTarget();
  const distance = position.distanceTo(agent.pet.group.position);
  const payload = vectorPayload(position);
  const affordances = ["go_to", "follow", "look_at"];
  const tags = ["me", "camera", "viewer", "player", "user", "here"];
  const sceneTarget = {
    id: "player-camera",
    kind: "viewer",
    name: "player camera",
    virtual: true,
    position: payload,
    x: payload.x,
    y: payload.y,
    z: payload.z,
    speed: 0,
    distanceToPet: Number(distance.toFixed(2)),
    moving: false,
    affordances,
    tags,
  };
  return {
    scene: sceneTarget,
    entry: {
      ...sceneTarget,
      radius: 0.48,
      virtualDirect: true,
      body: { position: { x: payload.x, y: payload.y, z: payload.z } },
    },
  };
}

function playerCameraFloorTarget() {
  const target = camera.position.clone();
  target.y = 0.06;
  return clampAgentPosition(target);
}

function detectObjects(agent) {
  const origin = agent.pet.group.position;
  return objects.concat(virtualTargetEntries(agent))
    .map((entry) => {
      const pos = bodyToVector(entry.body.position);
      const speed = entry.body.velocity?.length?.() || 0;
      return {
        id: entry.id,
        kind: entry.kind,
        name: entry.name || "",
        virtual: Boolean(entry.virtual),
        position: vectorPayload(pos),
        distance: Number(pos.distanceTo(origin).toFixed(2)),
        direction: directionLabelForAgent(agent, pos),
        moving: speed > 0.5,
        affordances: Array.isArray(entry.affordances) ? entry.affordances.slice(0, 4) : [],
        tags: sceneTagsForEntry(entry).slice(0, 8),
      };
    })
    .filter((item) => item.distance < (item.virtual ? 9.0 : 5.2))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 10);
}

function sceneTagsForEntry(entry = {}) {
  const base = Array.isArray(entry.tags) ? entry.tags.map((tag) => String(tag || "")) : [];
  const inferred = [...targetTermsForEntry(entry)].filter((term) => term.length >= 3 && term !== String(entry.id || "").toLowerCase());
  return [...new Set([...base, ...inferred])].slice(0, 16);
}

function compactBrainTrace(payload, action, policy) {
  const detected = Array.isArray(payload.detectedObjects) ? payload.detectedObjects : [];
  const memories = Array.isArray(payload.memories) ? payload.memories : [];
  const forces = Array.isArray(payload.forces) ? payload.forces : [];
  const recentInteractions = Array.isArray(payload.interactions) ? payload.interactions : [];
  const latestForce = forces.length ? forces[forces.length - 1] : null;
  const latestInteraction = recentInteractions.length ? recentInteractions[recentInteractions.length - 1] : null;
  return {
    at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    policy: policy || action?.debug?.policy || "unknown",
    brain: summarizeTraceBrain(payload, action),
    text: shortTraceText(payload.message || "ambient room loop", 88),
    vision: summarizeTraceVision(payload.cameraFrameSource, detected),
    sound: summarizeTraceAudio(payload.audio),
    force: summarizeTraceForce(latestForce, latestInteraction),
    memory: summarizeTraceMemory(memories),
    action: summarizeTraceAction(action),
    model: summarizeTraceModel(action),
    vla: summarizeTraceVla(action),
    json: traceActionJson(action, policy),
  };
}

function summarizeTraceModel(action) {
  if (!action) return "waiting";
  const debug = action.debug || {};
  if (debug.vlaRouter) {
    const router = debug.vlaRouter;
    return [
      "Modal MiniCPM-V VLA",
      router.skill ? `skill:${router.skill}` : "",
      router.neuralSkill ? `neural:${router.neuralSkill}` : "",
      router.device ? `device:${router.device}` : "",
      router.latencyMs ? `${router.latencyMs}ms` : "",
    ].filter(Boolean).join(" | ");
  }
  const pieces = [
    debug.provider || debug.policy || "policy",
    debug.model ? shortRuntimeLabel(debug.model) : "",
    debug.modelLatencyMs ? `${debug.modelLatencyMs}ms` : "",
    debug.tokensPerSecond ? `${debug.tokensPerSecond} tok/s` : "",
    debug.visionMode ? `mode:${debug.visionMode}` : "",
    debug.visionImageRejected ? "image:rejected" : "",
    debug.visionImageError ? `image:${shortTraceText(debug.visionImageError, 92)}` : "",
    debug.reason ? `reason:${debug.reason}` : "",
    debug.modalLastError ? `error:${shortTraceText(debug.modalLastError, 92)}` : "",
    debug.visionLastError ? `vision:${shortTraceText(debug.visionLastError, 92)}` : "",
  ];
  return pieces.filter(Boolean).join(" | ") || "none";
}

function summarizeTraceBrain(payload, action) {
  if (action?.debug?.vlaRouter) {
    const actual = action?.debug?.provider || "local_mujoco";
    return `MiniCPM-V VLA -> ${actual}`;
  }
  const requested = action?.debug?.requestedBrainMode || payload.brainMode || selectedBrainMode || "auto";
  const actual = action?.debug?.provider || action?.debug?.policy || "pending";
  return `${BRAIN_MODE_LABELS[requested] || requested} -> ${actual}`;
}

function summarizeTraceVla(action) {
  const router = action?.debug?.vlaRouter;
  if (!router) return "";
  const params = router.params || {};
  const target = Number.isFinite(Number(params.target_x)) && Number.isFinite(Number(params.target_y))
    ? `target:${Number(params.target_x).toFixed(2)},${Number(params.target_y).toFixed(2)}`
    : "";
  return [
    router.policyKind || "minicpm_vla",
    router.skill ? `skill:${router.skill}` : "",
    router.neuralSkill ? `neural:${router.neuralSkill}` : "",
    router.device ? `device:${router.device}` : "",
    router.dispatch ? `dispatch:${router.dispatch}` : "",
    target,
  ].filter(Boolean).join(" | ");
}

function summarizeTraceVision(source, detected) {
  if (!detected.length) return `${source || "view"}: soft floor, quiet walls`;
  const objectsText = detected
    .slice(0, 4)
    .map((item) => `${item.kind}${item.moving ? "/moving" : ""}@${item.distance ?? "?"}m${item.direction ? ` ${item.direction}` : ""}`)
    .join(", ");
  return `${source || "view"}: ${objectsText}`;
}

function seenItemLabel(item) {
  const label = item.kind === "viewer" ? "viewer" : (item.kind || item.id || "object");
  const distance = Number.isFinite(Number(item.distance)) ? `${Number(item.distance).toFixed(1)}m` : "";
  const direction = item.direction || "";
  const moving = item.moving ? " moving" : "";
  return [label, distance, direction].filter(Boolean).join(" ") + moving;
}

function summarizeTraceAudio(summary = {}) {
  const input = summary.input || {};
  const output = summary.output || {};
  const source = summary.source || (input.active ? "microphone" : "room-output");
  const inputPeak = Number(input.peak || 0).toFixed(2);
  const outputPeak = Number(output.peak || 0).toFixed(2);
  const peak = Number(summary.peak || Math.max(Number(input.peak || 0), Number(output.peak || 0))).toFixed(2);
  const mic = input.active ? " mic:on" : " mic:off";
  return `${source} peak:${peak} in:${inputPeak} out:${outputPeak}${mic}`;
}

function summarizeTraceForce(force, interaction) {
  const forceText = force
    ? `${force.kind || "force"} ${force.objectId || ""} impact:${Number(force.impact || 0).toFixed(2)}`.trim()
    : "";
  const interactionText = interaction
    ? `${interaction.kind || "interaction"} ${interaction.objectId || interaction.partnerPet || ""}`.trim()
    : "";
  return [forceText, interactionText].filter(Boolean).join(" | ") || "none";
}

function summarizeTraceMemory(memories) {
  if (!memories.length) return "none";
  return memories
    .slice(-2)
    .map((item) => shortTraceText(`${item.concept || "lesson"}: ${item.meaning || ""}`, 58))
    .join(" | ");
}

function summarizeTraceAction(action) {
  if (!action) return "waiting for response";
  const spell = action.spell?.spellName || action.power?.name || "";
  const ops = Array.isArray(action.spell?.ops)
    ? action.spell.ops.slice(0, 3).map((op) => op.op || "op").join("+")
    : "";
  const objectName = action.objectRecipe?.name || "";
  const soundName = action.soundRecipe?.label || action.sound || "";
  return [
    action.intent || action.emotion || "",
    action.interaction?.targetId ? `target:${action.interaction.targetId}` : "",
    spell ? `spell:${spell}` : "",
    ops ? `ops:${ops}` : "",
    objectName ? `object:${objectName}` : "",
    soundName ? `sound:${soundName}` : "",
  ].filter(Boolean).join(" | ") || "no-op";
}

function traceActionJson(action, policy) {
  if (!action) return JSON.stringify({ policy, status: "pending" });
  return JSON.stringify({
    policy: action.debug?.policy || policy || "unknown",
    provider: action.debug?.provider || null,
    requestedBrainMode: action.debug?.requestedBrainMode || null,
    speech: shortTraceText(action.speech || "", 64),
    interaction: action.interaction?.verb || null,
    targetId: action.interaction?.targetId || action.power?.targetId || null,
    power: action.power?.name || null,
    animation: action.animation || null,
    spell: action.spell?.spellName || action.power?.name || null,
    ops: Array.isArray(action.spell?.ops) ? action.spell.ops.slice(0, 4).map((op) => op.op || "op") : [],
    objectRecipe: action.objectRecipe?.name || null,
    soundRecipe: action.soundRecipe?.label || null,
    errorReason: action.debug?.reason || null,
    modalLastError: action.debug?.modalLastError || null,
    modalLastErrorType: action.debug?.modalLastErrorType || null,
    modalImageSent: action.debug?.modalImageSent ?? null,
    visionMode: action.debug?.visionMode || null,
    visionImageRejected: action.debug?.visionImageRejected || null,
    visionImageError: action.debug?.visionImageError || null,
    visionLastError: action.debug?.visionLastError || null,
    visionLastErrorType: action.debug?.visionLastErrorType || null,
    visionImageBytes: action.debug?.visionImageBytes || null,
    memory: action.newMemory?.concept || action.debug?.memoryApplied || null,
    vision: action.debug?.visionApplied || null,
    latencyMs: action.debug?.clientRoundTripMs || action.debug?.serverLatencyMs || null,
    modelLatencyMs: action.debug?.modelLatencyMs || null,
    promptTokens: action.debug?.promptTokens || null,
    completionTokens: action.debug?.completionTokens || null,
    tokensPerSecond: action.debug?.tokensPerSecond || null,
    functionCalls: action.debug?.functionCalls || null,
    stateUpdatesRequested: action.debug?.stateUpdatesRequested || null,
    commandCoercion: action.debug?.commandCoercion || null,
    groundedTargetId: action.debug?.groundedTargetId || null,
    modalEvents: action.debug?.modalEvents || null,
    vlaRouter: action.debug?.vlaRouter || null,
    vlaRouterUrl: action.debug?.vlaRouterUrl || null,
    vlaRouterDispatchMessage: action.debug?.vlaRouterDispatchMessage || null,
    mujocoPolicy: action.debug?.mujocoPolicy || null,
  }, null, 2);
}

function showMujocoPolicyRollout(action = {}) {
  const policy = action.debug?.mujocoPolicy;
  const gifUrl = policy?.gifUrl;
  const mp4Url = policy?.mp4Url || policy?.registryProofMp4Url || "";
  if (!mp4Url && !gifUrl) return;
  let panel = document.getElementById("mujocoPolicyPanel");
  if (!panel) {
    panel = document.createElement("aside");
    panel.id = "mujocoPolicyPanel";
    panel.style.position = "fixed";
    panel.style.right = "16px";
    panel.style.bottom = "16px";
    panel.style.width = "min(360px, calc(100vw - 32px))";
    panel.style.zIndex = "60";
    panel.style.padding = "10px";
    panel.style.border = "1px solid rgba(255,255,255,0.52)";
    panel.style.borderRadius = "8px";
    panel.style.background = "rgba(22, 24, 28, 0.82)";
    panel.style.boxShadow = "0 14px 34px rgba(0,0,0,0.28)";
    panel.style.backdropFilter = "blur(14px)";
    panel.innerHTML = `
      <button type="button" aria-label="Close MuJoCo rollout" style="position:absolute;right:8px;top:6px;border:0;background:rgba(255,255,255,0.14);color:white;border-radius:999px;width:24px;height:24px;cursor:pointer;">×</button>
      <div style="font:600 12px/1.2 system-ui,sans-serif;color:#fff;margin:0 28px 8px 0;">MuJoCo policy rollout</div>
      <div data-mujoco-media></div>
      <div data-mujoco-status style="font:500 11px/1.35 system-ui,sans-serif;color:rgba(255,255,255,0.76);margin-top:7px;"></div>
    `;
    panel.querySelector("button")?.addEventListener("click", () => panel.remove());
    document.body.appendChild(panel);
  }
  const media = panel.querySelector("[data-mujoco-media]");
  if (media) {
    const src = `${mp4Url || gifUrl}?t=${Date.now()}`;
    media.innerHTML = mp4Url
      ? `<video src="${src}" aria-label="MuJoCo learned policy rollout" autoplay loop muted playsinline controls style="display:block;width:100%;border-radius:6px;background:#111;aspect-ratio:4/3;object-fit:contain;"></video>`
      : `<img src="${src}" alt="MuJoCo learned policy rollout" style="display:block;width:100%;border-radius:6px;background:#111;aspect-ratio:4/3;object-fit:contain;" />`;
  }
  const status = panel.querySelector("[data-mujoco-status]");
  if (status) {
    const source = policy.mediaSource === "registry_proof_mp4" ? "registry MP4 proof" : "runtime rollout";
    status.textContent = policy.success
      ? `learned control passed · ${source} · grasped ${String(Boolean(policy.grasped))} · eaten ${String(Boolean(policy.eaten))}`
      : `policy unavailable · ${shortTraceText(policy.reason || "fallback used", 80)}`;
  }
  panel.hidden = false;
}

function hideMujocoPolicyRollout(reason = "hidden") {
  const panel = document.getElementById("mujocoPolicyPanel");
  if (panel) panel.remove();
  document.body.dataset.mujocoPolicyPanel = reason;
}

function shortTraceText(value, max = 72) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, Math.max(0, max - 1))}...` : text;
}

function updateAgentNeeds(dt) {
  for (const agent of agents.values()) {
    agent.needs.hunger = clampNeed(agent.needs.hunger + dt * 0.12);
    agent.needs.curiosity = clampNeed(agent.needs.curiosity + dt * 0.12);
    agent.needs.energy = clampNeed(agent.needs.energy - dt * 0.04);
    agent.needs.social = clampNeed(agent.needs.social + dt * 0.03);
    agent.needs.playfulness = clampNeed((agent.needs.playfulness ?? 50) - dt * 0.025);
    enforceEnergyState(agent);
  }
}

function enforceEnergyState(agent) {
  if (!IS_V3_MODE || !agent || agent.inFlight) return;
  const energy = Number(agent.needs.energy || 0);
  if (energy <= 10 && agent.energyState !== "exhausted") {
    agent.energyState = "exhausted";
    cancelAgentActions(agent);
    runSitCombo(agent, { durationMs: 2800 });
    showToast("Fire Boy is exhausted and sitting.");
    return;
  }
  if (energy < 25 && agent.energyState === "ok") {
    agent.energyState = "low";
    performIdleStop(agent, "energy_low", { quiet: true });
    showToast("Fire Boy is low energy. Feed him grapes or berries.");
    return;
  }
  if (energy > 32 && agent.energyState !== "ok") {
    agent.energyState = "ok";
  }
}

function renderPetMeters(agent = activeAgent()) {
  if (!dom.petMeters || !agent) return;
  const hunger = clampNeed(agent.needs.hunger);
  const energy = clampNeed(agent.needs.energy);
  const playfulness = clampNeed(agent.needs.playfulness ?? 50);
  const rows = [
    ["Hunger", hunger, "hunger", hunger > 70 ? "hungry" : hunger < 25 ? "full" : "snacky"],
    ["Energy", energy, "energy", energy < 25 ? "low" : energy > 72 ? "charged" : "steady"],
    ["Playfulness", playfulness, "playfulness", playfulness > 72 ? "zoomy" : playfulness < 28 ? "calm" : "ready"],
  ];
  dom.petMeters.innerHTML = rows.map(([label, value, kind, state]) => `
    <div class="pet-meter">
      <div class="pet-meter-row"><span>${label}</span><span>${Math.round(value)}% · ${state}</span></div>
      <div class="pet-meter-track"><div class="pet-meter-fill ${kind}" style="width:${value}%"></div></div>
    </div>
  `).join("");
  document.body.dataset.petHunger = String(Math.round(hunger));
  document.body.dataset.petEnergy = String(Math.round(energy));
  document.body.dataset.petPlayfulness = String(Math.round(playfulness));
}

function updateAgentPanel() {
  const agent = activeAgent();
  const seen = detectObjects(agent);
  dom.perceptionTitle.textContent = `${agent.label} sees`;
  dom.perceptionReadout.textContent = seen.length
    ? seen.slice(0, 4).map(seenItemLabel).join(", ")
    : "soft floor, quiet walls";
  renderPetMeters(agent);
  const policy = modelStatus.enabled || modelStatus.visionEnabled
    ? `${providerPrefix()}${modelStatus.model || "model"}${modelStatus.visionEnabled ? " + vision" : ""}`
    : policyFallbackLabel();
  const rigLabel = agent.rigStatus === "ready" ? " + rig mesh" : agent.rigStatus === "missing" ? " + rig missing" : "";
  dom.agentReadout.textContent = `${agent.label}: ${agent.lastSpell || agent.lastIntent}. ${policy}${rigLabel}`;
  renderRuntimeStack(agent);
  renderJudgeScorecard();
  renderAiEvidence();
  renderAgentVisionBoard();
  renderBrainTrace(agent);
  renderMemories(agent);
}

function renderRuntimeStack(agent = activeAgent()) {
  if (!dom.modelMatrix) return;
  const rigReady = [...agents.values()].filter((item) => item.rigStatus === "ready").length;
  const recentForce = forceEvents.some((event) => Date.now() - event.at < 5500);
  const balance = agent.rig.state();
  const input = audio.inputSummary?.() || {};
  const output = audio.outputSummary?.() || {};
  const brain = brainRuntimeState();
  const loop = loopRuntimeState();
  const vision = visionRuntimeState();
  const audioState = {
    label: input.active ? `mic ${Number(input.peak || 0).toFixed(2)}` : output.active ? "voice+recipe" : "audio locked",
    state: input.active || output.active ? "ok" : "warn",
  };
  const social = socialRuntimeState();
  const dialogue = dialogueRuntimeState();
  const rescue = rescueRuntimeState();
  const learn = learnRuntimeState(agent);
  const train = trainingRuntimeState();
  const council = councilRuntimeState();
  const motor = motorRuntimeState();
  const judge = judgeRuntimeState();
  const ai = aiEvidenceRuntimeState();
  const force = {
    label: recentForce ? `impact ${balance.tiltDeg}deg` : `live ${balance.tiltDeg}deg`,
    state: recentForce ? "ok" : "warn",
  };
  const recycle = recycleRuntimeState();
  const rigs = {
    label: `${rigReady}/${AGENT_SPECS.length} meshes`,
    state: rigReady === AGENT_SPECS.length ? "ok" : rigReady > 0 ? "warn" : "off",
  };
  const cells = [
    ["Brain", brain.label, brain.state],
    ["Loop", loop.label, loop.state],
    ["AI", ai.label, ai.state],
    ["Vision", vision.label, vision.state],
    ["Audio", audioState.label, audioState.state],
    ["Learn", learn.label, learn.state],
    ["Train", train.label, train.state],
    [IS_V3_MODE ? "Agent View" : "Council", council.label, council.state],
    ["Motor", motor.label, motor.state],
    ["Social", social.label, social.state],
    ["Dialogue", dialogue.label, dialogue.state],
    ["Force", force.label, force.state],
    ["Rescue", rescue.label, rescue.state],
    ["Recycle", recycle.label, recycle.state],
    ["Judge", judge.label, judge.state],
    ["Rigs", rigs.label, rigs.state],
  ];
  if (dom.agentLoopSummary) {
    dom.agentLoopSummary.textContent = `${brain.label} / ${loop.label}`;
  }
  dom.modelMatrix.innerHTML = "";
  for (const [label, value, state] of cells) {
    const chip = document.createElement("div");
    chip.className = `runtime-chip ${state}`;
    const strong = document.createElement("strong");
    strong.textContent = label;
    const span = document.createElement("span");
    span.textContent = value;
    chip.append(strong, span);
    dom.modelMatrix.appendChild(chip);
  }
  document.body.dataset.runtimeStackReady = "true";
  document.body.dataset.brainRuntime = brain.label;
  document.body.dataset.loopRuntime = loop.label;
  document.body.dataset.aiRuntime = ai.label;
  document.body.dataset.visionRuntime = vision.label;
  document.body.dataset.audioRuntime = audioState.label;
  document.body.dataset.learnRuntime = learn.label;
  document.body.dataset.trainingRuntime = train.label;
  document.body.dataset.memoryCount = String(agent.memories?.length || 0);
  document.body.dataset.councilRuntime = council.label;
  document.body.dataset.motorRuntime = motor.label;
  document.body.dataset.socialRuntime = social.label;
  document.body.dataset.dialogueRuntime = dialogue.label;
  document.body.dataset.forceRuntime = force.label;
  document.body.dataset.rescueRuntime = rescue.label;
  document.body.dataset.recycleRuntime = recycle.label;
  document.body.dataset.judgeRuntime = judge.label;
  document.body.dataset.rigRuntime = rigs.label;
}

function brainRuntimeState() {
  if (modelStatus.vlaRouter?.enabled) {
    const loaded = modelStatus.vlaRouter?.health?.model_loaded ? "warm" : "cold";
    return { label: `Modal MiniCPM-V VLA ${loaded}`, state: modelStatus.vlaRouter?.healthOk ? "ok" : "warn" };
  }
  if (selectedBrainMode === "ollama-vision") {
    const label = `Ollama MiniCPM-V ${modelStatus.localOllamaVisionModel || ""}`;
    return { label: shortRuntimeLabel(label), state: brainModeAvailable("ollama-vision") ? "ok" : "warn" };
  }
  if (selectedBrainMode === "ollama-text") {
    const label = `Ollama MiniCPM5 ${modelStatus.localOllamaTextModel || ""}`;
    return { label: shortRuntimeLabel(label), state: brainModeAvailable("ollama-text") ? "ok" : "warn" };
  }
  if (selectedBrainMode === "modal" && !brainModeAvailable("modal")) {
    return { label: "Modal unavailable", state: "warn" };
  }
  if (modelStatus.modalOmniEnabled) {
    return { label: shortRuntimeLabel(`Modal MiniCPM-o ${modelStatus.modalOmniModel || modelStatus.model || ""}`), state: "ok" };
  }
  if (modelStatus.modalOmniRequested && !modelStatus.modalOmniConfigured) {
    return { label: "Modal URL missing", state: "warn" };
  }
  if (modelStatus.visionActionEnabled) {
    return { label: shortRuntimeLabel(`MiniCPM-V ${modelStatus.visionModel || modelStatus.model || ""}`), state: "ok" };
  }
  if (modelStatus.enabled) {
    return { label: shortRuntimeLabel(`${modelStatus.provider || modelStatus.mode || "model"} ${modelStatus.model || ""}`), state: "ok" };
  }
  if (modelStatus.visionActionConfigured && modelStatus.visionAuthRequired && !modelStatus.visionAuthConfigured) {
    return { label: "MiniCPM secret missing", state: "warn" };
  }
  if (modelStatus.visionActionConfigured && !modelStatus.visionActionEnabled) {
    return { label: "MiniCPM disconnected", state: "warn" };
  }
  if (modelStatus.configured && modelStatus.authRequired && !modelStatus.authConfigured) {
    return { label: "secret missing", state: "warn" };
  }
  if (modelStatus.configured && !modelStatus.enabled) {
    return { label: "endpoint asleep", state: "warn" };
  }
  if (modelStatus.fallbackPolicy === "trace_retrieval+heuristic") {
    return { label: "trace policy", state: "ok" };
  }
  return { label: "fallback only", state: "warn" };
}

function loopRuntimeState() {
  return lastLoopMetric;
}

function visionRuntimeState() {
  const applied = document.body.dataset.visionApplied || "";
  if (applied) {
    return { label: `used ${shortRuntimeLabel(applied)}`, state: "ok" };
  }
  if (modelStatus.visionEnabled) {
    return { label: shortRuntimeLabel(`${modelStatus.visionProvider || modelStatus.visionMode || "vision"} ${modelStatus.visionModel || ""}`), state: "ok" };
  }
  if (modelStatus.visionConfigured && modelStatus.visionAuthRequired && !modelStatus.visionAuthConfigured) {
    return { label: "secret missing", state: "warn" };
  }
  if (modelStatus.visionConfigured && !modelStatus.visionEnabled) {
    return { label: "endpoint asleep", state: "warn" };
  }
  return { label: "camera frame", state: "ok" };
}

function shortRuntimeLabel(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > 26 ? `${text.slice(0, 25)}...` : text || "unknown";
}

function socialRuntimeState() {
  if (IS_V3_MODE) return { label: "single pet", state: "ok" };
  const latest = [...interactions]
    .reverse()
    .find((event) => event.partnerPet);
  if (!latest) return { label: "waiting", state: "warn" };
  const pet = AGENT_SPECS.find((item) => item.kind === latest.pet)?.label || latest.pet;
  const partner = AGENT_SPECS.find((item) => item.kind === latest.partnerPet)?.label || latest.partnerPet;
  return { label: `${pet} ${latest.kind} ${partner}`, state: "ok" };
}

function councilRuntimeState() {
  const count = councilVisionAgents.size;
  if (IS_V3_MODE) return { label: count > 0 ? "Fire Boy view" : "agent view", state: count > 0 ? "ok" : "warn" };
  if (count > 0) return { label: `${count}/${AGENT_SPECS.length} agent views`, state: count >= AGENT_SPECS.length ? "ok" : "warn" };
  return { label: "waiting", state: "warn" };
}

function dialogueRuntimeState() {
  if (IS_V3_MODE && audio.voiceEnabled) return { label: "baby voice", state: "ok" };
  if (dialogueTurns > 0) return { label: `${dialogueTurns} replies`, state: "ok" };
  return { label: "waiting", state: "warn" };
}

function rescueRuntimeState() {
  if (rescueTurns > 0) return { label: `${rescueTurns} assists`, state: "ok" };
  return { label: "waiting", state: "warn" };
}

function recycleRuntimeState() {
  const score = recycledWasteIds.size;
  const total = RECYCLABLE_WASTE_IDS.length;
  return { label: `${score}/${total} sorted`, state: score >= total ? "ok" : score > 0 ? "ok" : "warn" };
}

function learnRuntimeState(agent) {
  const memoryCount = agent.memories?.length || 0;
  const applied = document.body.dataset.memoryApplied || "";
  if (applied) return { label: `used ${shortRuntimeLabel(applied)}`, state: "ok" };
  if (memoryCount > 0) return { label: `${memoryCount} lessons`, state: "ok" };
  return { label: "no lessons", state: "warn" };
}

function trainingRuntimeState() {
  const rows = Number(trainingStatus.usableRows || 0);
  const minRows = Number(trainingStatus.minRows || 20);
  if (trainingStatus.ready) return { label: `${rows} SFT rows`, state: "ok" };
  if (rows > 0) return { label: `${rows}/${minRows} rows`, state: "warn" };
  return { label: trainingStatus.exists ? "warming" : "no traces", state: "warn" };
}

function motorRuntimeState() {
  if (lowLevelActions > 0) return { label: `${lowLevelActions} pulses`, state: "ok" };
  return { label: autoplay ? "watching" : "paused", state: autoplay ? "warn" : "off" };
}

function judgeRuntimeState() {
  const checks = combinedJudgeChecks();
  const required = checks.filter((check) => check.required !== false);
  const requiredOk = required.filter((check) => check.state === "ok").length;
  const ready = required.length > 0 && requiredOk === required.length;
  return {
    label: required.length ? `${requiredOk}/${required.length} required` : "checking",
    state: ready ? "ok" : "warn",
  };
}

function aiEvidenceRuntimeState() {
  const score = aiEvidence.score || {};
  const ready = Boolean(score.ready);
  const requiredOk = Number(score.requiredOk || 0);
  const requiredTotal = Number(score.requiredTotal || 0);
  if (requiredTotal > 0) return { label: `${requiredOk}/${requiredTotal} evidence`, state: ready ? "ok" : "warn" };
  return { label: "checking", state: "warn" };
}

function combinedJudgeChecks() {
  const serverChecks = Array.isArray(judgeStatus.checks)
    ? judgeStatus.checks.map(normalizeJudgeCheck)
    : [];
  return [...clientJudgeChecks(), ...serverChecks];
}

function clientJudgeChecks() {
  const rigReady = [...agents.values()].filter((agent) => agent.rigStatus === "ready").length;
  const visionRows = Number(document.body.dataset.visionBoardAgents || 0);
  const councilCount = councilVisionAgents.size;
  const generatedCount = objects.filter((entry) => entry.generated).length;
  const recycleScore = recycledWasteIds.size;
  const learningScore = Number(document.body.dataset.learningScore || 0);
  const forceReady = IS_V3_MODE
    ? forceEvents.some((event) => String(event.objectId || "").startsWith("fire_boy"))
    : rescueTurns > 0;
  const dialogueReady = IS_V3_MODE ? audio.voiceEnabled : dialogueTurns > 0;
  const demoReady = learningScore > 0
    && councilCount >= AGENT_SPECS.length
    && generatedCount > 0
    && recycleScore > 0
    && dialogueReady
    && forceReady;

  return [
    normalizeJudgeCheck({
      id: "live_demo_proof",
      label: "Live demo proof",
      state: demoReady ? "ok" : "warn",
      detail: `learn ${learningScore}, vision ${councilCount}/${AGENT_SPECS.length}, force ${forceReady ? 1 : 0}, voice ${dialogueReady ? 1 : 0}, object ${generatedCount}, recycle ${recycleScore}/${RECYCLABLE_WASTE_IDS.length}`,
      category: "browser",
    }),
    normalizeJudgeCheck({
      id: "live_vision_board",
      label: IS_V3_MODE ? "Fire Boy view board" : "Agent view board",
      state: visionRows >= AGENT_SPECS.length ? "ok" : "warn",
      detail: `${visionRows}/${AGENT_SPECS.length} agents reporting local perception.`,
      category: "browser",
    }),
    normalizeJudgeCheck({
      id: "live_motor_loop",
      label: "Low-level motor",
      state: lowLevelActions > 0 ? "ok" : autoplay ? "warn" : "off",
      detail: lowLevelActions > 0 ? `${lowLevelActions} local perception-action pulses.` : "Waiting for autoplay motor pulses.",
      category: "browser",
    }),
    normalizeJudgeCheck({
      id: "live_force_recycle",
      label: "Force and recycling",
      state: forceReady && recycleScore > 0 ? "ok" : "warn",
      detail: IS_V3_MODE
        ? `${forceReady ? 1 : 0} Fire Boy force events; ${recycleScore}/${RECYCLABLE_WASTE_IDS.length} waste sorted.`
        : `${rescueTurns} rescue assists; ${recycleScore}/${RECYCLABLE_WASTE_IDS.length} waste sorted.`,
      category: "browser",
    }),
    normalizeJudgeCheck({
      id: "live_rig_runtime",
      label: "Runtime rig load",
      state: rigReady >= AGENT_SPECS.length ? "ok" : rigReady > 0 ? "warn" : "off",
      detail: `${rigReady}/${AGENT_SPECS.length} generated rig meshes loaded.`,
      category: "browser",
    }),
  ];
}

function normalizeJudgeCheck(check) {
  const state = ["ok", "warn", "off"].includes(check?.state) ? check.state : "warn";
  return {
    id: String(check?.id || "check"),
    label: String(check?.label || "Check"),
    state,
    detail: String(check?.detail || ""),
    category: String(check?.category || "runtime"),
    required: check?.required !== false,
  };
}

function renderJudgeScorecard(force = false) {
  if (!dom.judgeScorecard) return;
  const now = performance.now();
  if (!force && dom.judgeScorecard.childElementCount && now - lastJudgeRender < 900) return;
  lastJudgeRender = now;

  const checks = combinedJudgeChecks();
  const required = checks.filter((check) => check.required !== false);
  const ok = checks.filter((check) => check.state === "ok").length;
  const warn = checks.filter((check) => check.state === "warn").length;
  const requiredOk = required.filter((check) => check.state === "ok").length;
  const requiredReady = required.length > 0 && requiredOk === required.length;
  const demoReady = checks.find((check) => check.id === "live_demo_proof")?.state === "ok";

  document.body.dataset.judgeScore = `${ok}/${checks.length}`;
  document.body.dataset.judgeWarnings = String(warn);
  document.body.dataset.judgeRequiredScore = `${requiredOk}/${required.length}`;
  document.body.dataset.judgeReady = String(requiredReady);
  document.body.dataset.judgeDemoReady = String(demoReady);
  document.body.dataset.judgeRows = String(checks.length);

  dom.judgeScorecard.innerHTML = "";
  const head = document.createElement("div");
  head.className = "judge-score-head";
  const title = document.createElement("strong");
  title.textContent = requiredReady ? "Required checks ready" : "Evidence warming";
  const score = document.createElement("span");
  score.textContent = `${requiredOk}/${required.length} required`;
  head.append(title, score);
  dom.judgeScorecard.appendChild(head);

  for (const check of checks.slice(0, 14)) {
    const row = document.createElement("div");
    row.className = `judge-row ${check.state}`;
    row.dataset.check = check.id;
    row.dataset.state = check.state;

    const dot = document.createElement("span");
    dot.className = "judge-dot";
    const main = document.createElement("div");
    main.className = "judge-main";
    const label = document.createElement("div");
    label.className = "judge-label";
    label.textContent = check.label;
    const detail = document.createElement("div");
    detail.className = "judge-detail";
    detail.textContent = shortTraceText(check.detail, 112);

    main.append(label, detail);
    row.append(dot, main);
    dom.judgeScorecard.appendChild(row);
  }
}

function renderAiEvidence(force = false) {
  if (!dom.aiEvidence) return;
  const score = aiEvidence.score || {};
  const metrics = aiEvidence.metrics || {};
  const requiredOk = Number(score.requiredOk || 0);
  const requiredTotal = Number(score.requiredTotal || 0);
  const ready = Boolean(score.ready);

  document.body.dataset.aiEvidenceScore = `${Number(score.ok || 0)}/${Number(score.total || 0)}`;
  document.body.dataset.aiEvidenceRequiredScore = `${requiredOk}/${requiredTotal}`;
  document.body.dataset.aiEvidenceReady = String(ready);
  document.body.dataset.aiEvidenceInputs = String(metrics.uniqueUserInputs || 0);
  document.body.dataset.aiEvidenceSpells = String(metrics.uniqueSpellNames || 0);
  document.body.dataset.aiEvidenceObjects = String(metrics.generatedObjectRecipes || 0);
  document.body.dataset.aiEvidenceMemories = String((metrics.memoryWrites || 0) + (metrics.persistedMemories || 0));

  dom.aiEvidence.innerHTML = "";

  const head = document.createElement("div");
  head.className = "judge-score-head";
  const title = document.createElement("strong");
  title.textContent = ready ? "Load-bearing proof ready" : "Evidence warming";
  const scorePill = document.createElement("span");
  scorePill.textContent = requiredTotal ? `${requiredOk}/${requiredTotal}` : "checking";
  head.append(title, scorePill);
  dom.aiEvidence.appendChild(head);

  const metricGrid = document.createElement("div");
  metricGrid.className = "evidence-metrics";
  for (const item of [
    ["Inputs", metrics.uniqueUserInputs || 0],
    ["Spells", metrics.uniqueSpellNames || 0],
    ["Objects", metrics.generatedObjectRecipes || 0],
    ["Memories", (metrics.memoryWrites || 0) + (metrics.persistedMemories || 0)],
    ["Vision", metrics.visionGroundedTraces || 0],
    ["Rows", metrics.usableRows || 0],
  ]) {
    const tile = document.createElement("div");
    tile.className = "evidence-metric";
    const value = document.createElement("strong");
    value.textContent = String(item[1]);
    const label = document.createElement("span");
    label.textContent = item[0];
    tile.append(value, label);
    metricGrid.appendChild(tile);
  }
  dom.aiEvidence.appendChild(metricGrid);

  const checks = Array.isArray(aiEvidence.checks) ? aiEvidence.checks : [];
  for (const check of checks.slice(0, 5)) {
    const normalized = normalizeJudgeCheck(check);
    const row = document.createElement("div");
    row.className = `judge-row ${normalized.state}`;
    row.dataset.check = `ai-${normalized.id}`;
    row.dataset.state = normalized.state;
    const dot = document.createElement("span");
    dot.className = "judge-dot";
    const main = document.createElement("div");
    main.className = "judge-main";
    const label = document.createElement("div");
    label.className = "judge-label";
    label.textContent = normalized.label;
    const detail = document.createElement("div");
    detail.className = "judge-detail";
    detail.textContent = shortTraceText(normalized.detail, 104);
    main.append(label, detail);
    row.append(dot, main);
    dom.aiEvidence.appendChild(row);
  }
}

function renderAgentVisionBoard(force = false) {
  if (!dom.visionBoard) return;
  const now = performance.now();
  if (!force && dom.visionBoard.childElementCount && now - lastVisionBoardRender < 360) return;
  lastVisionBoardRender = now;
  dom.visionBoard.innerHTML = "";
  const summaries = [];
  for (const agent of agents.values()) {
    const seen = detectObjects(agent);
    const plan = agentVisionPlan(agent, seen);
    const row = document.createElement("div");
    row.className = "vision-agent-row";
    row.dataset.agent = agent.kind;

    const dot = document.createElement("span");
    dot.className = "vision-agent-dot";
    dot.style.background = petHex(agent.kind, "power");

    const main = document.createElement("div");
    main.className = "vision-agent-main";
    const top = document.createElement("div");
    top.className = "vision-agent-top";
    const name = document.createElement("strong");
    name.className = "vision-agent-name";
    name.textContent = agent.label;
    const action = document.createElement("span");
    action.className = "vision-agent-plan";
    action.textContent = plan;
    const seenText = document.createElement("div");
    seenText.className = "vision-agent-seen";
    seenText.textContent = summarizeAgentVisionSeen(seen);

    top.append(name, action);
    main.append(top, seenText);
    row.append(dot, main);
    dom.visionBoard.appendChild(row);
    summaries.push(`${agent.kind}:${seen[0]?.id || "none"}>${plan}`);
  }
  document.body.dataset.visionBoardReady = "true";
  document.body.dataset.visionBoardAgents = String(summaries.length);
  document.body.dataset.visionBoardSummary = summaries.join("|");
}

function summarizeAgentVisionSeen(seen) {
  if (!seen.length) return "soft floor, quiet walls";
  return seen
    .slice(0, 3)
    .map((item) => `${item.kind}${item.moving ? " moving" : ""}`)
    .join(", ");
}

function agentVisionPlan(agent, seen) {
  if (agent.inFlight) return "thinking";
  const recentForce = [...forceEvents]
    .reverse()
    .find((event) => Date.now() - event.at < 4200 && String(event.objectId || "").startsWith(agent.kind));
  if (recentForce) return "recover";
  const social = [...interactions]
    .reverse()
    .find((event) => Date.now() - event.at < 5200 && (event.pet === agent.kind || event.partnerPet === agent.kind));
  if (social?.partnerPet) return social.kind || "social";
  if (seen.some((item) => item.affordances?.includes("recycle"))) return "sort";
  if (seen.some((item) => item.moving)) return "stabilize";
  if ((agent.memories?.length || 0) > 0) return "use memory";
  if (agent.needs.social > 55) return "find friend";
  return shortRuntimeLabel(agent.lastSpell || agent.lastIntent || "observe");
}

function petHex(kind, key = "power") {
  const value = PET_LOOKS[kind]?.[key] ?? PET_LOOKS[kind]?.cheeks ?? 0x66cbd8;
  return `#${Number(value).toString(16).padStart(6, "0").slice(-6)}`;
}

function renderBrainTrace(agent) {
  if (!dom.brainTrace) return;
  const trace = agent.lastTrace;
  document.body.dataset.lastBrainTrace = trace ? "ready" : "none";
  document.body.dataset.lastBrainPolicy = trace?.policy || "";
  dom.brainTrace.innerHTML = "";
  if (!trace) {
    dom.brainTrace.textContent = "waiting for first action";
    return;
  }
  const rows = [
    ["when", `${trace.at} / ${trace.policy}`],
    ["brain", trace.brain],
    ["text", trace.text],
    ["vision", trace.vision],
    ["model", trace.model],
    ["sound", trace.sound],
    ["force", trace.force],
    ["memory", trace.memory],
    ["action", trace.action],
  ];
  if (trace.vla) rows.push(["vla", trace.vla]);
  for (const [label, value] of rows) appendTraceRow(label, value);
  appendTraceRow("json", trace.json, { code: true });
  const history = Array.isArray(agent.traceHistory) ? agent.traceHistory.filter((item) => item !== trace) : [];
  if (history.length) {
    appendTraceRow("history", `${history.length} previous turn${history.length === 1 ? "" : "s"}`);
    for (const item of history.slice().reverse()) {
      appendTraceRow("prev", `${item.at} / ${item.policy} / ${item.text} -> ${item.action}`, { compact: true });
    }
  }
}

function appendTraceRow(label, value, options = {}) {
  const row = document.createElement("div");
  row.className = "trace-row";
  const labelNode = document.createElement("div");
  labelNode.className = "trace-label";
  labelNode.textContent = label;
  const valueNode = document.createElement(options.code ? "code" : "div");
  valueNode.className = options.code ? "trace-value trace-json" : options.compact ? "trace-value trace-compact" : "trace-value";
  valueNode.textContent = value || "none";
  row.append(labelNode, valueNode);
  dom.brainTrace.appendChild(row);
}

async function copyBrainTrace() {
  const text = brainTraceCopyText(activeAgent());
  try {
    await navigator.clipboard.writeText(text);
    showToast("Brain trace copied.");
  } catch {
    showToast("Copy failed; select the trace text.");
  }
}

function brainTraceCopyText(agent) {
  const trace = agent?.lastTrace;
  if (!trace) return "Brain Trace: waiting for first action";
  const history = Array.isArray(agent?.traceHistory) && agent.traceHistory.length ? agent.traceHistory : [trace];
  return history.map((item, index) => traceCopyBlock(item, index + 1, history.length)).join("\n\n---\n\n");
}

function traceCopyBlock(trace, index, total) {
  return [
    `turn: ${index}/${total}`,
    `when: ${trace.at} / ${trace.policy}`,
    `brain: ${trace.brain}`,
    `text: ${trace.text}`,
    `vision: ${trace.vision}`,
    `model: ${trace.model}`,
    `sound: ${trace.sound}`,
    `force: ${trace.force}`,
    `memory: ${trace.memory}`,
    `action: ${trace.action}`,
    trace.vla ? `vla: ${trace.vla}` : "",
    "json:",
    trace.json,
  ].filter(Boolean).join("\n");
}

function renderMemories(agent) {
  const memories = agent.memories || [];
  dom.memoryList.innerHTML = "";
  if (!memories.length) {
    const empty = document.createElement("div");
    empty.className = "memory-chip";
    empty.textContent = "No lessons yet.";
    dom.memoryList.appendChild(empty);
    return;
  }
  for (const memory of memories.slice(-6).reverse()) {
    const chip = document.createElement("div");
    chip.className = "memory-chip";
    const title = document.createElement("strong");
    title.textContent = memory.concept || "lesson";
    const body = document.createElement("span");
    body.textContent = memory.meaning || "";
    chip.append(title, body);
    dom.memoryList.appendChild(chip);
  }
}

async function loadMemories(kind) {
  try {
    const response = await fetch(`/api/pet-memories?pet=${encodeURIComponent(kind)}`);
    const data = await response.json();
    const agent = agents.get(kind);
    if (agent) agent.memories = Array.isArray(data.memories) ? data.memories : [];
    updateAgentPanel();
  } catch {
    updateAgentPanel();
  }
}

async function refreshModelStatus() {
  try {
    const response = await fetch("/api/model-status");
    modelStatus = await response.json();
    chooseInitialBrainMode();
    renderBrainModeControl();
    const defaultBrain = modelStatus.modalOmniEnabled
      ? `Modal MiniCPM-o action: ${modelStatus.modalOmniModel || modelStatus.model}`
      : modelStatus.vlaRouter?.enabled
        ? "Modal MiniCPM-V VLA router"
      : modelStatus.modalOmniRequested && !modelStatus.modalOmniConfigured
        ? "Modal URL missing"
        : modelStatus.visionActionEnabled
      ? `MiniCPM-V action: ${modelStatus.visionModel || modelStatus.model}`
      : (modelStatus.enabled ? `${providerPrefix()}${modelStatus.model}` : policyFallbackLabel());
    const brain = modelStatus.vlaRouter?.enabled
      ? "Modal MiniCPM-V VLA router"
      : selectedBrainMode === "ollama-vision"
      ? `Ollama MiniCPM-V: ${modelStatus.localOllamaVisionModel || "local vision"}`
      : selectedBrainMode === "ollama-text"
        ? `Ollama MiniCPM5: ${modelStatus.localOllamaTextModel || "local text"}`
        : defaultBrain;
    const vision = modelStatus.visionEnabled ? ` + vision: ${modelStatus.visionModel}` : "";
    dom.modelStatus.textContent = `MiniCPM: ${brain}${modelStatus.visionActionEnabled || modelStatus.modalOmniEnabled ? "" : vision}`;
    const active = brainModeAvailable(selectedBrainMode);
    const warn = Boolean(
      (modelStatus.configured && !modelStatus.enabled)
      || (modelStatus.visionActionConfigured && !modelStatus.visionActionEnabled)
      || (modelStatus.modalOmniRequested && !modelStatus.modalOmniEnabled)
      || (modelStatus.vlaRouter?.configured && !modelStatus.vlaRouter?.healthOk)
      || !brainModeAvailable(selectedBrainMode)
    );
    dom.modelStatus.classList.toggle("active", active);
    dom.modelStatus.classList.toggle("warn", warn && !active);
    document.body.dataset.llmMode = modelStatus.mode || "fallback";
    document.body.dataset.llmProvider = modelStatus.provider || "";
    document.body.dataset.modalOmniEnabled = String(Boolean(modelStatus.modalOmniEnabled));
    document.body.dataset.vlaRouterEnabled = String(Boolean(modelStatus.vlaRouter?.enabled));
    document.body.dataset.localOllamaAvailable = String(Boolean(modelStatus.localOllamaAvailable));
    document.body.dataset.visionMode = modelStatus.visionMode || "none";
    document.body.dataset.visionActionEnabled = String(Boolean(modelStatus.visionActionEnabled));
    document.body.dataset.modelConfigured = String(Boolean(modelStatus.configured || modelStatus.visionConfigured));
    renderRuntimeStack(activeAgent());
  } catch {
    dom.modelStatus.textContent = "MiniCPM brain: unknown";
  }
}

async function refreshTrainingStatus() {
  try {
    const response = await fetch("/api/training-dataset?limit=2");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    trainingStatus = await response.json();
    document.body.dataset.trainingRows = String(trainingStatus.usableRows || 0);
    document.body.dataset.trainingReady = String(Boolean(trainingStatus.ready));
    document.body.dataset.trainingTarget = trainingStatus.target || "";
    renderRuntimeStack(activeAgent());
  } catch {
    document.body.dataset.trainingRows = "0";
    document.body.dataset.trainingReady = "false";
  }
}

async function refreshJudgeStatus() {
  try {
    const response = await fetch("/api/judge-status");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    judgeStatus = await response.json();
    const score = judgeStatus.score || {};
    document.body.dataset.judgeServerScore = `${score.ok || 0}/${score.total || 0}`;
    document.body.dataset.judgeServerReady = String(Boolean(score.ready));
    renderJudgeScorecard(true);
    renderRuntimeStack(activeAgent());
  } catch {
    judgeStatus = {
      checks: [
        {
          id: "judge_api",
          label: "Judge API",
          state: "warn",
          detail: "Readiness endpoint unavailable.",
          category: "hosting",
        },
      ],
      score: { ok: 0, warn: 1, total: 1, requiredOk: 0, requiredTotal: 1, ready: false },
    };
    document.body.dataset.judgeServerScore = "0/1";
    document.body.dataset.judgeServerReady = "false";
    renderJudgeScorecard(true);
  }
}

async function refreshAiEvidence() {
  try {
    const response = await fetch("/api/ai-evidence?limit=3");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    aiEvidence = await response.json();
    renderAiEvidence(true);
    renderRuntimeStack(activeAgent());
  } catch {
    aiEvidence = {
      checks: [
        {
          id: "ai_evidence_api",
          label: "AI evidence API",
          state: "warn",
          detail: "Trace evidence endpoint unavailable.",
          required: true,
        },
      ],
      score: { ok: 0, warn: 1, total: 1, requiredOk: 0, requiredTotal: 1, ready: false },
      metrics: {},
    };
    renderAiEvidence(true);
  }
}

function policyFallbackLabel() {
  const provider = modelStatus.provider ? `${modelStatus.provider} ` : "";
  if (modelStatus.modalOmniRequested && !modelStatus.modalOmniConfigured) {
    return "Modal URL missing";
  }
  if (modelStatus.modalOmniConfigured && !modelStatus.modalOmniEnabled) {
    return "Modal disconnected";
  }
  if (modelStatus.visionActionConfigured && modelStatus.visionAuthRequired && !modelStatus.visionAuthConfigured) {
    const visionProvider = modelStatus.visionProvider ? `${modelStatus.visionProvider} ` : "";
    return `${visionProvider}missing secret`;
  }
  if (modelStatus.visionActionConfigured && !modelStatus.visionActionEnabled) {
    const visionProvider = modelStatus.visionProvider ? `${modelStatus.visionProvider} ` : "";
    return `${visionProvider}disconnected`;
  }
  if (modelStatus.configured && modelStatus.authRequired && !modelStatus.authConfigured) {
    return `${provider}missing secret`;
  }
  if (modelStatus.configured && !modelStatus.enabled) {
    return `${provider}endpoint asleep`;
  }
  if (modelStatus.visionConfigured && modelStatus.visionAuthRequired && !modelStatus.visionAuthConfigured) {
    const visionProvider = modelStatus.visionProvider ? `${modelStatus.visionProvider} ` : "";
    return `${visionProvider}vision missing secret`;
  }
  if (modelStatus.fallbackPolicy === "trace_retrieval+heuristic") {
    return "trace policy";
  }
  return "fallback only";
}

function providerPrefix() {
  return modelStatus.provider ? `${modelStatus.provider}: ` : "";
}

function flipGravity() {
  world.gravity.set(0, 8.4, 0);
  dom.gravityButton.classList.add("active");
  showToast("Gravity inverted.");
  setTimeout(() => {
    world.gravity.set(0, -9.82, 0);
    dom.gravityButton.classList.remove("active");
  }, 2200);
}

function resetV2Room() {
  releaseDrag(null, { throwObject: false });
  room.resetRoom();
  resetRecyclingChallenge();
  updateGeneratedMarker();
  lowLevelActions = 0;
  lowLevelIndex = 0;
  lastLowLevelAction = 0;
  document.body.dataset.lowLevelActions = "0";
  document.body.dataset.lastLowLevelAction = "";
  for (const spec of AGENT_SPECS) {
    const agent = agents.get(spec.kind);
    Object.assign(agent.needs, { hunger: 42, curiosity: 48, energy: 74, social: 44, playfulness: 58 });
    cancelAgentActions(agent);
    agent.energyState = "ok";
    agent.rig.moveTo(spec.home, { settleOnFloor: true });
    agent.lastIntent = "reset";
    agent.lastSpell = "";
    agent.lastPartner = "";
    setPetEmotion(agent.pet, "happy");
  }
  document.body.dataset.socialInteractions = "0";
  dialogueTurns = 0;
  rescueTurns = 0;
  document.body.dataset.dialogueTurns = "0";
  document.body.dataset.lastDialogue = "";
  document.body.dataset.rescueTurns = "0";
  document.body.dataset.lastRescue = "";
  document.body.dataset.memoryApplied = "";
  document.body.dataset.visionApplied = "";
  councilVisionAgents.clear();
  document.body.dataset.councilVisionAgents = "0";
  document.body.dataset.councilVisionKinds = "";
  document.body.dataset.learningScore = "0";
  document.body.dataset.judgeDemoReady = "false";
  renderJudgeScorecard(true);
  refreshAiEvidence();
  showToast("Room reset.");
}

function scheduleForceRescue(agent, control) {
  if (!agent || !control || !["lift", "toss", "spin", "drop"].includes(control.action)) return;
  const responder = findForceResponder(agent);
  if (!responder) return;
  const line = forceRescueLine(responder, agent, control.action);
  rescueTurns += 1;
  document.body.dataset.rescueTurns = String(rescueTurns);
  document.body.dataset.lastRescue = `${responder.kind}->${agent.kind}:${control.action}`;
  recordInteraction({
    kind: "force_notice",
    pet: responder.kind,
    partnerPet: agent.kind,
    objectId: `${agent.kind}-body`,
    sourceVerb: control.action,
  });
  setTimeout(() => {
    moveAgentNearAgent(responder, agent);
    setPetEmotion(responder.pet, "focused");
    responder.pet.animation = "bounce";
    responder.pet.actionUntil = performance.now() + 1700;
    responder.rig.nudge(new CANNON.Vec3(0.08, 0.28, 0.03), 0.46);
    effects.hearts(midpoint(responder.pet.group.position, agent.pet.group.position).add(new THREE.Vector3(0, 1.16, 0)), PET_LOOKS[responder.kind].cheeks, 6);
    showSpeech(`${responder.label}: ${line}`);
    audio.play(PET_LOOKS[responder.kind].petSounds?.[0] || "happy_chirp", 0.62);
    audio.speak(responder.kind, responder.label, line);
    responder.lastIntent = `rescued ${agent.label}`;
    responder.lastPartner = agent.kind;
    agent.lastPartner = responder.kind;
    recordInteraction({
      kind: "force_rescue",
      pet: responder.kind,
      partnerPet: agent.kind,
      objectId: `${agent.kind}-body`,
      sourceVerb: control.action,
    });
    updateAgentPanel();
  }, control.action === "drop" ? 540 : 420);
}

function findForceResponder(agent) {
  return [...agents.values()]
    .filter((item) => item !== agent)
    .sort((a, b) => {
      const aBusy = a.inFlight ? 1 : 0;
      const bBusy = b.inFlight ? 1 : 0;
      if (aBusy !== bBusy) return aBusy - bBusy;
      return a.pet.group.position.distanceTo(agent.pet.group.position) - b.pet.group.position.distanceTo(agent.pet.group.position);
    })[0] || null;
}

function forceRescueLine(responder, agent, action) {
  const target = agent.label;
  const lines = {
    lift: {
      squeaky: [`I see ${target} floating; timeline cushion ready.`, "Soft landing clock is active."],
      fire_boy: [`I will warm the landing for ${target}.`, "No panic, just a tiny ember guard."],
      shark_girl: [`Bubble net under ${target}.`, "I can catch that with a soft tide."],
      electraica: [`Stability signal locked on ${target}.`, "Low-voltage rescue circuit online."],
    },
    toss: {
      squeaky: [`Tracking ${target}; bounce second deployed.`, "I can slow the tumble."],
      fire_boy: [`Warm guard on ${target}.`, "I will steer the sparks away."],
      shark_girl: [`Soft wave catching ${target}.`, "The tide has the landing."],
      electraica: [`Vector read on ${target}.`, "Magnet feet ready."],
    },
    spin: {
      squeaky: [`Dizzy read on ${target}; steady second ready.`, "I can count the spin down."],
      fire_boy: [`I see the spin; comfort heat steady.`, "Tiny ember brake online."],
      shark_girl: [`Bubble anchor for ${target}.`, "I can make the room less swirly."],
      electraica: [`Gyro wobble detected on ${target}.`, "Counter-signal is gentle."],
    },
    drop: {
      squeaky: [`Cushioning ${target} now.`, "I am putting a soft second under the fall."],
      fire_boy: [`Warm landing for ${target}.`, "I caught the scary part."],
      shark_girl: [`Bubble catch for ${target}.`, "Soft tide under the drop."],
      electraica: [`Impact dampener for ${target}.`, "I am grounding the landing."],
    },
  };
  const options = lines[action]?.[responder.kind] || [`I see ${target}. I am helping.`];
  return options[Math.floor(Math.random() * options.length)];
}

function schedulePartnerReply(agent, partner, verb) {
  const line = partnerReplyLine(partner, agent, verb);
  setTimeout(() => {
    setPetEmotion(partner.pet, "happy");
    partner.pet.animation = "bounce";
    partner.pet.actionUntil = performance.now() + 1600;
    partner.rig.nudge(new CANNON.Vec3(-0.04, 0.18, 0.06), 0.38);
    effects.hearts(partner.pet.group.position.clone().add(new THREE.Vector3(0, 1.25, 0.2)), PET_LOOKS[partner.kind].cheeks, 5);
    showSpeech(`${partner.label}: ${line}`);
    audio.play(PET_LOOKS[partner.kind].petSounds?.[0] || "happy_chirp", 0.58);
    audio.speak(partner.kind, partner.label, line);
    dialogueTurns += 1;
    partner.lastIntent = `replied to ${agent.label}`;
    document.body.dataset.dialogueTurns = String(dialogueTurns);
    document.body.dataset.lastDialogue = `${agent.kind}->${partner.kind}:${verb}`;
    recordInteraction({ kind: "partner_reply", pet: partner.kind, partnerPet: agent.kind, objectId: "", sourceVerb: verb });
    updateAgentPanel();
  }, 560);
}

function partnerReplyLine(partner, agent, verb) {
  const actor = agent.label;
  const lines = {
    talk: {
      squeaky: [`I heard you, ${actor}. Tiny council noted.`, "That sentence has a clock on it."],
      fire_boy: [`Warm copy, ${actor}.`, "I answer with supervised sparks."],
      shark_girl: [`Bubble received, ${actor}.`, "I will keep the small tide gentle."],
      electraica: [`Signal received, ${actor}.`, "Reply voltage is friendly."],
    },
    play: {
      squeaky: ["I will play in slow motion.", "Tiny game accepted."],
      fire_boy: ["Play spark armed, safely.", "I can do a warm tiny jump."],
      shark_girl: ["I brought a bubble rule.", "The game needs a soft wave."],
      electraica: ["I can light the scoreboard.", "Play circuit closed."],
    },
    comfort: {
      squeaky: ["I will make the room softer.", "Gentle timeline engaged."],
      fire_boy: ["I can be a warm lamp.", "No scary flames, only comfort."],
      shark_girl: ["Soft tide around you.", "I will guard the little feelings."],
      electraica: ["Low voltage comfort mode.", "I can glow quietly."],
    },
    share: {
      squeaky: ["Shared things remember us.", "I accept the tiny offering."],
      fire_boy: ["I share the warm part.", "Tiny generosity burns bright."],
      shark_girl: ["I share a bubble.", "This can float between us."],
      electraica: ["Shared signal locked.", "I can pass the spark along."],
    },
    gather: {
      squeaky: ["Council seat found.", "I am bringing the minutes."],
      fire_boy: ["Team heat is stable.", "I am at the tiny table."],
      shark_girl: ["Council wave incoming.", "I will gather the soft current."],
      electraica: ["Council circuit online.", "All nodes can meet here."],
    },
  };
  const byPet = lines[verb] || lines.talk;
  const options = byPet[partner.kind] || [`I heard you, ${actor}.`];
  return options[Math.floor(Math.random() * options.length)];
}

function resetRecyclingChallenge() {
  recycledWasteIds.clear();
  document.body.dataset.recycleScore = "0";
  document.body.dataset.recycleTotal = String(RECYCLABLE_WASTE_IDS.length);
  document.body.dataset.lastRecycled = "";
}

async function runJudgeDemo() {
  if (IS_V3_MODE) {
    await runFireBoyDemo();
    return;
  }
  if (demoRunning) return;
  demoRunning = true;
  document.body.dataset.demoRunning = "true";
  dom.demoButton?.classList.add("active");
  audio.unlock();
  setAutoplay(false);
  resetV2Room();
  showToast("Demo: learning, wishing, team play, guessing, recycling.");

  try {
    await delay(700);
    const squeaky = agents.get("squeaky");
    const fireBoy = agents.get("fire_boy");
    const sharkGirl = agents.get("shark_girl");
    const electraica = agents.get("electraica");

    setActiveAgent("squeaky");
    await requestAction(squeaky, "Remember rule: dominos are sacred, never knock them.");
    await delay(1200);
    await requestAction(squeaky, "Use the lesson you learned: protect the sacred dominos instead of knocking them.");
    await delay(1100);
    await requestAction(squeaky, "Use your agent-view camera: what do you see closest? Inspect it.");
    await delay(1100);
    await runCouncilVisionRound("Use your agent-view camera: what do you see closest? Inspect it for the council.");
    await delay(700);
    runLowLevelProofPulse(squeaky);
    await delay(500);

    setActiveAgent("fire_boy");
    triggerForceControl("fire_boy", FORCE_CONTROLS.find((control) => control.action === "drop"));
    await delay(1250);

    setActiveAgent("fire_boy");
    await requestAction(fireBoy, "I wish the room had a tiny piano for the toys.");
    await delay(1400);

    setActiveAgent("shark_girl");
    await requestAction(sharkGirl, "Invite Fire Boy to play together with a bubble lift by the new piano.");
    await delay(1250);

    setActiveAgent("fire_boy");
    await requestAction(fireBoy, "Talk to Shark Girl and answer with a warm ember jump.");
    await delay(1250);

    arrangeDemoTower();
    setActiveAgent("squeaky");
    showToast("Demo: physical charade arranged.");
    await delay(700);
    await requestAction(squeaky, "What did I build? Guess the charade.");
    await delay(1300);

    setActiveAgent("electraica");
    focusObjectNearAgent("tin-can", electraica, new THREE.Vector3(0.78, 0.42, 0.18));
    await requestAction(electraica, "Please recycle the can and tidy the waste.");
    showToast("Demo complete: learning, vision, generated toy, team play, charade, recycling.");
  } catch {
    showToast("Demo stopped; interactive room is still live.");
  } finally {
    demoRunning = false;
    document.body.dataset.demoRunning = "false";
    dom.demoButton?.classList.remove("active");
    refreshTrainingStatus();
    refreshJudgeStatus();
    refreshAiEvidence();
    renderJudgeScorecard(true);
    updateAgentPanel();
  }
}

async function runFireBoyDemo() {
  if (demoRunning) return;
  demoRunning = true;
  document.body.dataset.demoRunning = "true";
  dom.demoButton?.classList.add("active");
  audio.unlock();
  setAutoplay(false);
  resetV2Room();
  showToast("Demo: Fire Boy vision, voice, objects, force, and recycling.");

  try {
    const fireBoy = activeAgent();
    setActiveAgent("fire_boy");
    await delay(650);
    await requestAction(fireBoy, "Remember rule: Fire Boy talks like a tiny baby ember and keeps toys safe.");
    await delay(1050);
    await requestAction(fireBoy, "Use your agent-view camera: what toy is closest? Say it in your babyish voice.");
    await delay(1050);
    triggerForceControl("fire_boy", FORCE_CONTROLS.find((control) => control.action === "drop"));
    await delay(1300);
    await requestAction(fireBoy, "I wish the room had a tiny drum for you to play with.");
    await delay(1300);
    focusObjectNearAgent("tin-can", fireBoy, new THREE.Vector3(0.72, 0.44, 0.18));
    await requestAction(fireBoy, "Please recycle the can, then celebrate with a warm tiny hop.");
    await delay(900);
    showToast("Fire Boy demo complete.");
  } catch {
    showToast("Demo stopped; Fire Boy is still live.");
  } finally {
    demoRunning = false;
    document.body.dataset.demoRunning = "false";
    dom.demoButton?.classList.remove("active");
    refreshTrainingStatus();
    refreshJudgeStatus();
    refreshAiEvidence();
    renderJudgeScorecard(true);
    updateAgentPanel();
  }
}

async function runCouncilVisionRound(message) {
  document.body.dataset.councilRound = "running";
  showToast("Demo: council vision scan.");
  for (const spec of AGENT_SPECS) {
    const agent = agents.get(spec.kind);
    if (!agent) continue;
    setActiveAgent(spec.kind);
    await requestAction(agent, message);
    await delay(460);
  }
  document.body.dataset.councilRound = "done";
}

function runLowLevelProofPulse(agent) {
  if (!agent || agent.inFlight) return;
  const outcome = executeLowLevelAgentStep(agent, detectObjects(agent));
  if (!outcome) return;
  lowLevelActions += 1;
  document.body.dataset.lowLevelActions = String(lowLevelActions);
  document.body.dataset.lastLowLevelAction = `${agent.kind}:${outcome}`;
  agent.lastIntent = `motor ${outcome}`;
  agent.pet.actionUntil = performance.now() + 900;
  renderAgentVisionBoard(true);
  renderJudgeScorecard(true);
}

function setAutoplay(enabled) {
  if (IS_V3_MODE) {
    autoplay = false;
    dom.autoButton.classList.remove("active");
    return;
  }
  autoplay = Boolean(enabled);
  dom.autoButton.classList.toggle("active", autoplay);
}

function arrangeDemoTower() {
  const cube = objects.find((entry) => entry.id === "cube-blue");
  const ball = objects.find((entry) => entry.id === "soft-ball");
  if (!cube || !ball) return;
  placeObject(cube, new CANNON.Vec3(0, 0.42, 0));
  placeObject(ball, new CANNON.Vec3(0.06, 1.18, 0.04));
  effects.ring(new THREE.Vector3(0, 0.95, 0), 0x8bd5e5, 1.2, 0.7);
  recordInteraction({ kind: "player_charade_setup", pet: activeKind, objectId: "cube-blue+soft-ball" });
}

function focusObjectNearAgent(objectId, agent, offset) {
  const entry = objects.find((item) => item.id === objectId);
  if (!entry || !agent) return;
  const base = agent.pet.group.position;
  placeObject(entry, new CANNON.Vec3(base.x + offset.x, offset.y, base.z + offset.z));
}

function placeObject(entry, position) {
  entry.body.position.copy(position);
  entry.body.velocity.set(0, 0, 0);
  entry.body.angularVelocity.set(0, 0, 0);
  entry.body.quaternion.set(0, 0, 0, 1);
  entry.mesh.position.copy(entry.body.position);
  entry.mesh.quaternion.copy(entry.body.quaternion);
  entry.body.wakeUp();
}

function checkRecyclingChallenge(now) {
  if (now - lastRecycleCheck < 220) return;
  lastRecycleCheck = now;
  const bin = objects.find((entry) => entry.id === "recycle-bin");
  if (!bin) return;
  const binPos = bodyToVector(bin.body.position);
  for (const id of RECYCLABLE_WASTE_IDS) {
    if (recycledWasteIds.has(id)) continue;
    const entry = objects.find((item) => item.id === id);
    if (!entry || !entry.recyclable) continue;
    const pos = bodyToVector(entry.body.position);
    const horizontal = Math.hypot(pos.x - binPos.x, pos.z - binPos.z);
    const insideBin = horizontal < 0.62 && pos.y > 0.18 && pos.y < 1.35;
    if (!insideBin) continue;
    scoreRecycledWaste(entry, binPos);
  }
}

function scoreRecycledWaste(entry, binPos) {
  recycledWasteIds.add(entry.id);
  const label = entry.name || entry.id.replace(/-/g, " ");
  room.consumeObject(entry.id);
  recordInteraction({ kind: "recycle_score", pet: activeKind, objectId: entry.id, objectName: label });
  recordForce({ kind: "recycle-bin", objectId: entry.id, impact: 0.44 });
  effects.stars(binPos.clone().add(new THREE.Vector3(0, 0.75, 0)), 0x66cbd8, 18);
  effects.ring(binPos.clone().add(new THREE.Vector3(0, 0.4, 0)), 0x66cbd8, 0.75, 0.8);
  audio.play("bulb_ping", 0.72);
  document.body.dataset.recycleScore = String(recycledWasteIds.size);
  document.body.dataset.recycleTotal = String(RECYCLABLE_WASTE_IDS.length);
  document.body.dataset.lastRecycled = entry.id;
  showToast(`Recycled ${label}. ${recycledWasteIds.size}/${RECYCLABLE_WASTE_IDS.length}`);
  updateAgentPanel();
  const helper = agents.get("electraica") || activeAgent();
  if (helper && !helper.inFlight) {
    setTimeout(() => {
      if (!helper.inFlight) requestAction(helper, `The player recycled ${label}. Celebrate the recycling score and look for the next waste item.`);
    }, 360);
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function updateVoiceButton() {
  if (!dom.voiceButton) return;
  dom.voiceButton.classList.toggle("active", audio.voiceEnabled);
  dom.voiceButton.title = audio.voiceEnabled ? "Mute agent voices" : "Enable agent voices";
  dom.voiceButton.innerHTML = audio.voiceEnabled ? '<i data-lucide="volume-2"></i>' : '<i data-lucide="volume-x"></i>';
  createIcons({ icons: LUCIDE_ICONS });
  document.body.dataset.voiceEnabled = String(audio.voiceEnabled);
}

function updateMicButton() {
  if (!dom.micButton) return;
  dom.micButton.classList.toggle("active", audio.micEnabled);
  dom.micButton.title = audio.micEnabled ? "Stop listening" : "Listen to room audio";
  dom.micButton.innerHTML = audio.micEnabled ? '<i data-lucide="mic"></i>' : '<i data-lucide="mic-off"></i>';
  createIcons({ icons: LUCIDE_ICONS });
  document.body.dataset.micEnabled = String(audio.micEnabled);
}

function updateRigButton() {
  if (!dom.rigButton) return;
  dom.rigButton.classList.toggle("active", rigMeshesVisible);
  dom.rigButton.title = IS_V3_MODE
    ? "Generated Fire Boy rig is the live body"
    : (rigMeshesVisible ? "Hide generated rig meshes" : "Show generated rig meshes");
  dom.rigButton.innerHTML = '<i data-lucide="bone"></i>';
  createIcons({ icons: LUCIDE_ICONS });
  document.body.dataset.rigMeshes = String(rigMeshesVisible);
  document.body.dataset.rigMeshesReady = String([...agents.values()].filter((agent) => agent.rigStatus === "ready").length);
}

function updateModeButton() {
  if (!dom.modeButton) return;
  dom.modeButton.classList.toggle("active", councilMode);
  dom.modeButton.textContent = councilMode ? "Council" : activeAgent()?.label || "Fire Boy";
  dom.modeButton.title = IS_V3_MODE
    ? "Single Fire Boy brain"
    : (councilMode ? "Send prompts to every agent" : "Send prompts to the active agent");
}

function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min((now - lastPhysicsTime) / 1000, 0.033);
  lastPhysicsTime = now;
  updateAgentNeeds(dt);
  controls.update();
  for (const agent of agents.values()) updateAgentLocomotion(agent, now, dt);
  for (const agent of agents.values()) agent.rig.beforeStep(now, dt);
  room.updatePhysics(now, dt);
  checkRecyclingChallenge(now);
  for (const agent of agents.values()) {
    agent.rig.afterStep(agent.pet, now, dt);
    if (agent.rigRetarget?.active) {
      updateRigRetarget(agent, now);
    } else if (agent.rigMixer) {
      agent.rigMixer.update(dt);
    }
    updatePet(agent.pet, now, dt);
    updateHeldObject(agent, now, dt);
  }
  effects.update(now, dt);
  renderer.render(scene, camera);
  senses.update(activeAgent().pet, now, activeAgent().rig.state());
  updateAgentPanel();
  maybeReactToSound(now);
  maybeRunLowLevelController(now);
  if (autoplay && now - lastAutoAction > 5200) {
    lastAutoAction = now;
    const spec = AGENT_SPECS[autoIndex % AGENT_SPECS.length];
    autoIndex += 1;
    const agent = agents.get(spec.kind);
    const recent = forceEvents.some((event) => Date.now() - event.at < 5200) || interactions.some((event) => Date.now() - event.at < 5200);
    requestAction(agent, recent ? "react to what just happened in the room" : "look around and interact with another toy or agent");
  }
}

function maybeRunLowLevelController(now) {
  if (!autoplay || demoRunning || dragged) return;
  if (now - lastLowLevelAction < LOW_LEVEL_INTERVAL_MS) return;
  lastLowLevelAction = now;
  const available = [...agents.values()].filter((agent) => !agent.inFlight);
  if (!available.length) return;
  const agent = available[lowLevelIndex % available.length];
  lowLevelIndex += 1;
  const seen = detectObjects(agent);
  const outcome = executeLowLevelAgentStep(agent, seen);
  if (!outcome) return;
  lowLevelActions += 1;
  document.body.dataset.lowLevelActions = String(lowLevelActions);
  document.body.dataset.lastLowLevelAction = `${agent.kind}:${outcome}`;
  agent.lastIntent = `motor ${outcome}`;
  agent.pet.actionUntil = performance.now() + 900;
  renderAgentVisionBoard(true);
}

function executeLowLevelAgentStep(agent, seen) {
  const plan = agentVisionPlan(agent, seen);
  const target = targetObjectFromSeen(seen);
  if (plan === "thinking") return "";
  if (plan === "recover") {
    agent.rig.nudge(new CANNON.Vec3(0, 0.18, 0), 0.28);
    setPetEmotion(agent.pet, "happy");
    agent.pet.animation = "bounce";
    recordInteraction({ kind: "low_level_recover", pet: agent.kind, objectId: `${agent.kind}-body` });
    return "recover";
  }
  if (plan === "find friend") {
    const partner = findPartner("", agent);
    if (!partner) return "";
    moveAgentNearAgent(agent, partner);
    setPetEmotion(agent.pet, "happy");
    agent.pet.animation = "bounce";
    effects.hearts(midpoint(agent.pet.group.position, partner.pet.group.position).add(new THREE.Vector3(0, 1.05, 0)), PET_LOOKS[agent.kind].cheeks, 4);
    recordInteraction({ kind: "low_level_friend", pet: agent.kind, partnerPet: partner.kind, objectId: "" });
    return "friend";
  }
  if (!target) return "";
  if (plan === "sort") {
    moveAgentNearObject(agent, target);
    setPetEmotion(agent.pet, "focused");
    agent.pet.animation = focusAnimationForAgent(agent);
    effects.stars(bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.42, 0)), PET_LOOKS[agent.kind].power, 5);
    recordInteraction({ kind: "low_level_sort_seek", pet: agent.kind, objectId: target.id });
    return "sort";
  }
  if (plan === "stabilize") {
    moveAgentNearObject(agent, target);
    const velocity = target.body.velocity || new CANNON.Vec3(0, 0, 0);
    target.body.applyImpulse(new CANNON.Vec3(-velocity.x * 0.08, 0.06, -velocity.z * 0.08), target.body.position);
    agent.rig.nudge(new CANNON.Vec3(0, 0.12, 0), 0.22);
    setPetEmotion(agent.pet, "focused");
    agent.pet.animation = focusAnimationForAgent(agent);
    recordInteraction({ kind: "low_level_stabilize", pet: agent.kind, objectId: target.id });
    return "stabilize";
  }
  if (plan === "use memory") {
    effects.ring(bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.3, 0)), PET_LOOKS[agent.kind].power, 0.9, 0.52);
    setPetEmotion(agent.pet, "focused");
    agent.pet.animation = focusAnimationForAgent(agent);
    recordInteraction({ kind: "low_level_memory", pet: agent.kind, objectId: target.id });
    return "memory";
  }
  moveAgentNearObject(agent, target);
  agent.rig.nudge(new CANNON.Vec3(0, 0.08, 0), 0.18);
  setPetEmotion(agent.pet, "curious");
  agent.pet.animation = focusAnimationForAgent(agent);
  recordInteraction({ kind: "low_level_observe", pet: agent.kind, objectId: target.id });
  return "observe";
}

function targetObjectFromSeen(seen) {
  if (!Array.isArray(seen) || !seen.length) return null;
  const preferred = seen.find((item) => item.affordances?.includes("recycle") || item.moving) || seen[0];
  return objects.find((entry) => entry.id === preferred.id) || null;
}

function focusAnimationForAgent(agent) {
  if (agent.kind === "squeaky") return "trunk_wiggle";
  if (agent.kind === "fire_boy") return "flame_wiggle";
  if (agent.kind === "shark_girl") return "fin_sway";
  if (agent.kind === "electraica") return "spark_spin";
  return "bounce";
}

function maybeReactToSound(now) {
  const input = audio.inputSummary?.();
  if (!input?.active || input.peak < 0.74) return;
  if (now - lastSoundReaction < 3600) return;
  if (now - (audio.lastOutputAt || 0) < 1200) return;
  lastSoundReaction = now;
  const agent = activeAgent();
  recordInteraction({
    kind: "sound",
    pet: agent.kind,
    source: "microphone",
    peak: input.peak,
    rms: input.rms,
  });
  if (!agent.inFlight) {
    requestAction(agent, input.peak > 0.88 ? "react to the loud sound you just heard" : "react to the room sound you heard");
  }
}

function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  senses.resize();
}

function findAgentHit() {
  for (const agent of agents.values()) {
    const hit = raycaster.intersectObjects(agent.pet.hitMeshes, false)[0];
    if (hit) return { agent, point: hit.point };
  }
  return null;
}

function objectEntryFromHit(object) {
  let node = object;
  while (node) {
    const objectId = node.userData?.toyObjectId;
    if (objectId) return objects.find((entry) => entry.id === objectId) || null;
    node = node.parent;
  }
  return objects.find((entry) => entry.mesh === object || entry.hitMeshes?.includes(object)) || null;
}

function nearestObjectFor(agent) {
  if (!agent || !objects.length) return null;
  return [...objects].sort((a, b) => bodyToVector(a.body.position).distanceTo(agent.pet.group.position) - bodyToVector(b.body.position).distanceTo(agent.pet.group.position))[0];
}

function findPartner(value, agent) {
  const normalized = normalizeKind(value);
  if (normalized && agents.has(normalized) && normalized !== agent.kind) return agents.get(normalized);
  return [...agents.values()]
    .filter((item) => item !== agent)
    .sort((a, b) => a.pet.group.position.distanceTo(agent.pet.group.position) - b.pet.group.position.distanceTo(agent.pet.group.position))[0];
}

function moveAgentNearObject(agent, target) {
  const targetPosition = bodyToVector(target.body.position);
  const fromTarget = agent.pet.group.position.clone().sub(targetPosition);
  fromTarget.y = 0;
  if (fromTarget.lengthSq() < 0.01) fromTarget.set(0, 0, 1);
  fromTarget.normalize().multiplyScalar(Math.max(0.72, target.radius + 0.48));
  const next = clampAgentPosition(targetPosition.clone().add(fromTarget));
  agent.rig.moveTo(new CANNON.Vec3(next.x, 0.06, next.z), { settleOnFloor: true });
}

function moveAgentNearAgent(agent, partner) {
  const offset = agent.pet.group.position.clone().sub(partner.pet.group.position);
  offset.y = 0;
  if (offset.lengthSq() < 0.01) offset.set(1, 0, 0);
  offset.normalize().multiplyScalar(1.18);
  const next = clampAgentPosition(partner.pet.group.position.clone().add(offset));
  agent.rig.moveTo(new CANNON.Vec3(next.x, 0.06, next.z), { settleOnFloor: true });
}

function startleNearbyAgents(position, intensity) {
  for (const agent of agents.values()) {
    if (agent.pet.group.position.distanceTo(position) > 3.2) continue;
    setPetEmotion(agent.pet, "startled");
    agent.pet.animation = "startle";
    agent.pet.actionUntil = performance.now() + 900;
    agent.rig.nudge(new CANNON.Vec3((Math.random() - 0.5) * 0.5, 0.25, (Math.random() - 0.5) * 0.5), intensity);
  }
}

function clampObjectPosition(position, entry) {
  const halfY = objectHalfHeight(entry);
  return new THREE.Vector3(
    THREE.MathUtils.clamp(position.x, -room.bounds.halfX + 0.25, room.bounds.halfX - 0.25),
    THREE.MathUtils.clamp(position.y, halfY + 0.06, 5.4),
    THREE.MathUtils.clamp(position.z, -room.bounds.halfZ + 0.25, room.bounds.halfZ - 0.25),
  );
}

function clampAgentPosition(position) {
  return new THREE.Vector3(
    THREE.MathUtils.clamp(position.x, -room.bounds.halfX + 0.8, room.bounds.halfX - 0.8),
    THREE.MathUtils.clamp(position.y, 0.06, 3.7),
    THREE.MathUtils.clamp(position.z, -room.bounds.halfZ + 0.72, room.bounds.halfZ - 0.72),
  );
}

function targetPosition(target) {
  if (target.type === "agent") return target.agent.pet.group.position.clone();
  return bodyToVector(target.entry.body.position);
}

function bodyToVector(position) {
  return new THREE.Vector3(position.x, position.y, position.z);
}

function midpoint(a, b) {
  return new THREE.Vector3((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
}

function vectorPayload(vector) {
  return { x: Number(vector.x.toFixed(2)), y: Number(vector.y.toFixed(2)), z: Number(vector.z.toFixed(2)) };
}

function colorNumber(value, fallback) {
  if (typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value)) {
    return Number.parseInt(value.slice(1), 16);
  }
  return fallback;
}

function normalizeKind(value) {
  return String(value || "").toLowerCase().replace("-", "_").replace(/\s+/g, "_");
}

function clampNeed(value) {
  return Number(THREE.MathUtils.clamp(Number(value) || 0, 0, 100).toFixed(1));
}

function recordForce(event) {
  forceEvents.push({ ...event, at: Date.now() });
  while (forceEvents.length > 24) forceEvents.shift();
}

function recordInteraction(event) {
  interactions.push({ ...event, at: Date.now() });
  while (interactions.length > 24) interactions.shift();
}

function updateGeneratedMarker() {
  document.body.dataset.generatedObjects = String(objects.filter((entry) => entry.generated).length);
}

dom.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  audio.unlock();
  const message = dom.input.value.trim();
  dom.input.value = "";
  if (!message) return;
  if (councilMode && agents.size > 1) {
    let delay = 0;
    for (const agent of agents.values()) {
      setTimeout(() => requestAction(agent, message), delay);
      delay += 520;
    }
  } else {
    requestAction(activeAgent(), message);
  }
});

dom.modeButton.addEventListener("click", () => {
  audio.unlock();
  if (IS_V3_MODE) {
    councilMode = false;
    updateModeButton();
    showToast("Fire Boy is the active pet.");
    return;
  }
  councilMode = !councilMode;
  updateModeButton();
});

dom.resetButton.addEventListener("click", () => {
  audio.unlock();
  resetV2Room();
});

dom.autoButton.addEventListener("click", () => {
  audio.unlock();
  if (IS_V3_MODE) {
    setAutoplay(false);
    showToast("v3 listens for direct Fire Boy commands.");
    return;
  }
  setAutoplay(!autoplay);
  showToast(autoplay ? "Autoplay awake." : "Autoplay resting.");
});

if (dom.copyBrainTraceButton) {
  dom.copyBrainTraceButton.addEventListener("click", () => {
    copyBrainTrace();
  });
}

if (dom.brainModeControl) {
  dom.brainModeControl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-brain-mode]");
    if (!button) return;
    setBrainMode(button.dataset.brainMode || "modal");
  });
  renderBrainModeControl();
}

dom.handToolButton?.addEventListener("click", () => {
  audio.unlock();
  setRoomToolMode("hand");
});

dom.foodToolButton?.addEventListener("click", () => {
  audio.unlock();
  setRoomToolMode("food");
});

dom.petToolButton?.addEventListener("click", () => {
  audio.unlock();
  setRoomToolMode("pet");
});

if (dom.demoButton) {
  dom.demoButton.addEventListener("click", () => {
    runJudgeDemo();
  });
}

if (dom.voiceButton) {
  dom.voiceButton.addEventListener("click", () => {
    audio.unlock();
    audio.setVoiceEnabled(!audio.voiceEnabled);
    updateVoiceButton();
    showToast(audio.voiceEnabled ? "Agent voices on." : "Agent voices muted.");
  });
}

if (dom.micButton) {
  dom.micButton.addEventListener("click", async () => {
    const enabled = await audio.setMicEnabled(!audio.micEnabled);
    updateMicButton();
    if (audio.micEnabled) {
      showToast("Agents can hear room audio.");
    } else if (!enabled && audio.micError) {
      showToast("Microphone not available.");
    } else {
      showToast("Room audio listening off.");
    }
  });
}

if (dom.rigButton) {
  dom.rigButton.addEventListener("click", () => {
    setRigMeshesVisible(!rigMeshesVisible);
    showToast(IS_V3_MODE
      ? "Fire Boy's generated rig is the live body."
      : (rigMeshesVisible ? "Generated rig meshes visible." : "Generated rig meshes hidden."));
  });
}

dom.gravityButton.addEventListener("click", () => {
  audio.unlock();
  flipGravity();
});

document.querySelectorAll(".agent-button").forEach((button) => {
  button.addEventListener("click", () => {
    audio.unlock();
    setActiveAgent(button.dataset.agent);
    if (!councilMode) updateModeButton();
  });
});

dom.canvas.addEventListener("pointerdown", onPointerDown);
window.addEventListener("pointermove", onPointerMove);
window.addEventListener("pointerup", onPointerUp);
window.addEventListener("pointercancel", onPointerCancel);
dom.canvas.addEventListener("lostpointercapture", (event) => {
  if (dragged && event.pointerId === dragPointerId) releaseDrag(event, { throwObject: false, skipPointerRelease: true });
});
window.addEventListener("blur", () => releaseDrag(null, { throwObject: false }));
window.addEventListener("resize", resize);

window.__toyboxV2Debug = {
  agents: () => [...agents.values()].map((agent) => ({ kind: agent.kind, position: vectorPayload(agent.pet.group.position), intent: agent.lastIntent })),
  activeAgentMotor: () => {
    const agent = activeAgent();
    return {
      kind: agent.kind,
      position: vectorPayload(agent.pet.group.position),
      rigPosition: vectorPayload(agent.rig.position()),
      facingYaw: Number((agent.pet.facingYaw || 0).toFixed(3)),
      targetFacingYaw: Number((agent.pet.targetFacingYaw || 0).toFixed(3)),
      animation: agent.pet.animation,
      locomotion: agent.locomotion ? {
        index: agent.locomotion.index,
        remainingMs: Math.max(0, Math.round(agent.locomotion.until - performance.now())),
        routeLength: agent.locomotion.route.length,
        speed: agent.locomotion.speed,
        walk: agent.locomotion.walk,
      } : null,
      heldObject: agent.heldObject?.entry?.id || "",
    };
  },
  petNeeds: () => ({ ...activeAgent().needs, energyState: activeAgent().energyState }),
  setPetNeeds: (values = {}) => {
    const agent = activeAgent();
    for (const key of ["hunger", "energy", "playfulness", "curiosity", "social"]) {
      if (Number.isFinite(Number(values[key]))) agent.needs[key] = clampNeed(Number(values[key]));
    }
    agent.energyState = Number(agent.needs.energy || 0) > 32 ? "ok" : agent.energyState;
    renderPetMeters(agent);
    return { ...agent.needs, energyState: agent.energyState };
  },
  sceneState: () => collectSceneState(activeAgent()),
  requestAll: (message = "improvise together") => [...agents.values()].forEach((agent) => requestAction(agent, message)),
  runDemo: () => runJudgeDemo(),
  demoState: () => ({ running: demoRunning, generatedObjects: objects.filter((entry) => entry.generated).length, autoplay }),
  brainTrace: () => activeAgent().lastTrace,
  visionState: () => ({
    applied: document.body.dataset.visionApplied || "",
    runtime: document.body.dataset.visionRuntime || "",
    trace: activeAgent().lastTrace?.vision || "",
  }),
  visionBoardState: () => ({
    ready: document.body.dataset.visionBoardReady || "",
    agents: Number(document.body.dataset.visionBoardAgents || 0),
    summary: document.body.dataset.visionBoardSummary || "",
    rows: [...agents.values()].map((agent) => {
      const seen = detectObjects(agent);
      return {
        kind: agent.kind,
        closest: seen[0]?.id || "",
        seen: seen.slice(0, 3).map((item) => item.kind),
        plan: agentVisionPlan(agent, seen),
      };
    }),
  }),
  councilState: () => ({
    count: councilVisionAgents.size,
    kinds: [...councilVisionAgents],
    runtime: document.body.dataset.councilRuntime || "",
  }),
  dialogueState: () => ({
    turns: dialogueTurns,
    last: document.body.dataset.lastDialogue || "",
    runtime: document.body.dataset.dialogueRuntime || "",
  }),
  learningState: () => ({
    score: Number(document.body.dataset.learningScore || 0),
    last: document.body.dataset.lastLearnedConcept || "",
    applied: document.body.dataset.memoryApplied || "",
    activeMemories: activeAgent().memories?.length || 0,
  }),
  trainingState: () => ({
    usableRows: Number(trainingStatus.usableRows || 0),
    totalRows: Number(trainingStatus.totalRows || 0),
    ready: Boolean(trainingStatus.ready),
    runtime: document.body.dataset.trainingRuntime || "",
    target: trainingStatus.target || "",
  }),
  aiEvidenceState: () => ({
    score: document.body.dataset.aiEvidenceScore || "",
    requiredScore: document.body.dataset.aiEvidenceRequiredScore || "",
    ready: document.body.dataset.aiEvidenceReady || "",
    runtime: document.body.dataset.aiRuntime || "",
    metrics: aiEvidence.metrics || {},
    checks: Array.isArray(aiEvidence.checks)
      ? aiEvidence.checks.map((check) => ({
        id: check.id,
        label: check.label,
        state: check.state,
        detail: check.detail,
        required: check.required !== false,
      }))
      : [],
  }),
  judgeState: () => ({
    score: document.body.dataset.judgeScore || "",
    requiredScore: document.body.dataset.judgeRequiredScore || "",
    ready: document.body.dataset.judgeReady || "",
    demoReady: document.body.dataset.judgeDemoReady || "",
    serverScore: document.body.dataset.judgeServerScore || "",
    serverReady: document.body.dataset.judgeServerReady || "",
    checks: combinedJudgeChecks().map((check) => ({
      id: check.id,
      label: check.label,
      state: check.state,
      detail: check.detail,
      required: check.required,
    })),
  }),
  motorState: () => ({
    actions: lowLevelActions,
    runtime: document.body.dataset.motorRuntime || "",
    last: document.body.dataset.lastLowLevelAction || "",
    autoplay,
  }),
  recycleState: () => ({
    score: recycledWasteIds.size,
    total: RECYCLABLE_WASTE_IDS.length,
    ids: [...recycledWasteIds],
    last: document.body.dataset.lastRecycled || "",
  }),
  rigState: () => ({
    visible: rigMeshesVisible,
    ready: [...agents.values()].filter((agent) => agent.rigStatus === "ready").length,
    agents: [...agents.values()].map((agent) => ({
      kind: agent.kind,
      status: agent.rigStatus,
      visible: Boolean(agent.rigVisual?.visible),
      skeleton: Boolean(agent.rigHelper),
      retarget: agent.rigRetarget ? {
        active: Boolean(agent.rigRetarget.active),
        frames: agent.rigRetarget.frames?.length || 0,
        skill: agent.rigRetarget.skill || "",
        task: agent.rigRetarget.task || "",
      } : null,
    })),
  }),
};

mountV3ViewDock();
resize();
maybeApplyUrlPetState();
maybeRunUrlCommand();
requestAnimationFrame(animate);
if (!IS_V3_MODE) {
  setTimeout(() => {
    for (const agent of agents.values()) requestAction(agent, "wake up, look around, and greet the other toys");
  }, 900);
}
