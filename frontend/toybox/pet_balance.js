import * as THREE from "three";
import * as CANNON from "cannon-es";

const WORLD_UP = new CANNON.Vec3(0, 1, 0);
const DEFAULT_HOME = new CANNON.Vec3(0, 0.06, 1.02);

const PART_WEIGHTS = {
  squeaky: [
    { name: "body", weight: 4.4, local: new CANNON.Vec3(0, 0.84, 0) },
    { name: "head", weight: 2.0, local: new CANNON.Vec3(0, 1.7, 0.02) },
    { name: "hat", weight: 0.55, local: new CANNON.Vec3(0, 2.25, 0) },
    { name: "trunk", weight: 0.45, local: new CANNON.Vec3(0, 1.44, 0.62) },
    { name: "feet", weight: 1.1, local: new CANNON.Vec3(0, 0.16, 0.28) },
  ],
  electraica: [
    { name: "body", weight: 3.9, local: new CANNON.Vec3(0, 0.86, 0) },
    { name: "head", weight: 1.8, local: new CANNON.Vec3(0, 1.72, 0.02) },
    { name: "bulb", weight: 0.7, local: new CANNON.Vec3(0, 2.38, 0) },
    { name: "feet", weight: 1.0, local: new CANNON.Vec3(0, 0.16, 0.28) },
  ],
  fire_boy: [
    { name: "body", weight: 3.7, local: new CANNON.Vec3(0, 0.84, 0) },
    { name: "head", weight: 1.55, local: new CANNON.Vec3(0, 1.72, 0.02) },
    { name: "flame", weight: 0.35, local: new CANNON.Vec3(0, 2.24, 0) },
    { name: "pack", weight: 0.9, local: new CANNON.Vec3(0, 1.05, -0.58) },
    { name: "feet", weight: 1.0, local: new CANNON.Vec3(0, 0.16, 0.28) },
  ],
  shark_girl: [
    { name: "body", weight: 4.0, local: new CANNON.Vec3(0, 0.84, 0) },
    { name: "head", weight: 1.8, local: new CANNON.Vec3(0, 1.7, 0.02) },
    { name: "fin", weight: 0.35, local: new CANNON.Vec3(0, 2.25, -0.1) },
    { name: "ukulele", weight: 0.45, local: new CANNON.Vec3(0.44, 0.9, 0.58) },
    { name: "feet", weight: 1.0, local: new CANNON.Vec3(0, 0.16, 0.28) },
  ],
};

