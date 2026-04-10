// Custom Post-Processing Effects
import * as THREE from 'three';
import { EffectComposer } from 'three-stdlib';
import { RenderPass } from 'three-stdlib';
import { ShaderPass } from 'three-stdlib';
import { UnrealBloomPass } from 'three-stdlib';

// Vignette + Chromatic Aberration + Color Grading Shader
const VignetteChromaticShader = {
  uniforms: {
    tDiffuse: { value: null },
    uVignetteIntensity: { value: 0.4 },
    uChromaticOffset: { value: 0.002 },
    uTime: { value: 0 },
    uSaturation: { value: 1.1 }
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
    uniform float uVignetteIntensity;
    uniform float uChromaticOffset;
    uniform float uTime;
    uniform float uSaturation;
    varying vec2 vUv;

    vec3 adjustSaturation(vec3 color, float sat) {
      float grey = dot(color, vec3(0.299, 0.587, 0.114));
      return mix(vec3(grey), color, sat);
    }

    void main() {
      vec2 uv = vUv;
      vec2 center = uv - 0.5;

      // Chromatic aberration
      float dist = length(center);
      float offset = uChromaticOffset * dist;

      float r = texture2D(tDiffuse, uv + vec2(offset, 0.0)).r;
      float g = texture2D(tDiffuse, uv).g;
      float b = texture2D(tDiffuse, uv - vec2(offset, 0.0)).b;

      vec3 color = vec3(r, g, b);

      // Vignette
      float vignette = 1.0 - smoothstep(0.3, 0.9, dist * 1.2);
      vignette = mix(0.5, 1.0, vignette);
      color *= vignette;

      // Saturation boost
      color = adjustSaturation(color, uSaturation);

      // Subtle film grain
      float grain = fract(sin(dot(uv * uTime, vec2(12.9898, 78.233))) * 43758.5453);
      color += (grain - 0.5) * 0.02;

      gl_FragColor = vec4(color, 1.0);
    }
  `
};

// God Rays Pass
export class GodRaysPass {
  constructor(renderer, scene, camera) {
    this.renderer = renderer;
    this.scene = scene;
    this.camera = camera;

    this.composer = new EffectComposer(renderer);
    const renderPass = new RenderPass(scene, camera);
    this.composer.addPass(renderPass);

    // Extract bright areas for god rays
    this.brightPass = this.createBrightPass();
    this.composer.addPass(this.brightPass);

    // Blur pass (horizontal + vertical)
    this.hBlurPass = this.createBlurPass(true);
    this.vBlurPass = this.createBlurPass(false);
    this.composer.addPass(this.hBlurPass);
    this.composer.addPass(this.vBlurPass);

    // Composite god rays
    this.compositePass = this.createCompositePass();
    this.composer.addPass(this.compositePass);
  }

  createBrightPass() {
    return new ShaderPass({
      uniforms: {
        tDiffuse: { value: null },
        uThreshold: { value: 0.6 }
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
        uniform float uThreshold;
        varying vec2 vUv;

        void main() {
          vec4 color = texture2D(tDiffuse, vUv);
          float brightness = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
          vec3 bright = brightness > uThreshold ? color.rgb : vec3(0.0);
          gl_FragColor = vec4(bright, 1.0);
        }
      `
    });
  }

  createBlurPass(horizontal) {
    const direction = horizontal ? 1.0 : 0.0;
    const resolution = new THREE.Vector2(window.innerWidth, window.innerHeight);

    return new ShaderPass({
      uniforms: {
        tDiffuse: { value: null },
        uDirection: { value: new THREE.Vector2(direction, 1.0 - direction) },
        uResolution: { value: resolution }
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
        uniform vec2 uDirection;
        uniform vec2 uResolution;
        varying vec2 vUv;

        void main() {
          vec4 color = vec4(0.0);
          vec2 off1 = vec2(1.3846153846) * uDirection / uResolution;
          vec2 off2 = vec2(3.2307692308) * uDirection / uResolution;

          color += texture2D(tDiffuse, vUv) * 0.2270270270;
          color += texture2D(tDiffuse, vUv + off1) * 0.3162162162;
          color += texture2D(tDiffuse, vUv - off1) * 0.0702702703;
          color += texture2D(tDiffuse, vUv + off2) * 0.1216216216;
          color += texture2D(tDiffuse, vUv - off2) * 0.0108108108;

          gl_FragColor = color;
        }
      `
    });
  }

  createCompositePass() {
    return new ShaderPass({
      uniforms: {
        tDiffuse: { value: null },
        tGlow: { value: null },
        uIntensity: { value: 0.5 },
        uCenter: { value: new THREE.Vector2(0.5, 0.5) }
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
        uniform sampler2D tGlow;
        uniform float uIntensity;
        uniform vec2 uCenter;
        varying vec2 vUv;

        void main() {
          vec4 original = texture2D(tDiffuse, vUv);
          vec4 glow = texture2D(tGlow, vUv);

          // Tint glow golden
          vec3 goldenGlow = vec3(1.0, 0.9, 0.5) * glow.r;

          // Add glow radiating from center
          vec2 toCenter = uCenter - vUv;
          float radialGlow = 1.0 - smoothstep(0.0, 0.7, length(toCenter));
          goldenGlow += vec3(1.0, 0.8, 0.3) * radialGlow * 0.1;

          gl_FragColor = vec4(original.rgb + goldenGlow * uIntensity, original.a);
        }
      `
    });
  }

  render() {
    this.composer.render();
  }
}

// Main post-processing composer with all effects
export class EffectsComposer {
  constructor(renderer, scene, camera) {
    this.renderer = renderer;
    this.scene = scene;
    this.camera = camera;

    this.composer = new EffectComposer(renderer);

    // Render pass
    const renderPass = new RenderPass(scene, camera);
    this.composer.addPass(renderPass);

    // Bloom pass
    this.bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      1.2,   // intensity
      0.4,   // radius
      0.1    // threshold
    );
    this.composer.addPass(this.bloomPass);

    // Vignette + chromatic aberration
    this.vignettePass = new ShaderPass(VignetteChromaticShader);
    this.composer.addPass(this.vignettePass);
  }

  setSize(width, height) {
    this.composer.setSize(width, height);
  }

  render() {
    this.composer.render();
  }

  updateTime(time) {
    if(this.vignettePass.uniforms) {
      this.vignettePass.uniforms.uTime.value = time;
    }
  }
}
