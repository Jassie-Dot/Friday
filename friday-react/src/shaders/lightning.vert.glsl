precision highp float;

uniform float uTime;
uniform float uAudioLevel;
uniform float uEnergy;
uniform int uState;

varying float vIntensity;
varying float vSegment;

// Lightning noise
float hash(float n) { return fract(sin(n) * 43758.5453123); }

float lightning(vec2 p, float time, float seed) {
  float result = 0.0;
  float amplitude = 1.0;
  float frequency = 1.0;

  for(int i = 0; i < 5; i++) {
    // Jumping noise
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
  // Coordinate from 0-1 along the tendril
  vec2 uv = gl_PointCoord;

  float timeScale = 1.0;
  if(uState == 0) timeScale = 0.3;
  else if(uState == 1) timeScale = 0.8 + uAudioLevel * 1.5;
  else if(uState == 2) timeScale = 2.5 + uEnergy * 3.0;
  else if(uState == 3) timeScale = 1.5 + uAudioLevel * 2.0;
  else timeScale = 6.0;

  float t = uTime * timeScale;

  // Core lightning path
  float intensity = lightning(uv, t, vSegment);

  // Add flicker
  float flicker = 0.7 + hash(vSegment * 50.0 + floor(t * 10.0)) * 0.3;

  // Boost based on energy/audio
  intensity *= 1.0 + uEnergy * 0.5 + uAudioLevel * 0.5;

  intensity *= flicker;
  vIntensity = intensity;

  gl_PointSize = 3.0 + intensity * 5.0;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
