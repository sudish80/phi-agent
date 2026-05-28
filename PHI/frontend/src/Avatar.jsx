/* Three.js 3D Avatar with lip sync, emotion display, and equalizer effect.
   Renders a futuristic AI head that animates mouth shapes from viseme data
   and shows a live audio equalizer on its face/holographic ring.
*/

import React, { useRef, useEffect, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

/* ---- Equalizer bar component ---- */
function EqualizerBar({ index, data, total }) {
  const ref = useRef();
  const height = useMemo(() => (data && data[index] !== undefined ? data[index] : 0), [data, index]);

  useEffect(() => {
    if (ref.current) {
      const scaleY = 0.1 + (height / 255) * 2.5;
      ref.current.scale.y = scaleY;
      const hue = 0.55 + (height / 255) * 0.2;
      ref.current.material.color.setHSL(hue, 0.9, 0.5 + (height / 255) * 0.3);
      ref.current.material.opacity = 0.3 + (height / 255) * 0.7;
    }
  }, [height]);

  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
  const radius = 2.4;

  return (
    <mesh
      ref={ref}
      position={[Math.cos(angle) * radius, Math.sin(angle) * radius * 0.3 - 0.3, Math.sin(angle) * radius * 0.2]}
      rotation={[0, 0, 0]}
    >
      <boxGeometry args={[0.06, 0.1, 0.06]} />
      <meshPhysicalMaterial
        transparent
        opacity={0.6}
        roughness={0.3}
        metalness={0.8}
        color="#00d4ff"
      />
    </mesh>
  );
}

/* ---- Equalizer ring ---- */
function EqualizerRing({ data }) {
  const bars = useMemo(() => {
    if (!data || data.length === 0) return Array(16).fill(0);
    return data;
  }, [data]);

  if (!bars || bars.length === 0) return null;

  return (
    <group>
      {bars.map((val, i) => (
        <EqualizerBar key={i} index={i} data={bars} total={bars.length} />
      ))}
    </group>
  );
}

/* ---- Holographic head with lip sync ---- */
function JarvisHead({ emotion, isSpeaking, isListening, visemes, equalizerData }) {
  const headRef = useRef();
  const mouthRef = useRef();
  const glowRef = useRef();
  const ringRef = useRef();

  const emotionColors = {
    neutral: { color: '#00d4ff', emissive: '#004466', intensity: 0.3 },
    happy: { color: '#00ff88', emissive: '#006633', intensity: 0.5 },
    serious: { color: '#4488ff', emissive: '#003366', intensity: 0.4 },
    excited: { color: '#ff6600', emissive: '#663300', intensity: 0.6 },
    calm: { color: '#88ddff', emissive: '#224466', intensity: 0.2 },
    angry: { color: '#ff2244', emissive: '#660011', intensity: 0.5 },
    sad: { color: '#6688cc', emissive: '#223366', intensity: 0.2 },
    whisper: { color: '#aabbdd', emissive: '#334466', intensity: 0.15 },
  };

  const currentColor = emotionColors[emotion] || emotionColors.neutral;

  /* Lip sync state */
  const mouthOpenRef = useRef(0);
  const currentVisemeRef = useRef(null);
  const visemeIndexRef = useRef(0);

  useFrame((state, delta) => {
    const elapsed = state.clock.elapsedTime;

    /* Floating animation */
    if (headRef.current) {
      headRef.current.position.y = Math.sin(elapsed * 0.8) * 0.05;
      headRef.current.rotation.z = Math.sin(elapsed * 0.3) * 0.02;
    }

    /* Ring rotation */
    if (ringRef.current) {
      ringRef.current.rotation.y += delta * 0.5;
      ringRef.current.rotation.x = Math.sin(elapsed * 0.2) * 0.05;
    }

    /* Glow pulse */
    if (glowRef.current) {
      const pulse = 0.8 + Math.sin(elapsed * 2) * 0.2;
      glowRef.current.material.opacity = pulse * 0.3;
    }

    /* Lip sync from visemes */
    if (isSpeaking && visemes && visemes.length > 0) {
      const animTime = elapsed * 1000;
      let targetOpen = 0;

      for (const v of visemes) {
        if (animTime >= v.start_ms && animTime <= v.end_ms) {
          const shape = v.shape;
          if (['A', 'E', 'I', 'O', 'U'].includes(shape)) targetOpen = 1;
          else if (shape === 'M') targetOpen = 0;
          else targetOpen = 0.5;
          currentVisemeRef.current = shape;
          break;
        }
      }

      mouthOpenRef.current += (targetOpen - mouthOpenRef.current) * 0.15;
    } else if (isSpeaking) {
      /* Idle mouth movement when speaking but no visemes */
      const idle = Math.sin(elapsed * 12) * 0.5 + 0.5;
      mouthOpenRef.current += (idle * 0.4 - mouthOpenRef.current) * 0.1;
    } else {
      mouthOpenRef.current *= 0.95;
    }

    /* Apply mouth shape */
    if (mouthRef.current) {
      const open = mouthOpenRef.current;
      mouthRef.current.scale.y = 0.3 + open * 0.7;
      mouthRef.current.position.y = -0.15 - open * 0.08;
    }

    /* Dynamic color shift from equalizer - speaking = green, listening = orange */
    if ((isSpeaking || isListening) && equalizerData && equalizerData.length > 0) {
      const avg = equalizerData.reduce((a, b) => a + b, 0) / equalizerData.length;
      if (headRef.current) {
        const intensity = 0.3 + (avg / 255) * 0.7;
        headRef.current.material.emissiveIntensity = intensity * currentColor.intensity;
      }
    } else if (headRef.current) {
      headRef.current.material.emissiveIntensity = currentColor.intensity;
    }

    /* Listening ring glow */
    if (isListening) {
      const pulse = 0.5 + Math.sin(elapsed * 4) * 0.5;
      if (ringRef.current) {
        ringRef.current.material.color.setHSL(0.08, 0.9, 0.5);
        ringRef.current.material.opacity = 0.2 + pulse * 0.4;
      }
    } else if (ringRef.current) {
      ringRef.current.material.color.setHSL(0.55, 0.9, 0.5);
      ringRef.current.material.opacity = 0.3;
    }
  });

  return (
    <group>
      {/* Holographic ring */}
      <mesh ref={ringRef} rotation={[0.2, 0, 0]}>
        <torusGeometry args={[1.8, 0.02, 16, 64]} />
        <meshBasicMaterial color="#00d4ff" transparent opacity={0.3} />
      </mesh>

      {/* Outer glow */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.9, 32, 32]} />
        <meshBasicMaterial
          color={currentColor.color}
          transparent
          opacity={0.1}
          wireframe
        />
      </mesh>

      {/* Main head */}
      <mesh ref={headRef}>
        <sphereGeometry args={[0.6, 32, 32]} />
        <MeshDistortMaterial
          color={currentColor.color}
          emissive={currentColor.emissive}
          emissiveIntensity={currentColor.intensity}
          roughness={0.2}
          metalness={0.6}
          transparent
          opacity={0.85}
          distort={0.15}
          speed={2}
        />
      </mesh>

      {/* Eyes */}
      <mesh position={[-0.2, 0.15, 0.52]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color="#00d4ff" />
      </mesh>
      <mesh position={[0.2, 0.15, 0.52]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color="#00d4ff" />
      </mesh>

      {/* Eye glow */}
      <mesh position={[-0.2, 0.15, 0.55]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>
      <mesh position={[0.2, 0.15, 0.55]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>

      {/* Mouth (lip sync) - capsule shape that scales for visemes */}
      <mesh ref={mouthRef} position={[0, -0.15, 0.55]}>
        <capsuleGeometry args={[0.04, 0.08, 4, 8]} />
        <meshBasicMaterial color="#003355" />
      </mesh>

      {/* Equalizer bars around head - animate both when talking AND listening */}
      {(isSpeaking || isListening) && (
        <group>
          <EqualizerRing data={equalizerData} />
          {/* Pulsing listening ring */}
          {isListening && (
            <mesh>
              <ringGeometry args={[1.9, 2.0, 48]} />
              <meshBasicMaterial
                color="#ff8800"
                transparent
                opacity={0.15 + Math.sin(Date.now() * 0.005) * 0.1}
                side={2}
              />
            </mesh>
          )}
        </group>
      )}
    </group>
  );
}

/* ---- Main Avatar component ---- */
function Avatar({ emotion = 'neutral', isSpeaking = false, isListening = false, visemes = [], equalizerData = [] }) {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      minHeight: 400,
      background: 'radial-gradient(ellipse at center, #0d1b2a 0%, #0a0a1a 70%)',
      borderRadius: 16,
      overflow: 'hidden',
      position: 'relative',
    }}>
      <Canvas
        camera={{ position: [0, 0, 3.5], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.3} />
        <pointLight position={[2, 2, 3]} intensity={0.8} color="#00d4ff" />
        <pointLight position={[-2, -1, 2]} intensity={0.4} color="#4488ff" />
        <JarvisHead
          emotion={emotion}
          isSpeaking={isSpeaking}
          isListening={isListening}
          visemes={visemes}
          equalizerData={equalizerData}
        />
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          maxPolarAngle={Math.PI / 2}
          minPolarAngle={Math.PI / 3}
          autoRotate
          autoRotateSpeed={0.5}
        />
      </Canvas>

      {/* Emotion label overlay */}
      <div style={{
        position: 'absolute',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(0,0,0,0.6)',
        padding: '4px 16px',
        borderRadius: 12,
        fontSize: '0.75rem',
        color: '#00d4ff',
        textTransform: 'uppercase',
        letterSpacing: 2,
        border: '1px solid rgba(0,212,255,0.3)',
      }}>
        {emotion}
      </div>
    </div>
  );
}

export default Avatar;
