import * as THREE from "three";

export const PET_LOOKS = {
  squeaky: {
    label: "Squeaky",
    body: 0x8db6bd,
    belly: 0xc4dddd,
    accent: 0x123238,
    cheeks: 0xff9b69,
    power: 0x8bd5e5,
    eye: 0x241d16,
    petSounds: ["clock_chime", "soft_pop", "tick_tock", "happy_chirp"],
  },
  electraica: {
    label: "Electraica",
    body: 0xffcc36,
    belly: 0xfff3ca,
    accent: 0x8f7b55,
    cheeks: 0xff8d68,
    power: 0xfff071,
    eye: 0x302612,
    petSounds: ["spark", "bulb_ping", "happy_chirp"],
  },
  fire_boy: {
    label: "Fire Boy",
    body: 0xff684c,
    belly: 0xffefd6,
    accent: 0x1c1c1c,
    cheeks: 0xffb082,
    power: 0xff7347,
    eye: 0x24120d,
    petSounds: ["whoosh", "soft_pop", "happy_chirp"],
  },
  shark_girl: {
    label: "Shark Girl",
    body: 0x89d4e6,
    belly: 0xfff0d9,
    accent: 0xeebd7d,
    cheeks: 0xffa386,
    power: 0x75d7ea,
    eye: 0x1e2b30,
    petSounds: ["water_plink", "soft_pop", "happy_chirp"],
  },
};

export const FACE_BLENDSHAPE_KEYS = ["eye", "smile", "mouth", "brow", "cheek", "squash", "tilt", "sparkle"];

export const EMOTION_SHAPES = {
  happy: { eye: 0.95, smile: 0.7, mouth: 0.08, brow: 0, cheek: 0.75, squash: 0.05, tilt: 0, sparkle: 0.35 },
  curious: { eye: 1.05, smile: 0.34, mouth: 0.04, brow: 0.28, cheek: 0.65, squash: 0.0, tilt: -0.12, sparkle: 0.45 },
  surprised: { eye: 1.35, smile: -0.08, mouth: 0.7, brow: 0.45, cheek: 0.85, squash: -0.05, tilt: 0.08, sparkle: 0.85 },
  glee: { eye: 0.75, smile: 1.0, mouth: 0.2, brow: 0.1, cheek: 1.0, squash: 0.12, tilt: -0.04, sparkle: 1.0 },
  focused: { eye: 0.86, smile: 0.12, mouth: 0.02, brow: -0.55, cheek: 0.62, squash: -0.02, tilt: 0.0, sparkle: 0.18 },
  sleepy: { eye: 0.28, smile: 0.22, mouth: 0.04, brow: -0.08, cheek: 0.45, squash: 0.0, tilt: 0.13, sparkle: 0.05 },
  petted: { eye: 0.55, smile: 0.95, mouth: 0.1, brow: 0.18, cheek: 1.2, squash: 0.16, tilt: -0.18, sparkle: 0.95 },
  startled: { eye: 1.42, smile: -0.18, mouth: 0.56, brow: 0.75, cheek: 0.92, squash: -0.08, tilt: 0.18, sparkle: 0.9 },
  dizzy: { eye: 1.1, smile: 0.02, mouth: 0.25, brow: 0.35, cheek: 0.75, squash: -0.04, tilt: 0.24, sparkle: 0.15 },
  shy: { eye: 0.64, smile: 0.5, mouth: 0.03, brow: 0.15, cheek: 1.25, squash: 0.08, tilt: -0.1, sparkle: 0.4 },
};

export const POWER_COLORS = {
  time_freeze: 0x8bd5e5,
  shrink: 0xb4edf2,
  rewind: 0x9ed4ff,
  clock_bubble: 0x8bd5e5,
  shock: 0xfff071,
  magnet_pull: 0xffd855,
  lamp_burst: 0xffeb91,
  fireball: 0xff704d,
  ember_jump: 0xff9b45,
  smoke_poof: 0x9aa1a2,
  wave: 0x75d7ea,
  bubble_lift: 0x9aeaf5,
  tide_pull: 0x75d7ea,
};

export const POWER_BY_PET = {
  squeaky: ["time_freeze", "shrink", "rewind", "clock_bubble"],
  electraica: ["shock", "lamp_burst", "magnet_pull"],
  fire_boy: ["fireball", "ember_jump", "smoke_poof"],
  shark_girl: ["wave", "bubble_lift", "tide_pull"],
};

export function makeMat(color, options = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: options.roughness ?? 0.78,
    metalness: options.metalness ?? 0,
    emissive: options.emissive ?? 0x000000,
    emissiveIntensity: options.emissiveIntensity ?? 0,
    transparent: options.transparent ?? false,
    opacity: options.opacity ?? 1,
  });
}

export function makePlushMaterial(color, options = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = 96;
  canvas.height = 96;
  const ctx = canvas.getContext("2d");
  const base = new THREE.Color(color);
  ctx.fillStyle = `#${base.getHexString()}`;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < 900; i += 1) {
    const shade = 0.86 + Math.random() * 0.28;
    ctx.fillStyle = `rgba(${Math.round(base.r * 255 * shade)}, ${Math.round(base.g * 255 * shade)}, ${Math.round(base.b * 255 * shade)}, 0.18)`;
    ctx.fillRect(Math.random() * canvas.width, Math.random() * canvas.height, 1.3, 1.3);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3, 3);
  return new THREE.MeshStandardMaterial({
    color,
    map: texture,
    roughness: options.roughness ?? 0.92,
    metalness: 0,
    emissive: options.emissive ?? 0x000000,
    emissiveIntensity: options.emissiveIntensity ?? 0,
  });
}
