import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import {
  Bone,
  createIcons,
  Download,
  RefreshCw,
  RotateCcw,
} from "https://cdn.jsdelivr.net/npm/lucide@0.468.0/+esm";

createIcons({ icons: { Bone, Download, RefreshCw, RotateCcw } });

const dom = {
  canvas: document.getElementById("modelCanvas"),
  assetList: document.getElementById("assetList"),
  assetTitle: document.getElementById("assetTitle"),
  assetVersion: document.getElementById("assetVersion"),
  assetPath: document.getElementById("assetPath"),
  statsGrid: document.getElementById("statsGrid"),
  renderStrip: document.getElementById("renderStrip"),
  previewImage: document.getElementById("previewImage"),
  previewLabel: document.getElementById("previewLabel"),
  downloadLink: document.getElementById("downloadLink"),
  resetView: document.getElementById("resetView"),
  rotateToggle: document.getElementById("rotateToggle"),
  wireToggle: document.getElementById("wireToggle"),
  rigToggle: document.getElementById("rigToggle"),
  labelToggle: document.getElementById("labelToggle"),
  animationSelect: document.getElementById("animationSelect"),
  status: document.getElementById("viewerStatus"),
};

const renderer = new THREE.WebGLRenderer({ canvas: dom.canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.22;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const labelRenderer = new CSS2DRenderer();
labelRenderer.domElement.className = "rig-label-layer";
dom.canvas.parentElement.appendChild(labelRenderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf7f2e8);

const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 200);
camera.position.set(2.6, 1.8, 4.6);
scene.add(camera);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.autoRotate = false;
controls.autoRotateSpeed = 0.85;
controls.target.set(0, 0.8, 0);
controls.minDistance = 0.8;
controls.maxDistance = 14;

const floor = new THREE.Mesh(
  new THREE.CylinderGeometry(1.75, 1.95, 0.07, 96),
  new THREE.MeshStandardMaterial({ color: 0xfff2d8, roughness: 0.84 }),
);
floor.position.y = -0.04;
floor.receiveShadow = true;
scene.add(floor);

const grid = new THREE.GridHelper(4.2, 16, 0x91bfc0, 0xd9d0bd);
grid.position.y = 0;
grid.material.transparent = true;
grid.material.opacity = 0.28;
scene.add(grid);

scene.add(new THREE.AmbientLight(0xffffff, 0.58));
scene.add(new THREE.HemisphereLight(0xffffff, 0x8fb3b4, 2.8));

const key = new THREE.DirectionalLight(0xffffff, 2.8);
key.position.set(3.2, 5.0, 5.2);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
scene.add(key);

const frontFill = new THREE.DirectionalLight(0xfff3dc, 2.15);
frontFill.position.set(-2.4, 2.6, 5.6);
scene.add(frontFill);

const cameraFill = new THREE.PointLight(0xffffff, 1.05, 8.0);
cameraFill.position.set(0, 0.4, 1.2);
camera.add(cameraFill);

const rim = new THREE.DirectionalLight(0x70cfe0, 1.35);
rim.position.set(-3.2, 2.3, -2.5);
scene.add(rim);

const loader = new GLTFLoader();
const clock = new THREE.Clock();
const scratchVertex = new THREE.Vector3();
const scratchBonePoint = new THREE.Vector3();

let assets = [];
let activeAsset = null;
let activeRoot = null;
let activeRigHelper = null;
let activeRigLabels = [];
let activeRigMarkers = [];
let mixer = null;
let activeAction = null;
let actions = new Map();
let wireframe = false;
let rigVisible = false;
let labelsVisible = false;

const RIG_BONE_LABELS = new Map([
  ["Root", "Hip / Root"],
  ["Spine", "Body / Spine"],
  ["Head", "Head"],
  ["Arm.L", "Left arm"],
  ["Hand.L", "Left hand"],
  ["Arm.R", "Right arm"],
  ["Hand.R", "Right hand"],
  ["Leg.L", "Left leg"],
  ["Foot.L", "Left foot"],
  ["Leg.R", "Right leg"],
  ["Foot.R", "Right foot"],
  ["Hat", "Hat socket"],
  ["Backpack", "Backpack socket"],
  ["Chest", "Chest socket"],
  ["Prop.L", "Left prop socket"],
  ["Prop.R", "Right prop socket"],
]);

const RIG_LABEL_OFFSETS = {
  Root: [-0.18, 0.04, 0],
  Spine: [0.18, 0.03, 0],
  Head: [0.16, 0.06, 0],
  "Arm.L": [-0.14, 0.03, 0],
  "Hand.L": [-0.18, -0.02, 0],
  "Arm.R": [0.14, 0.03, 0],
  "Hand.R": [0.18, -0.02, 0],
  "Leg.L": [-0.13, 0.02, 0],
  "Foot.L": [-0.16, -0.02, 0],
  "Leg.R": [0.13, 0.02, 0],
  "Foot.R": [0.16, -0.02, 0],
  Hat: [0.15, 0.06, 0],
  Backpack: [0.16, 0.02, -0.04],
  Chest: [0.18, 0.02, 0],
  "Prop.L": [-0.19, 0.02, 0],
  "Prop.R": [0.19, 0.02, 0],
};

dom.resetView.addEventListener("click", () => frameActiveModel());
dom.rotateToggle.addEventListener("click", () => {
  controls.autoRotate = !controls.autoRotate;
  dom.rotateToggle.classList.toggle("active", controls.autoRotate);
});
dom.wireToggle.addEventListener("click", () => {
  wireframe = !wireframe;
  dom.wireToggle.classList.toggle("active", wireframe);
  applyWireframe();
});
dom.rigToggle.addEventListener("click", () => {
  rigVisible = !rigVisible;
  dom.rigToggle.classList.toggle("active", rigVisible);
  if (activeRigHelper) activeRigHelper.visible = rigVisible;
});
dom.labelToggle.addEventListener("change", () => {
  labelsVisible = dom.labelToggle.checked;
  if (labelsVisible && activeRigHelper && !rigVisible) {
    rigVisible = true;
    dom.rigToggle.classList.add("active");
    activeRigHelper.visible = true;
  }
  applyRigLabelVisibility();
});
dom.animationSelect.addEventListener("change", () => {
  playAnimation(dom.animationSelect.value);
});

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function sourceLabel(source) {
  if (source === "fal-sam-3-standing-rigged") return "SAM rig";
  if (source === "fal-sam-3-cleaned") return "SAM clean";
  if (source === "fal-sam-3-base-rigged") return "Base rig";
  if (source === "fal-sam-3-assembly") return "Assembly";
  if (source === "fal-sam-3-part") return "SAM part";
  if (source === "mixamo-motion-test") return "Mixamo";
  if (source === "fal-sam-3") return "SAM 3D";
  if (source === "procedural-blender") return "Blender";
  return "GLB";
}

function renderAssetList() {
  dom.assetList.replaceChildren(...assets.map((asset) => {
    const button = document.createElement("button");
    button.className = "asset-button";
    button.type = "button";
    button.dataset.assetId = asset.id;
    button.innerHTML = `
      <span class="asset-main">
        <span class="asset-name">${asset.title}</span>
        <span class="asset-version">${asset.version}</span>
      </span>
      <span class="asset-badge">${sourceLabel(asset.source)}</span>
    `;
    button.addEventListener("click", () => selectAsset(asset.id));
    return button;
  }));
}

function setStatus(message) {
  dom.status.textContent = message || "";
}

function renderStats(asset) {
  const stats = asset.stats || {};
  const rows = [
    ["Triangles", formatNumber(stats.triangles)],
    ["Vertices", formatNumber(stats.vertices)],
    ["Meshes", formatNumber(stats.meshes)],
    ["Primitives", formatNumber(stats.primitives)],
    ["Materials", formatNumber(stats.materials)],
    ["Textures", formatNumber(stats.textures)],
    ["Nodes", formatNumber(stats.nodes)],
    ["Skins", formatNumber(stats.skins)],
    ["Animations", formatNumber(stats.animations)],
    ["File", formatBytes(stats.file_size)],
  ];
  dom.statsGrid.replaceChildren(...rows.map(([label, value]) => {
    const item = document.createElement("div");
    item.className = "stat";
    item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    return item;
  }));
}

function renderPreviews(asset) {
  const previews = asset.previews || [];
  dom.renderStrip.replaceChildren(...previews.map((preview, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "preview-thumb";
    button.innerHTML = `<img src="${preview.url}" alt="${asset.title} ${preview.label}" /><span>${preview.label}</span>`;
    button.addEventListener("click", () => setPreview(preview, button));
    if (index === 0) requestAnimationFrame(() => setPreview(preview, button));
    return button;
  }));

  if (!previews.length) {
    dom.previewImage.removeAttribute("src");
    dom.previewImage.alt = "";
    dom.previewLabel.textContent = "No render";
  }
}

function setPreview(preview, button) {
  dom.renderStrip.querySelectorAll(".preview-thumb").forEach((thumb) => {
    thumb.classList.toggle("active", thumb === button);
  });
  dom.previewImage.src = preview.url;
  dom.previewImage.alt = preview.label;
  dom.previewLabel.textContent = preview.label;
}

function disposeObject(root) {
  disposeRigLabels();
  if (activeRigHelper) {
    scene.remove(activeRigHelper);
    activeRigHelper.geometry?.dispose?.();
    activeRigHelper.material?.dispose?.();
    activeRigHelper = null;
  }
  mixer?.stopAllAction();
  activeAction = null;
  actions = new Map();
  if (!root) return;
  root.traverse((child) => {
    if (child.isMesh) {
      child.geometry?.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.filter(Boolean).forEach((material) => material.dispose?.());
    }
  });
  scene.remove(root);
}

function selectAsset(id) {
  const asset = assets.find((item) => item.id === id) || assets[0];
  if (!asset) return;
  activeAsset = asset;
  document.querySelectorAll(".asset-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.assetId === asset.id);
  });
  dom.assetTitle.textContent = asset.title;
  dom.assetVersion.textContent = asset.version;
  dom.assetPath.textContent = asset.path;
  dom.downloadLink.href = asset.url;
  renderStats(asset);
  renderPreviews(asset);
  loadModel(asset);
  const params = new URLSearchParams(window.location.search);
  params.set("asset", asset.id);
  history.replaceState(null, "", `${window.location.pathname}?${params}`);
}

