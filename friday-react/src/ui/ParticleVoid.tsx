import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { BufferGeometry, Float32BufferAttribute, AdditiveBlending, ShaderMaterial } from 'three';
import { useAIStore } from '../core/store';

// ── State mapping ──
const STATE_MAP: Record<string, number> = { idle: 0, listening: 1, thinking: 2, responding: 3, error: 4 };
const stateToInt = (s: string) => STATE_MAP[s] ?? 0;

const PARTICLE_COUNT = 15000;

// ── Main ParticleVoid ──
export function ParticleVoid() {
  const pointsRef = useRef<any>(null);
  const timeRef = useRef(0);

  const state = useAIStore((s) => s.state);
  const audioLevel = useAIStore((s) => s.audioLevel);

  const { geometry, material } = useMemo(() => {
    const count = PARTICLE_COUNT;
    const positions = new Float32Array(count * 3);
    const randoms = new Float32Array(count);
    const velocities = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const r = 4 + Math.random() * 16;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.cos(phi) * 0.5;
      const z = r * Math.sin(phi) * Math.sin(theta);

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      randoms[i] = Math.random();

      const speed = (0.5 + Math.random() * 1.5) * 0.01;
      velocities[i * 3] = -z / r * speed;
      velocities[i * 3 + 1] = 0;
      velocities[i * 3 + 2] = x / r * speed;
    }

    const geo = new BufferGeometry();
    geo.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geo.setAttribute('aRandom', new Float32BufferAttribute(randoms, 1));
    geo.setAttribute('aVelocity', new Float32BufferAttribute(velocities, 3));

    const mat = new ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uAudioLevel: { value: 0 },
        uEnergy: { value: 0 },
        uState: { value: 0 },
        uParticleSize: { value: 0.08 },
      },
      vertexShader: `
        precision highp float;
        uniform float uTime;
        uniform float uAudioLevel;
        uniform float uEnergy;
        uniform int uState;
        uniform float uParticleSize;
        attribute float aRandom;
        attribute vec3 aVelocity;
        varying vec3 vColor;
        varying float vAlpha;
        varying float vPlasmaTrail;

        float hash(vec3 p) {
          p = fract(p * 0.3183099 + 0.1);
          p *= 17.0;
          return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
        }

        float noise(vec3 p) {
          vec3 i = floor(p);
          vec3 f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(
            mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x),
                mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
            mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
                mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y),
            f.z
          );
        }

        void main() {
          float timeScale = 1.0;
          float orbitalSpeed = 0.5;
          float inwardPull = 0.0;
          float burstForce = 0.0;
          vec3 colorA = vec3(0.0, 0.83, 1.0);
          vec3 colorB = vec3(0.38, 0.19, 0.53);

          if(uState == 0) {
            timeScale = 0.3;
            orbitalSpeed = 0.3;
            inwardPull = 0.01;
          } else if(uState == 1) {
            timeScale = 0.5 + uAudioLevel * 2.0;
            orbitalSpeed = 0.5 + uAudioLevel * 1.5;
            inwardPull = 0.02 + uAudioLevel * 0.03;
            colorA = vec3(0.0, 1.0, 1.0);
            colorB = vec3(0.5, 0.0, 1.0);
          } else if(uState == 2) {
            timeScale = 2.0 + uEnergy * 4.0;
            orbitalSpeed = 2.0 + uEnergy * 3.0;
            inwardPull = 0.05 + uEnergy * 0.1;
            colorA = vec3(0.2, 0.4, 1.0);
            colorB = vec3(1.0, 0.1, 0.8);
          } else if(uState == 3) {
            timeScale = 1.0 + uAudioLevel * 3.0;
            orbitalSpeed = 1.0 + uAudioLevel * 2.0;
            burstForce = uAudioLevel * 0.3;
            inwardPull = -0.02;
            colorA = vec3(0.13, 1.0, 0.8);
            colorB = vec3(0.0, 1.0, 0.5);
          } else {
            timeScale = 6.0;
            orbitalSpeed = 3.0;
            colorA = vec3(1.0, 0.13, 0.27);
            colorB = vec3(1.0, 0.5, 0.0);
          }

          float t = uTime * timeScale + aRandom * 100.0;

          float radius = length(position);
          float angle = atan(position.z, position.x) + t * orbitalSpeed * (0.5 + aRandom * 0.5);
          float yAngle = atan(position.y, length(position.xz)) + t * orbitalSpeed * 0.3;

          float radiusNoise = noise(position * 2.0 + uTime * 0.5);
          float radiusMod = 1.0 + radiusNoise * 0.2;

          float newRadius = radius * radiusMod;
          if(inwardPull > 0.0) {
            newRadius = mix(newRadius, radius * 0.8, inwardPull);
          } else if(inwardPull < 0.0) {
            newRadius = mix(newRadius, radius * (1.0 + abs(inwardPull) + burstForce), 0.1);
          }

          vec3 newPos;
          newPos.x = newRadius * cos(angle);
          newPos.z = newRadius * sin(angle);
          newPos.y = radius * sin(yAngle) * (1.0 + sin(t * 0.7 + aRandom * 6.28) * 0.3);

          float wave = sin(t * 2.0 + radius * 5.0) * 0.05;
          newPos += normalize(position) * wave;

          float colorMix = noise(position * 3.0 + uTime * 0.3) * 0.5 + 0.5;
          vColor = mix(colorA, colorB, colorMix);
          float brightness = 0.6 + noise(position * 10.0 + uTime) * 0.4;
          vColor *= brightness;
          vColor *= 1.0 + uAudioLevel * 0.5;

          float distFromCenter = length(newPos);
          vAlpha = smoothstep(20.0, 2.0, distFromCenter) * 0.8;
          vAlpha *= 0.5 + aRandom * 0.5;
          vPlasmaTrail = abs(wave) * 10.0;

          vec4 mvPosition = modelViewMatrix * vec4(newPos, 1.0);
          float size = uParticleSize * (1.0 + uAudioLevel * 2.0 + uEnergy * 1.0);
          size *= (1.0 + sin(t * 3.0 + aRandom * 6.28) * 0.2);
          gl_PointSize = size * (300.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        precision highp float;
        uniform float uAudioLevel;
        uniform int uState;
        varying vec3 vColor;
        varying float vAlpha;
        varying float vPlasmaTrail;

        void main() {
          vec2 center = gl_PointCoord - vec2(0.5);
          float dist = length(center);
          float circle = 1.0 - smoothstep(0.0, 0.5, dist);
          float glow1 = 1.0 - smoothstep(0.0, 0.3, dist);
          float glow2 = 1.0 - smoothstep(0.0, 0.5, dist);
          float core = 1.0 - smoothstep(0.0, 0.15, dist);
          vec3 finalColor = vColor;
          finalColor += vec3(core) * 0.5;
          finalColor += vColor * vPlasmaTrail * 0.5;
          float alpha = circle * vAlpha;
          alpha *= 1.0 + uAudioLevel * 0.3;
          gl_FragColor = vec4(finalColor, alpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });

    return { geometry: geo, material: mat };
  }, []);

  useFrame((_, delta) => {
    timeRef.current += delta;
    if (!pointsRef.current) return;

    const mat = pointsRef.current.material as ShaderMaterial;
    const energy = state === 'thinking' ? 0.7 : state === 'listening' ? 0.4 : 0.2;

    if (mat.uniforms) {
      mat.uniforms.uTime.value = timeRef.current;
      mat.uniforms.uAudioLevel.value = audioLevel;
      mat.uniforms.uEnergy.value = energy;
      mat.uniforms.uState.value = stateToInt(state);
    }

    pointsRef.current.rotation.y += delta * 0.03;
    pointsRef.current.rotation.x += delta * 0.01;
  });

  return <points ref={pointsRef} geometry={geometry} material={material} />;
}
