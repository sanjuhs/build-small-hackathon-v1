import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import * as CANNON from "cannon-es";
import {
  createIcons,
  Clock3,
  Flame,
  RotateCcw,
  ScanEye,
  Send,
  Sparkles,
  Waves,
  Zap
} from "https://cdn.jsdelivr.net/npm/lucide@0.468.0/+esm";

import { PET_LOOKS } from "./config.js";
import { ToyAudio } from "./audio.js";
import { ToyEffects } from "./effects.js";
import { applyPetBlendshape, createPet, disposePet, petPointerReaction, setPetEmotion, updatePet } from "./pet.js";
import { createPetBalanceRig } from "./pet_balance.js";
import { createPowerController } from "./powers.js";
import { createPhysicsWorld, createToyRoom } from "./room.js";
import { captureCameraFrame, collectSceneState as collectSceneStateFrom, detectObjects as detectObjectsFrom } from "./sensing.js";
import { createSenseFeeds } from "./senses.js";
import { getDom, ToyUi } from "./ui.js";

createIcons({ icons: { Clock3, Flame, RotateCcw, ScanEye, Send, Sparkles, Waves, Zap } });

const dom = getDom();
const ui = new ToyUi(dom);

const renderer = new THREE.WebGLRenderer({ canvas: dom.canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xfff6dd, 8, 22);

const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
camera.position.set(4.2, 3.4, 6.4);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 1.15, 0);
controls.enableDamping = true;
controls.minDistance = 4.2;
controls.maxDistance = 9.5;
controls.maxPolarAngle = Math.PI * 0.48;
controls.minPolarAngle = Math.PI * 0.18;

const audio = new ToyAudio();
const effects = new ToyEffects(scene);
const world = createPhysicsWorld();
const room = createToyRoom({ scene, world, ui, recordForce });
const balanceRig = createPetBalanceRig({ world, recordForce });
const senses = createSenseFeeds({ scene, userCamera: camera, userRenderer: renderer, dom, audio });
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const dragPlane = new THREE.Plane();
const dragHit = new THREE.Vector3();
const dragOffset = new THREE.Vector3();
const dragHistory = [];
const objects = room.objects;
const forceEvents = [];
const interactions = [];
const cooldowns = {};
const petNeeds = {
  hunger: 68,
  curiosity: 48,
  energy: 74,
  social: 42,
};

let pet = null;
let activePet = "squeaky";
let dragged = null;
let dragPointerId = null;
let hoverPet = false;
let autoplay = true;
let lastAutoAction = 0;
let lastPhysicsTime = performance.now();
let lastPetRequestAt = 0;

const powerController = createPowerController({
  audio,
  bodyHistory: room.bodyHistory,
  effects,
  frozenBodies: room.frozenBodies,
  getActivePet: () => activePet,
  getPet: () => pet,
  lights: room.lights,
  nearestObject: () => room.nearestObject(pet),
  objects,
  ui,
});

function switchPet(kind) {
  disposePet(pet, scene);
  activePet = kind;
  pet = createPet(activePet, scene);
  balanceRig.setPet(pet, activePet);
  senses.setPet(pet);
  dom.perceptionTitle.textContent = `${pet.label} sees`;
  ui.showSpeech(`${pet.label} hopped into the room.`);
  audio.play("happy_chirp", 0.75);
}

