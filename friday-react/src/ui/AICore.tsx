import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Mesh, Float32BufferAttribute, AdditiveBlending, ShaderMaterial, BufferGeometry } from 'three';
import { useAIStore } from '../core/store';

// ── State to int helper ──
const STATE_MAP: Record<string, number> = { idle: 0, listening: 1, thinking: 2, responding: 3, error: 4 };
const stateToInt = (s: string) => STATE_MAP[s] ?? 0;

// ── Generate lightning tendril points ──
function generateTendrilPoints(count: number, radius: number, seed: number) {
  const positions = new Float32Array(count * 3);
  const randoms = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const t = i / count;
    const angle = seed * 2.39996 + t * 6.28 + Math.sin(t * 20 + seed * 10) * 0.3;
    const r = radius * (1 - t * 0.7) * (1 + (Math.random() - 0.5) * 0.4);

    positions[i * 3] = Math.cos(angle) * r + (Math.random() - 0.5) * 0.1;
    positions[i * 3 + 1] = t * 4 - 2;
    positions[i * 3 + 2] = Math.sin(angle) * r + (Math.random() - 0.5) * 0.1;
    randoms[i] = Math.random();
  }

  return { positions, randoms };
}

// ── Tendril Component ──
function Tendril({ seed, count = 60, radius = 1.2 }: { seed: number; count?: number; radius?: number }) {
  const pointsRef = useRef<any>(null);
  const materialRef = useRef<ShaderMaterial | null>(null);

  const { positions, randoms } = useMemo(
    () => generateTendrilPoints(count, radius, seed),
    [count, radius, seed]
  );

  const geometry = useMemo(() => {
    const geo = new (require('three').BufferGeometry)();
    geo.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geo.setAttribute('aRandom', new Float32BufferAttribute(randoms, 1));
    return geo;
  }, [positions, randoms]);

  const material = useMemo(() => {
    materialRef.current = new ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uAudioLevel: { value: 0 },
        uEnergy: { value: 0 },
        uState: { value: 0 },
      },
      vertexShader: `
        precision highp float;
        uniform float uTime;
        uniform float uAudioLevel;
        uniform float uEnergy;
        uniform int uState;
        attribute float aRandom;
        varying float vIntensity;

        float hash(float n) { return fract(sin(n) * 43758.5453123); }

        float lightning(vec2 p, float time, float seed) {
          float result = 0.0;
          float amplitude = 1.0;
          float frequency = 1.0;
          for(int i = 0; i < 5; i++) {
            float noiseVal = hash(floor(p.y * frequency) + seed * 100.0);
            float wave = sin(p.y * frequency * 3.14159 + time * (5.0 + seed * 10.0));
            float displacement = (noiseVal - 0.5) * amplitude * 0.3;
            float line = 1.0 - abs((p.x + displacement * wave) - 0.5) * 2.0;
            result = max(result, line * amplitude);
            amplitude *= 0.5;
            frequency *= 2.0;
          }
          return result;
        }

        void main() {
          float timeScale = 1.0;
          if(uState == 0) timeScale = 0.3;
          else if(uState == 1) timeScale = 0.8 + uAudioLevel * 1.5;
          else if(uState == 2) timeScale = 2.5 + uEnergy * 3.0;
          else if(uState == 3) timeScale = 1.5 + uAudioLevel * 2.0;
          else timeScale = 6.0;

          float t = uTime * timeScale;
          float intensity = lightning(position.xy * 0.5 + 0.5, t, aRandom);
          float flicker = 0.7 + hash(aRandom * 50.0 + floor(t * 10.0)) * 0.3;
          intensity *= 1.0 + uEnergy * 0.5 + uAudioLevel * 0.5;
          intensity *= flicker;
          vIntensity = intensity;

          gl_PointSize = 3.0 + intensity * 5.0;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        precision highp float;
        uniform float uAudioLevel;
        uniform int uState;
        varying float vIntensity;

        void main() {
          float dist = length(gl_PointCoord - vec2(0.5));
          float glow = 1.0 - smoothstep(0.0, 0.5, dist);

          vec3 colorA, colorB;
          if(uState == 0) { colorA = vec3(0.0, 0.83, 1.0); colorB = vec3(0.38, 0.19, 0.53); }
          else if(uState == 1) { colorA = vec3(0.0, 1.0, 1.0); colorB = vec3(0.5, 0.0, 1.0); }
          else if(uState == 2) { colorA = vec3(0.2, 0.4, 1.0); colorB = vec3(1.0, 0.1, 0.8); }
          else if(uState == 3) { colorA = vec3(0.13, 1.0, 0.8); colorB = vec3(0.0, 1.0, 0.5); }
          else { colorA = vec3(1.0, 0.13, 0.27); colorB = vec3(1.0, 0.5, 0.0); }

          vec3 color = mix(colorA, colorB, vIntensity);
          color += vec3(vIntensity) * 0.5;
          color *= vIntensity;

          float alpha = glow * vIntensity;
          alpha *= 0.7 + uAudioLevel * 0.3;

          gl_FragColor = vec4(color, alpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });
    return materialRef.current;
  }, []);

  return <points ref={pointsRef} geometry={geometry} material={material} />;
}

// ── Main AICore ──
export function AICore() {
  const coreRef = useRef<Mesh>(null);
  const rippleRef1 = useRef<Mesh>(null);
  const rippleRef2 = useRef<Mesh>(null);
  const timeRef = useRef(0);
  const errorPulseRef = useRef(0);

  const state = useAIStore((s) => s.state);
  const audioLevel = useAIStore((s) => s.audioLevel);
  const energy = state === 'thinking' ? 0.7 : state === 'listening' ? 0.4 : 0.2;

  const plasmaMaterial = useMemo(() => {
    return new ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uAudioLevel: { value: 0 },
        uEnergy: { value: 0 },
        uState: { value: 0 },
        uErrorPulse: { value: 0 },
      },
      vertexShader: `
        precision highp float;
        uniform float uTime;
        uniform float uAudioLevel;
        uniform float uEnergy;
        uniform int uState;
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec3 vWorldPosition;
        varying float vDisplacement;
        varying float vPlasmaIntensity;

        vec4 permute(vec4 x) { return mod(((x*34.0)+1.0)*x, 289.0); }
        vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

        float snoise(vec3 v) {
          const vec2 C = vec2(1.0/6.0, 1.0/3.0);
          const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
          vec3 i = floor(v + dot(v, C.yyy));
          vec3 x0 = v - i + dot(i, C.xxx);
          vec3 g = step(x0.yzx, x0.xyz);
          vec3 l = 1.0 - g;
          vec3 i1 = min(g.xyz, l.zxy);
          vec3 i2 = max(g.xyz, l.zxy);
          vec3 x1 = x0 - i1 + C.xxx;
          vec3 x2 = x0 - i2 + C.yyy;
          vec3 x3 = x0 - D.yyy;
          i = mod(i, 289.0);
          vec4 p = permute(permute(permute(
            i.z + vec4(0.0, i1.z, i2.z, 1.0))
            + i.y + vec4(0.0, i1.y, i2.y, 1.0))
            + i.x + vec4(0.0, i1.x, i2.x, 1.0));
          float n_ = 1.0/7.0;
          vec3 ns = n_ * D.wyz - D.xzx;
          vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
          vec4 x_ = floor(j * ns.z);
          vec4 y_ = floor(j - 7.0 * x_);
          vec4 x = x_ *ns.x + ns.yyyy;
          vec4 y = y_ *ns.x + ns.yyyy;
          vec4 h = 1.0 - abs(x) - abs(y);
          vec4 b0 = vec4(x.xy, y.xy);
          vec4 b1 = vec4(x.zw, y.zw);
          vec4 s0 = floor(b0)*2.0 + 1.0;
          vec4 s1 = floor(b1)*2.0 + 1.0;
          vec4 sh = -step(h, vec4(0.0));
          vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
          vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
          vec3 p0 = vec3(a0.xy, h.x);
          vec3 p1 = vec3(a0.zw, h.y);
          vec3 p2 = vec3(a1.xy, h.z);
          vec3 p3 = vec3(a1.zw, h.w);
          vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
          p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
          vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
          m = m * m;
          return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
        }

        float fbm(vec3 p, int octaves) {
          float value = 0.0;
          float amplitude = 0.5;
          float frequency = 1.0;
          for(int i = 0; i < 6; i++) {
            if(i >= octaves) break;
            value += amplitude * snoise(p * frequency);
            amplitude *= 0.5;
            frequency *= 2.0;
          }
          return value;
        }

        void main() {
          vUv = uv;
          vNormal = normalize(normalMatrix * normal);
          vPosition = position;

          float timeScale = 1.0;
          float displacementAmount = 0.0;

          if(uState == 0) {
            timeScale = 0.4;
            displacementAmount = 0.05;
          } else if(uState == 1) {
            timeScale = 0.8 + uAudioLevel * 2.0;
            displacementAmount = 0.08 + uAudioLevel * 0.15;
          } else if(uState == 2) {
            timeScale = 3.0 + uEnergy * 2.0;
            displacementAmount = 0.15 + uEnergy * 0.2;
          } else if(uState == 3) {
            timeScale = 1.5 + uAudioLevel * 3.0;
            displacementAmount = 0.1 + uAudioLevel * 0.25;
          } else {
            timeScale = 8.0;
            displacementAmount = 0.3;
          }

          float t = uTime * timeScale;
          float noise1 = fbm(position * 2.0 + t * 0.3, 4);
          float noise2 = snoise(position * 4.0 - t * 0.5) * 0.5;
          float noise3 = fbm(position * 8.0 + t * 0.7, 3);
          float displacement = (noise1 + noise2 + noise3) / 3.0;
          displacement *= displacementAmount;
          float audioPulse = sin(t * 10.0) * uAudioLevel * 0.05;
          float totalDisplacement = displacement + audioPulse;

          vDisplacement = totalDisplacement;
          vPlasmaIntensity = abs(displacement) / max(displacementAmount, 0.001);

          vec3 newPosition = position + normal * totalDisplacement;
          vWorldPosition = (modelMatrix * vec4(newPosition, 1.0)).xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
        }
      `,
      fragmentShader: `
        precision highp float;
        uniform float uTime;
        uniform float uAudioLevel;
        uniform float uEnergy;
        uniform int uState;
        uniform float uErrorPulse;
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec3 vWorldPosition;
        varying float vDisplacement;
        varying float vPlasmaIntensity;

        const vec3 COLOR_IDLE_A = vec3(0.0, 0.83, 1.0);
        const vec3 COLOR_IDLE_B = vec3(0.38, 0.19, 0.53);
        const vec3 COLOR_LISTEN_A = vec3(0.0, 1.0, 1.0);
        const vec3 COLOR_LISTEN_B = vec3(0.5, 0.0, 1.0);
        const vec3 COLOR_THINK_A = vec3(0.2, 0.4, 1.0);
        const vec3 COLOR_THINK_B = vec3(1.0, 0.1, 0.8);
        const vec3 COLOR_RESPOND_A = vec3(0.13, 1.0, 0.8);
        const vec3 COLOR_RESPOND_B = vec3(0.0, 1.0, 0.5);
        const vec3 COLOR_ERROR_A = vec3(1.0, 0.13, 0.27);
        const vec3 COLOR_ERROR_B = vec3(1.0, 0.5, 0.0);

        vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
        vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
        vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

        float snoise(vec2 v) {
          const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
          vec2 i = floor(v + dot(v, C.yy));
          vec2 x0 = v - i + dot(i, C.xx);
          vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
          vec4 x12 = x0.xyxy + C.xxzz;
          x12.xy -= i1;
          i = mod289(i);
          vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
          vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
          m = m*m; m = m*m;
          vec3 x = 2.0 * fract(p * C.www) - 1.0;
          vec3 h = abs(x) - 0.5;
          vec3 ox = floor(x + 0.5);
          vec3 a0 = x - ox;
          m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
          vec3 g;
          g.x = a0.x * x0.x + h.x * x0.y;
          g.yz = a0.yz * x12.xz + h.yz * x12.yw;
          return 130.0 * dot(m, g);
        }

        float fbm(vec2 p) {
          float f = 0.0;
          f += 0.5000 * snoise(p); p *= 2.02;
          f += 0.2500 * snoise(p); p *= 2.03;
          f += 0.1250 * snoise(p); p *= 2.01;
          f += 0.0625 * snoise(p);
          return f;
        }

        void main() {
          vec3 viewDir = normalize(cameraPosition - vWorldPosition);
          float fresnel = pow(1.0 - max(0.0, dot(vNormal, viewDir)), 3.0);

          vec3 colorA, colorB;
          float glowIntensity = 0.5;

          if(uState == 0) {
            colorA = COLOR_IDLE_A; colorB = COLOR_IDLE_B; glowIntensity = 0.4;
          } else if(uState == 1) {
            colorA = COLOR_LISTEN_A; colorB = COLOR_LISTEN_B; glowIntensity = 0.6 + uAudioLevel * 0.4;
          } else if(uState == 2) {
            colorA = COLOR_THINK_A; colorB = COLOR_THINK_B; glowIntensity = 0.7 + uEnergy * 0.5;
          } else if(uState == 3) {
            colorA = COLOR_RESPOND_A; colorB = COLOR_RESPOND_B; glowIntensity = 0.8 + uAudioLevel * 0.5;
          } else {
            colorA = COLOR_ERROR_A; colorB = COLOR_ERROR_B; glowIntensity = 0.9 + uErrorPulse;
          }

          float timeScale = 1.0;
          if(uState == 0) timeScale = 0.4;
          else if(uState == 1) timeScale = 0.8 + uAudioLevel * 2.0;
          else if(uState == 2) timeScale = 2.5 + uEnergy * 3.0;
          else if(uState == 3) timeScale = 1.5 + uAudioLevel * 3.0;
          else timeScale = 8.0;

          vec2 plasmaCoord = vPosition.xy * 3.0 + uTime * timeScale;
          float plasma1 = fbm(plasmaCoord);
          float plasma2 = fbm(plasmaCoord * 1.5 - uTime * timeScale * 0.5 + vPlasmaIntensity * 2.0);
          float plasma = (plasma1 + plasma2) * 0.5;
          plasma = plasma * 0.5 + 0.5;

          vec3 plasmaColor = mix(colorA, colorB, plasma);
          vec3 fresnelColor = mix(colorA, colorB, fresnel);
          plasmaColor = mix(plasmaColor, fresnelColor, fresnel * 0.7);

          float hotspot = pow(vPlasmaIntensity, 2.0) * glowIntensity;
          plasmaColor += vec3(hotspot) * 1.5;

          float audioGlow = uAudioLevel * 0.3;
          plasmaColor += colorA * audioGlow;

          float energyBoost = 1.0 + uEnergy * 0.5;
          plasmaColor *= energyBoost;

          float chromaOffset = fresnel * 0.02;
          plasmaColor.r *= 1.0 + chromaOffset;
          plasmaColor.b *= 1.0 - chromaOffset;

          float alpha = 0.6 + fresnel * 0.4 + hotspot * 0.3;
          alpha = clamp(alpha, 0.0, 1.0);

          gl_FragColor = vec4(plasmaColor, alpha);
        }
      `,
      transparent: true,
      side: 2,
    });
  }, []);

  useFrame((_, delta) => {
    timeRef.current += delta;

    if (coreRef.current) {
      const mat = coreRef.current.material as ShaderMaterial;
      if (mat.uniforms) {
        mat.uniforms.uTime.value = timeRef.current;
        mat.uniforms.uAudioLevel.value = audioLevel;
        mat.uniforms.uEnergy.value = energy;
        mat.uniforms.uState.value = stateToInt(state);
        mat.uniforms.uErrorPulse.value = errorPulseRef.current;
      }

      let targetScale = 1;
      if (state === 'idle') {
        targetScale = 1 + Math.sin(timeRef.current * 1.5) * 0.05;
      } else if (state === 'listening') {
        targetScale = 1 + audioLevel * 1.2;
      } else if (state === 'thinking') {
        targetScale = 0.85 + Math.sin(timeRef.current * 8) * 0.02;
      } else if (state === 'responding') {
        targetScale = 1.0 + audioLevel * 1.8;
      }

      coreRef.current.scale.lerp(
        { x: targetScale, y: targetScale, z: targetScale } as any,
        0.15
      );
    }

    [rippleRef1, rippleRef2].forEach((ref, i) => {
      if (!ref.current) return;
      if (state === 'listening') {
        const speed = 1.5 + i * 0.5;
        const currentScale = (ref.current.scale as any).x + delta * speed;
        ref.current.scale.setScalar(currentScale > 4 ? 1 : currentScale);
        (ref.current.material as any).opacity = Math.max(0, 0.4 - ((ref.current.scale as any).x - 1) / 3);
      } else {
        ref.current.scale.setScalar(1);
        (ref.current.material as any).opacity = 0;
      }
    });

    errorPulseRef.current = state === 'error'
      ? Math.abs(Math.sin(timeRef.current * 8)) * 0.5 + 0.5
      : 0;
  });

  return (
    <group>
      {/* Ripple rings */}
      <mesh ref={rippleRef1} visible={state === 'listening'}>
        <sphereGeometry args={[1.15, 32, 32]} />
        <meshBasicMaterial color="#00ffff" transparent opacity={0} wireframe />
      </mesh>
      <mesh ref={rippleRef2} visible={state === 'listening'}>
        <sphereGeometry args={[1.15, 32, 32]} />
        <meshBasicMaterial color="#00ffff" transparent opacity={0} wireframe />
      </mesh>

      {/* Lightning tendrils */}
      <Tendril seed={1.618} count={80} radius={1.2} />
      <Tendril seed={2.718} count={60} radius={1.0} />
      <Tendril seed={3.141} count={50} radius={0.8} />

      {/* Main plasma core */}
      <mesh ref={coreRef} material={plasmaMaterial}>
        <sphereGeometry args={[1, 128, 128]} />
      </mesh>
    </group>
  );
}
