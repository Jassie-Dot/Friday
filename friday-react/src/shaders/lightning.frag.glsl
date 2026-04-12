precision highp float;

uniform float uAudioLevel;
uniform float uEnergy;
uniform int uState;

varying float vIntensity;

void main() {
  // Bright core with glow falloff
  float dist = length(gl_PointCoord - vec2(0.5));
  float glow = 1.0 - smoothstep(0.0, 0.5, dist);

  vec3 colorA, colorB;
  if(uState == 0) {
    colorA = vec3(0.0, 0.83, 1.0);
    colorB = vec3(0.38, 0.19, 0.53);
  } else if(uState == 1) {
    colorA = vec3(0.0, 1.0, 1.0);
    colorB = vec3(0.5, 0.0, 1.0);
  } else if(uState == 2) {
    colorA = vec3(0.2, 0.4, 1.0);
    colorB = vec3(1.0, 0.1, 0.8);
  } else if(uState == 3) {
    colorA = vec3(0.13, 1.0, 0.8);
    colorB = vec3(0.0, 1.0, 0.5);
  } else {
    colorA = vec3(1.0, 0.13, 0.27);
    colorB = vec3(1.0, 0.5, 0.0);
  }

  vec3 color = mix(colorA, colorB, vIntensity);
  color += vec3(vIntensity) * 0.5; // Brighten core
  color *= vIntensity;

  float alpha = glow * vIntensity;
  alpha *= 0.7 + uAudioLevel * 0.3;

  gl_FragColor = vec4(color, alpha);
}