function loadModel(asset) {
  disposeObject(activeRoot);
  activeRoot = null;
  mixer = null;
  activeAction = null;
  actions = new Map();
  renderAnimationOptions([]);
  setStatus("Loading");

  loader.load(
    asset.url,
    (gltf) => {
      activeRoot = gltf.scene;
      const samLike = asset.source?.startsWith("fal-sam-3");
      activeRoot.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true;
          child.receiveShadow = !samLike;
          const materials = Array.isArray(child.material) ? child.material : [child.material];
          materials.filter(Boolean).forEach((material) => {
            material.side = THREE.DoubleSide;
            if (samLike) tuneSamMaterial(material);
          });
        }
      });
      normalizeModel(activeRoot, samLike ? 1.68 : 2.25);
      scene.add(activeRoot);
      activeRigHelper = createRigHelper(activeRoot);
      if (activeRigHelper) scene.add(activeRigHelper);
      createRigLabels(activeRoot);
      const clips = sortAnimationClips(gltf.animations || []);
      if (clips.length) {
        mixer = new THREE.AnimationMixer(activeRoot);
        actions = new Map(clips.map((clip) => [clip.name, mixer.clipAction(clip)]));
        renderAnimationOptions(clips);
        playAnimation(clips[0].name);
      } else {
        renderAnimationOptions([]);
      }
      applyWireframe();
      applyRigLabelVisibility();
      frameActiveModel();
      setStatus("");
    },
    undefined,
    () => setStatus("Could not load this GLB"),
  );
}

