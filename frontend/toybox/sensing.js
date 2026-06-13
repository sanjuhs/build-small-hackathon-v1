import * as THREE from "three";

export function collectSceneState(activePet, pet, objects, balance = null, needs = null) {
  const petPos = pet?.group?.position || new THREE.Vector3();
  return {
    pet: {
      kind: activePet,
      emotion: pet?.emotion,
      hovered: pet?.hovered,
      recentlyTouched: performance.now() - (pet?.lastPettedAt || 0) < 2500,
      needs: needs || null,
      balance: balance || pet?.balanceState || null,
    },
    objects: objects.map((entry) => {
      const pos = entry.body.position;
      const speed = entry.body.velocity.length();
      const distanceToPet = new THREE.Vector3(pos.x, pos.y, pos.z).distanceTo(petPos);
      return {
        id: entry.id,
        kind: entry.kind,
        position: { x: Number(pos.x.toFixed(2)), y: Number(pos.y.toFixed(2)), z: Number(pos.z.toFixed(2)) },
        speed: Number(speed.toFixed(2)),
        distanceToPet: Number(distanceToPet.toFixed(2)),
        moving: speed > 0.5,
        affordances: Array.isArray(entry.affordances) ? entry.affordances.slice(0, 6) : [],
        tags: Array.isArray(entry.tags) ? entry.tags.slice(0, 6) : [],
        nutrition: Number(entry.nutrition || 0),
        readable: Boolean(entry.readable),
        comfort: Number(entry.comfort || 0),
        social: Number(entry.social || 0),
      };
    })
  };
}

export function detectObjects(pet, objects) {
  if (!pet) return [];
  const origin = pet.group.position;
  return objects
    .map((entry) => {
      const pos = new THREE.Vector3(entry.body.position.x, entry.body.position.y, entry.body.position.z);
      return {
        id: entry.id,
        kind: entry.kind,
        distance: Number(pos.distanceTo(origin).toFixed(2)),
        moving: entry.body.velocity.length() > 0.5,
        affordances: Array.isArray(entry.affordances) ? entry.affordances.slice(0, 4) : [],
      };
    })
    .filter((item) => item.distance < 4.2)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 8);
}

export function captureCameraFrame(renderer) {
  try {
    return renderer.domElement.toDataURL("image/jpeg", 0.45);
  } catch {
    return null;
  }
}
