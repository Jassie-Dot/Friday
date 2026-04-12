import "./style.css";
import * as THREE from "three";
import { GPUComputationRenderer } from "three-stdlib";

import simShader from "./shaders/simulation.glsl";
import vertShader from "./shaders/vertex.glsl";
import fragShader from "./shaders/fragment.glsl";
import { EffectsComposer } from "./effects.js";
import { WispsSystem } from "./wisps.js";

const SIZE = 160;
const RAW_API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const API_URL = RAW_API_URL.trim().replace(/\/+$/, "");
const PRESENCE_WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";
const SESSION_WS_URL = API_URL.replace(/^http/, "ws") + "/ws/session";
const VOICE_SAMPLE_RATE = 16000;

const stateIndex = {
  idle: 0,
  listening: 1,
  thinking: 2,
  speaking: 3,
  executing: 4,
  error: 5
};

const dom = {
  modePill: document.getElementById("mode-pill"),
  modeDot: document.getElementById("mode-dot"),
  modeLabel: document.getElementById("mode-label"),
  leadLine: document.getElementById("lead-line"),
  subLine: document.getElementById("sub-line"),
  whisperLine: document.getElementById("whisper-line"),
  activateButton: document.getElementById("activate-button"),
  micBar: document.getElementById("mic-bar"),
  voiceBar: document.getElementById("voice-bar")
};

const currentPresence = {
  mode: "idle",
  energy: 0.16,
  whisper: "Standing by",
  headline: "FRIDAY"
};

const audioState = {
  armed: false,
  sessionReady: false,
  micLevel: 0,
  audioContext: null,
  outputGain: null,
  processor: null,
  captureActive: false,
  silenceMs: 0,
  speechMs: 0,
  threshold: 0.028
};

const playbackState = {
  active: false,
  pendingStop: false,
  nextStart: 0,
  sources: new Set(),
  level: 0,
  targetLevel: 0
};

let presenceSocket = null;
let sessionSocket = null;
let reconnectTimer = null;

let scene;
let camera;
let renderer;
let composer;
let gpuCompute;
let posVariable;
let particleSystem;
let coreMesh;
let ringMesh;
let shellMesh;
let wisps;
const clock = new THREE.Clock();

boot();

function boot() {
  initScene();
  connectPresenceSocket();
  attachUI();
  window.addEventListener("resize", onWindowResize);
  animate();
}

function initScene() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(52, window.innerWidth / window.innerHeight, 0.1, 200);
  camera.position.set(0, 0, 11.5);

  renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById("canvas3d"),
    antialias: false,
    alpha: true,
    powerPreference: "high-performance"
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;

  initComputeRenderer();
  initParticles();
  initCoreMeshes();
  wisps = new WispsSystem(scene, currentPresence);
  composer = new EffectsComposer(renderer, scene, camera);
}

function initComputeRenderer() {
  gpuCompute = new GPUComputationRenderer(SIZE, SIZE, renderer);
  const dtPosition = gpuCompute.createTexture();
  const data = dtPosition.image.data;
  for (let i = 0; i < data.length; i += 4) {
    const radius = 1.2 + Math.random() * 4.1;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    data[i + 0] = radius * Math.sin(phi) * Math.cos(theta);
    data[i + 1] = radius * Math.cos(phi) * 0.65;
    data[i + 2] = radius * Math.sin(phi) * Math.sin(theta);
    data[i + 3] = 0.45 + Math.random() * 0.55;
  }

  posVariable = gpuCompute.addVariable("uCurrentPos", simShader, dtPosition);
  gpuCompute.setVariableDependencies(posVariable, [posVariable]);
  posVariable.material.uniforms.uTime = { value: 0 };
  posVariable.material.uniforms.uDelta = { value: 0 };
  posVariable.material.uniforms.uAudio = { value: 0 };
  posVariable.material.uniforms.uState = { value: 0 };
  posVariable.material.uniforms.uEnergy = { value: currentPresence.energy };
  const error = gpuCompute.init();
  if (error) {
    throw new Error(`GPU compute init failed: ${error}`);
  }
}