function createRigHelper(root) {
  let hasSkeleton = false;
  root.traverse((child) => {
    if (child.isSkinnedMesh && child.skeleton?.bones?.length) {
      hasSkeleton = true;
    }
  });
  if (!hasSkeleton) return null;

  const helper = new THREE.SkeletonHelper(root);
  helper.name = "Toybox_Rig_Helper";
  helper.visible = rigVisible;
  helper.renderOrder = 1000;
  helper.material.depthTest = false;
  helper.material.transparent = true;
  helper.material.opacity = 0.94;
  return helper;
}

function niceBoneName(name) {
  return name
    .replace(/^.*Toybox_BaseRig[_-]?/i, "")
    .replace(/_(L|R)$/i, ".$1")
    .replace(/^(Arm|Hand|Prop|Leg|Foot)(L|R)$/i, "$1.$2");
}

function boneClass(name) {
  if (name.endsWith(".L")) return "left";
  if (name.endsWith(".R")) return "right";
  if (["Hat", "Backpack", "Chest", "Prop.L", "Prop.R"].includes(name)) return "socket";
  return "core";
}

function markerColor(name) {
  if (name.endsWith(".L")) return 0x65cbda;
  if (name.endsWith(".R")) return 0xf47d58;
  if (boneClass(name) === "socket") return 0xffffff;
  return 0xf2c14f;
}