export function createPetBalanceRig({ world, recordForce, home: initialHome = DEFAULT_HOME } = {}) {
  let body = null;
  let petKind = "squeaky";
  let lastBumpAt = 0;
  const home = initialHome.clone ? initialHome.clone() : new CANNON.Vec3(initialHome.x ?? 0, initialHome.y ?? DEFAULT_HOME.y, initialHome.z ?? 1.02);
  const visualBase = new THREE.Vector3(home.x, home.y, home.z);
  const visualTilt = { x: 0, y: 0, z: 0 };
  let currentState = idleState();

  function setPet(pet, kind) {
    removeBody();
    petKind = kind || "squeaky";
    const parts = partWeights();
    const mass = totalWeight(parts);
    body = new CANNON.Body({ mass, material: world.defaultMaterial });
    body.position.copy(home);
    body.linearDamping = 0.34;
    body.angularDamping = 0.86;
    body.allowSleep = false;
    body.userData = { id: `${petKind}-balance`, kind: "pet-balance" };
    addPetShapes(body);
    body.addEventListener("collide", onPetCollision);
    world.addBody(body);
    if (pet) applyVisualState(pet, 1);
  }

  function removeBody() {
    if (!body) return;
    body.removeEventListener("collide", onPetCollision);
    world.removeBody(body);
    body = null;
  }

  function beforeStep(_now, dt) {
    if (!body) return;
    body.wakeUp();
    applyStandingForces(dt);
    currentState = readState();
  }

  function afterStep(pet, _now, dt) {
    if (!body || !pet) return;
    applyVisualState(pet, Math.min(1, dt * 14));
    currentState = readState();
  }

  function nudge(vector, strength = 1) {
    if (!body || !vector) return;
    const impulse = new CANNON.Vec3(
      Number(vector.x || 0) * strength,
      Number(vector.y || 0) * strength,
      Number(vector.z || 0) * strength,
    );
    body.applyImpulse(impulse, body.position);
    body.wakeUp();
  }

  function twist(vector, strength = 1) {
    if (!body || !vector) return;
    body.angularVelocity.x += Number(vector.x || 0) * strength;
    body.angularVelocity.y += Number(vector.y || 0) * strength;
    body.angularVelocity.z += Number(vector.z || 0) * strength;
    body.wakeUp();
  }

  function moveTo(position, { settleOnFloor = false } = {}) {
    home.set(
      Number(position.x || 0),
      settleOnFloor ? DEFAULT_HOME.y : Number(position.y || DEFAULT_HOME.y),
      Number(position.z || 0),
    );
    if (!body) return;
    body.position.copy(home);
    body.velocity.set(0, 0, 0);
    body.angularVelocity.set(0, 0, 0);
    body.wakeUp();
  }

  function steerTo(position, { settleOnFloor = false } = {}) {
    home.set(
      Number(position.x || 0),
      settleOnFloor ? DEFAULT_HOME.y : Number(position.y || DEFAULT_HOME.y),
      Number(position.z || 0),
    );
    if (body) body.wakeUp();
  }

  function drive(direction, speed = 1, dt = 1 / 60) {
    if (!body || !direction) return;
    const x = Number(direction.x || 0);
    const z = Number(direction.z || 0);
    const length = Math.hypot(x, z);
    if (length < 0.001) return;
    const targetVx = (x / length) * speed;
    const targetVz = (z / length) * speed;
    const velocityBlend = Math.min(1, Math.max(0.08, dt * 18));
    body.velocity.x += (targetVx - body.velocity.x) * velocityBlend;
    body.velocity.z += (targetVz - body.velocity.z) * velocityBlend;
    const step = Math.min(speed * Math.max(0.001, dt) * 0.82, 0.05);
    body.position.x += (x / length) * step;
    body.position.z += (z / length) * step;
    body.aabbNeedsUpdate = true;
    const gain = body.mass * (30 + Math.min(24, speed * 8));
    body.force.x += (targetVx - body.velocity.x) * gain;
    body.force.z += (targetVz - body.velocity.z) * gain;
    body.wakeUp();
  }

  function position() {
    const source = body?.position || home;
    return new THREE.Vector3(source.x, source.y, source.z);
  }

  function dropFrom(position) {
    home.set(Number(position.x || 0), DEFAULT_HOME.y, Number(position.z || 0));
    if (!body) return;
    body.position.set(Number(position.x || 0), Math.max(DEFAULT_HOME.y, Number(position.y || DEFAULT_HOME.y)), Number(position.z || 0));
    body.velocity.set(0, -0.25, 0);
    body.angularVelocity.set((Math.random() - 0.5) * 0.5, 0, (Math.random() - 0.5) * 0.5);
    body.wakeUp();
  }

  function state() {
    return currentState;
  }

  function applyStandingForces(dt) {
    const up = body.quaternion.vmult(WORLD_UP);
    const correction = up.cross(WORLD_UP);
    const torqueGain = 180;
    const torqueDamping = 36;
    body.torque.x += correction.x * torqueGain - body.angularVelocity.x * torqueDamping;
    body.torque.y += correction.y * torqueGain * 0.15 - body.angularVelocity.y * torqueDamping * 0.2;
    body.torque.z += correction.z * torqueGain - body.angularVelocity.z * torqueDamping;

    const mass = Math.max(1, body.mass);
    const horizontalSpring = 32;
    const horizontalDamping = 9;
    body.force.x += ((home.x - body.position.x) * horizontalSpring - body.velocity.x * horizontalDamping) * mass;
    body.force.z += ((home.z - body.position.z) * horizontalSpring - body.velocity.z * horizontalDamping) * mass;

    if (body.position.y < home.y - 0.02) {
      body.force.y += (home.y - body.position.y) * 42 * mass - body.velocity.y * 4 * mass;
    }

    for (const part of partWeights()) {
      const localForce = new CANNON.Vec3(0, -part.weight * 0.18 * Math.max(0.5, dt * 60), 0);
      body.applyLocalForce(localForce, part.local);
    }
  }

  function applyVisualState(pet, alpha) {
    const q = new THREE.Quaternion(body.quaternion.x, body.quaternion.y, body.quaternion.z, body.quaternion.w);
    const euler = new THREE.Euler().setFromQuaternion(q, "XYZ");
    visualBase.lerp(new THREE.Vector3(body.position.x, Math.max(0.035, body.position.y), body.position.z), alpha);
    visualTilt.x = THREE.MathUtils.lerp(visualTilt.x, THREE.MathUtils.clamp(euler.x, -0.16, 0.16), alpha);
    visualTilt.y = THREE.MathUtils.lerp(visualTilt.y, THREE.MathUtils.clamp(euler.y, -0.18, 0.18), alpha);
    visualTilt.z = THREE.MathUtils.lerp(visualTilt.z, THREE.MathUtils.clamp(euler.z, -0.2, 0.2), alpha);
    pet.basePosition = visualBase.clone();
    pet.balanceTilt = { ...visualTilt };
    pet.balanceState = currentState;
  }

  function readState() {
    if (!body) return idleState();
    const up = body.quaternion.vmult(WORLD_UP);
    const tiltRadians = Math.acos(THREE.MathUtils.clamp(up.dot(WORLD_UP), -1, 1));
    const center = weightedCenterOfMass();
    const stability = THREE.MathUtils.clamp(1 - tiltRadians / 0.8 - horizontalDistance(center, home) * 0.28, 0, 1);
    return {
      active: true,
      mass: Number(body.mass.toFixed(2)),
      stability: Number(stability.toFixed(2)),
      tiltDeg: Number(THREE.MathUtils.radToDeg(tiltRadians).toFixed(1)),
      speed: Number(body.velocity.length().toFixed(2)),
      centerOfMass: {
        x: Number(center.x.toFixed(2)),
        y: Number(center.y.toFixed(2)),
        z: Number(center.z.toFixed(2)),
      },
    };
  }

  function weightedCenterOfMass() {
    const parts = partWeights();
    const center = new CANNON.Vec3();
    for (const part of parts) {
      const worldPoint = body.pointToWorldFrame(part.local);
      center.x += worldPoint.x * part.weight;
      center.y += worldPoint.y * part.weight;
      center.z += worldPoint.z * part.weight;
    }
    const mass = totalWeight(parts);
    center.scale(1 / mass, center);
    return center;
  }

  function onPetCollision(event) {
    const now = performance.now();
    if (now - lastBumpAt < 360) return;
    lastBumpAt = now;
    let impact = body.velocity.length();
    try {
      impact = Math.abs(event.contact.getImpactVelocityAlongNormal());
    } catch {}
    if (impact > 0.55) {
      recordForce?.({ kind: "pet-balance", objectId: `${petKind}-body`, impact: Number(Math.min(impact / 6, 1).toFixed(2)) });
    }
  }

  function partWeights() {
    return PART_WEIGHTS[petKind] || PART_WEIGHTS.squeaky;
  }

  return { afterStep, beforeStep, drive, dropFrom, moveTo, nudge, position, removeBody, setPet, state, steerTo, twist };
}

function addPetShapes(body) {
  body.addShape(new CANNON.Sphere(0.68), new CANNON.Vec3(0, 0.84, 0));
  body.addShape(new CANNON.Sphere(0.5), new CANNON.Vec3(0, 1.67, 0.02));
  body.addShape(new CANNON.Sphere(0.18), new CANNON.Vec3(-0.34, 0.16, 0.28));
  body.addShape(new CANNON.Sphere(0.18), new CANNON.Vec3(0.34, 0.16, 0.28));
  body.addShape(new CANNON.Box(new CANNON.Vec3(0.25, 0.05, 0.22)), new CANNON.Vec3(0, 0.09, 0.28));
}

function totalWeight(parts) {
  return parts.reduce((sum, part) => sum + part.weight, 0);
}

function horizontalDistance(a, b) {
  return Math.hypot(a.x - b.x, a.z - b.z);
}

function idleState() {
  return {
    active: false,
    mass: 0,
    stability: 1,
    tiltDeg: 0,
    speed: 0,
    centerOfMass: { x: DEFAULT_HOME.x, y: DEFAULT_HOME.y + 1, z: DEFAULT_HOME.z },
  };
}
