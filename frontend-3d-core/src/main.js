import './style.css';
import * as THREE from 'three';
import { GPUComputationRenderer } from 'three-stdlib';

import simShader from './shaders/simulation.glsl';
import vertShader from './shaders/vertex.glsl';
import fragShader from './shaders/fragment.glsl';
import { EffectsComposer } from './effects.js';

// === TUNABLE PARAMETERS ===
const SIZE = 160; // 25,600 particles for high detail
const BOLT_COUNT = 12; // Max simultaneous lightning bolts
const BOLT_SEGMENTS = 20; // Segments per bolt (detail level)

const API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";

// State
let currentPresence = { mode: 'idle', energy: 0.15 };
let audioLevel = 0;
let scene, camera, renderer, composer, gpuCompute, posVariable;
let particleSystem;
let clock = new THREE.Clock();
let bolts = []; // Lightning bolt pool

// UI Elements
const presenceModeEl = document.getElementById('presence-mode');
const presenceHeadlineEl = document.getElementById('presence-headline');
const presenceWhisperEl = document.getElementById('presence-whisper');
const feedListEl = document.getElementById('feed-list');
const formEl = document.getElementById('objective-form');
const inputEl = document.getElementById('objective-input');

init();

// ===============================================
// LIGHTNING BOLT SYSTEM
// ===============================================
function createBoltGeometry() {
  // Generate a jagged lightning path from origin outward
  const points = [];
  const direction = new THREE.Vector3(
    Math.random() - 0.5,
    Math.random() - 0.5,
    Math.random() - 0.5
  ).normalize();

  const startRadius = 1.5 + Math.random() * 1.5;
  let current = direction.clone().multiplyScalar(startRadius);

  points.push(current.clone());

  const boltLength = 2.0 + Math.random() * 4.0;
  const segmentLength = boltLength / BOLT_SEGMENTS;

  for (let i = 0; i < BOLT_SEGMENTS; i++) {
    // Move outward along direction with random jitter
    const jitter = new THREE.Vector3(
      (Math.random() - 0.5) * 0.8,
      (Math.random() - 0.5) * 0.8,
      (Math.random() - 0.5) * 0.8
    );

    current = current.clone().add(
      direction.clone().multiplyScalar(segmentLength).add(jitter)
    );
    points.push(current.clone());
  }

  return new THREE.BufferGeometry().setFromPoints(points);
}

function createBranch(startPoint, parentDir) {
  const points = [startPoint.clone()];
  const branchDir = parentDir.clone().add(
    new THREE.Vector3(
      (Math.random() - 0.5) * 1.5,
      (Math.random() - 0.5) * 1.5,
      (Math.random() - 0.5) * 1.5
    )
  ).normalize();

  let current = startPoint.clone();
  const segments = 5 + Math.floor(Math.random() * 6);
  const segLen = 0.3 + Math.random() * 0.4;

  for (let i = 0; i < segments; i++) {
    const jitter = new THREE.Vector3(
      (Math.random() - 0.5) * 0.5,
      (Math.random() - 0.5) * 0.5,
      (Math.random() - 0.5) * 0.5
    );
    current = current.clone().add(branchDir.clone().multiplyScalar(segLen).add(jitter));
    points.push(current.clone());
  }

  return new THREE.BufferGeometry().setFromPoints(points);
}

function initLightningPool() {
  for (let i = 0; i < BOLT_COUNT; i++) {
    const boltMaterial = new THREE.LineBasicMaterial({
      color: 0x00d4ff,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      linewidth: 1
    });

    const boltGeo = createBoltGeometry();
    const boltLine = new THREE.Line(boltGeo, boltMaterial);
    boltLine.visible = false;
    scene.add(boltLine);

    // Each bolt can have branches
    const branches = [];
    for (let b = 0; b < 2; b++) {
      const branchMat = new THREE.LineBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        linewidth: 1
      });
      const branchGeo = createBoltGeometry();
      const branchLine = new THREE.Line(branchGeo, branchMat);
      branchLine.visible = false;
      scene.add(branchLine);
      branches.push({ line: branchLine, material: branchMat });
    }

    bolts.push({
      line: boltLine,
      material: boltMaterial,
      branches: branches,
      life: 0,
      maxLife: 0,
      active: false
    });
  }
}