function initParticles() {
  const geometry = new THREE.BufferGeometry();
  const references = new Float32Array(SIZE * SIZE * 2);
  const positions = new Float32Array(SIZE * SIZE * 3);

  for (let i = 0; i < SIZE * SIZE; i += 1) {
    references[i * 2] = (i % SIZE) / SIZE;
    references[i * 2 + 1] = Math.floor(i / SIZE) / SIZE;
  }

  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("reference", new THREE.BufferAttribute(references, 2));

  const palette = getStateColors("idle");
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uPosTexture: { value: null },
      uColorA: { value: palette.primary.clone() },
      uColorB: { value: palette.secondary.clone() },
      uSize: { value: 1.0 },
      uTime: { value: 0 },
      uState: { value: 0 },
      uEnergy: { value: currentPresence.energy },
      uAudio: { value: 0 }
    },
    vertexShader: vertShader,
    fragmentShader: fragShader,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  particleSystem = new THREE.Points(geometry, material);
  particleSystem.scale.setScalar(1.16);
  scene.add(particleSystem);
}

function initCoreMeshes() {
  const palette = getStateColors("idle");

  coreMesh = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.72, 28),
    new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uAudio: { value: 0 },
        uEnergy: { value: currentPresence.energy },
        uColorA: { value: palette.primary.clone() },
        uColorB: { value: palette.secondary.clone() }
      },
      vertexShader: `
        uniform float uTime;
        uniform float uAudio;
        uniform float uEnergy;
        varying vec3 vNormalDir;
        varying vec3 vWorldPos;

        void main() {
          vec3 displaced = position;
          displaced += normal * (sin(uTime * 1.8 + position.y * 5.0) * 0.05);
          displaced += normal * (sin(uTime * 3.1 + position.x * 7.0) * 0.025);
          displaced += normal * (uAudio * 0.08 + uEnergy * 0.05);

          vec4 world = modelMatrix * vec4(displaced, 1.0);
          vNormalDir = normalize(mat3(modelMatrix) * normal);
          vWorldPos = world.xyz;
          gl_Position = projectionMatrix * viewMatrix * world;
        }
      `,
      fragmentShader: `
        uniform float uTime;
        uniform float uAudio;
        uniform float uEnergy;
        uniform vec3 uColorA;
        uniform vec3 uColorB;
        varying vec3 vNormalDir;
        varying vec3 vWorldPos;

        void main() {
          vec3 viewDir = normalize(cameraPosition - vWorldPos);
          float fresnel = pow(1.0 - max(dot(viewDir, normalize(vNormalDir)), 0.0), 2.8);
          float plasma = sin(vWorldPos.y * 5.0 + uTime * 3.5) * 0.5 + 0.5;
          plasma += sin(vWorldPos.x * 7.0 - uTime * 2.3) * 0.25 + 0.25;
          plasma = clamp(plasma, 0.0, 1.0);

          vec3 color = mix(uColorB, uColorA, plasma);
          color += uColorA * fresnel * (0.5 + uAudio * 0.8);
          color += vec3(0.9, 1.0, 1.0) * pow(fresnel, 4.0) * 0.18;

          float alpha = 0.18 + fresnel * 0.44 + uEnergy * 0.16;
          gl_FragColor = vec4(color, alpha);
        }
      `
    })
  );
  scene.add(coreMesh);

  ringMesh = new THREE.Mesh(
    new THREE.TorusGeometry(3.35, 0.02, 16, 180),
    new THREE.MeshBasicMaterial({
      color: 0x6af0ff,
      transparent: true,
      opacity: 0.15,
      blending: THREE.AdditiveBlending
    })
  );
  ringMesh.rotation.x = Math.PI * 0.42;
  scene.add(ringMesh);

  shellMesh = new THREE.Mesh(
    new THREE.IcosahedronGeometry(4.9, 12),
    new THREE.ShaderMaterial({
      transparent: true,
      wireframe: true,
      depthWrite: false,
      uniforms: {
        uTime: { value: 0 },
        uAudio: { value: 0 },
        uColor: { value: palette.primary.clone() }
      },
      vertexShader: `
        uniform float uTime;
        uniform float uAudio;
        varying float vPulse;

        void main() {
          vec3 displaced = position + normal * (sin(uTime * 0.8 + position.y * 2.2) * 0.08 + uAudio * 0.08);
          vPulse = 0.45 + 0.55 * sin(uTime * 1.1 + position.x * 0.7);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying float vPulse;

        void main() {
          gl_FragColor = vec4(uColor, 0.04 + vPulse * 0.04);
        }
      `
    })
  );
  scene.add(shellMesh);
}

function attachUI() {
  dom.activateButton.addEventListener("click", () => {
    void armVoiceCore();
  });
}

