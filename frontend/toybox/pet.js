import * as THREE from "three";
import { EMOTION_SHAPES, FACE_BLENDSHAPE_KEYS, PET_LOOKS, makeMat, makePlushMaterial } from "./config.js";

export function createPet(kind, scene) {
  const look = PET_LOOKS[kind] || PET_LOOKS.squeaky;
  const group = new THREE.Group();
  group.position.set(0, 0.06, 1.02);
  scene.add(group);

  const plush = makePlushMaterial(look.body);
  const belly = makePlushMaterial(look.belly, { roughness: 0.9 });
  const accent = makeMat(look.accent, { roughness: 0.64 });
  const powerMat = makeMat(look.power, { emissive: look.power, emissiveIntensity: 0.16 });

  const parts = {};
  parts.body = meshSphere(0.78, plush, [0, 0.86, 0], [1.0, 0.9, 1.06]);
  parts.head = meshSphere(0.62, plush, [0, 1.72, 0.02], [1.07, 0.98, 0.95]);
  parts.belly = meshSphere(0.36, belly, [0, 0.93, 0.53], [1.02, 0.7, 0.16]);
  group.add(parts.body, parts.head, parts.belly);

  addLimbs(group, parts, plush);
  addPetSpecifics(kind, group, parts, plush, accent, powerMat, look);

  parts.face = createFace(look);
  parts.face.mesh.position.set(0, 1.79, 0.61);
  group.add(parts.face.mesh);

  const pet = {
    kind,
    label: look.label,
    look,
    group,
    parts,
    hitMeshes: meshesIn(group),
    basePosition: group.position.clone(),
    balanceTilt: { x: 0, y: 0, z: 0 },
    balanceState: null,
    targetScale: 1,
    actionUntil: 0,
    animation: "bounce",
    hovered: false,
    touchedUntil: 0,
    lastPettedAt: 0,
    face: {
      current: { ...EMOTION_SHAPES.happy },
      target: { ...EMOTION_SHAPES.happy },
      lastDraw: "",
    },
  };
  setPetEmotion(pet, "happy");
  drawFace(pet, true);
  return pet;
}

export function disposePet(pet, scene) {
  if (!pet) return;
  scene.remove(pet.group);
  pet.group.traverse((node) => {
    if (node.geometry) node.geometry.dispose();
    if (node.material) {
      if (node.material.map) node.material.map.dispose();
      node.material.dispose();
    }
  });
}

export function setPetEmotion(pet, emotion) {
  pet.emotion = EMOTION_SHAPES[emotion] ? emotion : "happy";
  pet.face.target = { ...EMOTION_SHAPES[pet.emotion] };
}

export function applyPetBlendshape(pet, blendshape = {}) {
  if (!pet || !blendshape || typeof blendshape !== "object") return;
  for (const key of FACE_BLENDSHAPE_KEYS) {
    if (Number.isFinite(Number(blendshape[key]))) {
      pet.face.target[key] = THREE.MathUtils.clamp(Number(blendshape[key]), -1.5, 1.5);
    }
  }
}

export function petPointerReaction(pet, type) {
  const now = performance.now();
  if (type === "hover") {
    pet.hovered = true;
    if (now > pet.actionUntil) setPetEmotion(pet, "curious");
    return;
  }
  if (type === "leave") {
    pet.hovered = false;
    if (now > pet.touchedUntil) setPetEmotion(pet, "happy");
    return;
  }
  if (type === "pet") {
    pet.lastPettedAt = now;
    pet.touchedUntil = now + 1400;
    pet.actionUntil = now + 900;
    pet.animation = "nuzzle";
    pet.targetScale = 1.05;
    setPetEmotion(pet, "petted");
    return;
  }
  if (type === "poke") {
    pet.touchedUntil = now + 1000;
    pet.actionUntil = now + 900;
    pet.animation = "startle";
    setPetEmotion(pet, "startled");
  }
}

