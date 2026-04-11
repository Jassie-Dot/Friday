import './style.css';
import * as THREE from 'three';
import { GPUComputationRenderer } from 'three-stdlib';

import simShader from './shaders/simulation.glsl';
import vertShader from './shaders/vertex.glsl';
import fragShader from './shaders/fragment.glsl';
import { EffectsComposer } from './effects.js';

// === TUNABLE PARAMETERS ===
const SIZE = 160; // 25,600 particles
const BOLT_COUNT = 12;
const BOLT_SEGMENTS = 20;

const API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";

// ── State ──
let currentPresence = { mode: 'idle', energy: 0.15 };
let audioLevel = 0;
let scene, camera, renderer, composer, gpuCompute, posVariable;
let particleSystem;
let clock = new THREE.Clock();
let bolts = [];

// Voice system state
let recognition;
let isListening = false;
let isContinuousMode = false;
let synth = window.speechSynthesis;
let wsSocket = null;
let spokenTexts = new Set(); // Track already-spoken texts

// ── UI Elements ──
const presenceModeEl     = document.getElementById('presence-mode');
const statusPillEl       = document.getElementById('status-pill');
const statusDotEl        = document.getElementById('status-dot');
const conversationListEl = document.getElementById('conversation-list');
const feedListEl         = document.getElementById('feed-list');
const micToggleBtn       = document.getElementById('mic-toggle');
const voiceIndicatorEl   = document.getElementById('voice-indicator');
const formEl             = document.getElementById('objective-form');
const inputEl            = document.getElementById('objective-input');
const voiceStatusEl      = document.getElementById('voice-status');
const statConnectionEl   = document.getElementById('stat-connection');

init();

// ═══════════════════════════════════════════
// LIGHTNING BOLT SYSTEM
// ═══════════════════════════════════════════
function createBoltGeometry() {
  const points = [];
  const direction = new THREE.Vector3(
    Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5
  ).normalize();
  const startRadius = 1.5 + Math.random() * 1.5;
  let current = direction.clone().multiplyScalar(startRadius);
  points.push(current.clone());
  const boltLength = 2.0 + Math.random() * 4.0;
  const segmentLength = boltLength / BOLT_SEGMENTS;
  for (let i = 0; i < BOLT_SEGMENTS; i++) {
    const jitter = new THREE.Vector3(
      (Math.random() - 0.5) * 0.8, (Math.random() - 0.5) * 0.8, (Math.random() - 0.5) * 0.8
    );
    current = current.clone().add(direction.clone().multiplyScalar(segmentLength).add(jitter));
    points.push(current.clone());
  }
  return new THREE.BufferGeometry().setFromPoints(points);
}

function createBranch(startPoint, parentDir) {
  const points = [startPoint.clone()];
  const branchDir = parentDir.clone().add(
    new THREE.Vector3((Math.random()-0.5)*1.5, (Math.random()-0.5)*1.5, (Math.random()-0.5)*1.5)
  ).normalize();
  let current = startPoint.clone();
  const segments = 5 + Math.floor(Math.random() * 6);
  const segLen = 0.3 + Math.random() * 0.4;
  for (let i = 0; i < segments; i++) {
    const jitter = new THREE.Vector3((Math.random()-0.5)*0.5, (Math.random()-0.5)*0.5, (Math.random()-0.5)*0.5);
    current = current.clone().add(branchDir.clone().multiplyScalar(segLen).add(jitter));
    points.push(current.clone());
  }
  return new THREE.BufferGeometry().setFromPoints(points);
}

function initLightningPool() {
  for (let i = 0; i < BOLT_COUNT; i++) {
    const boltMaterial = new THREE.LineBasicMaterial({
      color: 0x00d4ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, linewidth: 1
    });
    const boltGeo = createBoltGeometry();
    const boltLine = new THREE.Line(boltGeo, boltMaterial);
    boltLine.visible = false;
    scene.add(boltLine);
    const branches = [];
    for (let b = 0; b < 2; b++) {
      const branchMat = new THREE.LineBasicMaterial({
        color: 0x4488ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, linewidth: 1
      });
      const branchGeo = createBoltGeometry();
      const branchLine = new THREE.Line(branchGeo, branchMat);
      branchLine.visible = false;
      scene.add(branchLine);
      branches.push({ line: branchLine, material: branchMat });
    }
    bolts.push({ line: boltLine, material: boltMaterial, branches, life: 0, maxLife: 0, active: false });
  }
}

