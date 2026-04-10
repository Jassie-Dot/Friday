import './style.css';
import * as THREE from 'three';
import { GPUComputationRenderer } from 'three-stdlib';
import { EffectComposer } from 'three-stdlib';
import { RenderPass } from 'three-stdlib';
import { UnrealBloomPass } from 'three-stdlib';
import { ShaderPass } from 'three-stdlib';

// Shaders
import simShader from './shaders/simulation.glsl';
import vertShader from './shaders/vertex.glsl';
import fragShader from './shaders/fragment.glsl';
import nebulaVertShader from './shaders/nebula.vert.glsl';
import nebulaFragShader from './shaders/nebula.glsl';
import godraysVertShader from './shaders/godrays.vert.glsl';
import godraysFragShader from './shaders/godrays.glsl';

// Effects
import { WispsSystem } from './wisps.js';
import { EffectsComposer } from './effects.js';

// Constants
const SIZE = 512;
const API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";

// State
let currentPresence = { mode: 'idle', energy: 0.15 };
let audioLevel = 0;
let scene, camera, renderer, composer, gpuCompute, posVariable;
let particleSystem, nebulaPlane, wispsSystem;
let clock = new THREE.Clock();
let mouse = new THREE.Vector2(0.5, 0.5);

// UI Elements
const presenceModeEl = document.getElementById('presence-mode');
const presenceHeadlineEl = document.getElementById('presence-headline');
const presenceWhisperEl = document.getElementById('presence-whisper');
const feedListEl = document.getElementById('feed-list');
const formEl = document.getElementById('objective-form');
const inputEl = document.getElementById('objective-input');

init();

async function init() {
  // Scene Setup
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 10;

  renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById('canvas3d'),
    antialias: false,
    alpha: true,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;

  // Nebula Background
  initNebula();

  // GPGPU Setup
  initComputeRenderer();

  // Particles Setup
  initParticles();

  // Wisps System
  wispsSystem = new WispsSystem(scene, currentPresence);

  // Post Processing
  initPostProcessing();

  // Events
  window.addEventListener('resize', onWindowResize);
  window.addEventListener('mousemove', onMouseMove);
  formEl.addEventListener('submit', handleFormSubmit);

  // Audio & Socket
  setupAudio();
  connectWebSocket();

  // Animation Loop
  animate();
}

function initNebula() {
  const nebulaGeometry = new THREE.PlaneGeometry(30, 20);
  const nebulaMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      uMouse: { value: new THREE.Vector2(0.5, 0.5) }
    },
    vertexShader: nebulaVertShader,
    fragmentShader: nebulaFragShader,
    depthWrite: false,
    depthTest: false
  });

  nebulaPlane = new THREE.Mesh(nebulaGeometry, nebulaMaterial);
  nebulaPlane.position.z = -15;
  nebulaPlane.renderOrder = -1;
  scene.add(nebulaPlane);
}

function initComputeRenderer() {
  gpuCompute = new GPUComputationRenderer(SIZE, SIZE, renderer);

  const dtPosition = gpuCompute.createTexture();
  const positionData = dtPosition.image.data;

  // Initial Positions - Dramatic spiral pattern
  for (let i = 0; i < positionData.length; i += 4) {
    const r = 1.0 + Math.random() * 2.0; // Smaller core initialization (was 3 and 5)
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);

    // Spiral distribution
    const spiralAngle = theta + r * 0.3;
    positionData[i + 0] = r * Math.sin(phi) * Math.cos(spiralAngle);
    positionData[i + 1] = r * Math.cos(phi) * 0.5;
    positionData[i + 2] = r * Math.sin(phi) * Math.sin(spiralAngle);
    positionData[i + 3] = 0.5 + Math.random() * 0.5; // Life
  }

  posVariable = gpuCompute.addVariable('uCurrentPos', simShader, dtPosition);
  gpuCompute.setVariableDependencies(posVariable, [posVariable]);

  posVariable.material.uniforms.uTime = { value: 0 };
  posVariable.material.uniforms.uDelta = { value: 0 };
  posVariable.material.uniforms.uAudio = { value: 0 };
  posVariable.material.uniforms.uState = { value: 0 };
  posVariable.material.uniforms.uEnergy = { value: 0.15 };

  const error = gpuCompute.init();
  if (error !== null) {
    console.error('GPUCompute Init Error:', error);
  }
}

function initParticles() {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(SIZE * SIZE * 3);
  const references = new Float32Array(SIZE * SIZE * 2);

  for (let i = 0; i < SIZE * SIZE; i++) {
    const x = (i % SIZE) / SIZE;
    const y = Math.floor(i / SIZE) / SIZE;
    references[i * 2 + 0] = x;
    references[i * 2 + 1] = y;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('reference', new THREE.BufferAttribute(references, 2));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uPosTexture: { value: null },
      uColorA: { value: new THREE.Color(0xFFD700) },
      uColorB: { value: new THREE.Color(0x9D4EDD) },
      uSize: { value: 2.0 },
      uTime: { value: 0 },
      uState: { value: 0 },
      uEnergy: { value: 0.15 },
      uAudio: { value: 0 }
    },
    vertexShader: vertShader,
    fragmentShader: fragShader,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  particleSystem = new THREE.Points(geometry, material);
  particleSystem.position.z = 0;
  particleSystem.scale.set(0.6, 0.6, 0.6); // Scale down for smaller core
  scene.add(particleSystem);
}