export function updatePet(pet, now, dt) {
  if (!pet) return;
  const pulse = Math.sin(now * 0.004);
  const basePosition = pet.basePosition || new THREE.Vector3(0, 0.06, 1.02);
  const balanceTilt = pet.balanceTilt || { x: 0, y: 0, z: 0 };
  const shape = pet.face.current;
  lerpShape(shape, pet.face.target, 0.14);
  drawFace(pet);

  const actionActive = pet.actionUntil > now;
  const touchActive = pet.touchedUntil > now;
  const squash = shape.squash;
  const baseScale = pet.targetScale * (1 + pulse * 0.008);
  pet.group.scale.lerp(new THREE.Vector3(baseScale * (1 + squash * 0.18), baseScale * (1 - squash * 0.16), baseScale), 0.09);
  pet.group.position.y = basePosition.y + pulse * 0.028 * pet.targetScale;
  pet.group.position.z = THREE.MathUtils.lerp(pet.group.position.z, basePosition.z, 0.08);
  pet.group.rotation.x = THREE.MathUtils.lerp(pet.group.rotation.x, balanceTilt.x, 0.08);
  pet.group.rotation.z = THREE.MathUtils.lerp(
    pet.group.rotation.z,
    balanceTilt.z + shape.tilt + Math.sin(now * 0.0019) * 0.025,
    0.08,
  );

  pet.parts.head.rotation.z = THREE.MathUtils.lerp(pet.parts.head.rotation.z, shape.tilt * 0.45, 0.1);
  pet.parts.face.mesh.rotation.z = pet.parts.head.rotation.z;
  pet.parts.belly.scale.z = THREE.MathUtils.lerp(pet.parts.belly.scale.z, 0.16 + shape.squash * 0.025, 0.08);

  if (pet.parts.leftEar) {
    const earWiggle = Math.sin(now * 0.006) * 0.04 + (actionActive ? Math.sin(now * 0.026) * 0.08 : 0);
    pet.parts.leftEar.rotation.z = earWiggle;
    pet.parts.rightEar.rotation.z = -earWiggle;
  }
  if (pet.parts.powerGlow) {
    pet.parts.powerGlow.material.emissiveIntensity = 0.18 + Math.max(0, shape.cheek - 0.6) * 0.35 + (actionActive ? Math.sin(now * 0.018) * 0.2 + 0.25 : 0);
  }
  if (pet.parts.trunk) pet.parts.trunk.rotation.z = Math.sin(now * 0.006) * 0.08 + (actionActive ? Math.sin(now * 0.026) * 0.1 : 0);
  if (pet.parts.bulbHalo) pet.parts.bulbHalo.rotation.z += dt * 0.65;
  if (pet.parts.flameOuter) {
    const flameScale = 1 + Math.sin(now * 0.011) * 0.035 + (actionActive ? 0.05 : 0);
    pet.parts.flameOuter.scale.set(flameScale, 1 + Math.sin(now * 0.014) * 0.045, flameScale);
    pet.parts.flameInner.scale.set(0.72 + Math.sin(now * 0.013) * 0.025, 0.86 + Math.sin(now * 0.017) * 0.04, 0.72);
  }
  if (pet.parts.tail) pet.parts.tail.rotation.y = Math.sin(now * 0.004) * 0.16 + (actionActive ? Math.sin(now * 0.018) * 0.16 : 0);
  if (pet.parts.ukulele) pet.parts.ukulele.rotation.z = -0.72 + Math.sin(now * 0.004) * 0.025;

  if (actionActive && pet.animation?.includes("spin")) pet.group.rotation.y += dt * 4.4;
  else if (actionActive && (pet.animation?.includes("wiggle") || pet.animation?.includes("sway"))) pet.group.rotation.y = balanceTilt.y + Math.sin(now * 0.02) * 0.16;
  else if (actionActive && pet.animation?.includes("scamper")) pet.group.position.x = basePosition.x + Math.sin(now * 0.016) * 0.18;
  else if (actionActive && pet.animation === "nuzzle") pet.group.rotation.y = balanceTilt.y + Math.sin(now * 0.02) * 0.12;
  else if (actionActive && pet.animation === "startle") pet.group.position.x = basePosition.x + Math.sin(now * 0.045) * 0.08;
  else pet.group.rotation.y = THREE.MathUtils.lerp(pet.group.rotation.y, balanceTilt.y + Math.sin(now * 0.0009) * 0.05, 0.05);

  if (!actionActive) pet.group.position.x = THREE.MathUtils.lerp(pet.group.position.x, basePosition.x, 0.04);
  if (!touchActive && !pet.hovered && pet.emotion === "petted") setPetEmotion(pet, "happy");
  if (pet.targetScale !== 1 && !actionActive) pet.targetScale = THREE.MathUtils.lerp(pet.targetScale, 1, 0.05);
}