async function armVoiceCore() {
  if (audioState.armed) {
    return;
  }

  dom.activateButton.disabled = true;
  dom.activateButton.textContent = "Arming...";

  try {
    const audioContext = new AudioContext({ latencyHint: "interactive" });
    await audioContext.resume();

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const muteGain = audioContext.createGain();
    muteGain.gain.value = 0;
    const outputGain = audioContext.createGain();
    outputGain.gain.value = 1;
    outputGain.connect(audioContext.destination);

    source.connect(processor);
    processor.connect(muteGain);
    muteGain.connect(audioContext.destination);

    audioState.audioContext = audioContext;
    audioState.outputGain = outputGain;
    audioState.processor = processor;
    audioState.armed = true;

    processor.onaudioprocess = (event) => {
      handleMicBuffer(event.inputBuffer.getChannelData(0), audioContext.sampleRate);
    };

    connectSessionSocket();

    dom.activateButton.dataset.armed = "true";
    dom.activateButton.textContent = "Voice Core Armed";
    dom.subLine.textContent = "Continuous listening online. Speak naturally and FRIDAY will react in real time.";
    dom.whisperLine.textContent = "Barge-in is active. Start speaking at any point to cut through playback.";
  } catch (error) {
    console.error("FRIDAY voice arm failed", error);
    dom.leadLine.textContent = "Microphone activation failed.";
    dom.subLine.textContent = error.message || "Check browser microphone permissions and try again.";
    dom.activateButton.disabled = false;
    dom.activateButton.textContent = "Retry Voice Core";
  }
}

function handleMicBuffer(floatBuffer, inputSampleRate) {
  const rms = computeRms(floatBuffer);
  audioState.micLevel = rms;
  if (!audioState.armed || !audioState.sessionReady || !sessionSocket || sessionSocket.readyState !== WebSocket.OPEN) {
    return;
  }

  const durationMs = (floatBuffer.length / inputSampleRate) * 1000;
  const aboveThreshold = rms > audioState.threshold;

  if (!audioState.captureActive && aboveThreshold) {
    audioState.captureActive = true;
    audioState.silenceMs = 0;
    audioState.speechMs = 0;
    if (playbackState.active) {
      sessionSend({ type: "interrupt" });
      stopPlayback();
    }
  }

  if (!audioState.captureActive) {
    return;
  }

  const pcm16 = downsampleToInt16(floatBuffer, inputSampleRate, VOICE_SAMPLE_RATE);
  sessionSend({
    type: "audio.frame",
    audio: bytesToBase64(new Uint8Array(pcm16.buffer)),
    sample_rate: VOICE_SAMPLE_RATE,
    rms
  });

  audioState.speechMs += durationMs;
  if (aboveThreshold) {
    audioState.silenceMs = 0;
  } else {
    audioState.silenceMs += durationMs;
  }

  if (audioState.speechMs > 180 && audioState.silenceMs > 520) {
    sessionSend({ type: "audio.commit" });
    audioState.captureActive = false;
    audioState.silenceMs = 0;
    audioState.speechMs = 0;
  }
}

function connectPresenceSocket() {
  presenceSocket = new WebSocket(PRESENCE_WS_URL);
  presenceSocket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "bootstrap") {
      applyPresence(payload.presence);
      return;
    }
    if (payload.type === "presence") {
      applyPresence(payload.data);
      return;
    }
    if (payload.type === "event" && payload.data) {
      dom.whisperLine.textContent = `${payload.data.source.toUpperCase()} :: ${payload.data.message_type}`;
    }
  });
  presenceSocket.addEventListener("close", () => {
    window.setTimeout(connectPresenceSocket, 1200);
  });
}

function connectSessionSocket() {
  if (sessionSocket && (sessionSocket.readyState === WebSocket.OPEN || sessionSocket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  sessionSocket = new WebSocket(SESSION_WS_URL);

  sessionSocket.addEventListener("open", () => {
    audioState.sessionReady = false;
    dom.leadLine.textContent = "Voice transport linked.";
  });

  sessionSocket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    handleSessionMessage(payload);
  });

  sessionSocket.addEventListener("close", () => {
    audioState.sessionReady = false;
    if (audioState.armed) {
      dom.leadLine.textContent = "Voice transport reconnecting...";
      clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(connectSessionSocket, 1200);
    }
  });
}

