import { useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { AICore } from './ui/AICore';
import { ParticleVoid } from './ui/ParticleVoid';
import { MessageLayer } from './ui/MessageLayer';
import { StatusOverlay } from './ui/StatusOverlay';
import { ContextPanels } from './ui/ContextPanels';
import { InputBar } from './ui/InputBar';
import { connectWebSocket } from './core/socket';
import { initVoiceSystem } from './core/voice';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// ── Camera parallax rig ──
function CameraRig() {
  useFrame((state) => {
    const targetX = state.pointer.x * 2.5;
    const targetY = state.pointer.y * 2.5;
    state.camera.position.x = THREE.MathUtils.lerp(state.camera.position.x, targetX, 0.04);
    state.camera.position.y = THREE.MathUtils.lerp(state.camera.position.y, targetY, 0.04);
    state.camera.lookAt(0, 0, 0);
  });
  return null;
}

// ── Ambient particle drift ──
function AmbientDrift() {
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    // Subtle camera micro-movements
    state.camera.position.x += Math.sin(t * 0.3) * 0.001;
    state.camera.position.y += Math.cos(t * 0.2) * 0.001;
  });
  return null;
}

export default function App() {
  useEffect(() => {
    // Initialize WebSocket connection
    connectWebSocket();

    // Initialize voice input after a short delay
    const timer = setTimeout(() => {
      initVoiceSystem();
    }, 1000);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="w-screen h-screen bg-[#020204] overflow-hidden relative font-sans">
      {/* 2D HUD Layer */}
      <StatusOverlay />
      <MessageLayer />
      <ContextPanels />
      <InputBar />

      {/* 3D Render Layer */}
      <div className="absolute inset-0 z-0">
        <Canvas
          camera={{ position: [0, 0, 5], fov: 60 }}
          gl={{
            antialias: true,
            alpha: false,
            powerPreference: 'high-performance',
          }}
          dpr={[1, 2]}
        >
          <CameraRig />
          <AmbientDrift />

          {/* Ambient fill light */}
          <ambientLight intensity={0.3} />

          {/* Point lights for plasma glow */}
          <pointLight position={[0, 0, 0]} intensity={0.5} color="#00d4ff" distance={10} />

          {/* Particle field */}
          <ParticleVoid />

          {/* Plasma core */}
          <AICore />

          {/* Post-processing bloom */}
          <EffectComposer>
            <Bloom
              luminanceThreshold={0.15}
              luminanceSmoothing={0.9}
              intensity={1.8}
              mipmapBlur
              radius={0.8}
            />
          </EffectComposer>
        </Canvas>
      </div>

      {/* Vignette overlay */}
      <div
        className="absolute inset-0 pointer-events-none z-[5]"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(2, 2, 4, 0.7) 100%)',
        }}
      />

      {/* Scanline overlay for CRT feel */}
      <div
        className="absolute inset-0 pointer-events-none z-[6] opacity-[0.03]"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 212, 255, 0.1) 2px, rgba(0, 212, 255, 0.1) 4px)',
        }}
      />
    </div>
  );
}
