import * as THREE from "three";
import * as CANNON from "cannon-es";
import { PET_LOOKS, POWER_COLORS } from "./config.js";

export function createPowerController({
  audio,
  bodyHistory,
  effects,
  frozenBodies,
  getActivePet,
  getPet,
  lights,
  nearestObject,
  objects,
  ui,
}) {
  const handlers = {
    time_freeze: ({ target, durationMs }) => timeFreeze(target, durationMs),
    shrink: ({ durationMs }) => shrinkPet(durationMs),
    rewind: ({ target }) => rewindObject(target),
    clock_bubble: () => clockBubble(),
    shock: ({ target, strength }) => shockObject(target, strength),
    magnet_pull: ({ strength }) => magnetPull(strength),
    lamp_burst: () => lampBurst(),
    fireball: ({ target, strength }) => fireball(target, strength),
    ember_jump: () => emberJump(),
    smoke_poof: () => smokePoof(),
    wave: ({ strength }) => wave(strength),
    bubble_lift: ({ target }) => bubbleLift(target),
    tide_pull: ({ strength }) => tidePull(strength),
  };

  function apply(power = {}) {
    const handler = handlers[power.name];
    if (!handler) return false;
    audio.power(power.name);
    handler({
      target: findTarget(power.targetId),
      strength: Number(power.strength || 0.8),
      durationMs: Number(power.durationMs || 1600),
    });
    return true;
  }

  function findTarget(targetId) {
    if (!targetId || targetId === "all-moving") {
      const moving = objects.filter((entry) => entry.body.velocity.length() > 0.35);
      return moving[0] || nearestObject();
    }
    return objects.find((entry) => entry.id === targetId) || nearestObject();
  }

  function timeFreeze(target, durationMs) {
    const now = performance.now();
    const targets = target ? [target] : objects;
    for (const entry of targets.length ? targets : objects) {
      frozenBodies.set(entry.id, { until: now + durationMs, position: entry.body.position.clone(), quaternion: entry.body.quaternion.clone() });
      entry.body.velocity.set(0, 0, 0);
      entry.body.angularVelocity.set(0, 0, 0);
    }
    ui.flash(durationMs);
    effects.ring(new THREE.Vector3(0, 0.7, 0.4), POWER_COLORS.time_freeze, 1.8, 1.25);
    effects.stars(new THREE.Vector3(0, 1.25, 0.6), POWER_COLORS.time_freeze, 18);
  }

  function shrinkPet(durationMs) {
    const pet = getPet();
    if (!pet) return;
    pet.targetScale = 0.56;
    effects.burst(pet.group.position.clone().add(new THREE.Vector3(0, 1.1, 0)), PET_LOOKS[getActivePet()].power, 22, 0.9);
    setTimeout(() => {
      if (getPet()) getPet().targetScale = 1;
    }, durationMs);
  }

  function rewindObject(target) {
    const entry = target || nearestObject();
    if (!entry) return;
    const history = bodyHistory.get(entry.id) || [];
    const old = history[Math.max(0, history.length - 9)];
    if (!old) return;
    entry.body.position.set(old.position.x, old.position.y, old.position.z + 0.08);
    entry.body.quaternion.set(old.quaternion.x, old.quaternion.y, old.quaternion.z, old.quaternion.w);
    entry.body.velocity.set(0, 1.5, 0);
    entry.body.angularVelocity.set(0, 0, 0);
    effects.ring(new THREE.Vector3(old.position.x, old.position.y, old.position.z), POWER_COLORS.rewind, 1.1, 0.9);
  }

  function clockBubble() {
    const pet = getPet();
    if (!pet) return;
    effects.ring(pet.group.position.clone().add(new THREE.Vector3(0, 1.2, 0)), PET_LOOKS[getActivePet()].power, 2.6, 1.7, true);
    for (const entry of objects) {
      const dist = new THREE.Vector3(entry.body.position.x, entry.body.position.y, entry.body.position.z).distanceTo(pet.group.position);
      if (dist < 2.7) entry.body.velocity.scale(0.45, entry.body.velocity);
    }
  }

  function shockObject(target, strength) {
    const entry = target || nearestObject();
    if (!entry) return;
    entry.body.applyImpulse(new CANNON.Vec3((Math.random() - 0.5) * 2.5 * strength, 3.5 * strength, (Math.random() - 0.5) * 2.5 * strength));
    effects.stars(new THREE.Vector3(entry.body.position.x, entry.body.position.y, entry.body.position.z), POWER_COLORS.shock, 26);
  }

  function magnetPull(strength) {
    const pet = getPet();
    if (!pet) return;
    for (const entry of objects) {
      const dir = new CANNON.Vec3(pet.group.position.x - entry.body.position.x, 0.35, pet.group.position.z - entry.body.position.z);
      dir.normalize();
      entry.body.applyImpulse(dir.scale(1.4 * strength));
    }
    effects.ring(pet.group.position.clone().add(new THREE.Vector3(0, 1.1, 0)), POWER_COLORS.magnet_pull, 1.5, 1.0);
  }

  function lampBurst() {
    shockObject(objects.find((entry) => entry.id === "lamp") || nearestObject(), 0.9);
    lights.fillLight.intensity = 78;
    setTimeout(() => (lights.fillLight.intensity = 34), 260);
  }

  function fireball(target, strength) {
    const pet = getPet();
    if (!pet) return;
    const entry = target || nearestObject();
    const start = pet.group.position.clone().add(new THREE.Vector3(0, 1.25, 0.3));
    const end = entry ? new THREE.Vector3(entry.body.position.x, entry.body.position.y, entry.body.position.z) : new THREE.Vector3(0, 0.7, -1.2);
    effects.projectile(start, end, POWER_COLORS.fireball, () => {
      if (entry) entry.body.applyImpulse(new CANNON.Vec3(1.5 * strength, 2.6 * strength, -1.8 * strength));
      effects.stars(end, POWER_COLORS.fireball, 26);
    });
  }

  function emberJump() {
    const pet = getPet();
    if (!pet) return;
    pet.group.position.y += 0.12;
    effects.stars(pet.group.position.clone().add(new THREE.Vector3(0, 0.5, 0)), POWER_COLORS.ember_jump, 22);
  }

  function smokePoof() {
    const pet = getPet();
    if (!pet) return;
    effects.burst(pet.group.position.clone().add(new THREE.Vector3(0, 1.1, 0)), POWER_COLORS.smoke_poof, 34, 0.72);
  }

  function wave(strength) {
    for (const entry of objects) entry.body.applyImpulse(new CANNON.Vec3(0, 1.0 * strength, 2.6 * strength));
    effects.ring(new THREE.Vector3(0, 0.35, -1.6), POWER_COLORS.wave, 3.1, 1.15);
    effects.burst(new THREE.Vector3(0, 0.6, -1), POWER_COLORS.wave, 32, 1.18);
  }

  function bubbleLift(target) {
    const entry = target || nearestObject();
    if (!entry) return;
    entry.body.applyImpulse(new CANNON.Vec3(0, 4.2, 0));
    effects.ring(new THREE.Vector3(entry.body.position.x, entry.body.position.y, entry.body.position.z), POWER_COLORS.bubble_lift, 0.9, 1.4, true);
  }

  function tidePull(strength) {
    for (const entry of objects) entry.body.applyImpulse(new CANNON.Vec3(-entry.body.position.x * 0.32 * strength, 0.8, -entry.body.position.z * 0.32 * strength));
    effects.ring(new THREE.Vector3(0, 0.4, 0), POWER_COLORS.tide_pull, 2.4, 1.1);
  }

  return { apply };
}
