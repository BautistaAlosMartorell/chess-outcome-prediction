"use client";

import type { ReactNode } from "react";
import { useVisto } from "@/lib/useVisto";
import styles from "./Revelar.module.css";

// Brings a block in once, when it reaches the screen: it rises a few pixels while it fades in.
// `retraso` staggers siblings that appear as a list (keep the total under half a second).
export function Revelar({ children, retraso = 0, className }: { children: ReactNode; retraso?: number; className?: string }) {
  const { ref, listo, visto } = useVisto<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={`${styles.revelar} ${className ?? ""}`}
      data-listo={listo || undefined}
      data-visto={visto || undefined}
      style={retraso ? ({ "--retraso": `${retraso}ms` } as React.CSSProperties) : undefined}
    >
      {children}
    </div>
  );
}
