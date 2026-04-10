uniform vec3 uColorA;
uniform vec3 uColorB;
uniform float uTime;
uniform float uState;
uniform float uEnergy;
varying float vLife;

// Simplex noise for fragment shader
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

float random(vec2 st) {
  return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

void main() {
  // Distance from center of point
  vec2 center = gl_PointCoord - vec2(0.5);
  float dist = length(center);

  // Discard outside circle
  if(dist > 0.5) discard;

  // === WOOTIAN GLOW ===
  // Soft inner core
  float core = exp(-dist * 12.0);

  // Medium glow
  float glow = exp(-dist * 5.0);

  // Outer halo
  float halo = exp(-dist * 2.5);

  // === STATE-BASED COLORS ===
  // Transform state index to behavior
  vec3 baseColor, secondaryColor;

  if(uState < 0.5) {
    // IDLE: Divine Gold to Arcane Purple
    baseColor = vec3(1.0, 0.84, 0.0); // Gold
    secondaryColor = vec3(0.61, 0.31, 0.87); // Arcane purple
  } else if(uState < 1.5) {
    // LISTENING: Ethereal Cyan to Silver
    baseColor = vec3(0.0, 1.0, 1.0); // Cyan
    secondaryColor = vec3(0.75, 0.75, 0.75); // Silver
  } else if(uState < 2.5) {
    // THINKING: Intense Orange to Crimson
    baseColor = vec3(1.0, 0.42, 0.0); // Orange
    secondaryColor = vec3(1.0, 0.0, 0.24); // Crimson
  } else if(uState < 3.5) {
    // RESPONDING: Divine Gold to Pure Light
    baseColor = vec3(1.0, 0.84, 0.0); // Gold
    secondaryColor = vec3(1.0, 1.0, 1.0); // White
  } else {
    // ERROR: Blood Red to Void
    baseColor = vec3(0.55, 0.0, 0.0); // Blood red
    secondaryColor = vec3(0.05, 0.0, 0.05); // Near black
  }

  // Mix colors based on position within particle
  vec3 color = mix(baseColor, secondaryColor, dist * 2.0);

  // Add energy crackle effect
  float crackle = snoise(vec3(gl_PointCoord * 10.0, uTime * 2.0));
  color += vec3(crackle * 0.1);

  // === MULTI-LAYER GLOW ===
  // Core brightness
  float coreBrightness = core * 1.5;

  // Outer glow intensity
  float glowIntensity = glow * 0.6;

  // Combine
  vec3 finalColor = color * (coreBrightness + glowIntensity);

  // Add chromatic aberration at edges
  float chromatic = sin(dist * 20.0 + uTime) * 0.05;
  finalColor.r += chromatic;
  finalColor.b -= chromatic;

  // === LIFE-BASED EFFECTS ===
  // Fade out older particles
  float alpha = (core * 0.8 + glow * 0.4) * vLife;

  // Boost brightness for fresh particles
  if(vLife > 0.8) {
    finalColor *= 1.0 + (vLife - 0.8) * 2.0;
  }

  // === DIVINE SPARKLE ===
  // Random twinkling for star-like effect
  float sparkle = step(0.995, random(gl_PointCoord + uTime * 0.1));
  finalColor += vec3(sparkle * 2.0);

  // Clamp final output
  finalColor = clamp(finalColor, 0.0, 1.0);

  gl_FragColor = vec4(finalColor, alpha);
}
