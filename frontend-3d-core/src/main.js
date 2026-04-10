import './style.css';
import * as THREE from 'three';
import { GPUComputationRenderer } from 'three-stdlib';
import { EffectComposer } from 'three-stdlib';
import { RenderPass } from 'three-stdlib';
import { UnrealBloomPass } from 'three-stdlib';

// Shaders
import simShader from './shaders/simulation.glsl';
import vertShader from './shaders/vertex.glsl';
import fragShader from './shaders/fragment.glsl';

// Constants
const SIZE = 512; // 512x512 = 262,144 particles
const API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";

// State
let currentPresence = { mode: 'idle', energy: 0.15 };
let audioLevel = 0;
let scene, camera, renderer, composer, gpuCompute, posVariable;
let particleSystem;
const clock = new THREE.Clock();

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
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 12;

  renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById('canvas3d'),
    antialias: false,
    alpha: true,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  // GPGPU Setup
  initComputeRenderer();

  // Particles Setup
  initParticles();

  // Post Processing
  initPostProcessing();

  // Events
  window.addEventListener('resize', onWindowResize);
  formEl.addEventListener('submit', handleFormSubmit);
  
  // Audio & Socket
  setupAudio();
  connectWebSocket();

  // Animation Loop
  animate();
}

function initComputeRenderer() {
  gpuCompute = new GPUComputationRenderer(SIZE, SIZE, renderer);

  const dtPosition = gpuCompute.createTexture();
  const positionData = dtPosition.image.data;

  // Initial Positions (Random Sphere)
  for (let i = 0; i < positionData.length; i += 4) {
    const r = 4 + Math.random() * 4;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positionData[i + 0] = r * Math.sin(phi) * Math.cos(theta);
    positionData[i + 1] = r * Math.cos(phi);
    positionData[i + 2] = r * Math.sin(phi) * Math.sin(theta);
    positionData[i + 3] = Math.random(); // Life
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
      uColorA: { value: new THREE.Color('#4ef5d2') },
      uColorB: { value: new THREE.Color('#9d4edd') },
      uSize: { value: 1.8 } // Smaller particles
    },
    vertexShader: vertShader,
    fragmentShader: fragShader,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  particleSystem = new THREE.Points(geometry, material);
  scene.add(particleSystem);
}

function initPostProcessing() {
  const renderScene = new RenderPass(scene, camera);
  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight),
    0.6, // Drastically reduced from 1.5
    0.5, // Radius
    0.9 // Threshold
  );

  composer = new EffectComposer(renderer);
  composer.addPass(renderScene);
  composer.addPass(bloomPass);
}

function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();
  const elapsed = clock.getElapsedTime();

  // Update GPGPU
  posVariable.material.uniforms.uTime.value = elapsed;
  posVariable.material.uniforms.uDelta.value = delta;
  posVariable.material.uniforms.uAudio.value = audioLevel;
  posVariable.material.uniforms.uState.value = getStateIndex(currentPresence.mode);
  posVariable.material.uniforms.uEnergy.value = currentPresence.energy;

  gpuCompute.compute();

  // Update Particle Material
  particleSystem.material.uniforms.uPosTexture.value = gpuCompute.getCurrentRenderTarget(posVariable).texture;

  // Smooth Rotation
  particleSystem.rotation.y += 0.002 + (audioLevel * 0.05);
  particleSystem.rotation.x += 0.001;

  composer.render();
}

function getStateIndex(mode) {
  const map = { idle: 0, listening: 1, thinking: 2, responding: 3, error: 4 };
  return map[mode] ?? 0;
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
  
  // Dynamic colors based on energy
  const primaryColor = new THREE.Color('#4ef5d2').lerp(new THREE.Color('#ff003c'), presence.energy * 0.5);
  particleSystem.material.uniforms.uColorA.value = primaryColor;
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
}
