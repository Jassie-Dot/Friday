import * as THREE from 'three';
import { EffectComposer } from 'three-stdlib';
import { RenderPass } from 'three-stdlib';
import { ShaderPass } from 'three-stdlib';
import { UnrealBloomPass } from 'three-stdlib';

const CinematicPostShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    uColorTint: { value: new THREE.Color(0x00d4ff) }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform vec3 uColorTint;
    varying vec2 vUv;

    vec3 adjustSaturation(vec3 color, float sat) {
      float grey = dot(color, vec3(0.299, 0.587, 0.114));
      return mix(vec3(grey), color, sat);
    }

    void main() {
      vec2 uv = vUv;
      vec2 center = uv - 0.5;
      float dist = length(center);

      // Radial chromatic aberration
      float offset = 0.002 * dist * dist;
      vec2 dir = normalize(center + vec2(0.001));

      float r = texture2D(tDiffuse, uv + dir * offset * 1.3).r;
      float g = texture2D(tDiffuse, uv).g;
      float b = texture2D(tDiffuse, uv - dir * offset * 1.0).b;
      vec3 color = vec3(r, g, b);

      // Cinematic vignette
      float vignette = 1.0 - smoothstep(0.25, 1.0, dist * 1.4);
      vignette = mix(0.35, 1.0, vignette);
      color *= vignette;

      // Saturation
      color = adjustSaturation(color, 1.3);

      // Cyan shadow tinting
      float luminance = dot(color, vec3(0.299, 0.587, 0.114));
      color += mix(uColorTint * 0.02, vec3(0.0), luminance);

      // Anamorphic horizontal flare
      float flare = exp(-dist * 3.5) * 0.04;
      float flareStretch = exp(-abs(center.y) * 10.0);
      color += uColorTint * flare * flareStretch;

      // Film grain
      float grain = fract(sin(dot(uv * (uTime + 1.0), vec2(12.9898, 78.233))) * 43758.5453);
      color += (grain - 0.5) * 0.012;

      gl_FragColor = vec4(color, 1.0);
    }
  `
};

export class EffectsComposer {
  constructor(renderer, scene, camera) {
    this.composer = new EffectComposer(renderer);
    this.composer.addPass(new RenderPass(scene, camera));

    this.bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      0.6, 0.9, 0.3
    );
    this.composer.addPass(this.bloomPass);

    this.cinematicPass = new ShaderPass(CinematicPostShader);
    this.composer.addPass(this.cinematicPass);
  }

  setSize(w, h) { this.composer.setSize(w, h); }
  render() { this.composer.render(); }

  updateTime(time) {
    if(this.cinematicPass.uniforms) {
      this.cinematicPass.uniforms.uTime.value = time;
    }
  }
}
