uniform sampler2D uPosTexture;
uniform float uSize;
attribute vec2 reference;
varying float vLife;

void main() {
  vec4 data = texture2D(uPosTexture, reference);
  vec3 pos = data.rgb;
  vLife = data.a;

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  gl_PointSize = uSize * (300.0 / -mvPosition.z) * vLife;
  gl_Position = projectionMatrix * mvPosition;
}
