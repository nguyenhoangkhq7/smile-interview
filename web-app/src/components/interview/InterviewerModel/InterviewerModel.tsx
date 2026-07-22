'use client';

import { useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';

interface AudioAnalyserLike {
  frequencyBinCount: number;
  getByteFrequencyData(array: Uint8Array): void;
}

interface InterviewerModelProps {
  analyser?: AudioAnalyserLike | null;
  position?: [number, number, number];
  scale?: [number, number, number];
  rotation?: [number, number, number];
  isListening?: boolean;
  isThinking?: boolean;
}

interface MorphTargetRef {
  mesh: THREE.Mesh;
  index: number;
  name: string;
}

/**
 * InterviewerModel
 *
 * Loads a ReadyPlayerMe-compatible GLB avatar and drives animations.
 */
export function InterviewerModel({
  analyser,
  position = [0, 0, 0],
  scale    = [1, 1, 1],
  rotation = [0, 0, 0],
  isListening = false,
  isThinking = false,
}: InterviewerModelProps) {
  const { scene } = useGLTF('/models/avatar.glb') as unknown as { scene: THREE.Group };

  // ── All animation state lives in refs — zero re-renders ─────────────────
  const groupRef = useRef<THREE.Group | null>(null);

  // Per-band morph target buckets
  const jawTargetsRef  = useRef<MorphTargetRef[]>([]); // Low band  → jaw/open vowels (A, O, U)
  const midTargetsRef  = useRef<MorphTargetRef[]>([]); // Mid band  → E-vowels, consonants (CH, E)
  const highTargetsRef = useRef<MorphTargetRef[]>([]); // High band → sibilants (S, I, FF)
  const browTargetsRef = useRef<MorphTargetRef[]>([]); // Eyebrow raise targets
  const blinkTargetsRef = useRef<MorphTargetRef[]>([]); // Eyelid blink targets

  // Head / Neck bone for nodding
  const headBoneRef = useRef<THREE.Object3D | null>(null);
  const originalHeadRotationXRef = useRef<number>(0);

  // Frequency data buffer (lazily allocated)
  const freqDataRef = useRef<Uint8Array | null>(null);

  // Smoothed influence values per animation channel
  const inf = useRef<{ jaw: number; mid: number; high: number; brow: number }>({ jaw: 0, mid: 0, high: 0, brow: 0 });

  // Slow volume envelope (for brow raise and head nod) — exponential smoothing
  const volumeEnvRef = useRef<number>(0);

  // Blink state machine
  const blink = useRef<{ phase: string; timer: number; nextTime: number; value: number }>({ phase: 'idle', timer: 0, nextTime: 2.0, value: 0 });

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

    const found: {
      jaw: MorphTargetRef[];
      mid: MorphTargetRef[];
      high: MorphTargetRef[];
      brow: MorphTargetRef[];
      blink: MorphTargetRef[];
    } = { jaw: [], mid: [], high: [], brow: [], blink: [] };

    scene.traverse((node: THREE.Object3D) => {
      const mesh = node as THREE.Mesh;
      if (!mesh.isMesh || !mesh.morphTargetDictionary || !mesh.morphTargetInfluences) return;

      const dict = mesh.morphTargetDictionary;

      console.log('👉 TARGET MESH FOUND:', mesh.name, dict);

      const findFirst = (names: string[]): MorphTargetRef | null => {
        for (const name of names) {
          if (dict[name] !== undefined) return { mesh: mesh, index: dict[name], name };
        }
        return null;
      };

      const findAll = (names: string[]): MorphTargetRef[] => {
        const res: MorphTargetRef[] = [];
        for (const name of names) {
          if (dict[name] !== undefined) res.push({ mesh: mesh, index: dict[name], name });
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
    scene.traverse((node: THREE.Object3D) => {
      if (!headBoneRef.current && (node.type === 'Bone' || node.name.toLowerCase().includes('head') || node.name.toLowerCase().includes('neck'))) {
        const n = node.name.toLowerCase();
        if (n.includes('head') || n.includes('neck')) {
          headBoneRef.current = node;
          originalHeadRotationXRef.current = node.rotation.x;
          console.info(
            '[InterviewerModel] Head/neck bone found for alignment:', 
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
      if (freqDataRef.current) {
        analyser.getByteFrequencyData(freqDataRef.current as Uint8Array<ArrayBuffer>);
      }
      const bins = freqDataRef.current || new Uint8Array(0);

      const bandAvg = (from: number, to: number) => {
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
      const norm = (energy: number, maxClamp: number) =>
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

      const applyMorphs = (targets: MorphTargetRef[], value: number) => {
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

      const baseRotationX  = originalHeadRotationXRef.current || 0;
      let tiltCorrection = THREE.MathUtils.degToRad(8.5);
      
      // Attentive tilt when listening
      if (isListening) {
        tiltCorrection += THREE.MathUtils.degToRad(4.0); // Tilt slightly more forward
      }
      
      const nodPitch       = (volumeEnvRef.current - 0.25) * 0.06;

      bone.rotation.x = THREE.MathUtils.lerp(
        bone.rotation.x,
        baseRotationX + tiltCorrection + nodPitch,
        1 - Math.pow(0.05, delta)
      );

      // Yaw: gentle idle sway
      // If thinking, sway is slightly more pronounced and slower (confused/pondering look)
      const swayFreq = isThinking ? 0.25 : 0.44;
      const swayAmp = isThinking ? 0.045 : 0.015;
      const swayYaw = Math.sin(elapsed * swayFreq) * swayAmp;
      
      bone.rotation.y = THREE.MathUtils.lerp(
        bone.rotation.y,
        swayYaw,
        1 - Math.pow(0.1, delta)
      );

      // Roll: subtle head roll sway when thinking
      const rollFreq = 0.35;
      const rollAmp = isThinking ? 0.05 : 0;
      const rollAngle = Math.sin(elapsed * rollFreq) * rollAmp;
      bone.rotation.z = THREE.MathUtils.lerp(
        bone.rotation.z,
        rollAngle,
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
            // Reduce blink frequency when listening to show focus
            b.nextTime = (2.5 + Math.random() * 3.0) * (isListening ? 2 : 1);
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
