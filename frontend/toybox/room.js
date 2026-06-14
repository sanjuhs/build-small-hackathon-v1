import * as THREE from "three";
import * as CANNON from "cannon-es";
import { makeMat } from "./config.js";

export function createPhysicsWorld() {
  const material = new CANNON.Material("toy-world");
  const world = new CANNON.World({ gravity: new CANNON.Vec3(0, -9.82, 0) });
  world.allowSleep = true;
  world.broadphase = new CANNON.SAPBroadphase(world);
  world.defaultContactMaterial = new CANNON.ContactMaterial(material, material, {
    friction: 0.38,
    restitution: 0.46
  });
  world.defaultMaterial = material;
  return world;
}

export function createToyRoom({ scene, world, ui, recordForce, variant = "v1" }) {
  const worldMaterial = world.defaultMaterial;
  const objects = [];
  const bodyHistory = new Map();
  const frozenBodies = new Map();
  const palette = createPalette();
  const lights = addLights(scene);
  const bounds = variant === "v2" || variant === "v3"
    ? { halfX: 6.2, halfZ: 4.7, wallHeight: 4.8 }
    : { halfX: 4.5, halfZ: 3.5, wallHeight: 4.2 };
  let lastHistoryCapture = 0;

  addRoomShell();

  function addRoomShell() {
    const floor = new THREE.Mesh(new THREE.BoxGeometry(bounds.halfX * 2, 0.12, bounds.halfZ * 2), palette.floor);
    floor.position.y = -0.06;
    floor.receiveShadow = true;
    scene.add(floor);
    addStaticBody(new CANNON.Vec3(bounds.halfX, 0.06, bounds.halfZ), new CANNON.Vec3(0, -0.06, 0));

    const walls = [
      [new THREE.BoxGeometry(bounds.halfX * 2, bounds.wallHeight, 0.12), [0, bounds.wallHeight / 2 - 0.06, -bounds.halfZ - 0.06], new CANNON.Vec3(bounds.halfX, bounds.wallHeight / 2, 0.06)],
      [new THREE.BoxGeometry(0.12, bounds.wallHeight, bounds.halfZ * 2), [-bounds.halfX - 0.06, bounds.wallHeight / 2 - 0.06, 0], new CANNON.Vec3(0.06, bounds.wallHeight / 2, bounds.halfZ)],
    ];
    for (const [geometry, position, halfExtents] of walls) {
      const wall = new THREE.Mesh(geometry, palette.wall);
      wall.position.set(position[0], position[1], position[2]);
      wall.receiveShadow = true;
      scene.add(wall);
      addStaticBody(halfExtents, new CANNON.Vec3(position[0], position[1], position[2]));
    }
    addStaticBody(new CANNON.Vec3(0.06, bounds.wallHeight / 2, bounds.halfZ), new CANNON.Vec3(bounds.halfX + 0.06, bounds.wallHeight / 2 - 0.06, 0));
    addStaticBody(new CANNON.Vec3(bounds.halfX, bounds.wallHeight / 2, 0.06), new CANNON.Vec3(0, bounds.wallHeight / 2 - 0.06, bounds.halfZ + 0.06));
  }

  function addStaticBody(halfExtents, position) {
    const body = new CANNON.Body({ type: CANNON.Body.STATIC, material: worldMaterial });
    body.addShape(new CANNON.Box(halfExtents));
    body.position.copy(position);
    world.addBody(body);
  }

  function createBox(id, kind, size, position, material, mass = 1.2, metadata = {}) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(size.x, size.y, size.z), material);
    mesh.position.copy(position);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    const body = new CANNON.Body({ mass, material: worldMaterial });
    body.addShape(new CANNON.Box(new CANNON.Vec3(size.x / 2, size.y / 2, size.z / 2)));
    body.position.set(position.x, position.y, position.z);
    body.linearDamping = 0.08;
    body.angularDamping = 0.12;
    body.userData = { id, kind };
    world.addBody(body);
    return registerObject({ id, kind, mesh, body, size, radius: Math.max(size.x, size.y, size.z) * 0.5, ...metadata });
  }

  function createBall(id, kind, radius, position, material, mass = 0.9, metadata = {}) {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 32, 20), material);
    mesh.position.copy(position);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    const body = new CANNON.Body({ mass, material: worldMaterial });
    body.addShape(new CANNON.Sphere(radius));
    body.position.set(position.x, position.y, position.z);
    body.linearDamping = 0.04;
    body.angularDamping = 0.06;
    body.userData = { id, kind };
    world.addBody(body);
    return registerObject({ id, kind, mesh, body, size: new THREE.Vector3(radius * 2, radius * 2, radius * 2), radius, ...metadata });
  }

  function createCompositeObject(id, kind, position, collider, mass, build, metadata = {}) {
    const group = new THREE.Group();
    group.position.copy(position);
    scene.add(group);
    build(group);
    group.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
    });

    const size = collider.size || new THREE.Vector3(collider.radius * 2, collider.radius * 2, collider.radius * 2);
    const body = new CANNON.Body({ mass, material: worldMaterial });
    if (collider.type === "sphere") {
      body.addShape(new CANNON.Sphere(collider.radius));
    } else {
      body.addShape(new CANNON.Box(new CANNON.Vec3(size.x / 2, size.y / 2, size.z / 2)));
    }
    body.position.set(position.x, position.y, position.z);
    body.linearDamping = metadata.linearDamping ?? 0.14;
    body.angularDamping = metadata.angularDamping ?? 0.2;
    body.userData = { id, kind };
    world.addBody(body);
    return registerObject({ id, kind, mesh: group, body, size, radius: collider.radius || Math.max(size.x, size.y, size.z) * 0.5, ...metadata });
  }

  function registerObject(entry) {
    entry.affordances = Array.isArray(entry.affordances) ? entry.affordances : [];
    entry.tags = Array.isArray(entry.tags) ? entry.tags : [];
    entry.hitMeshes = meshesIn(entry.mesh);
    for (const mesh of entry.hitMeshes) {
      mesh.userData.toyObjectId = entry.id;
    }
    entry.body.addEventListener("collide", (event) => {
      let impact = entry.body.velocity.length();
      try {
        impact = Math.abs(event.contact.getImpactVelocityAlongNormal());
      } catch {}
      if (impact > 0.7) recordForce({ kind: "collision", objectId: entry.id, impact: Number(Math.min(impact / 7, 1).toFixed(2)) });
    });
    objects.push(entry);
    return entry;
  }

  function resetRoom() {
    clearObjects();
    if (variant === "v3") {
      resetRoomV3();
      return;
    }
    if (variant === "v2") {
      resetRoomV2();
      return;
    }
    createBox("cube-blue", "cube", new THREE.Vector3(0.62, 0.62, 0.62), new THREE.Vector3(-1.35, 0.9, 0.1), palette.cubeBlue, 1.2);
    createBox("cube-coral", "cube", new THREE.Vector3(0.52, 0.52, 0.52), new THREE.Vector3(1.5, 1.0, -0.15), palette.cubeCoral, 1.0);
    createBall("soft-ball", "ball", 0.34, new THREE.Vector3(0.9, 1.0, 1.05), palette.cubeAmber, 0.8);
    createBall("moon-ball", "ball", 0.25, new THREE.Vector3(-2.2, 0.9, 1.2), makeMat(0xd7eee8), 0.6);
    for (let i = 0; i < 5; i += 1) {
      createBox(`domino-${i + 1}`, "domino", new THREE.Vector3(0.16, 0.74, 0.38), new THREE.Vector3(-0.6 + i * 0.34, 0.78, -1.25), makeMat(i % 2 ? 0x1d2424 : 0xffffff), 0.5);
    }
    createBox("tiny-clock", "clock", new THREE.Vector3(0.48, 0.48, 0.18), new THREE.Vector3(2.35, 0.8, 1.0), palette.metal, 0.7);
    createBerry("berry-rose", new THREE.Vector3(-2.85, 0.31, 0.9), 0xb93576, 0xff77a8);
    createBerry("berry-amber", new THREE.Vector3(-2.35, 0.31, 0.55), 0xe6544e, 0xffb35b);
    createBerry("berry-moon", new THREE.Vector3(-1.85, 0.31, 0.92), 0x6d5bd6, 0x9ed4ff);
    createBerry("berry-sprout", new THREE.Vector3(2.35, 0.31, -0.82), 0x8d2a64, 0xff8bc7);
    createBook("story-book-blue", new THREE.Vector3(1.78, 0.15, -1.76), 0x3f87a8, 0xfff1c8);
    createBook("story-book-green", new THREE.Vector3(2.34, 0.15, -1.42), 0x5b9460, 0xffdf6e);
    createTable("tea-table", new THREE.Vector3(-1.2, 0.44, -2.0), 0x8e623a);
    createChair("chair-mint", new THREE.Vector3(-2.0, 0.45, -2.24), 0x7bb9a8);
    createChair("chair-coral", new THREE.Vector3(-0.46, 0.45, -2.2), 0xff8a6b);
    createChair("chair-honey", new THREE.Vector3(-1.2, 0.45, -2.72), 0xe5b94e);
    createToyLamp("lamp", new THREE.Vector3(-3.05, 0.5, -1.15), 0xffde71, 1.08);
    createToyLamp("reading-lamp", new THREE.Vector3(2.95, 0.42, 1.52), 0x9ed4ff, 0.82);
    createPlant("fern-pot", new THREE.Vector3(3.2, 0.42, -1.55), 0x5e9c62);
    createPlant("sprout-pot", new THREE.Vector3(-3.28, 0.42, 1.78), 0x6bbf75);
    ui.showSpeech("I packed snacks, books, seats, lamps, and leafy gossip.");
  }

  function resetRoomV2() {
    createBox("cube-blue", "cube", new THREE.Vector3(0.72, 0.72, 0.72), new THREE.Vector3(-2.1, 1.1, 0.3), palette.cubeBlue, 1.25, { affordances: ["stack", "boop"], tags: ["block", "blue"] });
    createBox("cube-coral", "cube", new THREE.Vector3(0.62, 0.62, 0.62), new THREE.Vector3(1.8, 1.2, -0.4), palette.cubeCoral, 1.0, { affordances: ["stack", "pretend"], tags: ["block", "coral"] });
    createBall("soft-ball", "ball", 0.38, new THREE.Vector3(0.4, 1.0, 1.55), palette.cubeAmber, 0.76, { affordances: ["boop", "throw", "play"], tags: ["ball", "soft", "yellow", "amber"] });
    createBall("moon-ball", "ball", 0.3, new THREE.Vector3(-3.1, 1.0, 1.9), makeMat(0xd7eee8), 0.62, { affordances: ["lift", "roll", "play"], tags: ["moon", "ball"] });
    createBall("beach-orb", "ball", 0.42, new THREE.Vector3(3.4, 1.0, 1.55), makeMat(0xf5f7ff), 0.58, { affordances: ["play", "roll", "bounce"], tags: ["beach", "ball"] });
    for (let i = 0; i < 8; i += 1) {
      createBox(`domino-${i + 1}`, "domino", new THREE.Vector3(0.16, 0.78, 0.38), new THREE.Vector3(-1.4 + i * 0.36, 0.82, -1.55), makeMat(i % 2 ? 0x1d2424 : 0xffffff), 0.5, { affordances: ["stack", "topple"], tags: ["domino", "chain"] });
    }
    createBox("tiny-clock", "clock", new THREE.Vector3(0.48, 0.48, 0.18), new THREE.Vector3(4.1, 0.8, 1.05), palette.metal, 0.7, { affordances: ["inspect", "rewind"], tags: ["clock", "metal"] });
    createBerry("berry-rose", new THREE.Vector3(-4.35, 0.31, 0.9), 0xb93576, 0xff77a8);
    createBerry("berry-amber", new THREE.Vector3(-3.8, 0.31, 0.55), 0xe6544e, 0xffb35b);
    createBerry("berry-moon", new THREE.Vector3(-3.25, 0.31, 1.0), 0x6d5bd6, 0x9ed4ff);
    createBook("story-book-blue", new THREE.Vector3(3.35, 0.16, -2.15), 0x3f87a8, 0xfff1c8);
    createBook("field-notes", new THREE.Vector3(4.0, 0.16, -1.78), 0x8c7ac0, 0xffdf6e);
    createTable("tea-table", new THREE.Vector3(-1.45, 0.44, -2.72), 0x8e623a);
    createChair("chair-mint", new THREE.Vector3(-2.32, 0.45, -2.98), 0x7bb9a8);
    createChair("chair-coral", new THREE.Vector3(-0.58, 0.45, -2.96), 0xff8a6b);
    createChair("chair-honey", new THREE.Vector3(-1.45, 0.45, -3.45), 0xe5b94e);
    createToyLamp("lamp", new THREE.Vector3(-4.65, 0.5, -1.25), 0xffde71, 1.08);
    createToyLamp("reading-lamp", new THREE.Vector3(4.75, 0.42, 1.82), 0x9ed4ff, 0.82);
    createPlant("fern-pot", new THREE.Vector3(4.65, 0.42, -2.42), 0x5e9c62);
    createPlant("sprout-pot", new THREE.Vector3(-4.7, 0.42, 2.38), 0x6bbf75);
    createWaste("crumpled-paper", new THREE.Vector3(1.05, 0.42, 2.82), "paper", 0xf3f1df);
    createWaste("tin-can", new THREE.Vector3(1.78, 0.44, 2.58), "can", 0xb8c7c3);
    createWaste("plastic-bottle", new THREE.Vector3(2.48, 0.5, 2.78), "bottle", 0x9ed4ff);
    createWaste("banana-peel", new THREE.Vector3(3.12, 0.34, 2.36), "peel", 0xffd75a);
    createRecycleBin("recycle-bin", new THREE.Vector3(4.65, 0.58, 2.58));
    createRamp("cardboard-ramp", new THREE.Vector3(-4.0, 0.38, -3.15));
    ui.showSpeech("Toy Room v2 is awake with four little agents.");
  }

  function resetRoomV3() {
    createBox("cube-blue", "cube", new THREE.Vector3(0.72, 0.72, 0.72), new THREE.Vector3(-2.45, 1.08, 0.45), palette.cubeBlue, 1.25, { affordances: ["stack", "boop", "push"], tags: ["block", "blue"] });
    createBox("cube-coral", "cube", new THREE.Vector3(0.62, 0.62, 0.62), new THREE.Vector3(1.82, 1.1, -0.44), palette.cubeCoral, 1.0, { affordances: ["stack", "pretend", "push"], tags: ["block", "coral"] });
    createBox("ember-block", "cube", new THREE.Vector3(0.48, 0.48, 0.48), new THREE.Vector3(-0.1, 1.0, -1.25), makeMat(0xff8a4a, { roughness: 0.62, emissive: 0xff704d, emissiveIntensity: 0.06 }), 0.8, { affordances: ["warm", "stack", "inspect"], tags: ["fire-boy", "block"] });
    createBall("soft-ball", "ball", 0.38, new THREE.Vector3(0.72, 1.0, 1.95), palette.cubeAmber, 0.76, { affordances: ["boop", "throw", "play"], tags: ["ball", "soft", "yellow", "amber"] });
    createBall("moon-ball", "ball", 0.3, new THREE.Vector3(-2.9, 0.95, 2.0), makeMat(0xd7eee8), 0.62, { affordances: ["lift", "roll", "play"], tags: ["moon", "ball"] });
    createBall("beach-orb", "ball", 0.42, new THREE.Vector3(3.3, 0.95, 1.65), makeMat(0xf5f7ff), 0.58, { affordances: ["play", "roll", "bounce"], tags: ["beach", "ball"] });
    for (let i = 0; i < 7; i += 1) {
      createBox(`domino-${i + 1}`, "domino", new THREE.Vector3(0.16, 0.78, 0.38), new THREE.Vector3(-1.25 + i * 0.36, 0.82, -2.02), makeMat(i % 2 ? 0x1d2424 : 0xffffff), 0.5, { affordances: ["stack", "topple"], tags: ["domino", "chain"] });
    }
    createBox("tiny-clock", "clock", new THREE.Vector3(0.48, 0.48, 0.18), new THREE.Vector3(3.72, 0.78, 0.78), palette.metal, 0.7, { affordances: ["inspect", "rewind"], tags: ["clock", "metal"] });
    createBerry("berry-rose", new THREE.Vector3(-3.95, 0.31, 0.95), 0xb93576, 0xff77a8);
    createBerry("berry-amber", new THREE.Vector3(-3.38, 0.31, 0.56), 0xe6544e, 0xffb35b);
    createBerry("berry-moon", new THREE.Vector3(-2.86, 0.31, 1.08), 0x6d5bd6, 0x9ed4ff);
    createBook("story-book-blue", new THREE.Vector3(2.72, 0.16, -2.35), 0x3f87a8, 0xfff1c8);
    createBook("field-notes", new THREE.Vector3(3.38, 0.16, -1.96), 0x8c7ac0, 0xffdf6e);
    createTable("tea-table", new THREE.Vector3(-1.45, 0.44, -3.0), 0x8e623a);
    createChair("chair-mint", new THREE.Vector3(-2.3, 0.45, -3.22), 0x7bb9a8);
    createChair("chair-coral", new THREE.Vector3(-0.6, 0.45, -3.18), 0xff8a6b);
    createChair("chair-honey", new THREE.Vector3(-1.45, 0.45, -3.66), 0xe5b94e);
    createToyLamp("lamp", new THREE.Vector3(-4.65, 0.5, -1.24), 0xffde71, 1.12);
    createToyLamp("reading-lamp", new THREE.Vector3(4.62, 0.42, 1.92), 0x9ed4ff, 0.86);
    createPlant("fern-pot", new THREE.Vector3(4.52, 0.42, -2.44), 0x5e9c62);
    createPlant("sprout-pot", new THREE.Vector3(-4.55, 0.42, 2.46), 0x6bbf75);
    createWaste("crumpled-paper", new THREE.Vector3(0.98, 0.42, 3.02), "paper", 0xf3f1df);
    createWaste("tin-can", new THREE.Vector3(1.72, 0.44, 2.76), "can", 0xb8c7c3);
    createWaste("plastic-bottle", new THREE.Vector3(2.45, 0.5, 2.96), "bottle", 0x9ed4ff);
    createWaste("banana-peel", new THREE.Vector3(3.08, 0.34, 2.46), "peel", 0xffd75a);
    createRecycleBin("recycle-bin", new THREE.Vector3(4.62, 0.58, 2.76));
    createRamp("cardboard-ramp", new THREE.Vector3(-4.0, 0.38, -3.18));
    ui.showSpeech("Toy Room v3 is awake with one tiny Fire Boy.");
  }

  function clearObjects() {
    for (const entry of objects) removeObject(entry);
    objects.length = 0;
    bodyHistory.clear();
    frozenBodies.clear();
  }

  function removeObject(entry) {
    scene.remove(entry.mesh);
    world.removeBody(entry.body);
    bodyHistory.delete(entry.id);
    frozenBodies.delete(entry.id);
  }

  function consumeObject(id) {
    const index = objects.findIndex((entry) => entry.id === id);
    if (index < 0) return null;
    const [entry] = objects.splice(index, 1);
    removeObject(entry);
    return entry;
  }

  function nearestObject(pet) {
    if (!pet || !objects.length) return null;
    return [...objects].sort((a, b) => {
      const pa = new THREE.Vector3(a.body.position.x, a.body.position.y, a.body.position.z);
      const pb = new THREE.Vector3(b.body.position.x, b.body.position.y, b.body.position.z);
      return pa.distanceTo(pet.group.position) - pb.distanceTo(pet.group.position);
    })[0];
  }

  function updatePhysics(now, dt) {
    world.step(1 / 60, dt, 4);
    for (const [id, freeze] of frozenBodies.entries()) {
      const entry = objects.find((item) => item.id === id);
      if (!entry || now > freeze.until) {
        frozenBodies.delete(id);
        continue;
      }
      entry.body.position.copy(freeze.position);
      entry.body.quaternion.copy(freeze.quaternion);
      entry.body.velocity.set(0, 0, 0);
      entry.body.angularVelocity.set(0, 0, 0);
    }
    for (const entry of objects) {
      entry.mesh.position.copy(entry.body.position);
      entry.mesh.quaternion.copy(entry.body.quaternion);
    }
    if (now - lastHistoryCapture > 140) {
      lastHistoryCapture = now;
      for (const entry of objects) {
        const arr = bodyHistory.get(entry.id) || [];
        arr.push({ position: entry.body.position.clone(), quaternion: entry.body.quaternion.clone() });
        while (arr.length > 42) arr.shift();
        bodyHistory.set(entry.id, arr);
      }
    }
  }

  function createBerry(id, position, baseColor, accentColor) {
    const berryMat = makeMat(baseColor, { roughness: 0.62 });
    const blushMat = makeMat(accentColor, { roughness: 0.58, emissive: accentColor, emissiveIntensity: 0.05 });
    const leafMat = makeMat(0x4f8f52, { roughness: 0.82 });
    const stemMat = makeMat(0x6d4c35, { roughness: 0.86 });
    return createCompositeObject(
      id,
      "berry",
      position,
      { type: "sphere", radius: 0.25 },
      0.22,
      (group) => {
        const berries = [
          [-0.08, -0.02, 0.02, 0.105, berryMat],
          [0.08, -0.02, 0.03, 0.105, berryMat],
          [0.0, 0.09, -0.02, 0.11, blushMat],
          [0.01, -0.1, -0.04, 0.09, berryMat],
        ];
        for (const [x, y, z, radius, mat] of berries) {
          group.add(meshSphere(radius, mat, [x, y, z], [1, 1.04, 0.96], 24));
        }
        group.add(meshCylinder(0.018, 0.18, stemMat, [0.02, 0.22, -0.02], [0.2, 0, -0.28], 12));
        group.add(meshSphere(0.065, leafMat, [-0.08, 0.19, 0.02], [1.6, 0.34, 0.78], 18));
        group.add(meshSphere(0.06, leafMat, [0.11, 0.18, 0.0], [1.45, 0.32, 0.72], 18));
      },
      { affordances: ["eat", "sniff", "share"], tags: ["food", "hunger"], nutrition: 34, consumable: true, linearDamping: 0.24, angularDamping: 0.32 },
    );
  }

  function createBook(id, position, coverColor, detailColor) {
    const cover = makeMat(coverColor, { roughness: 0.76 });
    const pages = makeMat(0xfff4dc, { roughness: 0.88 });
    const detail = makeMat(detailColor, { roughness: 0.64, emissive: detailColor, emissiveIntensity: 0.03 });
    return createCompositeObject(
      id,
      "book",
      position,
      { type: "box", size: new THREE.Vector3(0.68, 0.14, 0.48) },
      0.45,
      (group) => {
        group.add(meshBox([0.64, 0.05, 0.45], cover, [0, 0.035, 0], [0.02, 0.08, -0.04]));
        group.add(meshBox([0.6, 0.06, 0.4], pages, [0.02, -0.01, 0.02], [0.02, 0.08, -0.04]));
        group.add(meshBox([0.08, 0.08, 0.47], cover, [-0.31, 0.005, 0], [0.02, 0.08, -0.04]));
        group.add(meshBox([0.42, 0.018, 0.035], detail, [0.06, 0.075, -0.12], [0.02, 0.08, -0.04]));
        group.add(meshBox([0.28, 0.018, 0.035], detail, [0.02, 0.078, 0.06], [0.02, 0.08, -0.04]));
        group.add(meshBox([0.035, 0.012, 0.34], makeMat(0xff6f83, { roughness: 0.72 }), [0.24, 0.088, 0.01], [0.02, 0.08, -0.04]));
      },
      { affordances: ["read", "carry", "stack"], tags: ["book", "reading"], readable: true, curiosity: 28, linearDamping: 0.18, angularDamping: 0.24 },
    );
  }

  function createChair(id, position, color) {
    const painted = makeMat(color, { roughness: 0.78 });
    const cushion = makeMat(0xfff0d9, { roughness: 0.9 });
    return createCompositeObject(
      id,
      "chair",
      position,
      { type: "box", size: new THREE.Vector3(0.54, 0.78, 0.54) },
      1.15,
      (group) => {
        group.add(meshBox([0.46, 0.08, 0.42], painted, [0, -0.1, 0.04], [0, 0, 0]));
        group.add(meshBox([0.39, 0.055, 0.34], cushion, [0, -0.045, 0.05], [0, 0, 0]));
        group.add(meshBox([0.46, 0.48, 0.07], painted, [0, 0.17, -0.18], [0.08, 0, 0]));
        for (const x of [-0.17, 0.17]) {
          for (const z of [-0.13, 0.21]) {
            group.add(meshBox([0.055, 0.42, 0.055], painted, [x, -0.33, z], [0.02 * Math.sign(x), 0, 0.02 * Math.sign(z)]));
          }
        }
        group.add(meshSphere(0.065, cushion, [0, 0.4, -0.21], [2.7, 0.54, 0.72], 18));
      },
      { affordances: ["sit", "climb", "hide_under", "gather"], tags: ["furniture", "social"], comfort: 18, linearDamping: 0.22, angularDamping: 0.38 },
    );
  }

  function createTable(id, position, color) {
    const wood = makeMat(color, { roughness: 0.72 });
    const trim = makeMat(0xffe0a4, { roughness: 0.7 });
    return createCompositeObject(
      id,
      "table",
      position,
      { type: "box", size: new THREE.Vector3(0.96, 0.66, 0.72) },
      2.4,
      (group) => {
        group.add(meshBox([0.86, 0.09, 0.62], wood, [0, 0.2, 0], [0, 0.03, 0]));
        group.add(meshBox([0.72, 0.025, 0.5], trim, [0, 0.26, 0], [0, 0.03, 0]));
        for (const x of [-0.32, 0.32]) {
          for (const z of [-0.22, 0.22]) {
            group.add(meshCylinder(0.035, 0.52, wood, [x, -0.08, z], [0.03 * Math.sign(z), 0, 0.03 * Math.sign(x)], 16));
          }
        }
        group.add(meshSphere(0.06, trim, [0, 0.34, 0], [1.7, 0.45, 1.7], 18));
      },
      { affordances: ["gather", "place_object", "hide_under"], tags: ["furniture", "social"], social: 18, linearDamping: 0.24, angularDamping: 0.42 },
    );
  }

  function createToyLamp(id, position, glowColor, scale = 1) {
    const base = makeMat(0x64736c, { roughness: 0.48, metalness: 0.08 });
    const shade = makeMat(glowColor, { roughness: 0.58, emissive: glowColor, emissiveIntensity: 0.32, transparent: true, opacity: 0.9 });
    const warm = makeMat(0xfff2a6, { roughness: 0.36, emissive: 0xffde71, emissiveIntensity: 0.55 });
    return createCompositeObject(
      id,
      "lamp",
      position,
      { type: "box", size: new THREE.Vector3(0.38 * scale, 0.9 * scale, 0.38 * scale) },
      0.95 * scale,
      (group) => {
        group.scale.setScalar(scale);
        group.add(meshCylinder(0.16, 0.045, base, [0, -0.39, 0], [0, 0, 0], 32));
        group.add(meshCylinder(0.026, 0.5, base, [0, -0.12, 0], [0, 0, 0], 16));
        group.add(meshSphere(0.09, warm, [0, 0.16, 0], [1, 1, 1], 18));
        const shadeMesh = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.26, 32, 1, true), shade);
        shadeMesh.position.set(0, 0.27, 0);
        shadeMesh.rotation.y = Math.PI / 8;
        group.add(shadeMesh);
        group.add(meshSphere(0.04, base, [0, 0.43, 0], [1, 0.65, 1], 16));
      },
      { affordances: ["inspect", "light", "warm", "gather"], tags: ["lamp", "light"], comfort: 12, linearDamping: 0.2, angularDamping: 0.36 },
    );
  }

  function createPlant(id, position, leafColor) {
    const pot = makeMat(0xc9794b, { roughness: 0.86 });
    const potBand = makeMat(0xffc58e, { roughness: 0.78 });
    const leaf = makeMat(leafColor, { roughness: 0.88 });
    const darkLeaf = makeMat(0x3f7d4c, { roughness: 0.9 });
    return createCompositeObject(
      id,
      "plant",
      position,
      { type: "box", size: new THREE.Vector3(0.52, 0.78, 0.52) },
      1.05,
      (group) => {
        group.add(meshCylinder(0.19, 0.28, pot, [0, -0.25, 0], [0, 0, 0], 36));
        group.add(meshCylinder(0.205, 0.035, potBand, [0, -0.1, 0], [0, 0, 0], 36));
        const leaves = [
          [-0.13, 0.12, 0.0, -0.72, leaf],
          [0.14, 0.1, 0.02, 0.72, leaf],
          [0.0, 0.19, -0.1, 0.0, darkLeaf],
          [-0.06, 0.28, 0.08, -0.28, leaf],
          [0.08, 0.27, 0.1, 0.32, darkLeaf],
        ];
        for (const [x, y, z, rz, mat] of leaves) {
          const leafMesh = meshSphere(0.12, mat, [x, y, z], [0.64, 1.85, 0.24], 20);
          leafMesh.rotation.z = rz;
          leafMesh.rotation.x = 0.2;
          group.add(leafMesh);
        }
      },
      { affordances: ["sniff", "water", "hide", "inspect"], tags: ["plant", "calm"], comfort: 15, curiosity: 12, linearDamping: 0.24, angularDamping: 0.42 },
    );
  }

  function createWaste(id, position, wasteKind, color) {
    const mat = makeMat(color, { roughness: wasteKind === "can" ? 0.38 : 0.84, metalness: wasteKind === "can" ? 0.16 : 0 });
    return createCompositeObject(
      id,
      "waste",
      position,
      { type: wasteKind === "paper" ? "sphere" : "box", radius: 0.22, size: new THREE.Vector3(0.38, 0.36, 0.38) },
      wasteKind === "paper" ? 0.18 : 0.42,
      (group) => {
        if (wasteKind === "paper") {
          group.add(meshSphere(0.19, mat, [0, 0, 0], [1.2, 0.82, 1.0], 18));
          group.add(meshSphere(0.12, mat, [0.12, 0.05, -0.06], [0.8, 0.58, 0.7], 14));
        } else if (wasteKind === "can") {
          group.add(meshCylinder(0.16, 0.34, mat, [0, 0, 0], [0.12, 0, 0.18], 28));
          group.add(meshCylinder(0.13, 0.02, makeMat(0xe3ece9, { roughness: 0.34, metalness: 0.2 }), [0, 0.18, 0], [0.12, 0, 0.18], 28));
        } else if (wasteKind === "bottle") {
          group.add(meshCylinder(0.13, 0.42, mat, [0, -0.02, 0], [0.18, 0, -0.12], 28));
          group.add(meshCylinder(0.07, 0.18, makeMat(0x6cc2cf, { roughness: 0.52 }), [0.02, 0.27, 0], [0.18, 0, -0.12], 20));
          group.add(meshCylinder(0.075, 0.04, makeMat(0x1d2424, { roughness: 0.62 }), [0.03, 0.38, 0], [0.18, 0, -0.12], 20));
        } else {
          group.add(meshSphere(0.16, mat, [-0.08, 0, 0], [1.7, 0.28, 0.42], 18));
          group.add(meshSphere(0.13, mat, [0.12, 0.02, 0], [1.45, 0.24, 0.38], 18));
          group.add(meshSphere(0.05, makeMat(0x6d4c35), [0.0, 0.05, 0.01], [1, 0.5, 1], 12));
        }
      },
      { affordances: ["clean", "recycle", "inspect", "throw"], tags: ["waste", wasteKind], recyclable: wasteKind !== "peel", nutrition: wasteKind === "peel" ? 6 : 0, linearDamping: 0.18, angularDamping: 0.24 },
    );
  }

  function createRecycleBin(id, position) {
    const blue = makeMat(0x3f87a8, { roughness: 0.72 });
    const rim = makeMat(0xd7eee8, { roughness: 0.62 });
    return createCompositeObject(
      id,
      "recycle-bin",
      position,
      { type: "box", size: new THREE.Vector3(0.74, 0.92, 0.74) },
      3.2,
      (group) => {
        group.add(meshBox([0.7, 0.66, 0.68], blue, [0, -0.08, 0], [0, 0, 0]));
        group.add(meshBox([0.82, 0.08, 0.78], rim, [0, 0.29, 0], [0, 0, 0]));
        group.add(meshBox([0.38, 0.035, 0.05], rim, [0, 0.42, 0.34], [0, 0, 0]));
        group.add(meshBox([0.05, 0.2, 0.05], rim, [-0.19, 0.34, 0.34], [0, 0, 0]));
        group.add(meshBox([0.05, 0.2, 0.05], rim, [0.19, 0.34, 0.34], [0, 0, 0]));
      },
      { affordances: ["recycle", "clean", "gather"], tags: ["bin", "recycle", "target"], comfort: 4, linearDamping: 0.38, angularDamping: 0.5 },
    );
  }

  function createRamp(id, position) {
    const cardboard = makeMat(0xc7955d, { roughness: 0.9 });
    return createCompositeObject(
      id,
      "ramp",
      position,
      { type: "box", size: new THREE.Vector3(1.5, 0.24, 0.86) },
      1.6,
      (group) => {
        group.add(meshBox([1.45, 0.12, 0.82], cardboard, [0, 0, 0], [-0.28, 0, 0]));
        group.add(meshBox([1.35, 0.025, 0.72], makeMat(0xe9c796, { roughness: 0.86 }), [0.02, 0.08, 0], [-0.28, 0, 0]));
      },
      { affordances: ["roll", "jump", "play"], tags: ["ramp", "cardboard"], linearDamping: 0.24, angularDamping: 0.32 },
    );
  }

  function spawnGeneratedObject(recipe = {}, nearPosition = new THREE.Vector3(0, 0.8, 0)) {
    const id = uniqueObjectId(recipe.id || recipe.name || "generated-toy");
    const kind = safeToken(recipe.kind || "toy", "toy");
    const shape = ["box", "sphere", "cylinder", "composite"].includes(recipe.shape) ? recipe.shape : "composite";
    const size = safeSize(recipe.size, shape);
    const position = clampSpawnPosition(
      new THREE.Vector3(
        Number(nearPosition.x || 0) + 0.78,
        Math.max(0.42, Number(nearPosition.y || 0.8) + 0.22),
        Number(nearPosition.z || 0) + 0.34,
      ),
      size,
    );
    const color = colorFromRecipe(recipe.color, 0x8bd5e5);
    const accent = colorFromRecipe(recipe.accentColor, 0xffd75a);
    const mass = THREE.MathUtils.clamp(Number(recipe.mass || 0.8), 0.08, 4);
    const parts = Array.isArray(recipe.parts) ? recipe.parts.slice(0, 6) : [];
    const collider = shape === "sphere"
      ? { type: "sphere", radius: THREE.MathUtils.clamp(Number(recipe.radius || Math.max(size.x, size.y, size.z) / 2), 0.08, 0.9) }
      : { type: "box", size };

    return createCompositeObject(
      id,
      kind,
      position,
      collider,
      mass,
      (group) => {
        if (parts.length) {
          for (const part of parts) buildGeneratedPart(group, part, color, accent);
        } else {
          buildDefaultGeneratedShape(group, shape, size, color, accent, Number(recipe.radius || 0.22));
        }
      },
      {
        name: String(recipe.name || id).slice(0, 54),
        affordances: safeStringList(recipe.affordances, ["play", "inspect"]),
        tags: safeStringList(recipe.tags, ["generated", kind]),
        generated: true,
        linearDamping: 0.16,
        angularDamping: 0.24,
      },
    );
  }

  function buildGeneratedPart(group, part, baseColor, accentColor) {
    const shape = ["box", "sphere", "cylinder"].includes(part.shape) ? part.shape : "box";
    const mat = makeMat(colorFromRecipe(part.color, group.children.length % 2 ? accentColor : baseColor), { roughness: 0.68 });
    const offset = safeArray(part.offset, [0, 0, 0], -1.4, 1.4);
    const rotation = safeArray(part.rotation, [0, 0, 0], -3.2, 3.2);
    let mesh;
    if (shape === "sphere") {
      mesh = meshSphere(THREE.MathUtils.clamp(Number(part.radius || 0.14), 0.03, 0.9), mat, offset, [1, 1, 1], 22);
    } else if (shape === "cylinder") {
      mesh = meshCylinder(
        THREE.MathUtils.clamp(Number(part.radius || 0.14), 0.03, 0.9),
        THREE.MathUtils.clamp(Number(part.height || 0.28), 0.04, 1.8),
        mat,
        offset,
        rotation,
        24,
      );
    } else {
      mesh = meshBox(safeArray(part.size, [0.32, 0.24, 0.32], 0.04, 1.8), mat, offset, rotation);
    }
    group.add(mesh);
  }

  function buildDefaultGeneratedShape(group, shape, size, color, accent, radius) {
    const primary = makeMat(color, { roughness: 0.66 });
    const detail = makeMat(accent, { roughness: 0.58, emissive: accent, emissiveIntensity: 0.04 });
    if (shape === "sphere") {
      group.add(meshSphere(Math.max(0.08, radius), primary, [0, 0, 0], [1, 1, 1], 28));
      group.add(meshSphere(Math.max(0.04, radius * 0.28), detail, [0, radius * 0.72, radius * 0.36], [1, 1, 1], 16));
    } else if (shape === "cylinder") {
      group.add(meshCylinder(Math.max(0.08, size.x / 2), size.y, primary, [0, 0, 0], [0, 0, 0], 28));
      group.add(meshCylinder(Math.max(0.06, size.x / 2.1), 0.035, detail, [0, size.y / 2 + 0.02, 0], [0, 0, 0], 28));
    } else {
      group.add(meshBox([size.x, size.y, size.z], primary, [0, 0, 0], [0.02, 0.06, -0.03]));
      group.add(meshBox([size.x * 0.62, 0.045, size.z * 0.22], detail, [0, size.y / 2 + 0.04, size.z * 0.18], [0.02, 0.06, -0.03]));
    }
  }

  function uniqueObjectId(value) {
    const base = safeToken(value, "generated-toy").slice(0, 44) || "generated-toy";
    let id = base;
    let suffix = 2;
    while (objects.some((entry) => entry.id === id)) {
      id = `${base}-${suffix}`;
      suffix += 1;
    }
    return id;
  }

  function safeToken(value, fallback) {
    const text = String(value || fallback).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return text || fallback;
  }

  function safeStringList(value, fallback) {
    if (!Array.isArray(value)) return fallback;
    const cleaned = value.map((item) => String(item || "").slice(0, 32)).filter(Boolean).slice(0, 6);
    return cleaned.length ? cleaned : fallback;
  }

  function safeSize(value, shape) {
    if (!value || typeof value !== "object") {
      const side = shape === "sphere" ? 0.46 : 0.58;
      return new THREE.Vector3(side, side, side);
    }
    return new THREE.Vector3(
      THREE.MathUtils.clamp(Number(value.x || 0.58), 0.12, 1.8),
      THREE.MathUtils.clamp(Number(value.y || 0.5), 0.12, 1.8),
      THREE.MathUtils.clamp(Number(value.z || 0.58), 0.12, 1.8),
    );
  }

  function safeArray(value, fallback, low, high) {
    if (!Array.isArray(value) || value.length < 3) return fallback;
    return [
      THREE.MathUtils.clamp(Number(value[0] || fallback[0]), low, high),
      THREE.MathUtils.clamp(Number(value[1] || fallback[1]), low, high),
      THREE.MathUtils.clamp(Number(value[2] || fallback[2]), low, high),
    ];
  }

  function colorFromRecipe(value, fallback) {
    if (typeof fallback === "string") fallback = Number.parseInt(fallback.slice(1), 16);
    if (typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value)) return Number.parseInt(value.slice(1), 16);
    if (Number.isFinite(value)) return Number(value);
    return fallback;
  }

  function clampSpawnPosition(position, size) {
    return new THREE.Vector3(
      THREE.MathUtils.clamp(position.x, -bounds.halfX + size.x, bounds.halfX - size.x),
      THREE.MathUtils.clamp(position.y, size.y / 2 + 0.1, 2.4),
      THREE.MathUtils.clamp(position.z, -bounds.halfZ + size.z, bounds.halfZ - size.z),
    );
  }

  return { bounds, consumeObject, objects, bodyHistory, frozenBodies, lights, nearestObject, resetRoom, spawnGeneratedObject, updatePhysics };
}

