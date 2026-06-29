'use client';

import { useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';

/**
 * DittoModel
 *
 * Loads a ReadyPlayerMe-compatible GLB avatar and drives:
 *   1. Multi-band lip-sync  — 3 frequency bands → 3 mouth shape categories.
 *      Capped at natural max influences (jaw/mouth open ≤ 0.40, others ≤ 0.45)
 *      to prevent exaggerated "screaming" facial distortions.
 *   2. Corrected head posture — applies a slight default downward pitch tilt (~9°)
 *      so the avatar gazes straight at the camera, blended with micro-nods.
 *   3. Eyebrow micro-expressions — volume envelope raises brows on emphasis.
 *   4. Head-nod micro-movement  — subtle bone rotation tied to speech energy.
 *   5. Randomised eye blinking  — 3-phase state machine.
 *   6. Idle breathing           — sine-wave vertical bob on the group.
 *
 * All animations gracefully degrade when specific morph targets or bones are
 * absent from the loaded GLB (no errors, just skipped).
 *
 * @param {Object}            props
 * @param {AnalyserNode|null} props.analyser  - Web Audio API AnalyserNode.
 * @param {number[]}          [props.position]
 * @param {number[]}          [props.scale]
 * @param {number[]}          [props.rotation]
 */
export function DittoModel({
  analyser,
  position = [0, 0, 0],
  scale    = [1, 1, 1],
  rotation = [0, 0, 0],
}) {
  const { scene } = useGLTF('/models/avatar.glb');

  // ── All animation state lives in refs — zero re-renders ─────────────────
  const groupRef = useRef(null);

  // Per-band morph target buckets
  const jawTargetsRef  = useRef([]); // Low band  → jaw/open vowels (A, O, U)
  const midTargetsRef  = useRef([]); // Mid band  → E-vowels, consonants (CH, E)
  const highTargetsRef = useRef([]); // High band → sibilants (S, I, FF)
  const browTargetsRef = useRef([]); // Eyebrow raise targets
  const blinkTargetsRef = useRef([]); // Eyelid blink targets

  // Head / Neck bone for nodding
  const headBoneRef = useRef(null);
  const originalHeadRotationXRef = useRef(0);

  // Frequency data buffer (lazily allocated)
  const freqDataRef = useRef(null);

  // Smoothed influence values per animation channel
  const inf = useRef({ jaw: 0, mid: 0, high: 0, brow: 0 });

  // Slow volume envelope (for brow raise and head nod) — exponential smoothing
  const volumeEnvRef = useRef(0);

  // Blink state machine
  const blink = useRef({ phase: 'idle', timer: 0, nextTime: 2.0, value: 0 });

  // ── Scene traversal — run once when GLB loads ────────────────────────────
  useEffect(() => {
    if (!scene) return;

    // ── Priority lists per animation band ──────────────────────────────────
    const JAW_TARGETS = [
      'jawOpen',
      'viseme_aa',   // RPM: wide-open A vowel
      'viseme_O',    // RPM: rounded O vowel
      'viseme_U',    // RPM: rounded U vowel
      'mouthOpen',
    ];
    const MID_TARGETS = [
      'viseme_E',    // RPM: E vowel / teeth-together sounds
      'viseme_CH',   // RPM: CH/J consonant
      'viseme_DD',   // RPM: D/N consonant
      'viseme_RR',   // RPM: R consonant
      'mouthSmileLeft',
      'mouthSmileRight',
    ];
    const HIGH_TARGETS = [
      'viseme_I',    // RPM: I vowel / narrow mouth
      'viseme_SS',   // RPM: S/Z sibilant
      'viseme_FF',   // RPM: F/V labiodental
      'viseme_TH',   // RPM: TH
      'viseme_PP',   // RPM: P/B bilabial
      'mouthDimpleLeft',
      'mouthDimpleRight',
    ];
    const BROW_TARGETS = [
      'browInnerUp',
      'browOuterUpLeft',
      'browOuterUpRight',
    ];
    const BLINK_TARGETS = [
      'eyeBlinkLeft',
      'eyeBlinkRight',
      'eyesClosed',
      'blink',
      'Blink',
      'Eye_Blink',
    ];

    const found = { jaw: [], mid: [], high: [], brow: [], blink: [] };

    scene.traverse((node) => {
      if (!node.isMesh || !node.morphTargetDictionary || !node.morphTargetInfluences) return;

      const dict = node.morphTargetDictionary;

      console.log('👉 TARGET MESH FOUND:', node.name, dict);

      const findFirst = (names) => {
        for (const name of names) {
          if (dict[name] !== undefined) return { mesh: node, index: dict[name], name };
        }
        return null;
      };

      const findAll = (names) => {
        const res = [];
        for (const name of names) {
          if (dict[name] !== undefined) res.push({ mesh: node, index: dict[name], name });
        }
        return res;
      };

      const jaw  = findFirst(JAW_TARGETS);  if (jaw)  found.jaw.push(jaw);
      const mid  = findFirst(MID_TARGETS);  if (mid)  found.mid.push(mid);
      const high = findFirst(HIGH_TARGETS); if (high) found.high.push(high);

      findAll(BROW_TARGETS).forEach(t  => found.brow.push(t));
      findAll(BLINK_TARGETS).forEach(t => found.blink.push(t));
    });

    jawTargetsRef.current   = found.jaw;
    midTargetsRef.current   = found.mid;
    highTargetsRef.current  = found.high;
    browTargetsRef.current  = found.brow;
    blinkTargetsRef.current = found.blink;

    // ── Find head / neck bone for nodding & alignment ──────────────────────
    scene.traverse((node) => {
      if (!headBoneRef.current && (node.isBone || node.type === 'Bone')) {
        const n = node.name.toLowerCase();
        if (n.includes('head') || n.includes('neck')) {
          headBoneRef.current = node;
          originalHeadRotationXRef.current = node.rotation.x;
          console.info(
            '[DittoModel] Head/neck bone found for alignment:', 
            node.name, 
            'original X rotation:', 
            node.rotation.x
          );
        }
      }
    });
  }, [scene]);

  // ── useFrame — every render tick ─────────────────────────────────────────
  useFrame((state, delta) => {
    const elapsed = state.clock.elapsedTime;

    // ─────────────────────────────────────────────────────────────────────────
    // 1. IDLE BREATHING
    // ─────────────────────────────────────────────────────────────────────────
    if (groupRef.current) {
      groupRef.current.position.y = position[1] + Math.sin(elapsed * 1.8) * 0.004;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 2. MULTI-BAND LIP-SYNC
    // ─────────────────────────────────────────────────────────────────────────
    if (analyser) {
      if (!freqDataRef.current || freqDataRef.current.length !== analyser.frequencyBinCount) {
        freqDataRef.current = new Uint8Array(analyser.frequencyBinCount);
      }
      analyser.getByteFrequencyData(freqDataRef.current);
      const bins = freqDataRef.current;

      const bandAvg = (from, to) => {
        let sum = 0;
        const n = to - from + 1;
        for (let i = from; i <= to; i++) sum += (bins[i] || 0);
        return sum / n;
      };

      // ── Splitting Bands ──
      const lowEnergy  = bandAvg(0,  5);
      const midEnergy  = bandAvg(6,  15);
      const highEnergy = bandAvg(16, 30);
      const overallEnergy = bandAvg(0, 30);

      // Volume envelope for brow & neck
      volumeEnvRef.current = THREE.MathUtils.lerp(
        volumeEnvRef.current,
        overallEnergy / 255,
        1 - Math.pow(0.15, delta)
      );

      // Snap-close logic
      const SNAP_THRESHOLD = 5;
      const isSilent = overallEnergy < SNAP_THRESHOLD;

      const SENS = 110; // lower = more reactive
      const AMP  = 3.2; // amplification
      const FLOOR = 8;

      // Safe normalization helper with custom maximum influence clamps
      const norm = (energy, maxClamp) =>
        isSilent
          ? 0
          : THREE.MathUtils.clamp(((energy - FLOOR) / SENS) * AMP, 0, maxClamp);

      // Clamped limits to avoid exaggerated "unhinged jaw" distortion
      const jawTarget  = norm(lowEnergy, 0.40);  // Cap jaw/wide open to 0.40 max
      const midTarget  = norm(midEnergy, 0.45);  // Cap smile/consonants to 0.45 max
      const highTarget = norm(highEnergy, 0.45); // Cap dimple/sibilants to 0.45 max

      // Smooth decay factor (tuned for natural syllable separations without jitter)
      const fastLerp = 1 - Math.pow(0.001, delta); // Instant response when opening
      const slowLerp = 1 - Math.pow(0.08, delta);  // Slightly smoother closure decay

      const { jaw: jawInf, mid: midInf, high: highInf } = inf.current;

      inf.current.jaw  = THREE.MathUtils.lerp(jawInf,  jawTarget,  jawTarget  > jawInf  ? fastLerp : slowLerp);
      inf.current.mid  = THREE.MathUtils.lerp(midInf,  midTarget,  midTarget  > midInf  ? fastLerp : slowLerp);
      inf.current.high = THREE.MathUtils.lerp(highInf, highTarget, highTarget > highInf ? fastLerp : slowLerp);

      const applyMorphs = (targets, value) => {
        for (const { mesh, index } of targets) {
          if (mesh.morphTargetInfluences) mesh.morphTargetInfluences[index] = value;
        }
      };

      applyMorphs(jawTargetsRef.current,  inf.current.jaw);
      applyMorphs(midTargetsRef.current,  inf.current.mid);
      applyMorphs(highTargetsRef.current, inf.current.high);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 3. EYEBROW MICRO-EXPRESSIONS
    // ─────────────────────────────────────────────────────────────────────────
    if (browTargetsRef.current.length > 0) {
      const idleSine  = (Math.sin(elapsed * 0.6) + 1) * 0.5;
      const browTarget = THREE.MathUtils.clamp(
        volumeEnvRef.current * 1.8 + idleSine * 0.05,
        0,
        0.35
      );

      inf.current.brow = THREE.MathUtils.lerp(
        inf.current.brow,
        browTarget,
        1 - Math.pow(0.12, delta)
      );

      for (const { mesh, index } of browTargetsRef.current) {
        if (mesh.morphTargetInfluences) mesh.morphTargetInfluences[index] = inf.current.brow;
      }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 4. CORRECTED HEAD POSTURE & SPEECH NOD
    // ─────────────────────────────────────────────────────────────────────────
    if (headBoneRef.current) {
      const bone = headBoneRef.current;

      // Pitch adjustment: Base posture adjustment to positive +8.5 degrees
      // (relative to original GLB rotation) to rotate the head forward (downward)
      // blended with reactive audio-driven nods of up to ~3.5 degrees (0.06 rad).
      const baseRotationX  = originalHeadRotationXRef.current || 0;
      const tiltCorrection = THREE.MathUtils.degToRad(8.5);
      const nodPitch       = (volumeEnvRef.current - 0.25) * 0.06;

      bone.rotation.x = THREE.MathUtils.lerp(
        bone.rotation.x,
        baseRotationX + tiltCorrection + nodPitch,
        1 - Math.pow(0.05, delta)
      );

      // Yaw: gentle idle sway left-right at ~0.07 Hz (very subtle)
      const swayYaw = Math.sin(elapsed * 0.44) * 0.015;
      bone.rotation.y = THREE.MathUtils.lerp(
        bone.rotation.y,
        swayYaw,
        1 - Math.pow(0.1, delta)
      );
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 5. BLINKING
    // ─────────────────────────────────────────────────────────────────────────
    if (blinkTargetsRef.current.length > 0) {
      const b = blink.current;
      b.timer += delta;

      switch (b.phase) {
        case 'idle':
          if (b.timer >= b.nextTime) { b.phase = 'closing'; b.timer = 0; }
          break;
        case 'closing':
          b.value = Math.min(1, b.value + delta / 0.06);
          if (b.value >= 1) { b.phase = 'opening'; b.timer = 0; }
          break;
        case 'opening':
          b.value = Math.max(0, b.value - delta / 0.10);
          if (b.value <= 0) {
            b.phase    = 'idle';
            b.timer    = 0;
            b.nextTime = 2.5 + Math.random() * 3.0;
          }
          break;
        default:
          b.phase = 'idle';
      }

      for (const { mesh, index } of blinkTargetsRef.current) {
        if (mesh.morphTargetInfluences) mesh.morphTargetInfluences[index] = b.value;
      }
    }
  });

  return (
    <group ref={groupRef}>
      <primitive
        object={scene}
        position={position}
        scale={scale}
        rotation={rotation}
      />
    </group>
  );
}

// Preload so the GLB is cached before the Canvas mounts
useGLTF.preload('/models/avatar.glb');