function addLimbs(group, parts, plush) {
  parts.leftArm = meshSphere(0.22, plush, [-0.5, 0.77, 0.38], [0.72, 1.06, 0.72]);
  parts.rightArm = meshSphere(0.22, plush, [0.5, 0.77, 0.38], [0.72, 1.06, 0.72]);
  parts.leftFoot = meshSphere(0.24, plush, [-0.34, 0.13, 0.28], [1.08, 0.68, 0.9]);
  parts.rightFoot = meshSphere(0.24, plush, [0.34, 0.13, 0.28], [1.08, 0.68, 0.9]);
  group.add(parts.leftArm, parts.rightArm, parts.leftFoot, parts.rightFoot);
}

function addPetSpecifics(kind, group, parts, plush, accent, powerMat, look) {
  const faceMat = makePlushMaterial(look.belly, { roughness: 0.9 });
  const darkAccent = makeMat(look.accent, { roughness: 0.72 });
  const cream = makeMat(0xfff5df, { roughness: 0.82 });
  const stitch = makeMat(0x6d4c35, { roughness: 0.88 });

  if (kind === "squeaky") {
    parts.leftEar = meshSphere(0.38, plush, [-0.68, 1.74, -0.03], [0.86, 0.24, 1.22]);
    parts.rightEar = meshSphere(0.38, plush, [0.68, 1.74, -0.03], [0.86, 0.24, 1.22]);
    const leftInnerEar = meshSphere(0.27, faceMat, [-0.69, 1.72, 0.02], [0.78, 0.13, 0.98]);
    const rightInnerEar = meshSphere(0.27, faceMat, [0.69, 1.72, 0.02], [0.78, 0.13, 0.98]);

    const trunk = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.48, 8, 24), plush);
    trunk.position.set(0, 1.45, 0.78);
    trunk.rotation.x = Math.PI / 2.35;
    trunk.castShadow = true;
    parts.trunk = trunk;

    const trunkRingMat = makeMat(0x77a5ad, { roughness: 0.82 });
    const trunkRings = [-0.1, 0.06, 0.21].map((z, index) => {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.125 - index * 0.011, 0.009, 8, 28), trunkRingMat);
      ring.position.set(0, 1.47 - index * 0.03, 0.75 + z);
      ring.rotation.x = Math.PI / 2.35;
      ring.castShadow = true;
      return ring;
    });

    const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.46, 0.1, 48), accent);
    brim.position.set(0, 2.26, 0);
    const dome = meshSphere(0.32, accent, [0, 2.36, 0], [1, 1, 0.62]);
    const hatBand = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.36, 0.048, 48), makeMat(0x0d2227, { roughness: 0.66 }));
    hatBand.position.set(0, 2.29, 0);

    const jacketMat = makeMat(0x153f48, { roughness: 0.86 });
    const jacketLeft = meshBox([0.44, 0.52, 0.055], jacketMat, [-0.19, 0.94, 0.69], [0, 0, -0.16]);
    const jacketRight = meshBox([0.44, 0.52, 0.055], jacketMat, [0.19, 0.94, 0.69], [0, 0, 0.16]);
    const leftCollar = meshTriangle(0.24, 0.24, cream, [-0.12, 1.23, 0.735], -0.28);
    const rightCollar = meshTriangle(0.24, 0.24, cream, [0.12, 1.23, 0.735], 0.28);
    const tieTop = meshBox([0.085, 0.1, 0.04], darkAccent, [0, 1.12, 0.765], [0, 0, Math.PI / 4]);
    const tie = meshBox([0.09, 0.28, 0.035], darkAccent, [0, 0.96, 0.765], [0, 0, 0]);
    const backpack = meshBox([0.48, 0.58, 0.32], makeMat(0x9e7239, { roughness: 0.88 }), [-0.62, 0.96, -0.34], [0, -0.12, 0]);
    const strap = meshBox([0.08, 0.64, 0.04], darkAccent, [-0.41, 0.99, 0.42], [0, 0, -0.08]);

    const clockRim = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.022, 10, 36), powerMat);
    clockRim.position.set(0.47, 1.04, 0.66);
    const clock = new THREE.Mesh(new THREE.CylinderGeometry(0.135, 0.135, 0.035, 36), makeMat(0xf7ead0, { roughness: 0.5 }));
    clock.position.set(0.47, 1.04, 0.64);
    clock.rotation.x = Math.PI / 2;
    clockRim.rotation.x = Math.PI / 2;
    const hand = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.09, 0.012), darkAccent);
    hand.position.set(0.47, 1.04, 0.673);
    hand.rotation.z = -0.45;
    const shortHand = new THREE.Mesh(new THREE.BoxGeometry(0.014, 0.062, 0.012), darkAccent);
    shortHand.position.set(0.47, 1.04, 0.676);
    shortHand.rotation.z = 0.8;
    const ticks = makeClockTicks(new THREE.Vector3(0.47, 1.04, 0.682), darkAccent, 0.105);
    parts.powerGlow = clock;
    group.add(
      parts.leftEar,
      parts.rightEar,
      leftInnerEar,
      rightInnerEar,
      trunk,
      ...trunkRings,
      brim,
      dome,
      hatBand,
      jacketLeft,
      jacketRight,
      leftCollar,
      rightCollar,
      tieTop,
      tie,
      backpack,
      strap,
      clockRim,
      clock,
      hand,
      shortHand,
      ...ticks,
    );
    return;
  }

  if (kind === "electraica") {
    const visor = meshSphere(0.46, faceMat, [0, 1.7, 0.49], [1.18, 0.58, 0.08]);
    parts.leftEar = meshCylinder(0.24, 0.18, accent, [-0.68, 1.68, 0.02], [0, 0, Math.PI / 2]);
    parts.rightEar = meshCylinder(0.24, 0.18, accent, [0.68, 1.68, 0.02], [0, 0, Math.PI / 2]);
    const leftEarPad = meshCylinder(0.18, 0.2, makeMat(0xf0b832, { roughness: 0.82 }), [-0.75, 1.68, 0.02], [0, 0, Math.PI / 2]);
    const rightEarPad = meshCylinder(0.18, 0.2, makeMat(0xf0b832, { roughness: 0.82 }), [0.75, 1.68, 0.02], [0, 0, Math.PI / 2]);

    const bulbGlass = makeMat(0xfff2a6, { emissive: 0xffe46b, emissiveIntensity: 0.32, transparent: true, opacity: 0.72, roughness: 0.22 });
    const bulb = meshSphere(0.24, bulbGlass, [0, 2.41, 0], [1, 1.18, 1]);
    const bulbCore = meshSphere(0.14, powerMat, [0, 2.39, 0.01], [1, 1.05, 1]);
    const bulbBase = meshCylinder(0.12, 0.18, darkAccent, [0, 2.17, 0], [0, 0, 0]);
    const bulbThreadTop = meshCylinder(0.13, 0.025, makeMat(0xb39a5e, { roughness: 0.55, metalness: 0.05 }), [0, 2.26, 0], [0, 0, 0]);
    const bulbThreadBottom = meshCylinder(0.13, 0.025, makeMat(0xb39a5e, { roughness: 0.55, metalness: 0.05 }), [0, 2.09, 0], [0, 0, 0]);
    const bolt = meshBolt(makeMat(0xfff4a3, { emissive: 0xffdd55, emissiveIntensity: 0.7 }), [0, 2.11, 0.6], 0.54);
    const halo = new THREE.Mesh(new THREE.TorusGeometry(0.32, 0.018, 8, 48), powerMat);
    halo.position.set(0, 2.39, 0);
    halo.rotation.x = Math.PI / 2;
    parts.powerGlow = bulbCore;
    parts.bulbHalo = halo;

    const battery = meshBox([0.3, 0.54, 0.22], makeMat(0x8f7b55, { roughness: 0.72 }), [-0.58, 0.96, -0.32], [0, -0.1, 0]);
    const batteryBolt = meshBolt(makeMat(0x1e1a10, { roughness: 0.7 }), [-0.58, 1, -0.19], 0.24);
    batteryBolt.rotation.y = -0.18;
    const leftCoil = makeCoil([-0.42, 0.88, 0.58], 0.16, 0.34, look.accent);
    const rightCoil = makeCoil([0.44, 0.88, 0.58], 0.16, 0.34, look.accent);
    const chestPlate = meshBox([0.33, 0.2, 0.035], cream, [0, 0.91, 0.73], [0, 0, 0]);
    const chestMark = meshBolt(darkAccent, [0, 0.92, 0.757], 0.18);
    group.add(
      visor,
      parts.leftEar,
      parts.rightEar,
      leftEarPad,
      rightEarPad,
      bulb,
      bulbCore,
      bulbBase,
      bulbThreadTop,
      bulbThreadBottom,
      bolt,
      halo,
      battery,
      batteryBolt,
      leftCoil,
      rightCoil,
      chestPlate,
      chestMark,
    );
    return;
  }

  if (kind === "fire_boy") {
    const flame = new THREE.Mesh(new THREE.ConeGeometry(0.58, 1.1, 7), powerMat);
    flame.position.set(0, 2.16, 0);
    flame.rotation.y = Math.PI * 0.08;
    flame.castShadow = true;
    const midFlame = new THREE.Mesh(new THREE.ConeGeometry(0.42, 0.88, 7), makeMat(0xffa23b, { emissive: 0xff704d, emissiveIntensity: 0.32 }));
    midFlame.position.set(-0.08, 2.13, 0.04);
    midFlame.rotation.y = -Math.PI * 0.1;
    midFlame.castShadow = true;
    const innerFlame = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.78, 7), makeMat(0xffd36b, { emissive: 0xff9a3d, emissiveIntensity: 0.35 }));
    innerFlame.position.set(0.08, 2.12, 0.08);
    innerFlame.rotation.y = -Math.PI * 0.08;
    innerFlame.castShadow = true;
    const faceInset = meshSphere(0.45, faceMat, [0, 1.66, 0.49], [1.12, 0.62, 0.08]);
    const jacketLeft = meshBox([0.42, 0.48, 0.055], darkAccent, [-0.18, 0.96, 0.68], [0, 0, -0.14]);
    const jacketRight = meshBox([0.42, 0.48, 0.055], darkAccent, [0.18, 0.96, 0.68], [0, 0, 0.14]);
    const leftCollar = meshTriangle(0.23, 0.22, cream, [-0.12, 1.2, 0.735], -0.28);
    const rightCollar = meshTriangle(0.23, 0.22, cream, [0.12, 1.2, 0.735], 0.28);
    const tie = meshBox([0.07, 0.23, 0.036], darkAccent, [0, 0.98, 0.762], [0, 0, 0]);

    const pack = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.66, 8, 18), makeMat(0xe83e27, { roughness: 0.72 }));
    pack.position.set(0, 1.06, -0.72);
    pack.rotation.z = Math.PI / 2;
    const packBandTop = meshBox([0.48, 0.06, 0.04], darkAccent, [0, 1.28, -0.53], [0, 0, 0]);
    const packBandBottom = meshBox([0.48, 0.06, 0.04], darkAccent, [0, 0.84, -0.53], [0, 0, 0]);
    const hose = new THREE.Mesh(
      new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
        new THREE.Vector3(0.24, 1.15, -0.56),
        new THREE.Vector3(0.48, 1.08, -0.28),
        new THREE.Vector3(0.52, 0.97, 0.22),
        new THREE.Vector3(0.42, 0.88, 0.58),
      ]), 18, 0.017, 8, false),
      darkAccent,
    );
    hose.castShadow = true;

    const flute = new THREE.Mesh(new THREE.CapsuleGeometry(0.055, 0.74, 8, 16), makeMat(0xffd36b, { roughness: 0.72 }));
    flute.position.set(0.28, 0.94, 0.72);
    flute.rotation.z = -0.72;
    flute.rotation.x = Math.PI / 2;
    const fluteHoles = [-0.22, -0.08, 0.06, 0.2].map((offset) => {
      const hole = meshCylinder(0.018, 0.012, stitch, [0.28 + offset * 0.65, 0.94 - offset * 0.74, 0.78], [Math.PI / 2, 0, 0]);
      return hole;
    });
    parts.flameOuter = flame;
    parts.flameInner = innerFlame;
    parts.powerGlow = flame;
    group.add(
      flame,
      midFlame,
      innerFlame,
      faceInset,
      jacketLeft,
      jacketRight,
      leftCollar,
      rightCollar,
      tie,
      pack,
      packBandTop,
      packBandBottom,
      hose,
      flute,
      ...fluteHoles,
    );
    return;
  }

  const faceInset = meshSphere(0.47, faceMat, [0, 1.67, 0.49], [1.15, 0.64, 0.08]);
  const fin = new THREE.Mesh(new THREE.ConeGeometry(0.24, 0.62, 3), plush);
  fin.position.set(0, 2.32, -0.1);
  fin.rotation.x = -Math.PI / 2;
  fin.castShadow = true;
  const leftSideFin = meshSphere(0.22, plush, [-0.68, 1.25, 0.0], [0.5, 0.16, 1.08]);
  leftSideFin.rotation.z = 0.18;
  const rightSideFin = meshSphere(0.22, plush, [0.68, 1.25, 0.0], [0.5, 0.16, 1.08]);
  rightSideFin.rotation.z = -0.18;
  const tail = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.72, 3), plush);
  tail.position.set(0, 0.9, -0.86);
  tail.rotation.x = Math.PI / 2;
  tail.rotation.y = 0.1;
  tail.castShadow = true;
  parts.tail = tail;

  const star = meshStarfish(powerMat, [-0.36, 2.08, 0.58], 0.22);
  star.rotation.z = Math.PI * 0.18;
  const bowLeft = meshSphere(0.12, makePlushMaterial(look.accent, { roughness: 0.9 }), [-0.1, 1.14, 0.72], [1.2, 0.58, 0.34]);
  bowLeft.rotation.z = 0.28;
  const bowRight = meshSphere(0.12, makePlushMaterial(look.accent, { roughness: 0.9 }), [0.1, 1.14, 0.72], [1.2, 0.58, 0.34]);
  bowRight.rotation.z = -0.28;
  const bowKnot = meshSphere(0.065, makePlushMaterial(0xffd7ac, { roughness: 0.9 }), [0, 1.14, 0.745], [1, 1, 0.52]);

  const ukulele = makeUkulele([0.45, 0.88, 0.62], stitch);
  parts.ukulele = ukulele;
  const pearl = meshSphere(0.08, makeMat(0xfff7dd, { roughness: 0.35 }), [0.12, 1.17, 0.65], [1, 1, 0.55]);
  parts.powerGlow = star;
  group.add(faceInset, fin, leftSideFin, rightSideFin, tail, star, bowLeft, bowRight, bowKnot, pearl, ukulele);
}