function spawnBolt(color) {
  const bolt = bolts.find(b => !b.active);
  if (!bolt) return;
  const newGeo = createBoltGeometry();
  bolt.line.geometry.dispose();
  bolt.line.geometry = newGeo;
  bolt.material.color.set(color || 0x00d4ff);
  const positions = newGeo.attributes.position.array;
  const parentDir = new THREE.Vector3(
    positions[positions.length-3]-positions[0],
    positions[positions.length-2]-positions[1],
    positions[positions.length-1]-positions[2]
  ).normalize();
  bolt.branches.forEach((branch) => {
    const midIdx = Math.floor(BOLT_SEGMENTS * (0.3 + Math.random() * 0.4)) * 3;
    const branchStart = new THREE.Vector3(positions[midIdx], positions[midIdx+1], positions[midIdx+2]);
    const branchGeo = createBranch(branchStart, parentDir);
    branch.line.geometry.dispose();
    branch.line.geometry = branchGeo;
    branch.material.color.set(color || 0x4488ff);
    branch.line.visible = true;
    branch.material.opacity = 0.8;
  });
  bolt.active = true;
  bolt.life = 0;
  bolt.maxLife = 0.08 + Math.random() * 0.15;
  bolt.line.visible = true;
  bolt.material.opacity = 1.0;
}

function updateLightning(delta, stateIdx) {
  let spawnChance = 0;
  let boltColor = 0x00d4ff;
  if (stateIdx === 0) {
    spawnChance = 0.005 + audioLevel * 0.02;
    boltColor = 0x00d4ff;
  } else if (stateIdx === 1) {
    const beat = Math.pow(Math.sin(clock.getElapsedTime() * 3.5) * 0.5 + 0.5, 6);
    spawnChance = beat * 0.3 + audioLevel * 0.05;
    boltColor = 0x66ccff;
  } else if (stateIdx === 2) {
    spawnChance = 0.15 + audioLevel * 0.15;
    boltColor = 0x3366ff;
  } else if (stateIdx === 3) {
    spawnChance = 0.06 + audioLevel * 0.08;
    boltColor = 0x22ffcc;
  } else {
    spawnChance = 0.2;
    boltColor = 0xff2244;
  }
  if (Math.random() < spawnChance) spawnBolt(boltColor);
  bolts.forEach(bolt => {
    if (!bolt.active) return;
    bolt.life += delta;
    const progress = bolt.life / bolt.maxLife;
    if (progress >= 1.0) {
      bolt.active = false;
      bolt.line.visible = false;
      bolt.material.opacity = 0;
      bolt.branches.forEach(b => { b.line.visible = false; b.material.opacity = 0; });
      return;
    }
    const flash = Math.pow(1.0 - progress, 3.0);
    bolt.material.opacity = flash;
    bolt.branches.forEach(b => { b.material.opacity = flash * 0.7; });
  });
}

// ═══════════════════════════════════════════
// CORE INIT
// ═══════════════════════════════════════════
async function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 12;

  renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById('canvas3d'),
    antialias: false, alpha: true, powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;

  try {
    if (document.getElementById('canvas3d')) {
      initComputeRenderer();
      initParticles();
      initLightningPool();
      composer = new EffectsComposer(renderer, scene, camera);
    }
    window.addEventListener('resize', onWindowResize);
    if (formEl) formEl.addEventListener('submit', handleFormSubmit);

    setupAudio();
    connectWebSocket();
    initVoiceSystem();
    animate();
  } catch (err) {
    console.error('FRIDAY: Critical init failure', err);
    if (particleSystem) animate();
  }
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
  posVariable.material.uniforms.uTime   = { value: 0 };
  posVariable.material.uniforms.uDelta  = { value: 0 };
  posVariable.material.uniforms.uAudio  = { value: 0 };
  posVariable.material.uniforms.uState  = { value: 0 };
  posVariable.material.uniforms.uEnergy = { value: 0.15 };
  const error = gpuCompute.init();
  if (error) console.error('GPUCompute Init Error:', error);
}

function initParticles() {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(SIZE * SIZE * 3);
  const references = new Float32Array(SIZE * SIZE * 2);
  for (let i = 0; i < SIZE * SIZE; i++) {
    references[i * 2]     = (i % SIZE) / SIZE;
    references[i * 2 + 1] = Math.floor(i / SIZE) / SIZE;
  }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('reference', new THREE.BufferAttribute(references, 2));
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uPosTexture: { value: null },
      uColorA: { value: new THREE.Color(0x00d4ff) },
      uColorB: { value: new THREE.Color(0x613187) },
      uSize: { value: 0.9 }, uTime: { value: 0 },
      uState: { value: 0 }, uEnergy: { value: 0.15 }, uAudio: { value: 0 }
    },
    vertexShader: vertShader, fragmentShader: fragShader,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false
  });
  particleSystem = new THREE.Points(geometry, material);
  particleSystem.scale.set(1.2, 1.2, 1.2);
  scene.add(particleSystem);
}

