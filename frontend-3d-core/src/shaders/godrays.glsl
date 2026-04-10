// God Rays Fragment Shader - Volumetric light rays emanating from center
uniform sampler2D tDiffuse;
uniform vec2 uResolution;
uniform vec2 uCenter;
uniform float uTime;
uniform float uIntensity;
uniform float uDecay;
uniform float uWeight;
uniform float uDensity;
uniform int uSamples;

varying vec2 vUv;

void main() {
  vec2 uv = vUv;
  vec2 deltaTexCoord = (uv - uCenter);
  deltaTexCoord *= 1.0 / float(uSamples) * uDensity;

  vec4 color = texture2D(tDiffuse, uv);
  float illuminationDecay = 1.0;

  vec4 rays = vec4(0.0);

  for(int i = 0; i < 60; i++) {
    if(i >= uSamples) break;
    uv -= deltaTexCoord;
    vec4 sampleColor = texture2D(tDiffuse, uv);
    sampleColor *= illuminationDecay * uWeight;
    rays += sampleColor;
    illuminationDecay *= uDecay;
  }

  // Tint rays golden
  vec3 rayColor = vec3(1.0, 0.85, 0.4) * rays.rgb;

  // Add subtle color variation
  rayColor.r += rays.b * 0.2;
  rayColor.b += rays.r * 0.1;

  gl_FragColor = vec4(color.rgb + rayColor * uIntensity, color.a);
}