function meshesIn(group) {
  const meshes = [];
  group.traverse((node) => {
    if (node.isMesh) meshes.push(node);
  });
  return meshes;
}

function meshSphere(radius, material, position, scale = [1, 1, 1]) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 40, 24), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.scale.set(scale[0], scale[1], scale[2]);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function meshBox(size, material, position, rotation = [0, 0, 0]) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(size[0], size[1], size[2]), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function meshCylinder(radius, height, material, position, rotation = [0, 0, 0], segments = 36) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, segments), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function meshTriangle(width, height, material, position, rotationZ = 0) {
  const shape = new THREE.Shape();
  shape.moveTo(-width / 2, height / 2);
  shape.lineTo(width / 2, height / 2);
  shape.lineTo(0, -height / 2);
  shape.lineTo(-width / 2, height / 2);
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.rotation.z = rotationZ;
  mesh.castShadow = true;
  return mesh;
}

function meshBolt(material, position, size = 0.36) {
  const shape = new THREE.Shape();
  shape.moveTo(-0.08, 0.18);
  shape.lineTo(0.1, 0.18);
  shape.lineTo(0.02, 0.02);
  shape.lineTo(0.14, 0.02);
  shape.lineTo(-0.08, -0.22);
  shape.lineTo(-0.01, -0.05);
  shape.lineTo(-0.14, -0.05);
  shape.lineTo(-0.08, 0.18);
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.scale.setScalar(size / 0.4);
  mesh.castShadow = true;
  return mesh;
}