// ═══════════════════════════════════════════
// ANIMATION LOOP
// ═══════════════════════════════════════════
function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  const elapsed = clock.getElapsedTime();
  const stateIdx = getStateIndex(currentPresence.mode);

  posVariable.material.uniforms.uTime.value   = elapsed;
  posVariable.material.uniforms.uDelta.value  = delta;
  posVariable.material.uniforms.uAudio.value  = audioLevel;
  posVariable.material.uniforms.uState.value  = stateIdx;
  posVariable.material.uniforms.uEnergy.value = currentPresence.energy;
  gpuCompute.compute();

  const mat = particleSystem.material;
  mat.uniforms.uPosTexture.value = gpuCompute.getCurrentRenderTarget(posVariable).texture;
  mat.uniforms.uTime.value    = elapsed;
  mat.uniforms.uState.value   = stateIdx;
  mat.uniforms.uEnergy.value  = currentPresence.energy;
  mat.uniforms.uAudio.value   = audioLevel;

  const colors = getStateColors(currentPresence.mode);
  mat.uniforms.uColorA.value = colors.primary;
  mat.uniforms.uColorB.value = colors.secondary;

  let rotSpeed = 0.002;
  if (stateIdx === 1) rotSpeed = 0.003;
  if (stateIdx === 2) rotSpeed = 0.008;
  if (stateIdx === 3) rotSpeed = 0.004;
  particleSystem.rotation.y += rotSpeed + audioLevel * 0.01;
  particleSystem.rotation.x += rotSpeed * 0.2;

  updateLightning(delta, stateIdx);

  if (composer) {
    try { composer.updateTime(elapsed); composer.render(); }
    catch (e) { renderer.render(scene, camera); }
  } else {
    renderer.render(scene, camera);
  }
}

// ═══════════════════════════════════════════
// STATE MAPPING
// ═══════════════════════════════════════════
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

function updatePresenceUI(data) {
  const mode = data.mode || 'idle';
  currentPresence = data;

  // Update status pill
  if (presenceModeEl) presenceModeEl.textContent = mode.toUpperCase();
  if (statusPillEl) statusPillEl.setAttribute('data-state', mode);

  // Update status dot color
  if (statusDotEl) {
    const dotColors = { idle: '#00d4ff', listening: '#00ffff', thinking: '#3366ff', responding: '#22ffcc', error: '#ff2244' };
    statusDotEl.style.background = dotColors[mode] || dotColors.idle;
    statusDotEl.style.boxShadow = `0 0 6px ${dotColors[mode] || dotColors.idle}`;
  }
}

// ═══════════════════════════════════════════
// AUDIO INPUT
// ═══════════════════════════════════════════
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
    console.warn('FRIDAY: Audio visualization unavailable', e);
  }
}

// ═══════════════════════════════════════════
// CONVERSATION RENDERING
// ═══════════════════════════════════════════
function addChatMessage(role, text) {
  if (!conversationListEl || !text) return;

  const msg = document.createElement('div');
  msg.className = `chat-msg ${role}`;

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? 'YOU' : 'FRIDAY';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  if (role === 'friday') {
    // Typewriter effect for FRIDAY's responses
    typewriterBubble(bubble, text);
  } else {
    bubble.textContent = text;
  }

  msg.appendChild(label);
  msg.appendChild(bubble);
  conversationListEl.appendChild(msg);

  // Scroll to bottom
  const panel = document.getElementById('conversation-panel');
  if (panel) {
    requestAnimationFrame(() => {
      panel.scrollTop = panel.scrollHeight;
    });
  }
}

function typewriterBubble(element, text) {
  element.textContent = '';
  let i = 0;
  const speed = 12;
  if (element._typeInterval) clearInterval(element._typeInterval);
  element._typeInterval = setInterval(() => {
    if (i < text.length) {
      element.textContent += text.charAt(i);
      i++;
      // Auto scroll
      const panel = document.getElementById('conversation-panel');
      if (panel) panel.scrollTop = panel.scrollHeight;
    } else {
      clearInterval(element._typeInterval);
    }
  }, speed);
}