function collectRigBones(root) {
  const bones = new Map();
  const addBone = (bone) => {
    const cleanName = niceBoneName(bone.name);
    if (RIG_BONE_LABELS.has(cleanName) && !bones.has(cleanName)) {
      bones.set(cleanName, bone);
    }
  };

  root.traverse((child) => {
    if (child.isBone) {
      addBone(child);
    }
  });

  root.traverse((child) => {
    if (!child.isSkinnedMesh || !child.skeleton?.bones?.length) return;
    child.skeleton.bones.forEach(addBone);
  });

  return [...bones.entries()]
    .sort(([a], [b]) => [...RIG_BONE_LABELS.keys()].indexOf(a) - [...RIG_BONE_LABELS.keys()].indexOf(b));
}

function createRigLabels(root) {
  disposeRigLabels();
  const sceneBoneNames = [];
  const skinBoneNames = [];
  root.traverse((child) => {
    if (child.isBone) sceneBoneNames.push(child.name);
    if (child.isSkinnedMesh && child.skeleton?.bones?.length) {
      child.skeleton.bones.forEach((bone) => skinBoneNames.push(bone.name));
    }
  });
  const bones = collectRigBones(root);
  const markerGeometry = new THREE.SphereGeometry(0.018, 16, 10);

  activeRigLabels = bones.map(([name, bone]) => {
    const element = document.createElement("div");
    element.className = `rig-label ${boneClass(name)}`;
    element.textContent = RIG_BONE_LABELS.get(name) || name;

    const label = new CSS2DObject(element);
    label.name = `RigLabel_${name}`;
    label.userData.bone = bone;
    label.userData.offset = new THREE.Vector3(...(RIG_LABEL_OFFSETS[name] || [0.14, 0.03, 0]));
    label.visible = labelsVisible;
    scene.add(label);
    return label;
  });

  activeRigMarkers = bones.map(([name, bone]) => {
    const marker = new THREE.Mesh(
      markerGeometry,
      new THREE.MeshBasicMaterial({
        color: markerColor(name),
        depthTest: false,
        transparent: true,
        opacity: 0.94,
      }),
    );
    marker.name = `RigPoint_${name}`;
    marker.userData.bone = bone;
    marker.renderOrder = 1001;
    marker.visible = labelsVisible;
    scene.add(marker);
    return marker;
  });

  labelRenderer.domElement.dataset.rigLabelCount = String(activeRigLabels.length);
  labelRenderer.domElement.dataset.rigLabels = activeRigLabels
    .map((label) => label.element.textContent)
    .join(", ");
  labelRenderer.domElement.dataset.sceneBones = sceneBoneNames.join(", ");
  labelRenderer.domElement.dataset.skinBones = skinBoneNames.join(", ");
  dom.labelToggle.disabled = activeRigLabels.length === 0;
  dom.labelToggle.checked = labelsVisible && activeRigLabels.length > 0;
  updateRigLabels();
}