function meshStarfish(material, position, radius = 0.2) {
  const shape = new THREE.Shape();
  const points = 10;
  for (let i = 0; i <= points; i += 1) {
    const angle = -Math.PI / 2 + (i / points) * Math.PI * 2;
    const r = i % 2 === 0 ? radius : radius * 0.46;
    const x = Math.cos(angle) * r;
    const y = Math.sin(angle) * r;
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  }
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.castShadow = true;
  return mesh;
}

function makeClockTicks(center, material, radius) {
  const ticks = [];
  for (let i = 0; i < 12; i += 1) {
    const angle = (i / 12) * Math.PI * 2;
    const tick = new THREE.Mesh(new THREE.BoxGeometry(0.01, i % 3 === 0 ? 0.03 : 0.02, 0.008), material);
    tick.position.set(center.x + Math.sin(angle) * radius, center.y + Math.cos(angle) * radius, center.z);
    tick.rotation.z = -angle;
    ticks.push(tick);
  }
  return ticks;
}

function makeCoil(position, radius, height, color) {
  const group = new THREE.Group();
  group.position.set(position[0], position[1], position[2]);
  group.rotation.z = Math.PI / 2;
  const mat = makeMat(color, { roughness: 0.72, metalness: 0.04 });
  for (let i = 0; i < 5; i += 1) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, 0.012, 8, 28), mat);
    ring.position.y = -height / 2 + i * (height / 4);
    ring.rotation.x = Math.PI / 2;
    ring.castShadow = true;
    group.add(ring);
  }
  return group;
}