function showTypingIndicator() {
  if (!conversationListEl) return;
  // Remove existing typing indicator
  removeTypingIndicator();

  const msg = document.createElement('div');
  msg.className = 'chat-msg friday';
  msg.id = 'typing-msg';

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = 'FRIDAY';

  const indicator = document.createElement('div');
  indicator.className = 'typing-indicator';
  indicator.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';

  msg.appendChild(label);
  msg.appendChild(indicator);
  conversationListEl.appendChild(msg);

  const panel = document.getElementById('conversation-panel');
  if (panel) panel.scrollTop = panel.scrollHeight;
}

function removeTypingIndicator() {
  const existing = document.getElementById('typing-msg');
  if (existing) existing.remove();
}

// ═══════════════════════════════════════════
// VOICE SYSTEM (Always-On Wake Word)
// ═══════════════════════════════════════════

function initVoiceSystem() {
  if (!micToggleBtn) return;

  // Warm up speech synthesis
  if (synth) {
    try { synth.getVoices(); } catch (e) {}
    // Voices may load async
    if (speechSynthesis.onvoiceschanged !== undefined) {
      speechSynthesis.onvoiceschanged = () => { synth.getVoices(); };
    }
  }

  // Setup speech recognition
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = true;       // Always listening
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isListening = true;
      micToggleBtn.classList.add('active');
      if (voiceIndicatorEl) voiceIndicatorEl.classList.add('listening');
      if (voiceStatusEl) voiceStatusEl.innerHTML = 'Listening... say <strong>"Friday"</strong> to activate';
    };

    recognition.onresult = (event) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      // Show interim text
      if (interimTranscript && voiceStatusEl) {
        voiceStatusEl.textContent = `Hearing: "${interimTranscript}"`;
      }

      if (finalTranscript) {
        const cleaned = finalTranscript.trim();
        // Check for wake word "Friday" at the start
        const wakeWordPattern = /^(hey\s+)?friday[,.\s]*/i;
        const match = cleaned.match(wakeWordPattern);

        if (match) {
          // Strip wake word and send the rest
          const command = cleaned.replace(wakeWordPattern, '').trim();
          if (command) {
            submitObjective(command, 'voice');
          } else {
            // Just said "Friday" with nothing else — acknowledge
            submitObjective('Hello', 'voice');
          }
        } else if (isContinuousMode) {
          // If mic button was manually pressed, send everything
          submitObjective(cleaned, 'voice');
        }

        if (voiceStatusEl) {
          voiceStatusEl.innerHTML = 'Listening... say <strong>"Friday"</strong> to activate';
        }
      }
    };

    recognition.onerror = (event) => {
      if (event.error !== 'no-speech') {
        console.error('FRIDAY: Speech recognition error', event.error);
      }
      // Auto-restart on non-fatal errors
      if (event.error === 'no-speech' || event.error === 'aborted') {
        restartListening();
      }
    };

    recognition.onend = () => {
      // Auto-restart continuous listening
      if (isListening) {
        restartListening();
      }
    };

    // Start listening automatically
    startListening();
  } else {
    micToggleBtn.style.display = 'none';
    if (voiceStatusEl) voiceStatusEl.textContent = 'Voice not supported in this browser';
  }

  // Manual mic toggle for continuous mode (send all speech, not just wake-word)
  micToggleBtn.addEventListener('click', () => {
    if (isContinuousMode) {
      isContinuousMode = false;
      micToggleBtn.classList.remove('active');
      if (voiceStatusEl) voiceStatusEl.innerHTML = 'Listening... say <strong>"Friday"</strong> to activate';
    } else {
      isContinuousMode = true;
      micToggleBtn.classList.add('active');
      if (voiceStatusEl) voiceStatusEl.textContent = 'Open mic — all speech will be sent';
      if (!isListening) startListening();
    }
  });
}

function startListening() {
  try {
    recognition.start();
    isListening = true;
  } catch (e) {
    // Already started
  }
}

function restartListening() {
  setTimeout(() => {
    try {
      recognition.start();
    } catch (e) {
      // Already running
    }
  }, 300);
}