function handleSessionMessage(payload) {
  switch (payload.type) {
    case "session.ready":
      audioState.sessionReady = true;
      dom.leadLine.textContent = "Continuous voice transport active.";
      dom.subLine.textContent = "FRIDAY is listening locally through the backend session graph.";
      return;
    case "transcript.partial":
      dom.subLine.textContent = payload.text;
      return;
    case "transcript.final":
      dom.leadLine.textContent = `Heard: ${payload.text}`;
      dom.whisperLine.textContent = "Routing through fast model and background refinement.";
      return;
    case "assistant.start":
      dom.whisperLine.textContent = `Route: ${payload.route || "fast-smart"} | Model: ${payload.model || "local"}`;
      return;
    case "assistant.token":
      dom.subLine.textContent = tailText(payload.text, 160);
      return;
    case "assistant.final":
      dom.leadLine.textContent = payload.text;
      return;
    case "assistant.refinement":
      dom.whisperLine.textContent = payload.text;
      return;
    case "assistant.task_complete":
      dom.leadLine.textContent = payload.text;
      dom.whisperLine.textContent = "Execution pipeline completed.";
      return;
    case "voice.start":
      playbackState.active = true;
      playbackState.pendingStop = false;
      dom.modePill.dataset.mode = "speaking";
      return;
    case "voice.chunk":
      enqueuePlaybackChunk(payload.audio, payload.sample_rate);
      return;
    case "voice.end":
      playbackState.pendingStop = true;
      return;
    case "voice.interrupt":
      stopPlayback();
      dom.whisperLine.textContent = "Playback interrupted by live speech.";
      return;
    case "voice.error":
      dom.whisperLine.textContent = payload.message || "Voice synthesis fault.";
      return;
    default:
      return;
  }
}

function applyPresence(presence) {
  const mode = normalizeMode(presence.mode);
  currentPresence.mode = mode;
  currentPresence.energy = presence.energy ?? currentPresence.energy;
  currentPresence.whisper = presence.whisper || currentPresence.whisper;
  currentPresence.headline = presence.headline || currentPresence.headline;

  dom.modePill.dataset.mode = mode;
  dom.modeLabel.textContent = mode.toUpperCase();
  dom.modeDot.style.background = getModeColor(mode);
  dom.modeDot.style.boxShadow = `0 0 12px ${getModeColor(mode)}`;

  if (presence.whisper) {
    dom.whisperLine.textContent = presence.whisper;
  }
  if (presence.terminal_text && !playbackState.active) {
    dom.subLine.textContent = tailText(presence.terminal_text, 180);
  }
}

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  const elapsed = clock.getElapsedTime();

  playbackState.level = damp(playbackState.level, playbackState.targetLevel, 0.1);
  playbackState.targetLevel *= 0.9;
  const totalAudio = Math.max(audioState.micLevel * 0.95, playbackState.level * 1.15);

  posVariable.material.uniforms.uTime.value = elapsed;
  posVariable.material.uniforms.uDelta.value = delta;
  posVariable.material.uniforms.uAudio.value = totalAudio;
  posVariable.material.uniforms.uState.value = stateIndex[currentPresence.mode] ?? 0;
  posVariable.material.uniforms.uEnergy.value = currentPresence.energy;
  gpuCompute.compute();

  const palette = getStateColors(currentPresence.mode);
  const particleMaterial = particleSystem.material;
  particleMaterial.uniforms.uPosTexture.value = gpuCompute.getCurrentRenderTarget(posVariable).texture;
  particleMaterial.uniforms.uTime.value = elapsed;
  particleMaterial.uniforms.uState.value = stateIndex[currentPresence.mode] ?? 0;
  particleMaterial.uniforms.uEnergy.value = currentPresence.energy;
  particleMaterial.uniforms.uAudio.value = totalAudio;
  particleMaterial.uniforms.uColorA.value.copy(palette.primary);
  particleMaterial.uniforms.uColorB.value.copy(palette.secondary);

  coreMesh.material.uniforms.uTime.value = elapsed;
  coreMesh.material.uniforms.uAudio.value = totalAudio;
  coreMesh.material.uniforms.uEnergy.value = currentPresence.energy;
  coreMesh.material.uniforms.uColorA.value.copy(palette.primary);
  coreMesh.material.uniforms.uColorB.value.copy(palette.secondary);

  shellMesh.material.uniforms.uTime.value = elapsed;
  shellMesh.material.uniforms.uAudio.value = totalAudio;
  shellMesh.material.uniforms.uColor.value.copy(palette.primary);

  ringMesh.material.color.copy(palette.secondary);
  ringMesh.material.opacity = 0.08 + currentPresence.energy * 0.12;

  particleSystem.rotation.y += 0.0025 + totalAudio * 0.008;
  particleSystem.rotation.x = Math.sin(elapsed * 0.18) * 0.12;
  coreMesh.rotation.y -= 0.003 + currentPresence.energy * 0.005;
  coreMesh.rotation.z = Math.sin(elapsed * 0.35) * 0.08;
  shellMesh.rotation.y += 0.001 + currentPresence.energy * 0.002;
  shellMesh.rotation.x = Math.cos(elapsed * 0.12) * 0.16;
  ringMesh.rotation.z += 0.002 + currentPresence.energy * 0.003;
  ringMesh.rotation.y = Math.sin(elapsed * 0.2) * 0.5;

  wisps.update(currentPresence, delta);

  updateMeters();
  composer.updateTime(elapsed);
  composer.render();
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
}