function disposeRigLabels() {
  activeRigLabels.forEach((label) => {
    scene.remove(label);
    label.element?.remove?.();
  });
  activeRigLabels = [];
  activeRigMarkers.forEach((marker) => {
    scene.remove(marker);
    marker.geometry?.dispose?.();
    marker.material?.dispose?.();
  });
  activeRigMarkers = [];
  labelRenderer.domElement.dataset.rigLabelCount = "0";
  labelRenderer.domElement.dataset.rigLabels = "";
}

function applyRigLabelVisibility() {
  const visible = labelsVisible && activeRigLabels.length > 0;
  activeRigLabels.forEach((label) => {
    label.visible = visible;
  });
  activeRigMarkers.forEach((marker) => {
    marker.visible = visible;
  });
  dom.labelToggle.checked = visible;
  dom.labelToggle.disabled = activeRigLabels.length === 0;
}

function updateRigLabels() {
  activeRigLabels.forEach((label) => {
    label.userData.bone.getWorldPosition(scratchBonePoint);
    label.position.copy(scratchBonePoint).add(label.userData.offset);
  });
  activeRigMarkers.forEach((marker) => {
    marker.userData.bone.getWorldPosition(scratchBonePoint);
    marker.position.copy(scratchBonePoint);
  });
}

window.toyboxRigDebug = () => {
  const sceneBones = [];
  activeRoot?.traverse((child) => {
    if (child.isBone) sceneBones.push(child.name);
  });
  return {
    sceneBones,
    labelObjects: activeRigLabels.map((label) => ({
      text: label.element.textContent,
      bone: label.userData.bone.name,
      visible: label.visible,
      position: label.position.toArray(),
    })),
    markerObjects: activeRigMarkers.map((marker) => ({
      name: marker.name,
      bone: marker.userData.bone.name,
      visible: marker.visible,
      position: marker.position.toArray(),
    })),
  };
};

function cleanClipName(name, index) {
  if (!name) return `Motion ${index + 1}`;
  return name
    .replace(/_Toybox_BaseRigAction$/i, "")
    .replace(/_Toybox_/gi, " ")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
    .trim() || `Motion ${index + 1}`;
}

function sortAnimationClips(clips) {
  const preferred = new Map([
    ["Idle bounce", 0],
    ["Friendly wave", 1],
    ["Tiny waddle", 2],
    ["Happy hop", 3],
  ]);
  return [...clips].sort((a, b) => {
    const aOrder = preferred.get(a.name) ?? Number.MAX_SAFE_INTEGER;
    const bOrder = preferred.get(b.name) ?? Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return a.name.localeCompare(b.name);
  });
}

function renderAnimationOptions(clips) {
  dom.animationSelect.replaceChildren();
  if (!clips.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No animations";
    dom.animationSelect.append(option);
    dom.animationSelect.disabled = true;
    return;
  }

  clips.forEach((clip, index) => {
    const option = document.createElement("option");
    option.value = clip.name;
    option.textContent = cleanClipName(clip.name, index);
    dom.animationSelect.append(option);
  });
  dom.animationSelect.disabled = false;
  dom.animationSelect.value = clips[0].name;
}

function playAnimation(name) {
  if (!mixer || !actions.size) return;
  const next = actions.get(name) || actions.values().next().value;
  if (!next || next === activeAction) return;

  next.reset();
  next.setLoop(THREE.LoopRepeat, Infinity);
  next.clampWhenFinished = false;
  next.enabled = true;
  next.play();
  if (activeAction) {
    activeAction.crossFadeTo(next, 0.22, false);
  }
  activeAction = next;
}

