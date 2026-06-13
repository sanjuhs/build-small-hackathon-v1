import * as THREE from "three";

const PREVIEW_WIDTH = 164;
const PREVIEW_HEIGHT = 92;

export function createSenseFeeds({ scene, userCamera, userRenderer, dom, audio }) {
  const petCamera = new THREE.PerspectiveCamera(64, PREVIEW_WIDTH / PREVIEW_HEIGHT, 0.05, 18);
  const petRenderer = new THREE.WebGLRenderer({
    canvas: dom.petView,
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: true,
  });
  petRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  petRenderer.outputColorSpace = THREE.SRGBColorSpace;
  petRenderer.toneMapping = THREE.ACESFilmicToneMapping;
  petRenderer.toneMappingExposure = 1.04;

  const userCtx = dom.userView?.getContext("2d");
  const audioBars = createAudioBars(dom.audioBars);
  let pet = null;
  let lastUserCopy = 0;
  let lastPetRender = 0;

  resize();

  function setPet(nextPet) {
    pet = nextPet;
  }

  function resize() {
    resizeCanvas(dom.userView, PREVIEW_WIDTH, PREVIEW_HEIGHT);
    petRenderer.setSize(PREVIEW_WIDTH, PREVIEW_HEIGHT, false);
    petCamera.aspect = PREVIEW_WIDTH / PREVIEW_HEIGHT;
    petCamera.updateProjectionMatrix();
  }

  function update(nextPet, now, balanceState) {
    if (nextPet) pet = nextPet;
    if (now - lastUserCopy > 180) {
      lastUserCopy = now;
      copyUserView();
    }
    if (now - lastPetRender > 90) {
      lastPetRender = now;
      renderPetView();
    }
    updateAudioBars(audio?.getLevels?.() || []);
    updateBalance(balanceState);
  }

  function capturePetFrame() {
    renderPetView();
    try {
      return dom.petView.toDataURL("image/jpeg", 0.45);
    } catch {
      return null;
    }
  }

  function audioSummary() {
    const levels = audio?.getLevels?.() || [];
    const input = audio?.inputSummary?.() || summaryFromLevels([], false);
    const output = audio?.outputSummary?.() || summaryFromLevels([], false);
    const peak = Math.max(input.peak || 0, output.peak || 0);
    const rms = Math.max(input.rms || 0, output.rms || 0);
    return {
      active: Boolean(audio?.enabled || input.active || output.active),
      source: input.active && input.peak >= output.peak ? "microphone" : "room-output",
      peak: Number(peak.toFixed(2)),
      rms: Number(rms.toFixed(2)),
      bands: levels.slice(0, 10).map((value) => Number(value.toFixed(2))),
      input,
      output,
    };
  }

  function copyUserView() {
    if (!userCtx || !dom.userView || !userRenderer?.domElement) return;
    userCtx.clearRect(0, 0, dom.userView.width, dom.userView.height);
    userCtx.drawImage(userRenderer.domElement, 0, 0, dom.userView.width, dom.userView.height);
  }

  function renderPetView() {
    if (!pet) return;
    updatePetCamera();
    const wasVisible = pet.group.visible;
    pet.group.visible = false;
    petRenderer.render(scene, petCamera);
    pet.group.visible = wasVisible;
  }

  function updatePetCamera() {
    const eye = new THREE.Vector3(0, 1.86, 0.74);
    const target = new THREE.Vector3(0, 0.92, -2.4);
    pet.group.localToWorld(eye);
    pet.group.localToWorld(target);
    petCamera.position.copy(eye);
    petCamera.lookAt(target);
  }

  function updateAudioBars(levels) {
    audioBars.forEach((bar, index) => {
      const value = levels[index] ?? 0;
      bar.style.scale = `1 ${Math.max(0.06, value).toFixed(3)}`;
      bar.classList.toggle("hot", value > 0.58);
    });
  }

  function updateBalance(balanceState) {
    if (!dom.balanceReadout || !balanceState) return;
    dom.balanceReadout.textContent = `${Math.round(balanceState.stability * 100)}% / ${balanceState.tiltDeg}deg / ${balanceState.mass}kg`;
  }

  return { audioSummary, capturePetFrame, resize, setPet, update };
}

function summaryFromLevels(levels, active) {
  const peak = levels.reduce((max, value) => Math.max(max, value), 0);
  const rms = levels.length
    ? Math.sqrt(levels.reduce((sum, value) => sum + value * value, 0) / levels.length)
    : 0;
  return {
    active: Boolean(active),
    peak: Number(peak.toFixed(2)),
    rms: Number(rms.toFixed(2)),
    bands: levels.slice(0, 10).map((value) => Number(value.toFixed(2))),
  };
}

function resizeCanvas(canvas, width, height) {
  if (!canvas) return;
  canvas.width = width;
  canvas.height = height;
}

function createAudioBars(container) {
  if (!container) return [];
  if (!container.children.length) {
    for (let i = 0; i < 14; i += 1) {
      const bar = document.createElement("span");
      bar.className = "audio-bar";
      container.appendChild(bar);
    }
  }
  return [...container.children];
}