function sessionSend(payload) {
  if (!sessionSocket || sessionSocket.readyState !== WebSocket.OPEN) {
    return;
  }
  sessionSocket.send(JSON.stringify(payload));
}

function enqueuePlaybackChunk(base64Audio, sampleRate) {
  if (!audioState.audioContext || !audioState.outputGain) {
    return;
  }
  const bytes = base64ToBytes(base64Audio);
  const sampleCount = bytes.byteLength / 2;
  const buffer = audioState.audioContext.createBuffer(1, sampleCount, sampleRate);
  const channel = buffer.getChannelData(0);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let sum = 0;
  for (let i = 0; i < sampleCount; i += 1) {
    const sample = view.getInt16(i * 2, true) / 32768;
    channel[i] = sample;
    sum += sample * sample;
  }
  playbackState.targetLevel = Math.max(playbackState.targetLevel, Math.sqrt(sum / Math.max(sampleCount, 1)));

  const source = audioState.audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioState.outputGain);

  const now = audioState.audioContext.currentTime + 0.02;
  playbackState.nextStart = Math.max(playbackState.nextStart, now);
  source.start(playbackState.nextStart);
  playbackState.nextStart += buffer.duration;
  playbackState.sources.add(source);

  source.onended = () => {
    playbackState.sources.delete(source);
    if (playbackState.pendingStop && playbackState.sources.size === 0) {
      playbackState.active = false;
      playbackState.pendingStop = false;
      playbackState.nextStart = audioState.audioContext.currentTime;
    }
  };
}

function stopPlayback() {
  playbackState.sources.forEach((source) => {
    try {
      source.stop(0);
    } catch {
      // Source may already be finished.
    }
  });
  playbackState.sources.clear();
  playbackState.active = false;
  playbackState.pendingStop = false;
  playbackState.level = 0;
  playbackState.targetLevel = 0;
  if (audioState.audioContext) {
    playbackState.nextStart = audioState.audioContext.currentTime;
  }
}

function updateMeters() {
  dom.micBar.style.transform = `scaleX(${Math.min(1, 0.12 + audioState.micLevel * 4.2)})`;
  dom.voiceBar.style.transform = `scaleX(${Math.min(1, 0.12 + playbackState.level * 4.8)})`;
}

function computeRms(buffer) {
  let sum = 0;
  for (let i = 0; i < buffer.length; i += 1) {
    const value = buffer[i];
    sum += value * value;
  }
  return Math.sqrt(sum / Math.max(buffer.length, 1));
}

function downsampleToInt16(buffer, inputRate, outputRate) {
  if (outputRate > inputRate) {
    throw new Error("Output sample rate cannot exceed input sample rate.");
  }
  const sampleRateRatio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Int16Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i];
      count += 1;
    }
    const sample = Math.max(-1, Math.min(1, accum / Math.max(count, 1)));
    result[offsetResult] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function base64ToBytes(base64Text) {
  const binary = atob(base64Text);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function tailText(text, maxLength) {
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `...${text.slice(-maxLength)}` : text;
}

function damp(value, target, factor) {
  return value + (target - value) * factor;
}

function normalizeMode(mode) {
  if (mode === "responding") {
    return "speaking";
  }
  return mode in stateIndex ? mode : "idle";
}

function getModeColor(mode) {
  const colors = {
    idle: "#58d9ff",
    listening: "#83ffe2",
    thinking: "#79a9ff",
    speaking: "#f7fffb",
    executing: "#9afff3",
    error: "#ff5f75"
  };
  return colors[mode] || colors.idle;
}

function getStateColors(mode) {
  const palette = {
    idle: { primary: new THREE.Color("#4fdcff"), secondary: new THREE.Color("#1f95d2") },
    listening: { primary: new THREE.Color("#83ffe2"), secondary: new THREE.Color("#29c6bb") },
    thinking: { primary: new THREE.Color("#79a9ff"), secondary: new THREE.Color("#2848d7") },
    speaking: { primary: new THREE.Color("#f4fffd"), secondary: new THREE.Color("#5de6d6") },
    executing: { primary: new THREE.Color("#8cfffa"), secondary: new THREE.Color("#d9fff5") },
    error: { primary: new THREE.Color("#ff5f75"), secondary: new THREE.Color("#941d41") }
  };
  return palette[mode] || palette.idle;
}
