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

  // Calculate distance from camera for depth
  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  float dist = length(mvPosition.xyz);
  vDist = dist;

  // Audio reactive boost
  float audioBoost = 1.0 + (uAudio * 4.0); // Intense size pulse with audio

  // Base size with depth falloff
  float baseSize = uSize * (250.0 / dist) * audioBoost;

  // Size modulation based on state
  float statePulse = 1.0;
  if(uState > 2.5 && uState < 3.5) {
    // Responding: pulsing burst
    statePulse = 1.0 + sin(uTime * 15.0) * 0.4;
  } else if(uState > 1.5 && uState < 2.5) {
    // Thinking: rapid flicker
    statePulse = 1.0 + sin(uTime * 8.0) * 0.2;
  } else if(uState < 0.5) {
    // Idle: gentle breathing
    statePulse = 1.0 + sin(uTime * 1.5) * 0.15;
  }

  // Life-based size (fade out older particles)
  float lifeSize = 0.5 + vLife * 0.5;

  // Final point size
  gl_PointSize = baseSize * statePulse * lifeSize;

  // Clamp size to prevent overdraw
  gl_PointSize = clamp(gl_PointSize, 0.5, 30.0 * audioBoost);

  gl_Position = projectionMatrix * mvPosition;
}
