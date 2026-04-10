uniform float uTime;
uniform float uDelta;
uniform float uAudio;
uniform float uState;
uniform float uEnergy;

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

vec3 curlNoise(vec3 p) {
  const float e = 0.1;
  return vec3(
    snoise(p + vec3(0, 0, e)) - snoise(p - vec3(0, 0, e)) - snoise(p + vec3(0, e, 0)) + snoise(p - vec3(0, e, 0)),
    snoise(p + vec3(e, 0, 0)) - snoise(p - vec3(e, 0, 0)) - snoise(p + vec3(0, 0, e)) + snoise(p - vec3(0, 0, e)),
    snoise(p + vec3(0, e, 0)) - snoise(p - vec3(0, e, 0)) - snoise(p + vec3(e, 0, 0)) + snoise(p - vec3(e, 0, 0))
  ) / (2.0 * e);
}

void main() {
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec4 data = texture2D(uCurrentPos, uv);
  vec3 pos = data.rgb;
  float life = data.a;

  float dist = length(pos);
  vec3 dir = normalize(pos + vec3(0.001));
  float angle = atan(pos.z, pos.x);
  float elevation = atan(pos.y, length(pos.xz));

  // Particle identity (consistent per-particle random)
  float id = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453);
  float id2 = fract(sin(dot(uv, vec2(93.989, 67.345))) * 23456.78);

  // =============================================
  // IDLE: Solar Prominences
  // Slow, majestic ribbon-like plasma arcs that
  // loop up from the surface and fall back down.
  // Like the surface of the sun.
  // =============================================
  if(uState < 0.5) {
    float targetR = 3.0 + sin(uTime * 0.3) * 0.3;
    pos += dir * (targetR - dist) * 0.01;

    // Solar prominence: particles arc upward along field lines
    float prominencePhase = sin(angle * 2.0 + uTime * 0.15 + id * 6.28) * 0.5 + 0.5;
    float arcHeight = prominencePhase * 1.5 * smoothstep(2.5, 4.0, dist);
    pos.y += arcHeight * 0.008;

    // Slow ribbons flowing along the surface
    vec3 ribbon = curlNoise(pos * 0.08 + uTime * 0.015) * 0.4;
    pos += ribbon * 0.025;

    // Gentle equatorial drift
    float driftAngle = 0.0015;
    mat2 rot = mat2(cos(driftAngle), -sin(driftAngle), sin(driftAngle), cos(driftAngle));
    pos.xz = rot * pos.xz;

    // Magnetic field lines: particles follow toroidal paths
    vec3 toroid = vec3(-pos.y, pos.x * 0.5, 0.0) * 0.006;
    pos += toroid;
  }

  // =============================================
  // LISTENING: Sonar Pulse Rings
  // Concentric rings pulse inward toward center
  // like a radar/sonar ping. Particles compress
  // into thin bands then release.
  // =============================================
  else if(uState < 1.5) {
    float targetR = 3.2;
    pos += dir * (targetR - dist) * 0.012;

    // Sonar ring: particles form concentric shells that pulse inward
    float pingSpeed = 2.5;
    float pingWavelength = 2.0;
    float ping = sin(uTime * pingSpeed - dist * pingWavelength);
    float band = smoothstep(0.7, 1.0, ping); // sharp bands

    // Pull particles into ring bands
    float ringTarget = floor(dist / 1.2) * 1.2 + 0.6;
    pos += dir * (ringTarget - dist) * band * 0.04;

    // Flatten rings slightly
    pos.y *= 0.995 + band * 0.005;

    // Gentle inward spiral
    float spiralAngle = 0.004 + band * 0.008;
    mat2 rot = mat2(cos(spiralAngle), -sin(spiralAngle), sin(spiralAngle), cos(spiralAngle));
    pos.xz = rot * pos.xz;

    // Subtle surface flow
    vec3 flow = curlNoise(pos * 0.12 + uTime * 0.04) * 0.15;
    pos += flow * 0.03;

    // Audio-driven pulse intensity
    float audioPing = sin(uTime * 6.0 - dist * 3.0) * uAudio * 0.05;
    pos += dir * audioPing;
  }

  // =============================================
  // THINKING: Electromagnetic Tornado
  // Particles race in tight helical bands around
  // Y axis. Core compresses into a dense column.
  // High-frequency crackling plasma storm.
  // =============================================
  else if(uState < 2.5) {
    // Compress into elongated column
    float columnRadius = 2.0 + sin(uTime * 1.5) * 0.3;
    float xzDist = length(pos.xz);
    pos.xz *= mix(1.0, columnRadius / (xzDist + 0.1), 0.03);

    // Stretch vertically
    pos.y *= 1.003;
    // But contain height
    if(abs(pos.y) > 4.0) pos.y *= 0.98;

    // Intense helical orbit
    float helixSpeed = 0.025 + id * 0.01;
    float helixTilt = sin(pos.y * 0.5 + uTime * 0.5) * 0.003;
    mat2 rot = mat2(cos(helixSpeed), -sin(helixSpeed), sin(helixSpeed), cos(helixSpeed));
    pos.xz = rot * pos.xz;

    // Helical wave along Y axis
    float helix = sin(pos.y * 3.0 + uTime * 4.0 + angle * 2.0) * 0.04;
    pos.x += helix;
    pos.z += cos(pos.y * 3.0 + uTime * 4.0 + angle * 2.0) * 0.04;

    // Electric storm turbulence
    vec3 storm = curlNoise(pos * 0.5 + uTime * 0.15) * 0.2;
    storm += curlNoise(pos * 1.2 + uTime * 0.08) * 0.08;
    pos += storm * 0.06;

    // Crackling: random sharp displacement
    float crackle = step(0.92, snoise(pos * 2.0 + uTime * 3.0));
    pos += dir * crackle * 0.15;
  }

  // =============================================
  // RESPONDING: Plasma Jets / Solar Wind
  // Particles stream outward in focused beams from
  // the poles, creating bi-directional plasma jets.
  // Equatorial ring expands with voice waves.
  // =============================================
  else if(uState < 3.5) {
    float targetR = 3.5 + sin(uTime * 2.0) * 0.4;
    pos += dir * (targetR - dist) * 0.01;

    // Polar jet streams: particles near poles shoot outward
    float polarity = smoothstep(0.3, 1.2, abs(elevation)); // 1 near poles
    float jetForce = polarity * 0.06;
    float jetDir = sign(pos.y); // up or down
    pos.y += jetDir * jetForce;

    // Equatorial expansion waves (voice ripples)
    float wave = sin(uTime * 5.0 - dist * 2.0) * 0.04;
    float equatorial = 1.0 - polarity;
    pos += dir * wave * equatorial;

    // Harmonic interference pattern
    float wave2 = sin(uTime * 8.0 - dist * 1.5 + 2.0) * 0.02;
    pos += dir * wave2 * equatorial;

    // Flowing tendrils
    vec3 flow = curlNoise(pos * 0.15 + uTime * 0.06) * 0.3;
    pos += flow * 0.04;

    // Moderate orbit
    float orbitAngle = 0.005;
    mat2 rot = mat2(cos(orbitAngle), -sin(orbitAngle), sin(orbitAngle), cos(orbitAngle));
    pos.xz = rot * pos.xz;

    // Audio modulates jet intensity
    pos.y += sign(pos.y) * uAudio * polarity * 0.08;
  }

  // =============================================
  // ERROR: Magnetic Reconnection Event
  // Core tears apart, particles scatter along
  // broken field lines, random sharp dislocations.
  // =============================================
  else {
    float targetR = 3.0 + sin(uTime * 8.0) * 1.0;
    pos += dir * (targetR - dist) * 0.015;

    // Broken field lines: sudden displacement
    float tearGate = step(0.8, sin(uTime * 25.0) * 0.5 + 0.5);
    vec3 tear = curlNoise(pos * 3.0 + uTime * 2.0) * 0.4;
    pos += tear * tearGate * 0.12;

    // Chaotic orbit reversal
    float flipDir = sign(sin(uTime * 12.0));
    float orbitAngle = 0.01 * flipDir;
    mat2 rot = mat2(cos(orbitAngle), -sin(orbitAngle), sin(orbitAngle), cos(orbitAngle));
    pos.xz = rot * pos.xz;
  }

  // === GLOBAL: Audio reactivity ===
  float audioWave = sin(uTime * 8.0 - dist * 3.0) * uAudio * 0.03;
  pos += dir * audioWave;

  // === Anti-blob ===
  if(dist < 0.8) {
    pos += dir * 0.06 * (0.8 - dist);
  }

  // === Containment ===
  float newDist = length(pos);
  if(newDist > 10.0) pos *= 10.0 / newDist;

  // Life
  life -= 0.0005 + (1.0 - uEnergy) * 0.0006;

  // Respawn
  if(life <= 0.0 || newDist > 14.0) {
    float sa = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453 + uTime * 0.15) * 6.28318;
    float sr = 1.5 + id2 * 4.0;
    float sh = (id - 0.5) * 3.0;
    pos = vec3(cos(sa) * sr, sh, sin(sa) * sr);
    life = 0.5 + id2 * 0.5;
  }

  gl_FragColor = vec4(pos, life);
}
