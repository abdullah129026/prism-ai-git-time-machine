"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { Html } from "@react-three/drei";

import type { TimelineNode } from "@/lib/api";
import { commitMatchesFilter, usePrismStore } from "@/lib/store";
import { formatShortDate, type TimelineLayout } from "./scene/layout";

interface CommitGraphProps {
  layout: TimelineLayout;
  /** Full node metadata, keyed lookup for tooltips. */
  nodes: TimelineNode[];
  selectedSha: string | null;
  onSelect: (sha: string | null) => void;
}

const NODE_COLOR = new THREE.Color("#565d66");
const DIM_COLOR = new THREE.Color("#1f2327");
const HOVER_COLOR = new THREE.Color("#aab2bc");
const ACCENT = "#5E6AD2";

/**
 * Commit nodes as instanced spheres on the time axis, with faint
 * parent→child edge lines, a time-axis bar with date ticks, and an
 * accent wireframe ring on the selected commit.
 */
export default function CommitGraph({
  layout,
  nodes,
  selectedSha,
  onSelect,
}: CommitGraphProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const filterQuery = usePrismStore((s) => s.filterQuery);
  const filterAuthor = usePrismStore((s) => s.filterAuthor);

  const metaBySha = useMemo(() => new Map(nodes.map((n) => [n.sha, n])), [nodes]);

  /** Which nodes survive the current filters (for dimming the rest). */
  const matchFlags = useMemo(
    () =>
      layout.nodes.map((p) => {
        const meta = metaBySha.get(p.sha);
        return !meta || commitMatchesFilter(meta, filterQuery, filterAuthor);
      }),
    [layout, metaBySha, filterQuery, filterAuthor],
  );
  const baseColor = (i: number) => (matchFlags[i] ? NODE_COLOR : DIM_COLOR);

  // Place instances + base colors once per layout / filter change.
  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const m = new THREE.Matrix4();
    layout.nodes.forEach((p, i) => {
      m.makeScale(p.radius, p.radius, p.radius);
      m.setPosition(p.x, p.y, p.z);
      mesh.setMatrixAt(i, m);
      mesh.setColorAt(i, baseColor(i));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout, matchFlags]);

  // Hover tint, restored on unhover.
  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh?.instanceColor || hovered == null) return;
    mesh.setColorAt(hovered, HOVER_COLOR);
    mesh.instanceColor.needsUpdate = true;
    return () => {
      mesh.setColorAt(hovered, baseColor(hovered));
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hovered, matchFlags]);

  const edgePositions = useMemo(() => {
    const arr = new Float32Array(layout.edges.length * 6);
    layout.edges.forEach(([a, b], i) => {
      arr[i * 6] = a[0];
      arr[i * 6 + 1] = a[1];
      arr[i * 6 + 2] = a[2];
      arr[i * 6 + 3] = b[0];
      arr[i * 6 + 4] = b[1];
      arr[i * 6 + 5] = b[2];
    });
    return arr;
  }, [layout]);

  const ticks = useMemo(() => {
    if (layout.nodes.length === 0) return [];
    const span = Math.max(1, layout.tMax - layout.tMin);
    return [0, 0.25, 0.5, 0.75, 1].map((f) => ({
      x: -layout.width / 2 + f * layout.width,
      label: formatShortDate(layout.tMin + f * span),
    }));
  }, [layout]);

  const selected = selectedSha ? layout.bySha.get(selectedSha) : undefined;
  const hoveredNode = hovered != null ? layout.nodes[hovered] : undefined;
  const hoveredMeta = hoveredNode ? metaBySha.get(hoveredNode.sha) : undefined;

  return (
    <group>
      {/* Parent → child edges */}
      <lineSegments frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[edgePositions, 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#ffffff" transparent opacity={0.09} />
      </lineSegments>

      {/* Time axis bar + date ticks */}
      <mesh position={[0, -0.9, 0]}>
        <boxGeometry args={[layout.width + 6, 0.06, 0.06]} />
        <meshBasicMaterial color="#2a2e33" />
      </mesh>
      {ticks.map((tick, i) => (
        <Html
          key={i}
          position={[tick.x, -1.7, 0]}
          center
          zIndexRange={[10, 0]}
        >
          <div className="pointer-events-none whitespace-nowrap font-mono text-xs text-ink-faint">
            {tick.label}
          </div>
        </Html>
      ))}

      {/* Commit nodes (single instanced draw call) */}
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, layout.nodes.length]}
        frustumCulled={false}
        onClick={(e) => {
          e.stopPropagation();
          if (e.instanceId != null) {
            onSelect(layout.nodes[e.instanceId].sha);
          }
        }}
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
        <sphereGeometry args={[1, 20, 20]} />
        <meshStandardMaterial roughness={0.55} metalness={0.25} />
      </instancedMesh>

      {/* Selection ring */}
      {selected && (
        <mesh position={[selected.x, selected.y, selected.z]}>
          <sphereGeometry args={[selected.radius + 0.3, 24, 24]} />
          <meshBasicMaterial
            color={ACCENT}
            wireframe
            transparent
            opacity={0.9}
          />
        </mesh>
      )}

      {/* Hover tooltip — bottom edge anchored above the node so the box
          never covers it (keeps the node clickable) */}
      {hoveredNode && hoveredMeta && (
        <Html
          position={[
            hoveredNode.x,
            hoveredNode.y + hoveredNode.radius + 0.9,
            hoveredNode.z,
          ]}
          zIndexRange={[20, 0]}
        >
          <div className="pointer-events-none w-64 -translate-x-1/2 -translate-y-full rounded border hairline bg-elevated p-2.5">
            <p className="font-mono text-xs text-accent">
              {hoveredMeta.sha.slice(0, 7)}
            </p>
            <p className="mt-1 line-clamp-2 text-sm text-ink">
              {hoveredMeta.message.split("\n")[0]}
            </p>
            <p className="mt-1 font-mono text-xs text-ink-faint">
              {hoveredMeta.author} · +{hoveredMeta.additions}/-
              {hoveredMeta.deletions}
            </p>
          </div>
        </Html>
      )}
    </group>
  );
}