function pointerToNdc(event) {
  const rect = dom.canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function onPointerDown(event) {
  audio.unlock();
  if (dragged) return;
  pointerToNdc(event);
  raycaster.setFromCamera(pointer, camera);
  const petHit = pet && raycaster.intersectObjects(pet.hitMeshes, false)[0];
  if (petHit) {
    beginPetDrag(event, petHit.point);
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
    pointerId: dragPointerId,
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
  setPetEmotion(pet, "curious");
}

function beginPetDrag(event, hitPoint) {
  event.preventDefault();
  dragPointerId = event.pointerId;
  try {
    dom.canvas.setPointerCapture(dragPointerId);
  } catch {}
  dragPlane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(new THREE.Vector3()).normalize(), hitPoint);
  dragOffset.copy(pet.group.position).sub(hitPoint);
  dragged = {
    kind: "pet",
    pointerId: dragPointerId,
    plane: dragPlane.clone(),
    offset: dragOffset.clone(),
    startClient: { x: event.clientX, y: event.clientY },
    startPoint: hitPoint.clone(),
    touchType: event.altKey ? "poke" : "pet",
    moved: false,
  };
  dragHistory.length = 0;
  dragHistory.push({ t: performance.now(), x: pet.group.position.x, y: pet.group.position.y, z: pet.group.position.z });
  controls.enabled = false;
  dom.canvas.classList.add("dragging");
  setPetEmotion(pet, "curious");
}

function onPointerMove(event) {
  if (dragged && event.pointerId !== dragPointerId) return;
  pointerToNdc(event);
  raycaster.setFromCamera(pointer, camera);
  if (!dragged) {
    const isHoveringPet = pet && raycaster.intersectObjects(pet.hitMeshes, false).length > 0;
    if (isHoveringPet !== hoverPet) {
      hoverPet = isHoveringPet;
      petPointerReaction(pet, hoverPet ? "hover" : "leave");
      dom.canvas.classList.toggle("pet-hover", hoverPet);
      if (hoverPet) {
        applyPetBlendshape(pet, { eye: 1.18, smile: 0.54, brow: 0.36, cheek: 0.98, tilt: -0.1, sparkle: 1.1 });
        effects.stars(pet.group.position.clone().add(new THREE.Vector3(0, 1.55, 0.2)), PET_LOOKS[activePet].power, 8);
      }
    }
    return;
  }

  if (dragged.kind === "pet") {
    updatePetDrag(event);
    return;
  }
  updateObjectDrag();
}

function updateObjectDrag() {
  if (!raycaster.ray.intersectPlane(dragged.plane, dragHit)) return;
  const entry = dragged.entry;
  const next = clampObjectPosition(dragHit.clone().add(dragged.offset), entry);
  entry.body.position.set(next.x, next.y, next.z);
  entry.body.velocity.set(0, 0, 0);
  entry.body.angularVelocity.set(0, 0, 0);
  dragHistory.push({ t: performance.now(), x: next.x, y: next.y, z: next.z });
  while (dragHistory.length > 5) dragHistory.shift();
}

function updatePetDrag(event) {
  const movedPixels = Math.hypot(event.clientX - dragged.startClient.x, event.clientY - dragged.startClient.y);
  if (movedPixels > 6) dragged.moved = true;
  if (!dragged.moved) return;
  if (!raycaster.ray.intersectPlane(dragged.plane, dragHit)) return;
  const next = clampPetPosition(dragHit.clone().add(dragged.offset));
  balanceRig.moveTo(new CANNON.Vec3(next.x, next.y, next.z));
  dragHistory.push({ t: performance.now(), x: next.x, y: next.y, z: next.z });
  while (dragHistory.length > 5) dragHistory.shift();
}

function clampObjectPosition(position, entry) {
  const halfY = entry.size.y / 2;
  return new THREE.Vector3(
    THREE.MathUtils.clamp(position.x, -3.9, 3.9),
    THREE.MathUtils.clamp(position.y, halfY + 0.06, 3.35),
    THREE.MathUtils.clamp(position.z, -2.9, 2.9),
  );
}

function clampPetPosition(position) {
  return new THREE.Vector3(
    THREE.MathUtils.clamp(position.x, -3.2, 3.2),
    THREE.MathUtils.clamp(position.y, 0.06, 1.55),
    THREE.MathUtils.clamp(position.z, -2.25, 2.65),
  );
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
  if (dragged.kind === "pet") {
    releasePetDrag(event, { skipPointerRelease });
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
      ((last.x - first.x) / dt) * 540,
      THREE.MathUtils.clamp(((last.y - first.y) / dt) * 420 + 0.65, -1.4, 5.2),
      ((last.z - first.z) / dt) * 540,
    );
    recordForce({ kind: "throw", objectId: entry.id, impact: 0.75 });
    audio.play("startle", 0.8);
    setPetEmotion(pet, "startled");
  } else {
    entry.body.velocity.set(0, 0.2, 0);
  }
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

function releasePetDrag(event, { skipPointerRelease = false } = {}) {
  const wasMoved = Boolean(dragged.moved);
  const placed = dragHistory[dragHistory.length - 1] || { x: pet.group.position.x, y: pet.group.position.y, z: pet.group.position.z };
  if (wasMoved) {
    balanceRig.moveTo(new CANNON.Vec3(placed.x, 0.06, placed.z), { settleOnFloor: true });
    recordInteraction({ kind: "pet_move", pet: activePet, pointer: pointerSnapshot(event, new THREE.Vector3(placed.x, placed.y, placed.z)) });
    ui.showSpeech(`${pet.label} stands right there.`);
    audio.play("soft_pop", 0.72);
  } else {
    handlePetTouch(dragged.touchType, event, dragged.startPoint);
  }
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

function bodyToVector(position) {
  return new THREE.Vector3(position.x, position.y, position.z);
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

function handlePetTouch(type, event, worldPoint) {
  petPointerReaction(pet, type);
  const position = pet.group.position.clone().add(new THREE.Vector3(0, 1.3, 0.35));
  effects.hearts(position, PET_LOOKS[activePet].cheeks, type === "pet" ? 9 : 5);
  audio.play(type === "pet" ? "pet_touch" : "startle", 0.9);
  if (type === "pet") audio.play("purr", 0.5);
  const pointerEvent = pointerSnapshot(event, worldPoint);
  recordInteraction({ kind: type, pet: activePet, pointer: pointerEvent });
  ui.showSpeech(type === "pet" ? `${pet.label} wiggles happily.` : `${pet.label} made a tiny squeak.`);
  const now = performance.now();
  if (now - lastPetRequestAt > 3200) {
    lastPetRequestAt = now;
    const modality = pointerEvent.modality === "touch" ? "finger" : pointerEvent.modality;
    requestAction(type === "pet" ? `the user gently petted you with a ${modality}` : `the user poked you by surprise with a ${modality}`);
  }
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

function collectSceneState() {
  return collectSceneStateFrom(activePet, pet, objects, balanceRig.state(), normalizedNeeds());
}

function detectObjects() {
  return detectObjectsFrom(pet, objects);
}

async function requestAction(message = "") {
  const petFrame = senses.capturePetFrame();
  const payload = {
    pet: activePet,
    message,
    scene: collectSceneState(),
    forces: forceEvents.slice(-10),
    interactions: interactions.slice(-8),
    detectedObjects: detectObjects(),
    cameraFrame: petFrame || captureCameraFrame(renderer),
    cameraFrameSource: petFrame ? "pet-view" : "user-view",
    audio: senses.audioSummary(),
    cooldowns
  };

  try {
    const response = await fetch("/api/pet-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    applyPetAction(await response.json());
  } catch {
    ui.showToast("The pet brain blinked. Fallback stayed nearby.");
    applyPetAction({
      pet: activePet,
      speech: "I had a tiny thought anyway.",
      emotion: "curious",
      animation: "bounce",
      power: { name: activePet === "squeaky" ? "clock_bubble" : "shock", targetId: "all-moving", strength: 0.7, durationMs: 1500 },
      sound: "soft_pop"
    });
  }
}

function applyPetAction(action) {
  setPetEmotion(pet, action.emotion || "happy");
  applyPetBlendshape(pet, action.blendshape);
  pet.animation = action.animation || "bounce";
  pet.actionUntil = performance.now() + 1800;
  ui.showSpeech(action.speech);
  audio.play(action.sound || "happy_chirp", 0.85);
  const interactionApplied = executePetInteraction(action.interaction);
  if (!interactionApplied) powerController.apply(action.power);
}

function executePetInteraction(interaction = {}) {
  const verb = interaction?.verb || "none";
  if (verb === "none") return false;
  const target = objects.find((entry) => entry.id === interaction.targetId) || room.nearestObject(pet);
  if (!target) return false;
  movePetNearObject(target);
  recordInteraction({ kind: verb, pet: activePet, objectId: target.id, objectKind: target.kind });

  if (verb === "eat") {
    eatObject(target);
    return true;
  }
  if (verb === "read") {
    setPetEmotion(pet, "focused");
    pet.animation = activePet === "squeaky" ? "trunk_wiggle" : "look_left_right";
    pet.actionUntil = performance.now() + Number(interaction.durationMs || 2800);
    petNeeds.curiosity = clampNeed(petNeeds.curiosity - Number(target.curiosity || 18));
    petNeeds.energy = clampNeed(petNeeds.energy - 3);
    effects.stars(bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.32, 0)), PET_LOOKS[activePet].power, 12);
    audio.play("curious_hm", 0.74);
    return true;
  }
  if (verb === "sit" || verb === "gather") {
    setPetEmotion(pet, "happy");
    pet.animation = "bounce";
    pet.actionUntil = performance.now() + Number(interaction.durationMs || 2200);
    petNeeds.energy = clampNeed(petNeeds.energy + Number(target.comfort || 8));
    petNeeds.social = clampNeed(petNeeds.social + Number(target.social || 10));
    effects.hearts(pet.group.position.clone().add(new THREE.Vector3(0, 1.25, 0.16)), PET_LOOKS[activePet].cheeks, 5);
    return true;
  }
  if (verb === "sniff" || verb === "inspect" || verb === "water") {
    setPetEmotion(pet, "curious");
    pet.animation = "look_left_right";
    pet.actionUntil = performance.now() + Number(interaction.durationMs || 1800);
    petNeeds.curiosity = clampNeed(petNeeds.curiosity - Number(target.curiosity || 8));
    effects.stars(bodyToVector(target.body.position).add(new THREE.Vector3(0, 0.5, 0)), PET_LOOKS[activePet].power, 9);
    return true;
  }
  return false;
}

function eatObject(target) {
  const bitePosition = bodyToVector(target.body.position);
  setPetEmotion(pet, "glee");
  pet.animation = activePet === "squeaky" ? "tiny_scamper" : "bounce";
  pet.actionUntil = performance.now() + 2200;
  effects.hearts(bitePosition.clone().add(new THREE.Vector3(0, 0.24, 0)), PET_LOOKS[activePet].cheeks, 7);
  effects.stars(bitePosition.clone().add(new THREE.Vector3(0, 0.32, 0)), PET_LOOKS[activePet].power, 10);
  setTimeout(() => {
    const eaten = room.consumeObject(target.id);
    if (!eaten) return;
    petNeeds.hunger = clampNeed(petNeeds.hunger - Number(eaten.nutrition || 28));
    petNeeds.energy = clampNeed(petNeeds.energy + 8);
    petNeeds.social = clampNeed(petNeeds.social + 2);
    audio.play("tiny_giggle", 0.68);
  }, 560);
}

function movePetNearObject(target) {
  if (!pet || !target) return;
  const targetPosition = bodyToVector(target.body.position);
  const fromTarget = pet.group.position.clone().sub(targetPosition);
  fromTarget.y = 0;
  if (fromTarget.lengthSq() < 0.01) fromTarget.set(0, 0, 1);
  fromTarget.normalize().multiplyScalar(Math.max(0.68, target.radius + 0.46));
  const next = clampPetPosition(targetPosition.clone().add(fromTarget));
  balanceRig.moveTo(new CANNON.Vec3(next.x, 0.06, next.z), { settleOnFloor: true });
}

function recordForce(event) {
  forceEvents.push({ ...event, at: Date.now() });
  while (forceEvents.length > 18) forceEvents.shift();
}

function recordInteraction(event) {
  interactions.push({ ...event, at: Date.now() });
  while (interactions.length > 18) interactions.shift();
}

function updatePetNeeds(dt) {
  petNeeds.hunger = clampNeed(petNeeds.hunger + dt * 0.72);
  petNeeds.curiosity = clampNeed(petNeeds.curiosity + dt * 0.22);
  petNeeds.energy = clampNeed(petNeeds.energy - dt * 0.08);
  petNeeds.social = clampNeed(petNeeds.social + dt * 0.05);
}

function normalizedNeeds() {
  return {
    hunger: clampNeed(petNeeds.hunger),
    curiosity: clampNeed(petNeeds.curiosity),
    energy: clampNeed(petNeeds.energy),
    social: clampNeed(petNeeds.social),
  };
}

function clampNeed(value) {
  return Number(THREE.MathUtils.clamp(Number(value) || 0, 0, 100).toFixed(1));
}

function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  senses.resize();
}

function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min((now - lastPhysicsTime) / 1000, 0.033);
  lastPhysicsTime = now;
  updatePetNeeds(dt);
  controls.update();
  balanceRig.beforeStep(now, dt);
  room.updatePhysics(now, dt);
  balanceRig.afterStep(pet, now, dt);
  updatePet(pet, now, dt);
  effects.update(now, dt);
  ui.updatePerception(detectObjects());
  renderer.render(scene, camera);
  senses.update(pet, now, balanceRig.state());
  if (autoplay && now - lastAutoAction > 11500) {
    lastAutoAction = now;
    const recent = forceEvents.some((event) => Date.now() - event.at < 5000) || interactions.some((event) => Date.now() - event.at < 5000);
    if (recent || Math.random() > 0.46) requestAction("");
  }
}

dom.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  audio.unlock();
  const message = dom.input.value.trim();
  dom.input.value = "";
  requestAction(message);
});

dom.resetButton.addEventListener("click", () => {
  audio.unlock();
  releaseDrag(null, { throwObject: false });
  Object.assign(petNeeds, { hunger: 68, curiosity: 48, energy: 74, social: 42 });
  room.resetRoom();
});

dom.autoButton.addEventListener("click", () => {
  audio.unlock();
  autoplay = !autoplay;
  dom.autoButton.classList.toggle("active", autoplay);
  ui.showToast(autoplay ? "Autoplay awake." : "Autoplay resting.");
});

document.querySelectorAll(".pet-button").forEach((button) => {
  button.addEventListener("click", () => {
    audio.unlock();
    document.querySelectorAll(".pet-button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    switchPet(button.dataset.pet);
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

window.__toyboxDebug = {
  activeDrag: () => dragged ? { kind: dragged.kind, pointerId: dragged.pointerId, moved: Boolean(dragged.moved) } : null,
  sceneState: () => collectSceneState(),
};

switchPet(activePet);
room.resetRoom();
resize();
ui.updateModelStatus();
requestAnimationFrame(animate);
setTimeout(() => requestAction("wake up and inspect the toy room"), 900);
