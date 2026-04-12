precision highp float;

uniform float uAudioLevel;
uniform int uState;

varying vec3 vColor;
varying float vAlpha;
varying float vPlasmaTrail;

void main() {
  // Circular particle with soft glow
  vec2 center = gl_PointCoord - vec2(0.5);
  float dist = length(center);

  // Soft circular falloff
  float circle = 1.0 - smoothstep(0.0, 0.5, dist);

  // Glow layers
  float glow1 = 1.0 - smoothstep(0.0, 0.3, dist);
  float glow2 = 1.0 - smoothstep(0.0, 0.5, dist);

  // Plasma core bright center
  float core = 1.0 - smoothstep(0.0, 0.15, dist);
  vec3 finalColor = vColor;

  // Brighten core
  finalColor += core * vec3(0.5);

  // Add plasma trail glow
  finalColor += vColor * vPlasmaTrail * 0.5;

  // Alpha falloff
  float alpha = circle * vAlpha;

  // Audio reactive alpha boost
  alpha *= 1.0 + uAudioLevel * 0.3;

  gl_FragColor = vec4(finalColor, alpha);
}
