'use client';

import { useState, useRef, useCallback, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, ContactShadows } from '@react-three/drei';
import { useAudioLipSync } from '@/hooks/useAudioLipSync';
import { DittoModel } from '@/components/DittoModel';
import styles from '@/components/DittoAvatarModule.module.css';

/**
 * AvatarFallback — shown while the GLB model is loading
 */
function AvatarFallback() {
  return (
    <mesh>
      <sphereGeometry args={[0.4, 32, 32]} />
      <meshStandardMaterial color="#7c3aed" wireframe />
    </mesh>
  );
}

/**
 * DittoAvatarModule
 *
 * Top-level wrapper that:
 *  1. Manages AudioContext initialisation (requires a user gesture).
 *  2. Renders the WebSocket / lip-sync hook.
 *  3. Renders the Three.js Canvas with lighting, orbit controls, and the
 *     DittoModel avatar.
 *  4. Shows a status overlay with connection / playback indicators.
 */
export function DittoAvatarModule() {
  const [audioInitialized, setAudioInitialized] = useState(false);
  const [testText, setTestText] = useState('Xin chào, tôi là Ditto.');
  const audioElRef = useRef(null);

  const { analyser, audioUrl, isPlaying, isConnected, initAudio, sendTTS } =
    useAudioLipSync('http://localhost:8001');

  const handleInit = useCallback(() => {
    initAudio();
    setAudioInitialized(true);
  }, [initAudio]);

  const handleTestSpeak = useCallback((e) => {
    e.preventDefault();
    if (testText.trim()) {
      sendTTS(testText.trim());
    }
  }, [sendTTS, testText]);

  return (
    <div className={styles.wrapper}>
      {/* ── Hidden audio element (managed by the hook) ── */}
      {audioUrl && (
        <audio
          ref={audioElRef}
          src={audioUrl}
          style={{ display: 'none' }}
          aria-hidden="true"
        />
      )}

      {/* ── 3D Canvas ── */}
      <Canvas
        className={styles.canvas}
        camera={{
          // Set camera position to [0, 1.48, 0.75] to raise the camera lens
          position: [0, 1.60, 0.75],
          fov: 40,
          near: 0.01,
          far: 100,
        }}
        shadows
        dpr={[1, 2]}
      >
        {/* Lighting */}
        <ambientLight intensity={0.6} color="#e8e0ff" />
        <directionalLight
          position={[3, 6, 4]}
          intensity={1.4}
          castShadow
          shadow-mapSize={[1024, 1024]}
          color="#ffffff"
        />
        <directionalLight position={[-4, 2, -2]} intensity={0.4} color="#a78bfa" />

        {/* Subtle environment reflections */}
        <Environment preset="city" />

        {/* Contact shadow just below the feet (avatar stands at Y=0) */}
        <ContactShadows
          position={[0, -0.05, 0]}
          opacity={0.35}
          scale={4}
          blur={2}
          far={3}
        />

        {/* Avatar with Suspense fallback while GLB is loading */}
        <Suspense fallback={<AvatarFallback />}>
          <DittoModel analyser={analyser} />
        </Suspense>

        {/* Camera controls — face-level lock, T-pose body cropped out */}
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          enableDamping={true}
          dampingFactor={0.08}
          minPolarAngle={Math.PI / 2 - 0.26}
          maxPolarAngle={Math.PI / 2 + 0.26}
          minAzimuthAngle={-Math.PI / 6}
          maxAzimuthAngle={Math.PI / 6}
          // Target level at 1.45 to align the face center and bring the head down into view
          target={[0, 1.55, 0]}
        />
      </Canvas>

      {/* ── HUD Overlay ── */}
      <div className={styles.hud}>
        {/* Status pills */}
        <div className={styles.statusBar}>
          <span
            className={`${styles.pill} ${isConnected ? styles.pillGreen : styles.pillRed}`}
          >
            <span className={styles.dot} />
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>

          {isPlaying && (
            <span className={`${styles.pill} ${styles.pillPurple}`}>
              <span className={`${styles.dot} ${styles.dotPulse}`} />
              Speaking
            </span>
          )}
        </div>

        {/* Init button ── */}
        {!audioInitialized && (
          <button className={styles.initButton} onClick={handleInit}>
            <span className={styles.initIcon}>▶</span>
            Connect &amp; Initialize Audio
          </button>
        )}

        {/* Live Test Speech Panel */}
        {audioInitialized && isConnected && (
          <form className={styles.testConsole} onSubmit={handleTestSpeak}>
            <input
              type="text"
              className={styles.testInput}
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="Type test text here..."
              disabled={isPlaying}
            />
            <button type="submit" className={styles.testButton} disabled={isPlaying || !testText.trim()}>
              {isPlaying ? 'Speaking...' : 'Test Speech'}
            </button>
          </form>
        )}

        {audioInitialized && !isConnected && (
          <p className={styles.hint}>
            Waiting for streaming-service on <code>localhost:8001</code>&hellip;
          </p>
        )}
      </div>
    </div>
  );
}
