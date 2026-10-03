"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

import type { TimelineResponse } from "@/lib/api";
import type { ViewMode } from "@/lib/store";
import CommitGraph from "./CommitGraph";
import CityView from "./CityView";
import type { TimelineLayout } from "./scene/layout";

interface Scene3DProps {
  layout: TimelineLayout;
  timeline: TimelineResponse;
  viewMode: ViewMode;
  selectedSha: string | null;
  onSelect: (sha: string | null) => void;
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

interface ControlsLike {
  target: THREE.Vector3;
  update: () => void;
}

/**
 * Eased camera fly-through: when the selected commit changes, the camera
 * rig translates to the node over ~0.7s with cubic easing. The scene starts
 * still — no auto-play on load. A user grab (pointerdown) cancels a flight.
 */
function CameraRig({ focus }: { focus: THREE.Vector3 | null }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as ControlsLike | null;
  const anim = useRef<{
    t: number;
    fromTarget: THREE.Vector3;
    toTarget: THREE.Vector3;
    fromCam: THREE.Vector3;
    toCam: THREE.Vector3;
  } | null>(null);
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return; // start still
    }
    if (!focus || !controls) return;
    const toTarget = focus.clone();
    const delta = toTarget.clone().sub(controls.target);
    anim.current = {
      t: 0,
      fromTarget: controls.target.clone(),
      toTarget,
      fromCam: camera.position.clone(),
      toCam: camera.position.clone().add(delta),
    };
  }, [focus, controls, camera]);

  useEffect(() => {
    const cancel = () => {
      anim.current = null;
    };
    window.addEventListener("pointerdown", cancel);
    return () => window.removeEventListener("pointerdown", cancel);
  }, []);

  useFrame((_, dt) => {
    const a = anim.current;
    if (!a || !controls) return;
    a.t = Math.min(1, a.t + dt / 0.7);
    const k = easeInOutCubic(a.t);
    controls.target.lerpVectors(a.fromTarget, a.toTarget, k);
    camera.position.lerpVectors(a.fromCam, a.toCam, k);
    controls.update();
    if (a.t >= 1) anim.current = null;
  });

  return null;
}

/** The R3F 3D explorer: commit nodes on a time axis, or file buildings. */
export default function Scene3D({
  layout,
  timeline,
  viewMode,
  selectedSha,
  onSelect,
}: Scene3DProps) {
  const focus = useMemo(() => {
    const p = selectedSha ? layout.bySha.get(selectedSha) : undefined;
    return p ? new THREE.Vector3(p.x, p.y, p.z) : null;
  }, [selectedSha, layout]);

  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 30, layout.width * 0.55 + 24], fov: 42 }}
      gl={{ antialias: true }}
      onPointerMissed={() => onSelect(null)}
    >
      <color attach="background" args={["#08090A"]} />
      <fog attach="fog" args={["#08090A", 110, 260]} />
      <ambientLight intensity={0.85} />
      <directionalLight position={[24, 36, 12]} intensity={1.35} />

      <Grid
        position={[0, -1.05, 0]}
        args={[10, 10]}
        cellSize={1.6}
        cellThickness={0.6}
        cellColor="#14171a"
        sectionSize={8}
        sectionThickness={1}
        sectionColor="#1e2226"
        fadeDistance={170}
        fadeStrength={2.2}
        infiniteGrid
      />

      {viewMode === "timeline" ? (
        <CommitGraph
          layout={layout}
          nodes={timeline.nodes}
          selectedSha={selectedSha}
          onSelect={onSelect}
        />
      ) : (
        <CityView files={timeline.file_churn} />
      )}

      <CameraRig focus={viewMode === "timeline" ? focus : null} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        maxPolarAngle={Math.PI / 2.05}
        minDistance={6}
        maxDistance={240}
      />
    </Canvas>
  );
}
