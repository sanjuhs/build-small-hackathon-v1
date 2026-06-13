export function getDom() {
  return {
    canvas: document.getElementById("stage"),
    speech: document.getElementById("speech"),
    toast: document.getElementById("toast"),
    composer: document.getElementById("composer"),
    input: document.getElementById("messageInput"),
    resetButton: document.getElementById("resetButton"),
    autoButton: document.getElementById("autoButton"),
    effectFlash: document.getElementById("effectFlash"),
    perceptionTitle: document.getElementById("perceptionTitle"),
    perceptionReadout: document.getElementById("perceptionReadout"),
    modelStatus: document.getElementById("modelStatus"),
    userView: document.getElementById("userView"),
    petView: document.getElementById("petView"),
    audioBars: document.getElementById("audioBars"),
    balanceReadout: document.getElementById("balanceReadout"),
  };
}

export class ToyUi {
  constructor(dom) {
    this.dom = dom;
    this.speechTimer = 0;
  }

  showSpeech(text) {
    this.dom.speech.textContent = text || "Tiny thought.";
    this.dom.speech.classList.add("visible");
    clearTimeout(this.speechTimer);
    this.speechTimer = setTimeout(() => this.dom.speech.classList.remove("visible"), 4300);
  }

  showToast(text) {
    this.dom.toast.textContent = text;
    this.dom.toast.classList.add("visible");
    setTimeout(() => this.dom.toast.classList.remove("visible"), 2200);
  }

  flash(durationMs) {
    this.dom.effectFlash.classList.add("on");
    setTimeout(() => this.dom.effectFlash.classList.remove("on"), Math.min(durationMs, 1500));
  }

  updatePerception(seen) {
    this.dom.perceptionReadout.textContent = seen.length
      ? seen.slice(0, 3).map((item) => `${item.kind}${item.moving ? " moving" : ""}`).join(", ")
      : "soft floor, quiet walls";
  }

  async updateModelStatus() {
    try {
      const response = await fetch("/api/model-status");
      const status = await response.json();
      const brain = status.enabled ? status.model : "fallback";
      const vision = status.visionEnabled ? ` + vision: ${status.visionModel}` : "";
      this.dom.modelStatus.textContent = `PET LLM: ${brain}${vision}`;
      this.dom.modelStatus.classList.toggle("active", status.enabled || status.visionEnabled);
    } catch {
      this.dom.modelStatus.textContent = "PET LLM: unknown";
    }
  }
}
