import "./style.css";
import * as THREE from "three";

const RAW_API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const API_URL = RAW_API_URL.trim().replace(/\/+$/, "");
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";
const stateIndex = {
  idle: 0,
  listening: 1,
  thinking: 2,
  responding: 3,
  error: 4
};

const app = document.querySelector("#app");
app.innerHTML = `
  <div class="hud">
    <section class="headline">
      <p class="eyebrow">LOCAL PRESENCE FIELD</p>
      <h1 id="headline">FRIDAY</h1>
      <p id="whisper">Standing by</p>
    </section>
    <div class="statusline" id="statusline">Idle field · audio reactive once microphone access is granted</div>
    <div class="note" id="note">Press Enter after typing an objective. Click once anywhere to arm microphone reactivity.</div>
    <form class="commandline" id="objective-form">
      <span>Objective</span>
      <input id="objective-input" autocomplete="off" placeholder="Ask FRIDAY to investigate, automate, generate, or act." />
    </form>
  </div>
`;

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x000000, 0);
app.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(52, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 0, 10.5);

const particleCount = 6200;
const positions = new Float32Array(particleCount * 3);
const seeds = new Float32Array(particleCount);
const radii = new Float32Array(particleCount);
const angles = new Float32Array(particleCount);
const elevations = new Float32Array(particleCount);

for (let i = 0; i < particleCount; i += 1) {
  const r = 1.6 + Math.random() * 3.4;
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(THREE.MathUtils.randFloatSpread(2));
  positions[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
  positions[i * 3 + 1] = r * Math.cos(phi);
  positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
  seeds[i] = Math.random();
  radii[i] = r;
  angles[i] = theta;
  elevations[i] = phi;
}

const geometry = new THREE.BufferGeometry();
geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
geometry.setAttribute("aRadius", new THREE.BufferAttribute(radii, 1));
geometry.setAttribute("aAngle", new THREE.BufferAttribute(angles, 1));
geometry.setAttribute("aElevation", new THREE.BufferAttribute(elevations, 1));

const vertexShader = `
uniform float uTime;
uniform float uState;
uniform float uAudio;
uniform float uEnergy;
uniform float uTrail;
attribute float aSeed;
attribute float aRadius;
attribute float aAngle;
attribute float aElevation;
varying float vGlow;

vec3 spherical(float radius, float theta, float phi) {
  return vec3(
    radius * sin(phi) * cos(theta),
    radius * cos(phi),
    radius * sin(phi) * sin(theta)
  );
}

void main() {
  float time = uTime - uTrail;
  vec3 pos = position;
  float wobble = sin(time * 0.8 + aSeed * 12.0) * 0.18 + cos(time * 0.6 + aSeed * 16.0) * 0.12;
  vec3 idlePos = pos + normalize(pos) * wobble;

  float listeningMix = smoothstep(0.5, 1.5, uState) * (1.0 - smoothstep(1.5, 1.6, uState));
  vec3 listeningPos = mix(idlePos, normalize(pos) * (0.8 + aSeed * 0.35), listeningMix * 0.9);

  float swirl = sin(time * 4.0 + aSeed * 18.0) * 0.55;
  vec3 thinkingPos = spherical(aRadius + swirl * 0.7, aAngle + time * (0.4 + aSeed), aElevation + sin(time * 1.6 + aSeed * 10.0) * 0.35);

  float respondingWave = sin((length(pos.xy) * 8.0) - time * 8.5 + aSeed * 3.0);
  vec3 respondingPos = idlePos + normalize(pos) * respondingWave * 0.45;

  float glitch = step(0.84, fract(aSeed * 37.1 + floor(time * 8.0) * 0.13));
  vec3 errorPos = pos + vec3(glitch * 1.4, glitch * -0.6, glitch * 0.8);

  vec3 finalPos = idlePos;
  if (uState > 0.5 && uState < 1.5) {
    finalPos = listeningPos;
  } else if (uState > 1.5 && uState < 2.5) {
    finalPos = thinkingPos;
  } else if (uState > 2.5 && uState < 3.5) {
    finalPos = respondingPos;
  } else if (uState > 3.5) {
    finalPos = errorPos;
  }

  float audioPush = uAudio * (0.22 + aSeed * 0.6);
  finalPos += normalize(pos) * audioPush;

  vec4 mvPosition = modelViewMatrix * vec4(finalPos, 1.0);
  float size = 1.6 + (aSeed * 3.6) + uEnergy * 6.0 + uAudio * 10.0;
  gl_PointSize = size * (260.0 / -mvPosition.z);
  gl_Position = projectionMatrix * mvPosition;
  vGlow = 0.35 + aSeed * 0.65 + uEnergy * 0.45;
}
`;

const fragmentShader = `
uniform vec3 uColorA;
uniform vec3 uColorB;
uniform float uState;
varying float vGlow;

void main() {
  vec2 uv = gl_PointCoord - vec2(0.5);
  float dist = length(uv);
  float alpha = smoothstep(0.52, 0.0, dist);
  vec3 color = mix(uColorA, uColorB, clamp(vGlow, 0.0, 1.0));
  if (uState > 3.5) {
    color = mix(color, vec3(1.0, 0.4, 0.55), 0.7);
  }
  gl_FragColor = vec4(color, alpha * 0.88);
}
`;

function createMaterial(trail = 0) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uState: { value: 0 },
      uAudio: { value: 0 },
      uEnergy: { value: 0.18 },
      uTrail: { value: trail },
      uColorA: { value: new THREE.Color("#7fe6d4") },
      uColorB: { value: new THREE.Color("#65b4ff") }
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    blending: trail ? THREE.AdditiveBlending : THREE.NormalBlending
  });
}