function createPalette() {
  return {
    floor: makeMat(0xfff8e8, { roughness: 0.78 }),
    wall: makeMat(0xf0f7f3, { roughness: 0.86 }),
    cubeBlue: makeMat(0x88b9c2, { roughness: 0.66 }),
    cubeCoral: makeMat(0xff704d, { roughness: 0.66 }),
    cubeAmber: makeMat(0xffcc4f, { roughness: 0.6 }),
    metal: makeMat(0xbfc4b8, { roughness: 0.32, metalness: 0.18 }),
  };
}

function addLights(scene) {
  const hemi = new THREE.HemisphereLight(0xfff7df, 0x8bb8c2, 3.35);
  scene.add(hemi);
  const keyLight = new THREE.DirectionalLight(0xffffff, 3.15);
  keyLight.position.set(3.4, 6.8, 4.1);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(2048, 2048);
  keyLight.shadow.camera.near = 0.5;
  keyLight.shadow.camera.far = 18;
  keyLight.shadow.camera.left = -7;
  keyLight.shadow.camera.right = 7;
  keyLight.shadow.camera.top = 7;
  keyLight.shadow.camera.bottom = -7;
  scene.add(keyLight);
  const fillLight = new THREE.PointLight(0xffcc4f, 52, 9.5);
  fillLight.position.set(-2.8, 2.2, 2.4);
  scene.add(fillLight);
  const rimLight = new THREE.DirectionalLight(0xfff0d2, 1.15);
  rimLight.position.set(-3.8, 3.1, -4.2);
  scene.add(rimLight);
  return { keyLight, fillLight, rimLight };
}

function meshesIn(root) {
  const meshes = [];
  if (root?.isMesh) meshes.push(root);
  if (root?.traverse) {
    root.traverse((node) => {
      if (node.isMesh && !meshes.includes(node)) meshes.push(node);
    });
  }
  return meshes;
}

function meshSphere(radius, material, position, scale = [1, 1, 1], segments = 24) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, segments, Math.max(12, Math.round(segments * 0.65))), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.scale.set(scale[0], scale[1], scale[2]);
  return mesh;
}

function meshBox(size, material, position, rotation = [0, 0, 0]) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(size[0], size[1], size[2]), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  return mesh;
}

function meshCylinder(radius, height, material, position, rotation = [0, 0, 0], segments = 24) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, segments), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  return mesh;
}