function makeUkulele(position, lineMat) {
  const group = new THREE.Group();
  group.position.set(position[0], position[1], position[2]);
  group.rotation.z = -0.72;
  const wood = makeMat(0xd69b59, { roughness: 0.82 });
  const darkWood = makeMat(0x7b4a28, { roughness: 0.88 });
  const bodyLower = meshSphere(0.18, wood, [0, -0.08, 0], [1.08, 1.0, 0.32]);
  const bodyUpper = meshSphere(0.13, wood, [0, 0.09, 0], [0.95, 0.9, 0.32]);
  const neck = meshBox([0.08, 0.42, 0.035], darkWood, [0, 0.39, 0], [0, 0, 0]);
  const head = meshBox([0.16, 0.12, 0.038], darkWood, [0, 0.64, 0], [0, 0, 0.12]);
  const hole = meshCylinder(0.045, 0.01, lineMat, [0, 0.02, 0.062], [Math.PI / 2, 0, 0]);
  const bridge = meshBox([0.16, 0.035, 0.018], darkWood, [0, -0.19, 0.07], [0, 0, 0]);
  group.add(bodyLower, bodyUpper, neck, head, hole, bridge);
  for (let i = 0; i < 4; i += 1) {
    const x = -0.045 + i * 0.03;
    group.add(meshBox([0.007, 0.78, 0.009], lineMat, [x, 0.18, 0.091], [0, 0, 0]));
  }
  for (let i = 0; i < 3; i += 1) {
    group.add(meshBox([0.12, 0.01, 0.01], lineMat, [0, 0.3 + i * 0.09, 0.092], [0, 0, 0]));
  }
  return group;
}

