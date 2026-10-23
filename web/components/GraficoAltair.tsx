"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./GraficoAltair.module.css";

type Spec = Record<string, unknown> & { vconcat?: Record<string, unknown>[] };

type Props = {
  // A Vega-Lite spec written by src/build_app.py (made with Altair), under web/public.
  src: string;
  // What the chart shows, for screen readers.
  descripcion: string;
};

// Vega-Lite sizes single and layered views to their container, but not the views of a
// vconcat (Explorá): those get the container's width here, before drawing.
function ajustarAncho(spec: Spec, ancho: number): Spec {
  if (!spec.vconcat) return spec;
  return { ...spec, vconcat: spec.vconcat.map((vista) => ({ ...vista, width: Math.max(260, ancho - 90) })) };
}

// Draws an Altair chart as is: data, encodings and colors all come from the spec.
export function GraficoAltair({ src, descripcion }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [ancho, setAncho] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    let vigente = true;
    fetch(src)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
      .then((s: Spec) => vigente && setSpec(s))
      .catch(() => vigente && setError(true));
    return () => {
      vigente = false;
    };
  }, [src]);

  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    // Only the width matters; rounding avoids redrawing on sub-pixel changes.
    const observer = new ResizeObserver(([entry]) => setAncho(Math.round(entry.contentRect.width / 20) * 20));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = contenedor.current;
    if (!el || !spec || ancho === 0) return;
    let finalizar: (() => void) | undefined;
    let vigente = true;
    import("vega-embed").then(({ default: embed }) => {
      if (!vigente) return;
      const fuente = getComputedStyle(document.body).fontFamily;
      embed(el, ajustarAncho(spec, ancho) as never, {
        actions: false,
        renderer: "svg",
        // The page's font, which next/font names at build time: the spec can't know it.
        config: { font: fuente },
      })
        .then((resultado) => {
          if (vigente) finalizar = () => resultado.finalize();
          else resultado.finalize();
        })
        .catch(() => setError(true));
    });
    return () => {
      vigente = false;
      finalizar?.();
    };
  }, [spec, ancho]);

  return (
    <figure className={styles.figura}>
      <div ref={contenedor} className={styles.grafico} role="img" aria-label={descripcion} />
      {error ? <p className={styles.error}>No se pudo cargar el gráfico. Probá recargar la página.</p> : null}
      {!spec && !error ? <p className={styles.cargando}>Cargando el gráfico…</p> : null}
    </figure>
  );
}
