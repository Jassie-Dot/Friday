// Ethereal Wisps - Orbiting golden spirit particles
import * as THREE from 'three';

const WISP_COUNT = 800;

export class WispsSystem {
  constructor(scene, state = { mode: 'idle', energy: 0.15 }) {
    this.scene = scene;
    this.state = state;
    this.wisps = null;
    this.wispGeometry = null;
    this.wispMaterial = null;
    this.time = 0;
    this.positions = new Float32Array(WISP_COUNT * 3);
    this.velocities = new Float32Array(WISP_COUNT * 3);
    this.phases = new Float32Array(WISP_COUNT);
    this.sizes = new Float32Array(WISP_COUNT);

    this.init();
  }

  init() {
    // Initialize wisp positions in elliptical orbits
    for (let i = 0; i < WISP_COUNT; i++) {
      const radius = 3 + Math.random() * 6;
      const angle = Math.random() * Math.PI * 2;
      const height = (Math.random() - 0.5) * 4;

      // Elliptical orbit
      const ellipseX = radius * (0.8 + Math.random() * 0.4);
      const ellipseZ = radius * (0.6 + Math.random() * 0.6);

      this.positions[i * 3 + 0] = Math.cos(angle) * ellipseX;
      this.positions[i * 3 + 1] = height;
      this.positions[i * 3 + 2] = Math.sin(angle) * ellipseZ;

      // Random velocities
      this.velocities[i * 3 + 0] = (Math.random() - 0.5) * 0.02;
      this.velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.01;
      this.velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.02;

      // Phase offset for orbit
      this.phases[i] = Math.random() * Math.PI * 2;

      // Random sizes
      this.sizes[i] = 0.5 + Math.random() * 1.5;
    }

    // Geometry
    this.wispGeometry = new THREE.BufferGeometry();
    this.wispGeometry.setAttribute('position', new THREE.BufferAttribute(this.positions, 3));
    this.wispGeometry.setAttribute('size', new THREE.BufferAttribute(this.sizes, 1));
    this.wispGeometry.setAttribute('phase', new THREE.BufferAttribute(this.phases, 1));

    // Shader material for wisps
    this.wispMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uState: { value: 0 },
        uColor: { value: new THREE.Color(0xFFD700) },
        uColorSecondary: { value: new THREE.Color(0xFF6B00) }
      },
      vertexShader: `
        attribute float size;
        attribute float phase;
        uniform float uTime;
        uniform float uState;
        varying float vAlpha;
        varying float vPhase;

        void main() {
          vPhase = phase;
          vec3 pos = position;

          // Elliptical orbit motion
          float angle = phase + uTime * 0.3;
          float radius = length(pos.xz);
          float speedMod = 1.0 + uState * 0.5;

          pos.x = cos(angle * speedMod) * radius;
          pos.z = sin(angle * speedMod) * radius;

          // Vertical bobbing
          pos.y += sin(uTime * 2.0 + phase) * 0.2;

          // State-based effects
          if(uState > 2.5) {
            // Responding - explosive scatter
            pos += normalize(pos) * sin(uTime * 10.0) * 0.5;
          }

          vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
          gl_PointSize = size * (200.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;

          // Fade based on distance
          vAlpha = smoothstep(15.0, 3.0, length(mvPosition.xyz));
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform vec3 uColorSecondary;
        uniform float uTime;
        varying float vAlpha;
        varying float vPhase;

        void main() {
          vec2 center = gl_PointCoord - vec2(0.5);
          float dist = length(center);

          if(dist > 0.5) discard;

          // Soft glowing wisp
          float core = exp(-dist * 15.0);
          float glow = exp(-dist * 5.0);

          // Color shift based on phase
          float colorMix = sin(vPhase + uTime) * 0.5 + 0.5;
          vec3 color = mix(uColor, uColorSecondary, colorMix * 0.3);

          // Sparkle effect
          float sparkle = step(0.98, fract(sin(dot(gl_PointCoord, vec2(12.9898, 78.233)) + uTime) * 43758.5453));
          color += vec3(sparkle * 0.5);

          float alpha = (core * 0.8 + glow * 0.3) * vAlpha;
          alpha *= 0.7;

          gl_FragColor = vec4(color, alpha);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    this.wisps = new THREE.Points(this.wispGeometry, this.wispMaterial);
    this.scene.add(this.wisps);
  }

  update(state, deltaTime) {
    this.state = state;
    this.time += deltaTime;

    // Update uniforms
    this.wispMaterial.uniforms.uTime.value = this.time;
    this.wispMaterial.uniforms.uState.value = this.getStateIndex(state.mode);

    // Update colors based on state
    const colors = this.getStateColors(state.mode);
    this.wispMaterial.uniforms.uColor.value = colors.primary;
    this.wispMaterial.uniforms.uColorSecondary.value = colors.secondary;
  }

  getStateIndex(mode) {
    const map = { idle: 0, listening: 1, thinking: 2, responding: 3, error: 4 };
    return map[mode] ?? 0;
  }

  getStateColors(mode) {
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

  dispose() {
    if(this.wisps) {
      this.scene.remove(this.wisps);
      this.wispGeometry.dispose();
      this.wispMaterial.dispose();
    }
  }
}
