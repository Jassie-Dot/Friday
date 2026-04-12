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

// State color palettes
const vec3 COLOR_IDLE_A = vec3(0.0, 0.83, 1.0);      // Cyan #00d4ff
const vec3 COLOR_IDLE_B = vec3(0.38, 0.19, 0.53);    // Deep purple #613187
const vec3 COLOR_LISTEN_A = vec3(0.0, 1.0, 1.0);     // Bright cyan
const vec3 COLOR_LISTEN_B = vec3(0.5, 0.0, 1.0);     // Violet
const vec3 COLOR_THINK_A = vec3(0.2, 0.4, 1.0);       // Electric blue
const vec3 COLOR_THINK_B = vec3(1.0, 0.1, 0.8);       // Magenta
const vec3 COLOR_RESPOND_A = vec3(0.13, 1.0, 0.8);   // Mint #22ffcc
const vec3 COLOR_RESPOND_B = vec3(0.0, 1.0, 0.5);     // Green-cyan
const vec3 COLOR_ERROR_A = vec3(1.0, 0.13, 0.27);     // Red #ff2244
const vec3 COLOR_ERROR_B = vec3(1.0, 0.5, 0.0);       // Orange

// Noise functions
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                      -0.577350269189626, 0.024390243902439);
  vec2 i = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1;
  i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod289(i);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                   + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy),
                           dot(x12.zw,x12.zw)), 0.0);
  m = m*m;
  m = m*m;
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

  // Select color palette based on state
  vec3 colorA, colorB;
  float glowIntensity = 0.5;

  if(uState == 0) { // IDLE
    colorA = COLOR_IDLE_A; colorB = COLOR_IDLE_B; glowIntensity = 0.4;
  } else if(uState == 1) { // LISTENING
    colorA = COLOR_LISTEN_A; colorB = COLOR_LISTEN_B; glowIntensity = 0.6 + uAudioLevel * 0.4;
  } else if(uState == 2) { // THINKING
    colorA = COLOR_THINK_A; colorB = COLOR_THINK_B; glowIntensity = 0.7 + uEnergy * 0.5;
  } else if(uState == 3) { // RESPONDING
    colorA = COLOR_RESPOND_A; colorB = COLOR_RESPOND_B; glowIntensity = 0.8 + uAudioLevel * 0.5;
  } else { // ERROR
    colorA = COLOR_ERROR_A; colorB = COLOR_ERROR_B; glowIntensity = 0.9 + uErrorPulse;
  }

  // Plasma pattern using screen-space coordinates for consistent look
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
  plasma = plasma * 0.5 + 0.5; // Normalize to 0-1

  // Color mixing with plasma pattern
  vec3 plasmaColor = mix(colorA, colorB, plasma);

  // Fresnel glow
  vec3 fresnelColor = mix(colorA, colorB, fresnel);
  plasmaColor = mix(plasmaColor, fresnelColor, fresnel * 0.7);

  // Add bright hotspots from displacement
  float hotspot = pow(vPlasmaIntensity, 2.0) * glowIntensity;
  plasmaColor += vec3(hotspot) * 1.5;

  // Audio-reactive inner glow
  float audioGlow = uAudioLevel * 0.3;
  plasmaColor += colorA * audioGlow;

  // Energy-based intensity boost
  float energyBoost = 1.0 + uEnergy * 0.5;
  plasmaColor *= energyBoost;

  // Subtle chromatic aberration on edges
  float chromaOffset = fresnel * 0.02;
  plasmaColor.r *= 1.0 + chromaOffset;
  plasmaColor.b *= 1.0 - chromaOffset;

  // Final alpha with fresnel-based transparency
  float alpha = 0.6 + fresnel * 0.4 + hotspot * 0.3;
  alpha = clamp(alpha, 0.0, 1.0);

  gl_FragColor = vec4(plasmaColor, alpha);
}