function initPostProcessing() {
  composer = new EffectsComposer(renderer, scene, camera);
}

function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();
  const elapsed = clock.getElapsedTime();

  const stateIdx = getStateIndex(currentPresence.mode);

  // Update GPGPU
  posVariable.material.uniforms.uTime.value = elapsed;
  posVariable.material.uniforms.uDelta.value = delta;
  posVariable.material.uniforms.uAudio.value = audioLevel;
  posVariable.material.uniforms.uState.value = stateIdx;
  posVariable.material.uniforms.uEnergy.value = currentPresence.energy;

  gpuCompute.compute();

  // Update Particle Material
  particleSystem.material.uniforms.uPosTexture.value = gpuCompute.getCurrentRenderTarget(posVariable).texture;
  particleSystem.material.uniforms.uTime.value = elapsed;
  particleSystem.material.uniforms.uState.value = stateIdx;
  particleSystem.material.uniforms.uEnergy.value = currentPresence.energy;
  particleSystem.material.uniforms.uAudio.value = audioLevel; // Pass audio to particle system

  // Update colors based on state
  const colors = getStateColors(currentPresence.mode);
  particleSystem.material.uniforms.uColorA.value = colors.primary;
  particleSystem.material.uniforms.uColorB.value = colors.secondary;

  // Dynamic rotation based on state
  let rotSpeed = 0.003;
  if (stateIdx === 1) rotSpeed = 0.006; // Listening - faster
  if (stateIdx === 2) rotSpeed = 0.012; // Thinking - intense
  if (stateIdx === 3) rotSpeed = 0.008; // Responding - burst

  particleSystem.rotation.y += rotSpeed + (audioLevel * 0.03);
  particleSystem.rotation.x += rotSpeed * 0.5;

  // Update nebula
  if (nebulaPlane) {
    nebulaPlane.material.uniforms.uTime.value = elapsed;
    nebulaPlane.material.uniforms.uMouse.value = mouse;
  }

  // Update wisps
  wispsSystem.update(currentPresence, delta);

  // Update effects
  composer.updateTime(elapsed);

  composer.render();
}

function getStateIndex(mode) {
  const map = { idle: 0, listening: 1, thinking: 2, responding: 3, error: 4 };
  return map[mode] ?? 0;
}

function getStateColors(mode) {
  switch(mode) {
    case 'idle':
      return { primary: new THREE.Color(0xFFD700), secondary: new THREE.Color(0x9D4EDD) };
    case 'listening':
      return { primary: new THREE.Color(0x00FFFF), secondary: new THREE.Color(0xC0C0C0) };
    case 'thinking':
      return { primary: new THREE.Color(0xFF6B00), secondary: new THREE.Color(0xFF003C) };
    case 'responding':
      return { primary: new THREE.Color(0xFFD700), secondary: new THREE.Color(0xFFFFFF) };
    case 'error':
      return { primary: new THREE.Color(0x8B0000), secondary: new THREE.Color(0x000000) };
    default:
      return { primary: new THREE.Color(0xFFD700), secondary: new THREE.Color(0x9D4EDD) };
  }
}

// System Integrations
async function setupAudio() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    const buffer = new Uint8Array(analyser.frequencyBinCount);

    const updateAudio = () => {
      analyser.getByteFrequencyData(buffer);
      let sum = 0;
      for (let i = 0; i < buffer.length; i++) sum += buffer[i];
      audioLevel = (sum / buffer.length) / 255;
      requestAnimationFrame(updateAudio);
    };
    updateAudio();
  } catch (e) {
    console.warn('Audio feedback unavailable', e);
  }
}

function connectWebSocket() {
  const socket = new WebSocket(WS_URL);

  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === 'presence' || payload.type === 'bootstrap') {
      const data = payload.type === 'presence' ? payload.data : payload.presence;
      currentPresence = data;
      updatePresenceUI(data);
    }
    if (payload.type === 'event') {
      pushEvent(payload.data);
    }
  };

  socket.onclose = () => setTimeout(connectWebSocket, 2000);
}

function updatePresenceUI(presence) {
  presenceModeEl.textContent = `CORE: ${presence.mode.toUpperCase()}`;
  presenceHeadlineEl.textContent = presence.headline || "FRIDAY 3D";
  presenceWhisperEl.textContent = presence.whisper || "Ready for core dispatch";
}

function pushEvent(event) {
  const item = document.createElement('div');
  item.className = 'feed-item';
  item.innerHTML = `<span class="source">${event.source.toUpperCase()}</span> ${event.message_type}`;
  feedListEl.prepend(item);
  if (feedListEl.children.length > 20) feedListEl.removeChild(feedListEl.lastChild);
}

async function handleFormSubmit(e) {
  e.preventDefault();
  const objective = inputEl.value.trim();
  if (!objective) return;

  inputEl.value = "";
  inputEl.placeholder = "DISPATCHING...";

  try {
    await fetch(`${API_URL}/api/objectives/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, context: { source: "frontend-3d-core" } })
    });
  } catch (err) {
    console.error('Dispatch error', err);
  } finally {
    setTimeout(() => { inputEl.placeholder = "DISPATCH OBJECTIVE..."; }, 1000);
  }
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);

  if (nebulaPlane) {
    nebulaPlane.material.uniforms.uResolution.value.set(window.innerWidth, window.innerHeight);
  }
}

function onMouseMove(e) {
  mouse.x = e.clientX / window.innerWidth;
  mouse.y = 1.0 - e.clientY / window.innerHeight;
}
