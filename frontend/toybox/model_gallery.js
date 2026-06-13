import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
  createIcons,
  Clock3,
  Flame,
  RotateCcw,
  Sparkles,
  Waves,
  Zap
} from "https://cdn.jsdelivr.net/npm/lucide@0.468.0/+esm";

import { PET_LOOKS, POWER_BY_PET } from "./config.js";
import { applyPetBlendshape, createPet, disposePet, setPetEmotion, updatePet } from "./pet.js";

createIcons({ icons: { Clock3, Flame, RotateCcw, Sparkles, Waves, Zap } });

const MODEL_NOTES = {
  squeaky: {
    kind: "Time elephant",
    body: "rounded plush elephant, wide ears, soft trunk rings",
    gear: "bowler hat, suit panels, tie, backpack, readable pocket watch",
    copy: "The detailed pass leans into the tiny timekeeper idea: larger ears, a cleaner trunk silhouette, a full suit front, and clock hardware that still reads at game distance.",
  },
  electraica: {
    kind: "Electric helper",
    body: "helmeted plush robot shape with warm cream face panel",
    gear: "glowing bulb, screw base, side coils, battery pack, chest mark",
    copy: "Electraica now has the appliance-toy language from the reference: bulb, coil ears, battery pack, and little tool-like arms while keeping the soft character proportions.",
  },
  fire_boy: {
    kind: "Flame performer",
    body: "layered flame hood, rounded mascot body, cream face inset",
    gear: "dark jacket, tie, extinguisher tank, hose, small recorder",
    copy: "Fire Boy gets a stronger flame silhouette and more safety-performer props, so the character reads as fire-themed without losing the cute plush form.",
  },
  shark_girl: {
    kind: "Ocean musician",
    body: "shark hood, dorsal fin, side fins, soft tail",
    gear: "starfish clip, bow, pearl, detailed ukulele with strings",
    copy: "Shark Girl now has a clearer ocean costume and musical prop: fin shapes around the body, a starfish accent, and a proper ukulele instead of a single capsule.",
  },
};

const dom = {
  canvas: document.getElementById("modelStage"),
  title: document.getElementById("detailTitle"),
  kind: document.getElementById("detailKind"),
  copy: document.getElementById("detailCopy"),
  body: document.getElementById("detailBody"),
  gear: document.getElementById("detailGear"),
  powers: document.getElementById("detailPowers"),
};

const renderer = new THREE.WebGLRenderer({ canvas: dom.canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xfff7e4, 8, 18);

const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
camera.position.set(3.1, 2.2, 5.2);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 1.25, 0);
controls.enableDamping = true;
controls.autoRotate = false;
controls.autoRotateSpeed = 0.85;
controls.minDistance = 2.7;
controls.maxDistance = 7.2;
controls.maxPolarAngle = Math.PI * 0.55;
controls.minPolarAngle = Math.PI * 0.12;

const floor = new THREE.Mesh(
  new THREE.CylinderGeometry(1.72, 1.92, 0.08, 96),
  new THREE.MeshStandardMaterial({ color: 0xfff3da, roughness: 0.86 }),
);
floor.position.y = -0.02;
floor.receiveShadow = true;
scene.add(floor);

const backDisc = new THREE.Mesh(
  new THREE.CircleGeometry(2.8, 96),
  new THREE.MeshBasicMaterial({ color: 0xe9f7f7, transparent: true, opacity: 0.56 }),
);
backDisc.position.set(0, 1.6, -1.08);
scene.add(backDisc);

const hemi = new THREE.HemisphereLight(0xffffff, 0x8cb5b8, 2.2);
scene.add(hemi);

const key = new THREE.DirectionalLight(0xffffff, 2.6);
key.position.set(3.5, 4.4, 4.2);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
scene.add(key);

const rim = new THREE.DirectionalLight(0x8bd5e5, 1.2);
rim.position.set(-3.2, 2.1, -2.4);
scene.add(rim);

let pet = null;
let activePet = "squeaky";
let activeView = "front";
let lastTime = performance.now();

document.querySelectorAll(".pet-button").forEach((button) => {
  const look = PET_LOOKS[button.dataset.pet] || PET_LOOKS.squeaky;
  const swatch = button.querySelector(".swatch");
  if (swatch) swatch.style.background = `#${look.body.toString(16).padStart(6, "0")}`;
  button.addEventListener("click", () => switchPet(button.dataset.pet));
});

document.querySelectorAll(".view-button").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

function switchPet(kind) {
  disposePet(pet, scene);
  activePet = kind;
  pet = createPet(activePet, scene);
  pet.group.position.set(0, 0.02, 0);
  pet.group.scale.setScalar(activePet === "squeaky" ? 1.02 : 1.08);
  setPetEmotion(pet, "glee");
  applyPetBlendshape(pet, { eye: 0.78, smile: 0.98, cheek: 1.08, sparkle: 0.9 });

  document.querySelectorAll(".pet-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.pet === activePet);
  });
  updateDetails(activePet);
  const params = new URLSearchParams(window.location.search);
  params.set("pet", activePet);
  history.replaceState(null, "", `${window.location.pathname}?${params}`);
}

function updateDetails(kind) {
  const look = PET_LOOKS[kind] || PET_LOOKS.squeaky;
  const notes = MODEL_NOTES[kind] || MODEL_NOTES.squeaky;
  dom.kind.textContent = notes.kind;
  dom.title.textContent = look.label;
  dom.copy.textContent = notes.copy;
  dom.body.textContent = notes.body;
  dom.gear.textContent = notes.gear;
  dom.powers.replaceChildren(...POWER_BY_PET[kind].map((name) => {
    const chip = document.createElement("span");
    chip.className = "power-chip";
    chip.textContent = name.replaceAll("_", " ");
    return chip;
  }));
}

function setView(view) {
  activeView = view;
  configureViewportCamera();
  document.querySelectorAll(".view-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  controls.autoRotate = view === "reset";
  const compact = isCompactViewport();
  const distance = compact ? 8.4 : 5.2;
  const sideDistance = compact ? 8.0 : 5.0;
  const resetDistance = compact ? 7.4 : 5.2;
  const target = new THREE.Vector3(0, compact ? 1.34 : 1.25, 0);
  const positions = {
    front: new THREE.Vector3(0, compact ? 1.9 : 1.75, distance),
    side: new THREE.Vector3(sideDistance, compact ? 1.95 : 1.85, 0.12),
    back: new THREE.Vector3(0, compact ? 1.9 : 1.8, -distance),
    reset: new THREE.Vector3(compact ? 4.3 : 3.1, compact ? 2.55 : 2.2, resetDistance),
  };
  camera.position.copy(positions[view] || positions.reset);
  controls.target.copy(target);
  controls.update();
}

function isCompactViewport() {
  return window.innerWidth < 700;
}

function configureViewportCamera() {
  const compact = isCompactViewport();
  camera.fov = compact ? 44 : 36;
  controls.minDistance = compact ? 4.8 : 2.7;
  controls.maxDistance = compact ? 10.2 : 7.2;
}

function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  configureViewportCamera();
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  if (!controls.autoRotate) setView(activeView);
}

function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min((now - lastTime) / 1000, 0.033);
  lastTime = now;
  controls.update();
  if (pet) updatePet(pet, now, dt);
  renderer.render(scene, camera);
}

window.addEventListener("resize", resize);

const requestedPet = new URLSearchParams(window.location.search).get("pet");
switchPet(PET_LOOKS[requestedPet] ? requestedPet : activePet);
setView("front");
resize();
requestAnimationFrame(animate);