const trailMaterial = createMaterial(0.08);
trailMaterial.uniforms.uEnergy.value = 0.12;
const coreMaterial = createMaterial(0);

const trailPoints = new THREE.Points(geometry, trailMaterial);
const corePoints = new THREE.Points(geometry, coreMaterial);
trailPoints.scale.setScalar(1.05);
scene.add(trailPoints, corePoints);

const faintShell = new THREE.Mesh(
  new THREE.IcosahedronGeometry(4.8, 16),
  new THREE.ShaderMaterial({
    transparent: true,
    wireframe: true,
    depthWrite: false,
    uniforms: {
      uTime: { value: 0 }
    },
    vertexShader: `
      uniform float uTime;
      varying float vPulse;
      void main() {
        vec3 transformed = position + normal * sin(uTime * 0.7 + position.y * 1.5) * 0.05;
        vPulse = 0.5 + 0.5 * sin(uTime * 0.9 + position.x);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
      }
    `,
    fragmentShader: `
      varying float vPulse;
      void main() {
        gl_FragColor = vec4(0.35, 0.7, 1.0, 0.06 + vPulse * 0.04);
      }
    `
  })
);
scene.add(faintShell);

const clock = new THREE.Clock();
const headlineEl = document.getElementById("headline");
const whisperEl = document.getElementById("whisper");
const statuslineEl = document.getElementById("statusline");
const noteEl = document.getElementById("note");
const form = document.getElementById("objective-form");
const input = document.getElementById("objective-input");

let audioLevel = 0;
let audioReady = false;
let currentMode = "idle";

async function setupMicrophone() {
  if (audioReady) {
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const buffer = new Uint8Array(analyser.frequencyBinCount);

    function tickAudio() {
      analyser.getByteFrequencyData(buffer);
      let total = 0;
      for (let i = 0; i < buffer.length; i += 1) {
        total += buffer[i];
      }
      audioLevel = total / buffer.length / 255;
      requestAnimationFrame(tickAudio);
    }

    audioReady = true;
    noteEl.textContent = "Microphone reactivity armed. Type an objective or let FRIDAY idle in the room.";
    tickAudio();
  } catch {
    noteEl.textContent = "Microphone permission was denied. The field will still react to AI state.";
  }
}

window.addEventListener("pointerdown", () => {
  void setupMicrophone();
}, { once: true });

async function submitObjective(event) {
  event.preventDefault();
  const objective = input.value.trim();
  if (!objective) {
    return;
  }

  input.value = "";
  whisperEl.textContent = "Dispatching objective...";
  currentMode = "thinking";

  try {
    const response = await fetch(`${API_URL}/api/objectives/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objective,
        context: { source: "frontend-particles" },
        max_steps: 8,
        auto_retry: true,
        store_memory: true
      })
    });
    const payload = await response.json();
    statuslineEl.textContent = `Objective queued · ${payload.data.id.slice(0, 8)}`;
    noteEl.textContent = objective;
  } catch (error) {
    currentMode = "error";
    whisperEl.textContent = "Objective dispatch failed";
    noteEl.textContent = error.message;
  }
}

form.addEventListener("submit", submitObjective);

function connectRealtime() {
  const socket = new WebSocket(WS_URL);
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "bootstrap") {
      applyPresence(payload.presence);
      return;
    }
    if (payload.type === "presence") {
      applyPresence(payload.data);
      return;
    }
    if (payload.type === "event") {
      statuslineEl.textContent = `${payload.data.source.toUpperCase()} · ${payload.data.message_type}`;
    }
  });
  socket.addEventListener("close", () => {
    statuslineEl.textContent = "Realtime link lost · retrying";
    setTimeout(connectRealtime, 1200);
  });
}

function applyPresence(presence) {
  currentMode = presence.mode || "idle";
  headlineEl.textContent = presence.headline || "FRIDAY";
  whisperEl.textContent = presence.whisper || "Standing by";
  noteEl.textContent = presence.current_objective || noteEl.textContent;
  statuslineEl.textContent = `${currentMode.toUpperCase()} · ${presence.active_agents?.join(", ") || "no active agents"}`;
  coreMaterial.uniforms.uState.value = stateIndex[currentMode] ?? 0;
  trailMaterial.uniforms.uState.value = stateIndex[currentMode] ?? 0;
  coreMaterial.uniforms.uEnergy.value = presence.energy ?? 0.15;
  trailMaterial.uniforms.uEnergy.value = Math.max((presence.energy ?? 0.15) * 0.75, 0.08);
}

connectRealtime();

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate() {
  const elapsed = clock.getElapsedTime();
  coreMaterial.uniforms.uTime.value = elapsed;
  trailMaterial.uniforms.uTime.value = elapsed;
  faintShell.material.uniforms.uTime.value = elapsed;

  const pulsedAudio = audioLevel * 0.8 + (currentMode === "listening" ? 0.18 : 0);
  coreMaterial.uniforms.uAudio.value = pulsedAudio;
  trailMaterial.uniforms.uAudio.value = pulsedAudio;

  corePoints.rotation.y += 0.0009;
  trailPoints.rotation.y += 0.0005;
  corePoints.rotation.x = Math.sin(elapsed * 0.17) * 0.08;
  trailPoints.rotation.x = Math.sin(elapsed * 0.15) * 0.1;
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

animate();
