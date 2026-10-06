import { useEffect, useState } from "react";

/**
 * Whether the 3D scene should be swapped for the 2D fallback:
 * small screens, coarse pointers (touch), or no WebGL at all.
 */
export function usePrefer2D(): boolean {
  const [prefer2D, setPrefer2D] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px), (pointer: coarse)");
    let webglOK = true;
    try {
      const canvas = document.createElement("canvas");
      webglOK = !!(
        canvas.getContext("webgl2") || canvas.getContext("webgl")
      );
    } catch {
      webglOK = false;
    }
    const update = () => setPrefer2D(mq.matches || !webglOK);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return prefer2D;
}
