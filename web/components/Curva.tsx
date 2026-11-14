"use client";

import { useEffect, useRef, useState } from "react";
import type { Punto } from "@/lib/api";
import type { Momento } from "@/lib/movimiento";
import styles from "./Curva.module.css";

type Props = {
  curva: Punto[];
  // Ply currently shown on the board (replay) or the latest one (live game).
  actual?: number;
  momentos?: Momento[];
  onElegir?: (ply: number) => void;
  // Changing this key replays the left-to-right reveal (a newly opened game).
  revelar?: string;
  // The home page demo shows the chart without its frame and title.
  compacta?: boolean;
};

// The Altair spec written by src/build_app.py (app_charts.curva_partida): it has no data.
const SPEC = "/app/graficos/curva.json";
// The x axis starts this wide so the first moves don't stretch across the whole chart (same as the spec).
const PLIES_MINIMOS = 40;

type Vista = {
  data: (nombre: string, valores: object[]) => Vista;
  signal: { (nombre: string): unknown; (nombre: string, valor: unknown): Vista };
  runAsync: () => Promise<Vista>;
  addEventListener: (tipo: string, handler: () => void) => void;
  finalize: () => void;
};

let specCargada: Promise<object> | null = null;
function cargarSpec() {
  specCargada ??= fetch(SPEC).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))));
  specCargada.catch(() => {
    specCargada = null; // let the next mount retry
  });
  return specCargada;
}

function describir(m: Momento) {
  const puntos = Math.round(Math.abs(m.delta) * 100);
  return `Jugada ${Math.ceil(m.ply / 2)}: las blancas ${m.delta > 0 ? "suben" : "bajan"} ${puntos} puntos`;
}

// The hovered ply, as Vega-Lite resolves a point selection on "ply": {ply: [n]}.
function plyElegido(valor: unknown): number | undefined {
  const ply = (valor as { ply?: unknown } | null)?.ply;
  const n = Array.isArray(ply) ? ply[0] : ply;
  return typeof n === "number" ? n : undefined;
}

// Draws the Altair chart once and, on every move, only swaps its data.
export function Curva({ curva, actual, momentos = [], onElegir, revelar, compacta = false }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [vista, setVista] = useState<Vista | null>(null);
  const [error, setError] = useState(false);
  const elegir = useRef(onElegir);
  elegir.current = onElegir;

  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    let vigente = true;
    let creada: Vista | undefined;
    Promise.all([cargarSpec(), import("vega-embed")])
      .then(([spec, { default: embed }]) => {
        if (!vigente) return;
        return embed(el, spec as never, {
          actions: false,
          renderer: "svg",
          // The chart starts with empty datasets and gets its data move by move: Vega warns "Infinite
          // extent" on every empty draw. Errors still show; only that warning is left out.
          logLevel: 1,
          config: { font: getComputedStyle(document.body).fontFamily },
        }).then((resultado) => {
          creada = resultado.view as unknown as Vista;
          if (!vigente) return creada.finalize();
          creada.addEventListener("click", () => {
            const ply = plyElegido(creada?.signal("hover"));
            if (ply !== undefined) elegir.current?.(ply);
          });
          setVista(creada);
        });
      })
      .catch(() => vigente && setError(true));
    return () => {
      vigente = false;
      creada?.finalize();
    };
  }, []);

  useEffect(() => {
    if (!vista) return;
    const ultimo = curva.length ? curva[curva.length - 1].ply : 0;
    const visibles = curva.length >= 2 ? momentos : [];
    vista
      .data("curva", curva)
      .data("momentos", visibles.map((m) => ({ ply: m.ply, descripcion: describir(m) })))
      .data("actual", actual !== undefined && curva.length >= 2 ? [{ ply: actual }] : [])
      .signal("ply_maximo", Math.max(ultimo, PLIES_MINIMOS));
    vista.runAsync();
  }, [vista, curva, actual, momentos]);

  // A new key replays the reveal: restart the CSS animation on the same element.
  useEffect(() => {
    const el = contenedor.current;
    if (!el || !revelar) return;
    el.classList.remove(styles.revelado);
    void el.offsetWidth;
    el.classList.add(styles.revelado);
  }, [revelar]);

  return (
    <figure className={compacta ? styles.compacta : styles.figura}>
      {compacta ? null : (
        <figcaption className={styles.titulo}>
          <span>Cómo se movió la partida</span>
          {momentos.length ? <span className={styles.nota}>Línea punteada: momento clave</span> : null}
        </figcaption>
      )}
      <div className={styles.lienzo}>
        <div
          ref={contenedor}
          className={`${styles.grafico} ${onElegir ? styles.clicable : ""}`}
          role="img"
          aria-label="Área apilada: probabilidad de que ganen las blancas, de tablas y de que ganen las negras en cada jugada."
        />
        {curva.length < 2 && !error ? <p className={styles.vacioTexto}>La curva se dibuja a medida que avanza la partida.</p> : null}
        {error ? <p className={styles.vacioTexto}>No se pudo cargar el gráfico. Probá recargar la página.</p> : null}
      </div>
    </figure>
  );
}