function spawnBolt(color) {
  // Find an inactive bolt
  const bolt = bolts.find(b => !b.active);
  if (!bolt) return;

  // Generate new jagged path
  const newGeo = createBoltGeometry();
  bolt.line.geometry.dispose();
  bolt.line.geometry = newGeo;

  // Color based on state
  bolt.material.color.set(color || 0x00d4ff);

  // Spawn branches from midpoints of the main bolt
  const positions = newGeo.attributes.position.array;
  const parentDir = new THREE.Vector3(
    positions[positions.length - 3] - positions[0],
    positions[positions.length - 2] - positions[1],
    positions[positions.length - 1] - positions[2]
  ).normalize();

  bolt.branches.forEach((branch, idx) => {
    const midIdx = Math.floor(BOLT_SEGMENTS * (0.3 + Math.random() * 0.4)) * 3;
    const branchStart = new THREE.Vector3(
      positions[midIdx], positions[midIdx + 1], positions[midIdx + 2]
    );

    const branchGeo = createBranch(branchStart, parentDir);
    branch.line.geometry.dispose();
    branch.line.geometry = branchGeo;
    branch.material.color.set(color || 0x4488ff);
    branch.line.visible = true;
    branch.material.opacity = 0.8;
  });

  bolt.active = true;
  bolt.life = 0;
  bolt.maxLife = 0.08 + Math.random() * 0.15; // 80-230ms flash
  bolt.line.visible = true;
  bolt.material.opacity = 1.0;
}

function updateLightning(delta, stateIdx) {
  // Spawn rate based on state
  let spawnChance = 0;
  let boltColor = 0x00d4ff;

  if (stateIdx === 0) {
    // Idle: rare, subtle bolts
    spawnChance = 0.005 + audioLevel * 0.02;
    boltColor = 0x00d4ff;
  } else if (stateIdx === 1) {
    // Listening: rhythmic bolts on heartbeat
    const beat = Math.pow(Math.sin(clock.getElapsedTime() * 3.5) * 0.5 + 0.5, 6);
    spawnChance = beat * 0.3 + audioLevel * 0.05;
    boltColor = 0x66ccff;
  } else if (stateIdx === 2) {
    // Thinking: intense electric storm
    spawnChance = 0.15 + audioLevel * 0.15;
    boltColor = 0x3366ff;
  } else if (stateIdx === 3) {
    // Responding: outward arcing bolts
    spawnChance = 0.06 + audioLevel * 0.08;
    boltColor = 0x22ffcc;
  } else {
    // Error: chaotic red bolts
    spawnChance = 0.2;
    boltColor = 0xff2244;
  }

  // Random spawn
  if (Math.random() < spawnChance) {
    spawnBolt(boltColor);
  }

  // Update active bolts
  bolts.forEach(bolt => {
    if (!bolt.active) return;

    bolt.life += delta;
    const progress = bolt.life / bolt.maxLife;

    if (progress >= 1.0) {
      // Kill bolt
      bolt.active = false;
      bolt.line.visible = false;
      bolt.material.opacity = 0;
      bolt.branches.forEach(b => {
        b.line.visible = false;
        b.material.opacity = 0;
      });
      return;
    }

    // Flash: peak at start, rapid decay
    const flash = Math.pow(1.0 - progress, 3.0);
    bolt.material.opacity = flash;
    bolt.branches.forEach(b => {
      b.material.opacity = flash * 0.7;
    });
  });
}

// ===============================================
// CORE INITIALIZATION
// ===============================================
async function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 12;

  renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById('canvas3d'),
    antialias: false,
    alpha: true,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;

  initComputeRenderer();
  initParticles();
  initLightningPool();
  composer = new EffectsComposer(renderer, scene, camera);

  window.addEventListener('resize', onWindowResize);
  formEl.addEventListener('submit', handleFormSubmit);

  setupAudio();
  connectWebSocket();
  animate();
}

function initComputeRenderer() {
  gpuCompute = new GPUComputationRenderer(SIZE, SIZE, renderer);
  const dtPosition = gpuCompute.createTexture();
  const positionData = dtPosition.image.data;

  for (let i = 0; i < positionData.length; i += 4) {
    const r = 1.5 + Math.random() * 3.5;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const spiralAngle = theta + r * 0.3;

    positionData[i + 0] = r * Math.sin(phi) * Math.cos(spiralAngle);
    positionData[i + 1] = r * Math.cos(phi) * 0.5;
    positionData[i + 2] = r * Math.sin(phi) * Math.sin(spiralAngle);
    positionData[i + 3] = 0.5 + Math.random() * 0.5;
  }

  posVariable = gpuCompute.addVariable('uCurrentPos', simShader, dtPosition);
  gpuCompute.setVariableDependencies(posVariable, [posVariable]);

  posVariable.material.uniforms.uTime = { value: 0 };
  posVariable.material.uniforms.uDelta = { value: 0 };
  posVariable.material.uniforms.uAudio = { value: 0 };
  posVariable.material.uniforms.uState = { value: 0 };
  posVariable.material.uniforms.uEnergy = { value: 0.15 };

  const error = gpuCompute.init();
  if (error) console.error('GPUCompute Init Error:', error);
}

