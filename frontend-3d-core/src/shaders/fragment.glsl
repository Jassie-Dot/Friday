uniform vec3 uColorA;
uniform vec3 uColorB;
varying float vLife;

void main() {
  float dist = length(gl_PointCoord - vec2(0.5));
  if (dist > 0.5) discard;
  
  // Exponential decay for cleaner, sharper particles
  float falloff = exp(-dist * 8.0);
  
  // Use vLife to fade out older particles
  float alpha = falloff * vLife * 0.85;
  
  // Mix colors based on life
  vec3 color = mix(uColorA, uColorB, vLife);
  
  // Subtle transparency boost
  gl_FragColor = vec4(color, alpha);
}
