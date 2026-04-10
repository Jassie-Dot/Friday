uniform float uTime;
uniform float uDelta;
uniform float uAudio;
uniform float uState;
uniform float uEnergy;

// Simplex 3D Noise
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
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
  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
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

// Curl noise for organic flow
vec3 curlNoise(vec3 p) {
  const float e = 0.1;
  float x0 = snoise(p - vec3(e, 0, 0));
  float x1 = snoise(p + vec3(e, 0, 0));
  float y0 = snoise(p - vec3(0, e, 0));
  float y1 = snoise(p + vec3(0, e, 0));
  float z0 = snoise(p - vec3(0, 0, e));
  float z1 = snoise(p + vec3(0, 0, e));
  return vec3(
    (z1 - z0) - (y1 - y0),
    (x1 - x0) - (z1 - z0),
    (y1 - y0) - (x1 - x0)
  ) / (2.0 * e);
}

// Fractal Brownian Motion
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
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec4 data = texture2D(uCurrentPos, uv);
  vec3 pos = data.rgb;
  float life = data.a;

  // State-based behavior modifiers
  float stateTime = uTime * (uState > 1.5 && uState < 2.5 ? 2.5 : 1.0); // Thinking spins faster
  float burstMultiplier = uState > 2.5 && uState < 3.5 ? 1.8 : 1.0; // Responding bursts

  // === GOLDEN VORTEX CORE ===
  // Calculate distance and angle from center
  float dist = length(pos);
  float angle = atan(pos.z, pos.x);
  float heightFactor = pos.y * 0.15;

  // Spiral galaxy rotation
  float spiralAngle = angle + stateTime * 0.08 * (uEnergy + 0.3);
  float spiralRadius = dist * (1.0 + sin(stateTime * 0.3 + dist) * 0.1);

  // Create the main vortex position
  vec3 vortex = vec3(
    cos(spiralAngle) * spiralRadius,
    heightFactor + sin(stateTime * 0.5 + dist * 0.5) * 0.3,
    sin(spiralAngle) * spiralRadius
  );

  // === ORGANIC FLOW ===
  // Multi-octave curl noise for that WoW magical feel
  vec3 flow = curlNoise(pos * 0.15 + stateTime * 0.02) * 0.6;
  flow += curlNoise(pos * 0.4 - stateTime * 0.05) * 0.25;
  flow += curlNoise(pos * 0.8 + vec3(stateTime * 0.03)) * 0.1;

  // FBM turbulence
  float turb = fbm(pos * 0.2 + stateTime * 0.01, 4) * 0.4;

  // === STATE-BASED BEHAVIORS ===
  // Idle: Gentle breathing golden glow
  // Listening: Energy converges to center, cyan pulses
  // Thinking: Intense vortex spin, orange sparks
  // Responding: Explosive golden burst, divine rays
  // Error: Fragmenting red, chaotic

  vec3 flowDir = normalize(pos);
  float centerPull = 0.0;
  float explosiveForce = 0.0;

  if(uState < 0.5) {
    // IDLE: Soft golden breathing
    centerPull = 0.01 * (1.0 + sin(uTime * 0.8) * 0.5);
  } else if(uState < 1.5) {
    // LISTENING: Converging to center
    centerPull = 0.03 + sin(uTime * 3.0) * 0.02;
  } else if(uState < 2.5) {
    // THINKING: Intense spinning
    centerPull = 0.02;
  } else if(uState < 3.5) {
    // RESPONDING: Explosive burst
    centerPull = -0.02 * burstMultiplier; // Push outward!
    explosiveForce = 0.15 * burstMultiplier;
  } else {
    // ERROR: Chaotic fragmentation
    centerPull = 0.01;
    flow += curlNoise(pos * 2.0 + uTime * 0.5) * 0.8;
  }

  // Apply center pull/push
  vortex += flowDir * centerPull;

  // Apply explosive force
  vortex += flowDir * explosiveForce;

  // Mix with original position for organic feel
  pos = mix(pos, vortex, 0.4 + uEnergy * 0.3);

  // Apply flow and turbulence
  pos += flow * (0.02 + uEnergy * 0.03);

  // Anti-blob: Strong repulsion from center
  if(dist < 1.2) {
    pos += flowDir * 0.08 * (1.2 - dist);
  }

  // Gentle orbit rotation
  float orbitAngle = 0.003 + uAudio * 0.008;
  mat2 rot = mat2(cos(orbitAngle), -sin(orbitAngle), sin(orbitAngle), cos(orbitAngle));
  pos.xz = rot * pos.xz;

  // Update life
  life -= 0.001 + (1.0 - uEnergy) * 0.0015;

  // Respawn particles
  if(life <= 0.0 || dist > 14.0) {
    // Spawn in dramatic spiral pattern
    float spawnAngle = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453 + uTime * 0.1) * 6.28318;
    float spawnRadius = 6.0 + fract(sin(dot(uv, vec2(93.989, 67.345))) * 23456.78) * 4.0;
    float spawnHeight = (fract(sin(dot(uv, vec2(45.233, 89.123))) * 34567.89) - 0.5) * 4.0;

    pos = vec3(
      cos(spawnAngle) * spawnRadius,
      spawnHeight,
      sin(spawnAngle) * spawnRadius
    );
    life = 0.7 + fract(sin(dot(uv, vec2(123.456, 789.012))) * 45678.9) * 0.3;
  }

  gl_FragColor = vec4(pos, life);
}
