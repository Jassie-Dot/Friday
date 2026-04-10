uniform vec3 uColorA;
uniform vec3 uColorB;
uniform float uTime;
uniform float uState;
uniform float uEnergy;
uniform float uAudio;
varying float vLife;
varying float vDist;

float random(vec2 st) {
  return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

vec3 mod289v3(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289v4(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permutef(vec4 x) { return mod289v4(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrtf(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

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
  i = mod289v3(i);
  vec4 p = permutef(permutef(permutef(
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
  vec4 norm = taylorInvSqrtf(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

void main() {
  vec2 center = gl_PointCoord - vec2(0.5);
  float dist = length(center);
  if(dist > 0.5) discard;

  // === GLOW LAYERS ===
  float core = exp(-dist * 16.0);
  float envelope = exp(-dist * 7.0);
  float corona = exp(-dist * 3.0);
  float outerHaze = exp(-dist * 1.5);

  // === STATE-SPECIFIC COLORS ===
  vec3 hotColor = uColorA;
  vec3 coolColor = uColorB;
  float brightnessMultiplier = 1.0;

  if(uState < 0.5) {
    // IDLE: calm cyan + purple
    brightnessMultiplier = 0.8;
  } else if(uState < 1.5) {
    // LISTENING: brighter, warmer pulse
    float beat = pow(sin(uTime * 3.5) * 0.5 + 0.5, 6.0);
    brightnessMultiplier = 0.9 + beat * 0.6;
    hotColor = mix(uColorA, vec3(0.6, 0.9, 1.0), beat * 0.3);
  } else if(uState < 2.5) {
    // THINKING: electric blue, high energy crackling
    hotColor = mix(uColorA, vec3(0.3, 0.5, 1.0), 0.4);
    coolColor = mix(uColorB, vec3(0.1, 0.2, 0.8), 0.3);
    brightnessMultiplier = 1.2;
  } else if(uState < 3.5) {
    // RESPONDING: bright cyan-green, radiant outward
    hotColor = mix(uColorA, vec3(0.2, 1.0, 0.8), 0.3);
    brightnessMultiplier = 1.0 + sin(uTime * 4.0) * 0.15;
  } else {
    // ERROR: red-shifted
    hotColor = vec3(1.0, 0.1, 0.2);
    coolColor = vec3(0.5, 0.0, 0.3);
    float flicker = sin(uTime * 15.0) * 0.5 + 0.5;
    brightnessMultiplier = 0.5 + flicker * 0.5;
  }

  // Depth gradient
  float depthFade = smoothstep(0.0, 0.45, dist);
  vec3 color = mix(hotColor, coolColor, depthFade);

  // === PLASMA TEXTURE ===
  float plasma = snoise(vec3(gl_PointCoord * 10.0, uTime * 1.5)) * 0.5 + 0.5;
  float swirl = snoise(vec3(gl_PointCoord * 8.0 - vec2(uTime * 0.8), uTime * 0.5));
  float hotSpot = pow(plasma, 3.0) * 0.3 * brightnessMultiplier;
  color += hotColor * hotSpot * core;

  // Energy crackle (stronger during thinking)
  float crackleScale = uState > 1.5 && uState < 2.5 ? 20.0 : 15.0;
  float crackleSpeed = uState > 1.5 && uState < 2.5 ? 5.0 : 3.0;
  float crackle = snoise(vec3(gl_PointCoord * crackleScale, uTime * crackleSpeed));
  float crackleIntensity = smoothstep(0.4, 0.9, abs(crackle)) * 0.12;
  color += hotColor * crackleIntensity;

  // === ELECTRIC ARC LINES (thinking state) ===
  if(uState > 1.5 && uState < 2.5) {
    float arc = abs(sin(gl_PointCoord.x * 30.0 + uTime * 8.0 + gl_PointCoord.y * 20.0));
    arc = pow(arc, 12.0) * 0.4;
    color += vec3(0.5, 0.7, 1.0) * arc * core;
  }

  // === COMPOSITE ===
  float coreBright = core * 0.5 * brightnessMultiplier;
  float envBright = envelope * 0.25 * brightnessMultiplier;
  float coroBright = corona * 0.1;
  float hazeBright = outerHaze * 0.03;

  vec3 finalColor = color * (coreBright + envBright + coroBright + hazeBright);

  // Chromatic dispersion
  float chromatic = sin(dist * 30.0 + uTime * 3.0) * 0.02;
  finalColor.r += chromatic * 0.8;
  finalColor.b -= chromatic;

  // === LIFE EFFECTS ===
  float alpha = (core * 0.7 + envelope * 0.3 + corona * 0.15) * (vLife * 0.6);

  if(vLife > 0.8) {
    float fresh = (vLife - 0.8) * 2.0;
    finalColor += hotColor * fresh * 0.2;
    alpha *= 1.0 + fresh * 0.3;
  }
  if(vLife < 0.25) {
    float dying = (0.25 - vLife) / 0.25;
    finalColor = mix(finalColor, coolColor * 0.2, dying * 0.5);
  }

  // Sparkle
  float sparkle = step(0.993, random(gl_PointCoord + uTime * 0.03));
  finalColor += vec3(sparkle * 0.3) * hotColor;

  // Depth fog
  float fog = smoothstep(4.0, 15.0, vDist);
  finalColor = mix(finalColor, coolColor * 0.03, fog * 0.4);

  finalColor = clamp(finalColor, 0.0, 0.85);
  gl_FragColor = vec4(finalColor, alpha);
}
