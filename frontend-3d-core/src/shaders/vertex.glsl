uniform sampler2D uPosTexture;
uniform float uSize;
uniform float uTime;
uniform float uState;
uniform float uAudio;
attribute vec2 reference;
varying float vLife;
varying float vDist;

void main() {
  vec4 data = texture2D(uPosTexture, reference);
  vec3 pos = data.rgb;
  vLife = data.a;

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  float dist = length(mvPosition.xyz);
  vDist = dist;

  float audioBoost = 1.0 + (uAudio * 1.5);
  float baseSize = uSize * (350.0 / dist) * audioBoost;

  // Inner particles larger
  float worldDist = length(pos);
  float proximityBoost = 1.0 + smoothstep(4.0, 0.0, worldDist) * 2.0;

  // State-based size
  float pulse = 1.0;
  if(uState < 0.5) {
    // Idle: slow gentle breath
    pulse = 1.0 + sin(uTime * 1.0) * 0.08;
  } else if(uState < 1.5) {
    // Listening: heartbeat pump — particles swell on beat
    float beat = pow(sin(uTime * 3.5) * 0.5 + 0.5, 6.0);
    pulse = 0.85 + beat * 0.5; // shrink then pop
  } else if(uState < 2.5) {
    // Thinking: tight, compressed, rapid shimmer
    pulse = 0.8 + sin(uTime * 12.0) * 0.1;
    proximityBoost *= 1.4; // dense core
  } else if(uState < 3.5) {
    // Speaking: expanded, radiant, flowing
    pulse = 1.15 + sin(uTime * 4.0) * 0.15;
  } else if(uState < 4.5) {
    // Executing: compressed bursts with sharp staccato spikes
    pulse = 0.95 + step(0.45, sin(uTime * 18.0) * 0.5 + 0.5) * 0.45;
    proximityBoost *= 1.25;
  } else {
    // Error: flicker
    pulse = 0.7 + step(0.5, sin(uTime * 20.0) * 0.5 + 0.5) * 0.6;
  }

  float lifeSize = 0.3 + vLife * 0.7;
  gl_PointSize = clamp(baseSize * pulse * lifeSize * proximityBoost, 0.5, 30.0);
  gl_Position = projectionMatrix * mvPosition;
}
