// Nebula Background Shader - Procedural cosmic background
uniform float uTime;
uniform vec2 uResolution;
uniform vec2 uMouse;

varying vec2 vUv;

// Hash function for randomness
float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

// Smooth noise
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);

  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));

  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// Fractal Brownian Motion for nebula clouds
float fbm(vec2 p, int octaves) {
  float value = 0.0;
  float amplitude = 0.5;
  float frequency = 1.0;

  for(int i = 0; i < 7; i++) {
    if(i >= octaves) break;
    value += amplitude * noise(p * frequency);
    amplitude *= 0.5;
    frequency *= 2.0;
  }
  return value;
}

// Star field
float stars(vec2 uv, float density) {
  vec2 grid = uv * density;
  vec2 id = floor(grid);
  vec2 gv = fract(grid) - 0.5;

  float star = 0.0;
  float rnd = hash(id);

  if(rnd > 0.97) {
    vec2 starPos = vec2(hash(id * 1.1), hash(id * 2.3)) - 0.5;
    float d = length(gv - starPos * 0.8);
    float twinkle = sin(uTime * (2.0 + rnd * 3.0) + rnd * 6.28) * 0.5 + 0.5;
    star = smoothstep(0.05, 0.0, d) * (0.5 + twinkle * 0.5);
  }

  return star;
}

void main() {
  vUv = gl_FragCoord.xy / uResolution;

  // Mouse parallax
  vec2 mouseOffset = (uMouse - 0.5) * 0.02;
  vec2 uv = vUv + mouseOffset;

  // Center point for radial effects
  vec2 center = uv - 0.5;
  float dist = length(center);

  // === NEBULA LAYERS ===

  // Deep space base color
  vec3 spaceColor = vec3(0.01, 0.01, 0.03);

  // Inner golden glow (from center)
  float innerGlow = exp(-dist * 2.5);
  vec3 goldGlow = vec3(1.0, 0.7, 0.2) * innerGlow * 0.4;

  // Outer purple nebula
  vec2 nebulaUv = uv * 1.5 + vec2(uTime * 0.01);
  float nebula1 = fbm(nebulaUv + fbm(nebulaUv * 2.0, 4) * 0.5, 5);
  vec3 purpleNebula = vec3(0.2, 0.05, 0.3) * nebula1 * smoothstep(0.3, 0.8, dist);

  // Blue cosmic dust
  vec2 dustUv = uv * 2.0 - vec2(uTime * 0.015);
  float dust = fbm(dustUv, 4);
  vec3 blueDust = vec3(0.0, 0.1, 0.2) * dust * 0.3;

  // Arcane energy ribbons
  vec2 ribbonUv = uv * 3.0;
  float ribbon1 = sin(ribbonUv.x * 4.0 + uTime * 0.5 + sin(ribbonUv.y * 3.0)) * 0.5 + 0.5;
  float ribbon2 = sin(ribbonUv.y * 3.5 - uTime * 0.3 + sin(ribbonUv.x * 2.5)) * 0.5 + 0.5;
  float ribbons = ribbon1 * ribbon2 * fbm(uv * 4.0 + uTime * 0.02, 3);
  vec3 arcaneRibbons = vec3(0.3, 0.1, 0.5) * ribbons * 0.2;

  // === STAR FIELD ===
  float starLayer1 = stars(uv, 150.0);
  float starLayer2 = stars(uv + 0.5, 200.0) * 0.7;
  float starLayer3 = stars(uv + 0.25, 100.0) * 0.4;

  // Distant galaxy
  vec2 galaxyUv = uv * 0.3 - 0.4;
  float galaxy = fbm(galaxyUv + uTime * 0.005, 5);
  float galaxyMask = smoothstep(0.8, 0.2, dist * 0.8);
  vec3 distantGalaxy = vec3(0.1, 0.05, 0.15) * galaxy * galaxyMask * 0.5;

  // === COMBINE ===
  vec3 color = spaceColor;
  color += goldGlow;
  color += purpleNebula;
  color += blueDust;
  color += arcaneRibbons;
  color += distantGalaxy;

  // Add stars
  color += vec3(starLayer1 + starLayer2 + starLayer3);

  // Subtle vignette
  float vignette = 1.0 - smoothstep(0.4, 1.2, dist);
  color *= vignette * 0.7 + 0.3;

  // Slight color grading - push blues
  color.b += 0.02;

  // Gamma correction
  color = pow(color, vec3(0.9));

  gl_FragColor = vec4(color, 1.0);
}