function createFace(look) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 320;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.62), material);
  return { canvas, texture, mesh, look };
}

function drawFace(pet, force = false) {
  const shape = pet.face.current;
  const key = Object.values(shape).map((value) => value.toFixed(2)).join("|");
  if (!force && key === pet.face.lastDraw) return;
  pet.face.lastDraw = key;

  const { canvas, texture, look } = pet.parts.face;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = `#${look.eye.toString(16).padStart(6, "0")}`;
  ctx.fillStyle = ctx.strokeStyle;
  ctx.lineWidth = 16;

  const cheek = `#${look.cheeks.toString(16).padStart(6, "0")}`;
  ctx.globalAlpha = 0.45 + shape.cheek * 0.35;
  ctx.fillStyle = cheek;
  ctx.beginPath();
  ctx.ellipse(148, 190, 30 + shape.cheek * 9, 19 + shape.cheek * 7, 0, 0, Math.PI * 2);
  ctx.ellipse(364, 190, 30 + shape.cheek * 9, 19 + shape.cheek * 7, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.strokeStyle = `#${look.eye.toString(16).padStart(6, "0")}`;
  ctx.fillStyle = ctx.strokeStyle;

  drawEye(ctx, 172, 134, shape, -1);
  drawEye(ctx, 340, 134, shape, 1);
  drawSparkles(ctx, shape);
  drawMouth(ctx, shape);
  texture.needsUpdate = true;
}

function drawEye(ctx, x, y, shape, side) {
  const eyeOpen = shape.eye;
  const brow = shape.brow * side;
  if (eyeOpen < 0.45) {
    ctx.beginPath();
    ctx.moveTo(x - 30, y + 4);
    ctx.quadraticCurveTo(x, y + 16, x + 30, y + 2);
    ctx.stroke();
  } else if (eyeOpen < 1.12) {
    ctx.beginPath();
    ctx.arc(x, y + 20, 31, Math.PI * 1.08, Math.PI * (1.86 + eyeOpen * 0.04));
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.ellipse(x, y + 12, 14 * eyeOpen, 16 * eyeOpen, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  if (Math.abs(shape.brow) > 0.12) {
    ctx.beginPath();
    ctx.moveTo(x - 31, y - 28 - brow * 13);
    ctx.lineTo(x + 31, y - 20 + brow * 13);
    ctx.stroke();
  }
}

function drawSparkles(ctx, shape) {
  if ((shape.sparkle ?? 0) < 0.18) return;
  ctx.save();
  ctx.globalAlpha = Math.min(0.9, shape.sparkle);
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.lineWidth = 8;
  for (const [x, y, size] of [[215, 98, 12], [396, 114, 9]]) {
    ctx.beginPath();
    ctx.moveTo(x - size, y);
    ctx.lineTo(x + size, y);
    ctx.moveTo(x, y - size);
    ctx.lineTo(x, y + size);
    ctx.stroke();
  }
  ctx.restore();
}

function drawMouth(ctx, shape) {
  const x = 256;
  const y = 203;
  const width = 48 + shape.smile * 32;
  if (shape.mouth > 0.18) {
    ctx.beginPath();
    ctx.ellipse(x, y + 10, 19 + shape.mouth * 13, 12 + shape.mouth * 24, 0, 0, Math.PI * 2);
    ctx.stroke();
    return;
  }
  ctx.beginPath();
  ctx.moveTo(x - width / 2, y);
  ctx.quadraticCurveTo(x, y + width * (shape.smile * 0.32), x + width / 2, y);
  ctx.stroke();
}

function lerpShape(current, target, alpha) {
  for (const key of Object.keys(target)) {
    current[key] = THREE.MathUtils.lerp(current[key] ?? target[key], target[key], alpha);
  }
}
