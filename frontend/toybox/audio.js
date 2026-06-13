const SOUND_RECIPES = {
  soft_pop: [[360, 0.02, 0.05], [180, 0.08, 0.12]],
  happy_chirp: [[540, 0.02, 0.06], [760, 0.05, 0.08], [920, 0.08, 0.06]],
  pet_touch: [[420, 0.01, 0.04], [680, 0.04, 0.08]],
  purr: [[180, 0.00, 0.12], [205, 0.09, 0.12], [190, 0.18, 0.16]],
  tiny_giggle: [[620, 0.00, 0.04], [820, 0.045, 0.04], [700, 0.09, 0.05], [960, 0.14, 0.05]],
  curious_hm: [[310, 0.00, 0.1], [460, 0.08, 0.14]],
  electric_pip: [[1220, 0.00, 0.03], [1510, 0.04, 0.035], [980, 0.085, 0.05]],
  ember_purr: [[220, 0.00, 0.12], [260, 0.08, 0.12], [340, 0.16, 0.12]],
  bubble_chirp: [[520, 0.00, 0.06], [690, 0.06, 0.08], [430, 0.14, 0.1]],
  startle: [[280, 0.01, 0.04], [720, 0.04, 0.05]],
  clock_chime: [[660, 0.01, 0.18], [990, 0.04, 0.15]],
  tick_tock: [[880, 0.01, 0.025], [420, 0.12, 0.03]],
  spark: [[1100, 0.01, 0.04], [1480, 0.035, 0.035], [760, 0.07, 0.05]],
  bulb_ping: [[880, 0.01, 0.16], [1320, 0.03, 0.12]],
  whoosh: [[160, 0.01, 0.14], [240, 0.08, 0.16]],
  water_plink: [[520, 0.01, 0.08], [380, 0.08, 0.12], [720, 0.15, 0.05]],
};

export class ToyAudio {
  constructor() {
    this.context = null;
    this.master = null;
    this.analyser = null;
    this.frequencyData = null;
    this.inputAnalyser = null;
    this.inputFrequencyData = null;
    this.mediaStream = null;
    this.mediaSource = null;
    this.micEnabled = false;
    this.micError = "";
    this.lastOutputAt = 0;
    this.enabled = false;
    this.voiceEnabled = true;
    this.voiceQueue = [];
    this.voiceSpeaking = false;
    this.voices = [];
  }