// ═══════════════════════════════════════════
// SPEECH SYNTHESIS (FRIDAY's Voice)
// ═══════════════════════════════════════════
function speakText(text) {
  if (!text || !synth) return;

  // Don't re-speak the same text
  const textKey = text.substring(0, 100);
  if (spokenTexts.has(textKey)) return;
  spokenTexts.add(textKey);
  // Prevent memory leak
  if (spokenTexts.size > 50) {
    const first = spokenTexts.values().next().value;
    spokenTexts.delete(first);
  }

  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(text);

  const voices = synth.getVoices();
  // Priority: Irish Female → UK English Female → Zira → any Female → first available
  const preferredVoice =
    voices.find(v => /irish/i.test(v.name) && /female/i.test(v.name)) ||
    voices.find(v => /uk english female/i.test(v.name)) ||
    voices.find(v => /zira/i.test(v.name)) ||
    voices.find(v => /female/i.test(v.name)) ||
    voices.find(v => /hazel/i.test(v.name)) ||
    voices.find(v => /samantha/i.test(v.name)) ||
    voices[0];

  if (preferredVoice) utterance.voice = preferredVoice;

  utterance.pitch = 1.05;
  utterance.rate  = 1.05;

  utterance.onstart = () => {
    currentPresence.mode = 'responding';
    updatePresenceUI(currentPresence);
  };

  utterance.onend = () => {
    // Don't force idle here — let WebSocket presence handle it
  };

  synth.speak(utterance);
}

// ═══════════════════════════════════════════
// WEBSOCKET (Bidirectional)
// ═══════════════════════════════════════════
function connectWebSocket() {
  try {
    wsSocket = new WebSocket(WS_URL);

    wsSocket.onopen = () => {
      if (statConnectionEl) {
        statConnectionEl.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12"><circle cx="12" cy="12" r="5" fill="currentColor"/></svg> CONNECTED';
        statConnectionEl.style.color = '';
      }
    };

    wsSocket.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      // ── Presence updates ──
      if (payload.type === 'presence' || payload.type === 'bootstrap') {
        const data = payload.type === 'presence' ? payload.data : payload.presence;
        updatePresenceUI(data);

        if (data.mode === 'thinking') {
          showTypingIndicator();
        } else {
          removeTypingIndicator();
        }

        // Speak FRIDAY's terminal text when responding
        if (data.terminal_text && data.mode === 'responding') {
          speakText(data.terminal_text);
        }
      }

      // ── Conversation messages ──
      if (payload.type === 'conversation') {
        removeTypingIndicator();
        addChatMessage(payload.data.role, payload.data.text);

        // Speak FRIDAY's response
        if (payload.data.role === 'friday') {
          speakText(payload.data.text);
        }
      }

      // ── Bootstrap: load existing conversation ──
      if (payload.type === 'bootstrap' && payload.conversation) {
        payload.conversation.forEach(entry => {
          addChatMessage(entry.role, entry.text);
        });
      }

      // ── Telemetry events ──
      if (payload.type === 'event' && feedListEl) {
        const item = document.createElement('div');
        item.className = 'feed-item';
        item.innerHTML = `<span class="source">${payload.data.source.toUpperCase()}</span> ${payload.data.message_type}`;
        feedListEl.prepend(item);
        if (feedListEl.children.length > 20) feedListEl.removeChild(feedListEl.lastChild);
      }
    };

    wsSocket.onclose = () => {
      wsSocket = null;
      if (statConnectionEl) {
        statConnectionEl.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12"><circle cx="12" cy="12" r="5" fill="currentColor"/></svg> RECONNECTING...';
        statConnectionEl.style.color = '#ff9900';
      }
      setTimeout(connectWebSocket, 2000);
    };

    wsSocket.onerror = () => {};
  } catch (e) {
    setTimeout(connectWebSocket, 2000);
  }
}

// ═══════════════════════════════════════════
// SUBMIT OBJECTIVE (via WebSocket)
// ═══════════════════════════════════════════
function submitObjective(text, source = 'text') {
  if (!text || !text.trim()) return;
  const objective = text.trim();

  // Immediately show user message in conversation
  addChatMessage('user', objective);

  // Show typing indicator
  showTypingIndicator();

  // Send via WebSocket if connected, else fallback to HTTP
  if (wsSocket && wsSocket.readyState === WebSocket.OPEN) {
    wsSocket.send(JSON.stringify({
      type: 'objective',
      text: objective,
      context: { source: `frontend-3d-core-${source}` }
    }));
  } else {
    // HTTP fallback
    fetch(`${API_URL}/api/objectives/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ objective, context: { source: `frontend-3d-core-${source}` } })
    }).catch(err => console.error('FRIDAY: Dispatch error', err));
  }
}

// ═══════════════════════════════════════════
// FORM SUBMIT
// ═══════════════════════════════════════════
function handleFormSubmit(e) {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = '';
  submitObjective(text, 'text');
}

// ═══════════════════════════════════════════
// RESIZE
// ═══════════════════════════════════════════
function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  if (composer) composer.setSize(window.innerWidth, window.innerHeight);
}