function tuneSamMaterial(material) {
  if ("metalness" in material) material.metalness = 0;
  if ("roughness" in material) material.roughness = Math.max(material.roughness ?? 0.72, 0.72);
  if ("envMapIntensity" in material) material.envMapIntensity = 1.35;
  if ("emissive" in material) {
    material.emissive.setRGB(0.035, 0.028, 0.018);
    material.emissiveIntensity = 0.18;
  }
  material.needsUpdate = true;
}

function expandBoxByMeshVertices(box, mesh) {
  const position = mesh.geometry?.attributes?.position;
  if (!position) return;

  mesh.updateWorldMatrix(true, false);
  if (mesh.isSkinnedMesh) {
    mesh.skeleton?.update();
  }

  for (let index = 0; index < position.count; index += 1) {
    scratchVertex.fromBufferAttribute(position, index);
    if (mesh.isSkinnedMesh) {
      mesh.boneTransform(index, scratchVertex);
      mesh.localToWorld(scratchVertex);
    } else {
      mesh.localToWorld(scratchVertex);
    }
    box.expandByPoint(scratchVertex);
  }
}

function getModelBox(root) {
  root.updateMatrixWorld(true);
  const box = new THREE.Box3();
  let meshCount = 0;
  root.traverse((child) => {
    if (!child.isMesh) return;
    meshCount += 1;
    expandBoxByMeshVertices(box, child);
  });
  return meshCount ? box : new THREE.Box3().setFromObject(root);
}

function updateGroundForBox(box) {
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(1.25, Math.min(3.6, Math.max(size.x, size.z) * 0.72));
  floor.scale.set(radius / 1.75, 1, radius / 1.75);
  floor.position.y = -0.055;
  grid.scale.set(radius / 2.1, 1, radius / 2.1);
  grid.position.y = 0.004;
}

function normalizeModel(root, targetSize = 2.25) {
  const box = getModelBox(root);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const scale = targetSize / maxDim;

  root.scale.setScalar(scale);
  root.position.set(-center.x * scale, -center.y * scale, -center.z * scale);

  const normalizedBox = getModelBox(root);
  root.position.y -= normalizedBox.min.y;
  root.updateMatrixWorld(true);
  updateGroundForBox(getModelBox(root));
}

function applyWireframe() {
  if (!activeRoot) return;
  activeRoot.traverse((child) => {
    if (!child.isMesh) return;
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.filter(Boolean).forEach((material) => {
      material.wireframe = wireframe;
      material.needsUpdate = true;
    });
  });
}

function frameActiveModel() {
  if (!activeRoot) {
    camera.position.set(2.6, 1.8, 4.6);
    controls.target.set(0, 0.8, 0);
    controls.update();
    return;
  }
  const box = getModelBox(activeRoot);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const fov = THREE.MathUtils.degToRad(camera.fov);
  const distance = (maxDim / (2 * Math.tan(fov / 2))) * 1.95;
  camera.position.set(center.x + distance * 0.10, center.y + maxDim * 0.24, center.z + distance);
  controls.target.copy(center);
  controls.update();
}

function resize() {
  const rect = dom.canvas.parentElement.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  labelRenderer.setSize(width, height);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.033);
  mixer?.update(dt);
  updateRigLabels();
  controls.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}

async function init() {
  try {
    const response = await fetch("/api/glb-assets");
    const data = await response.json();
    assets = data.assets || [];
    renderAssetList();
    const requested = new URLSearchParams(window.location.search).get("asset");
    selectAsset(assets.some((asset) => asset.id === requested) ? requested : assets[0]?.id);
  } catch (_error) {
    setStatus("Could not read GLB manifest");
  }
  resize();
  requestAnimationFrame(animate);
}

window.addEventListener("resize", resize);
init();
