"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { Html } from "@react-three/drei";

import type { FileChurn } from "@/lib/api";
import { layoutCity } from "./scene/layout";

interface CityViewProps {
  files: FileChurn[];
}

const DARK = new THREE.Color("#22262b");
const LIGHT = new THREE.Color("#a9b0b9");

/**
 * File "buildings": each of the top churned files is an extruded box —
 * height = log-scaled churn, footprint grows with commit count, shade runs
 * monochrome from dark (quiet) to light (hot).
 */
export default function CityView({ files }: CityViewProps) {
  const layout = useMemo(() => layoutCity(files), [files]);
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const tmpColor = useMemo(() => new THREE.Color(), []);

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const m = new THREE.Matrix4();
    layout.buildings.forEach((b, i) => {
      m.makeScale(b.w, b.h, b.d);
      m.setPosition(b.x, b.h / 2, b.z);
      mesh.setMatrixAt(i, m);
      mesh.setColorAt(i, tmpColor.copy(DARK).lerp(LIGHT, b.shade * 0.9));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [layout, tmpColor]);

  const hoveredB = hovered != null ? layout.buildings[hovered] : undefined;

  return (
    <group>
      {/* Ground slab */}
      <mesh position={[0, -0.06, 0]}>
        <boxGeometry
          args={[
            layout.cols * layout.cell + 4,
            0.12,
            layout.rows * layout.cell + 4,
          ]}
        />
        <meshStandardMaterial color="#101214" roughness={1} metalness={0} />
      </mesh>

      {/* Buildings (single instanced draw call) */}
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, layout.buildings.length]}
        frustumCulled={false}
        onPointerMove={(e) => {
          e.stopPropagation();
          setHovered(e.instanceId ?? null);
          document.body.style.cursor =
            e.instanceId != null ? "pointer" : "auto";
        }}
        onPointerOut={() => {
          setHovered(null);
          document.body.style.cursor = "auto";
        }}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.7} metalness={0.1} />
      </instancedMesh>

      {/* Hover tooltip */}
      {hoveredB && (
        <Html
          position={[hoveredB.x, hoveredB.h + 0.8, hoveredB.z]}
          center
          zIndexRange={[20, 0]}
        >
          <div className="pointer-events-none w-64 rounded border hairline bg-elevated p-2.5">
            <p className="truncate font-mono text-xs text-ink">
              {hoveredB.path}
            </p>
            <p className="mt-1 font-mono text-xs text-ink-faint">
              {hoveredB.churn} lines changed · {hoveredB.commits} commits
            </p>
          </div>
        </Html>
      )}
    </group>
  );
}