function initParticles() {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(SIZE * SIZE * 3);
  const references = new Float32Array(SIZE * SIZE * 2);

  for (let i = 0; i < SIZE * SIZE; i++) {
    references[i * 2] = (i % SIZE) / SIZE;
    references[i * 2 + 1] = Math.floor(i / SIZE) / SIZE;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('reference', new THREE.BufferAttribute(references, 2));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uPosTexture: { value: null },
      uColorA: { value: new THREE.Color(0x00d4ff) },
      uColorB: { value: new THREE.Color(0x613187) },
      uSize: { value: 0.9 },
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
  particleSystem.scale.set(1.2, 1.2, 1.2);
  scene.add(particleSystem);
}

// ===============================================
// ANIMATION LOOP
// ===============================================
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

  // Update particle material
  const mat = particleSystem.material;
  mat.uniforms.uPosTexture.value = gpuCompute.getCurrentRenderTarget(posVariable).texture;
  mat.uniforms.uTime.value = elapsed;
  mat.uniforms.uState.value = stateIdx;
  mat.uniforms.uEnergy.value = currentPresence.energy;
  mat.uniforms.uAudio.value = audioLevel;

  // State colors
  const colors = getStateColors(currentPresence.mode);
  mat.uniforms.uColorA.value = colors.primary;
  mat.uniforms.uColorB.value = colors.secondary;

  // State-specific rotation speed
  let rotSpeed = 0.002;
  if (stateIdx === 1) rotSpeed = 0.003; // Listening
  if (stateIdx === 2) rotSpeed = 0.008; // Thinking — fast spin
  if (stateIdx === 3) rotSpeed = 0.004; // Responding
  particleSystem.rotation.y += rotSpeed + audioLevel * 0.01;
  particleSystem.rotation.x += rotSpeed * 0.2;

  // Update lightning bolts
  updateLightning(delta, stateIdx);

  composer.updateTime(elapsed);
  composer.render();
}

// ===============================================
// STATE MAPPING
// ===============================================
function getStateIndex(mode) {
  return { idle: 0, listening: 1, thinking: 2, responding: 3, error: 4 }[mode] ?? 0;
}

function getStateColors(mode) {
  const map = {
    idle:       { primary: new THREE.Color(0x00d4ff), secondary: new THREE.Color(0x613187) },
    listening:  { primary: new THREE.Color(0x00ffff), secondary: new THREE.Color(0x8844cc) },
    thinking:   { primary: new THREE.Color(0x3366ff), secondary: new THREE.Color(0x0022aa) },
    responding: { primary: new THREE.Color(0x22ffcc), secondary: new THREE.Color(0x00d4ff) },
    error:      { primary: new THREE.Color(0xff2244), secondary: new THREE.Color(0x613187) }
  };
  return map[mode] || map.idle;
}

// ===============================================
// SYSTEM INTEGRATIONS
// ===============================================
async function setupAudio() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const update = () => {
      analyser.getByteFrequencyData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i];
      audioLevel = (sum / buf.length) / 255;
      requestAnimationFrame(update);
    };
    update();
  } catch (e) {
    console.warn('Audio unavailable', e);
  }
}

function connectWebSocket() {
  try {
    const socket = new WebSocket(WS_URL);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'presence' || payload.type === 'bootstrap') {
        const data = payload.type === 'presence' ? payload.data : payload.presence;
        currentPresence = data;
        if (presenceModeEl) presenceModeEl.textContent = `CORE: ${data.mode.toUpperCase()}`;
        if (presenceHeadlineEl) presenceHeadlineEl.textContent = data.headline || "FRIDAY AI";
        if (presenceWhisperEl) presenceWhisperEl.textContent = data.whisper || "Ready";
      }
      if (payload.type === 'event' && feedListEl) {
        const item = document.createElement('div');
        item.className = 'feed-item';
        item.innerHTML = `<span class="source">${payload.data.source.toUpperCase()}</span> ${payload.data.message_type}`;
        feedListEl.prepend(item);
        if (feedListEl.children.length > 20) feedListEl.removeChild(feedListEl.lastChild);
      }
    };
    socket.onclose = () => setTimeout(connectWebSocket, 2000);
    socket.onerror = () => {};
  } catch (e) {
    setTimeout(connectWebSocket, 2000);
  }
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
  } catch (err) { console.error('Dispatch error', err); }
  finally { setTimeout(() => { inputEl.placeholder = "Awaiting text or voice input..."; }, 1000); }
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
}