  unlock() {
    if (!this.context) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      this.context = new AudioContextClass();
      this.master = this.context.createGain();
      this.master.gain.value = 0.16;
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 64;
      this.analyser.smoothingTimeConstant = 0.72;
      this.frequencyData = new Uint8Array(this.analyser.frequencyBinCount);
      this.master.connect(this.analyser);
      this.analyser.connect(this.context.destination);
      this.loadVoices();
    }
    if (this.context.state === "suspended") {
      this.context.resume();
    }
    this.enabled = true;
  }

  getLevels() {
    const output = this.getOutputLevels();
    const input = this.getInputLevels();
    return output.map((value, index) => Math.max(value, input[index] || 0));
  }

  getOutputLevels() {
    return levelsFromAnalyser(this.analyser, this.frequencyData);
  }

  getInputLevels() {
    return levelsFromAnalyser(this.inputAnalyser, this.inputFrequencyData);
  }

  outputSummary() {
    return summaryFromLevels(this.getOutputLevels(), this.enabled);
  }

  inputSummary() {
    return {
      ...summaryFromLevels(this.getInputLevels(), this.micEnabled),
      available: Boolean(navigator.mediaDevices?.getUserMedia),
      error: this.micError,
    };
  }

  play(name, intensity = 1) {
    if (!this.enabled) return;
    this.lastOutputAt = performance.now();
    const recipe = SOUND_RECIPES[name] || SOUND_RECIPES.soft_pop;
    const now = this.context.currentTime;
    for (const [frequency, offset, duration] of recipe) {
      this.tone(frequency, now + offset, duration, intensity);
    }
  }

  playRecipe(recipe, intensity = 1) {
    if (!this.enabled || !recipe || !Array.isArray(recipe.tones)) return false;
    const gain = clamp(Number(recipe.gain || 0.72), 0.05, 1.2) * intensity;
    const now = this.context.currentTime;
    let played = false;
    for (const tone of recipe.tones.slice(0, 6)) {
      if (!tone || typeof tone !== "object") continue;
      const frequency = clamp(Number(tone.frequency || 440), 80, 1800);
      const offset = clamp(Number(tone.offsetMs || 0), 0, 1200) / 1000;
      const duration = clamp(Number(tone.durationMs || 120), 24, 900) / 1000;
      const toneGain = clamp(Number(tone.gain || 0.36), 0.04, 1.0);
      this.tone(frequency, now + offset, duration, gain * toneGain, tone.wave);
      played = true;
    }
    if (played) this.lastOutputAt = performance.now();
    return played;
  }

  async setMicEnabled(enabled) {
    if (enabled) return this.startMic();
    this.stopMic();
    return true;
  }

  async startMic() {
    this.unlock();
    if (!navigator.mediaDevices?.getUserMedia) {
      this.micError = "unsupported";
      this.micEnabled = false;
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
      this.stopMic();
      this.mediaStream = stream;
      this.inputAnalyser = this.context.createAnalyser();
      this.inputAnalyser.fftSize = 64;
      this.inputAnalyser.smoothingTimeConstant = 0.68;
      this.inputFrequencyData = new Uint8Array(this.inputAnalyser.frequencyBinCount);
      this.mediaSource = this.context.createMediaStreamSource(stream);
      this.mediaSource.connect(this.inputAnalyser);
      this.micEnabled = true;
      this.micError = "";
      return true;
    } catch (error) {
      this.micError = error?.name || "permission";
      this.micEnabled = false;
      return false;
    }
  }

  stopMic() {
    if (this.mediaSource) {
      try {
        this.mediaSource.disconnect();
      } catch {}
    }
    if (this.mediaStream) {
      for (const track of this.mediaStream.getTracks()) track.stop();
    }
    this.mediaSource = null;
    this.mediaStream = null;
    this.inputAnalyser = null;
    this.inputFrequencyData = null;
    this.micEnabled = false;
  }

  setVoiceEnabled(enabled) {
    this.voiceEnabled = Boolean(enabled);
    if (!this.voiceEnabled) this.cancelSpeech();
  }

  speak(agentKind, label, text) {
    if (!this.enabled || !this.voiceEnabled || !this.canSpeak()) return;
    const clean = String(text || "")
      .replace(/\s+/g, " ")
      .replace(/<[^>]+>/g, "")
      .trim()
      .slice(0, 140);
    if (!clean) return;
    this.loadVoices();
    this.voiceQueue.push({ agentKind, label, text: clean });
    while (this.voiceQueue.length > 4) this.voiceQueue.shift();
    this.flushSpeechQueue();
  }

  flushSpeechQueue() {
    if (this.voiceSpeaking || !this.voiceQueue.length || !this.canSpeak()) return;
    const item = this.voiceQueue.shift();
    const utterance = new SpeechSynthesisUtterance(item.text);
    const config = voiceConfig(item.agentKind);
    utterance.pitch = config.pitch;
    utterance.rate = config.rate;
    utterance.volume = config.volume;
    utterance.lang = "en-US";
    this.lastOutputAt = performance.now();
    const voice = this.pickVoice(config);
    if (voice) utterance.voice = voice;
    utterance.onend = () => {
      this.voiceSpeaking = false;
      this.flushSpeechQueue();
    };
    utterance.onerror = () => {
      this.voiceSpeaking = false;
      this.flushSpeechQueue();
    };
    this.voiceSpeaking = true;
    window.speechSynthesis.speak(utterance);
  }

  cancelSpeech() {
    this.voiceQueue = [];
    this.voiceSpeaking = false;
    if (this.canSpeak()) window.speechSynthesis.cancel();
  }

  canSpeak() {
    return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  }

  loadVoices() {
    if (!this.canSpeak()) return;
    this.voices = window.speechSynthesis.getVoices?.() || [];
  }

  pickVoice(config) {
    if (!this.voices.length) return null;
    const preferred = this.voices.find((voice) => config.preferred.some((name) => voice.name.toLowerCase().includes(name)));
    if (preferred) return preferred;
    return this.voices.find((voice) => /^en[-_]/i.test(voice.lang || "")) || this.voices[0] || null;
  }

  tone(frequency, start, duration, intensity, wave = "sine") {
    const osc = this.context.createOscillator();
    const gain = this.context.createGain();
    const filter = this.context.createBiquadFilter();
    osc.type = ["sine", "triangle", "square", "sawtooth"].includes(wave) ? wave : "sine";
    osc.frequency.setValueAtTime(frequency, start);
    osc.frequency.exponentialRampToValueAtTime(Math.max(80, frequency * 0.82), start + duration);
    filter.type = "lowpass";
    filter.frequency.value = 2600;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.18 * intensity, start + duration * 0.18);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    osc.connect(filter);
    filter.connect(gain);
    gain.connect(this.master);
    osc.start(start);
    osc.stop(start + duration + 0.04);
  }

  power(name) {
    const soundByPower = {
      time_freeze: "clock_chime",
      shrink: "soft_pop",
      rewind: "tick_tock",
      clock_bubble: "clock_chime",
      shock: "spark",
      lamp_burst: "bulb_ping",
      magnet_pull: "spark",
      fireball: "whoosh",
      ember_jump: "whoosh",
      smoke_poof: "soft_pop",
      wave: "water_plink",
      bubble_lift: "water_plink",
      tide_pull: "water_plink",
    };
    this.play(soundByPower[name] || "happy_chirp", 0.9);
  }
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, Number.isFinite(value) ? value : low));
}

function levelsFromAnalyser(analyser, frequencyData) {
  if (!analyser || !frequencyData) return Array.from({ length: 14 }, () => 0);
  analyser.getByteFrequencyData(frequencyData);
  const levels = [];
  const binsPerBand = Math.max(1, Math.floor(frequencyData.length / 14));
  for (let band = 0; band < 14; band += 1) {
    let sum = 0;
    for (let i = 0; i < binsPerBand; i += 1) {
      sum += frequencyData[Math.min(frequencyData.length - 1, band * binsPerBand + i)];
    }
    levels.push(sum / binsPerBand / 255);
  }
  return levels;
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

function voiceConfig(agentKind) {
  const configs = {
    squeaky: { pitch: 1.32, rate: 1.04, volume: 0.78, preferred: ["samantha", "ava", "google us english"] },
    fire_boy: { pitch: 1.42, rate: 1.06, volume: 0.84, preferred: ["samantha", "ava", "google us english", "alex"] },
    shark_girl: { pitch: 1.08, rate: 0.9, volume: 0.78, preferred: ["victoria", "serena", "google uk english female"] },
    electraica: { pitch: 1.42, rate: 1.12, volume: 0.74, preferred: ["allison", "karen", "google us english"] },
  };
  return configs[agentKind] || { pitch: 1.0, rate: 1.0, volume: 0.76, preferred: [] };
}
