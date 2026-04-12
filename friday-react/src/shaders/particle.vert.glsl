precision highp float;

uniform float uTime;
uniform float uAudioLevel;
uniform float uEnergy;
uniform int uState;
uniform float uParticleSize;

attribute float aRandom;
attribute vec3 aVelocity;

varying vec3 vColor;
varying float vAlpha;
varying float vPlasmaTrail;

float hash(vec3 p) {
  p = fract(p * 0.3183099 + 0.1);
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x),
        mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
    mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
        mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y),
    f.z
  );
}

void main() {
  // State-based behavior
  float timeScale = 1.0;
  float orbitalSpeed = 0.5;
  float inwardPull = 0.0;
  float burstForce = 0.0;
  vec3 colorA = vec3(0.0, 0.83, 1.0);
  vec3 colorB = vec3(0.38, 0.19, 0.53);

  if(uState == 0) { // IDLE
    timeScale = 0.3;
    orbitalSpeed = 0.3;
    inwardPull = 0.01;
  } else if(uState == 1) { // LISTENING
    timeScale = 0.5 + uAudioLevel * 2.0;
    orbitalSpeed = 0.5 + uAudioLevel * 1.5;
    inwardPull = 0.02 + uAudioLevel * 0.03;
    colorA = vec3(0.0, 1.0, 1.0);
    colorB = vec3(0.5, 0.0, 1.0);
  } else if(uState == 2) { // THINKING
    timeScale = 2.0 + uEnergy * 4.0;
    orbitalSpeed = 2.0 + uEnergy * 3.0;
    inwardPull = 0.05 + uEnergy * 0.1;
    colorA = vec3(0.2, 0.4, 1.0);
    colorB = vec3(1.0, 0.1, 0.8);
  } else if(uState == 3) { // RESPONDING
    timeScale = 1.0 + uAudioLevel * 3.0;
    orbitalSpeed = 1.0 + uAudioLevel * 2.0;
    burstForce = uAudioLevel * 0.3;
    inwardPull = -0.02; // Negative = outward burst
    colorA = vec3(0.13, 1.0, 0.8);
    colorB = vec3(0.0, 1.0, 0.5);
  } else { // ERROR
    timeScale = 6.0;
    orbitalSpeed = 3.0;
    colorA = vec3(1.0, 0.13, 0.27);
    colorB = vec3(1.0, 0.5, 0.0);
  }

  float t = uTime * timeScale + aRandom * 100.0;

  // Orbital motion around center
  float radius = length(position);
  float angle = atan(position.z, position.x) + t * orbitalSpeed * (0.5 + aRandom * 0.5);
  float yAngle = atan(position.y, length(position.xz)) + t * orbitalSpeed * 0.3;

  // Radius modulation from noise
  float radiusNoise = noise(position * 2.0 + uTime * 0.5);
  float radiusMod = 1.0 + radiusNoise * 0.2;

  // Apply inward pull / outward burst
  float newRadius = radius * radiusMod;
  if(inwardPull > 0.0) {
    newRadius = mix(newRadius, radius * 0.8, inwardPull);
  } else if(inwardPull < 0.0) {
    newRadius = mix(newRadius, radius * (1.0 + abs(inwardPull) + burstForce), 0.1);
  }

  // Compute new position
  vec3 newPos;
  newPos.x = newRadius * cos(angle);
  newPos.z = newRadius * sin(angle);
  newPos.y = radius * sin(yAngle) * (1.0 + sin(t * 0.7 + aRandom * 6.28) * 0.3);

  // Add subtle plasma wave displacement
  float wave = sin(t * 2.0 + radius * 5.0) * 0.05;
  newPos += normalize(position) * wave;

  // Particle color from state palette
  float colorMix = noise(position * 3.0 + uTime * 0.3) * 0.5 + 0.5;
  vColor = mix(colorA, colorB, colorMix);

  // Add brightness variation
  float brightness = 0.6 + noise(position * 10.0 + uTime) * 0.4;
  vColor *= brightness;

  // Audio-reactive brightness boost
  vColor *= 1.0 + uAudioLevel * 0.5;

  // Alpha based on distance and state
  float distFromCenter = length(newPos);
  vAlpha = smoothstep(20.0, 2.0, distFromCenter) * 0.8;

  // Slow particles fade
  vAlpha *= 0.5 + aRandom * 0.5;

  // Plasma trail effect - particles leave glowing trails
  vPlasmaTrail = abs(wave) * 10.0;

  vec4 mvPosition = modelViewMatrix * vec4(newPos, 1.0);

  // Size attenuation
  float size = uParticleSize * (1.0 + uAudioLevel * 2.0 + uEnergy * 1.0);
  size *= (1.0 + sin(t * 3.0 + aRandom * 6.28) * 0.2); // Pulsing
  gl_PointSize = size * (300.0 / -mvPosition.z);

  gl_Position = projectionMatrix * mvPosition;
}
