"use client";

import { useEffect, useState } from "react";
import { PARTIDA_EJEMPLO } from "@/lib/ejemplo";
import { prefiereMenosMovimiento } from "@/lib/movimiento";
import { Barra } from "./Barra";
import styles from "./DemoEnVivo.module.css";

const PASO_MS = 700;
const PAUSA_FINAL = 4; // frames held on the last move before starting over

const ANCHO = 520;
const ALTO = 96;

// The home page's live demo: a real game replays itself, ply by ply, in a loop.
export function DemoEnVivo() {
  const total = PARTIDA_EJEMPLO.length;
  const [cuadro, setCuadro] = useState(0);

  useEffect(() => {
    if (prefiereMenosMovimiento()) {
      setCuadro(total - 1);
      return;
    }
    const intervalo = window.setInterval(() => setCuadro((c) => (c + 1) % (total + PAUSA_FINAL)), PASO_MS);
    return () => window.clearInterval(intervalo);
  }, [total]);

  const ply = Math.min(cuadro, total - 1);
  const [blancas, tablas, negras] = PARTIDA_EJEMPLO[ply];
  const x = (i: number) => (i / (total - 1)) * ANCHO;
  const y = (p: number) => ALTO - p * ALTO;
  const visibles = PARTIDA_EJEMPLO.slice(0, ply + 1);
  const banda = (desde: (p: number[]) => number, hasta: (p: number[]) => number) =>
    visibles.length < 2
      ? ""
      : `M${visibles.map((p, i) => `${x(i)},${y(hasta(p))}`).join("L")}L${visibles
          .map((p, i) => `${x(i)},${y(desde(p))}`)
          .reverse()
          .join("L")}Z`;

  return (
    <figure className={styles.demo}>
      <div className={styles.encabezado}>
        <span className={styles.envivo}>
          <span className={styles.punto} aria-hidden="true" /> Partida real de blitz
        </span>
        <span className="cifra">{ply === 0 ? "Antes de mover" : `Jugada ${Math.ceil(ply / 2)}`}</span>
      </div>
      <Barra valores={{ blancas, tablas, negras }} tamano="grande" />
      <svg className={styles.curva} viewBox={`0 0 ${ANCHO} ${ALTO}`} preserveAspectRatio="none" aria-hidden="true">
        <rect width={ANCHO} height={ALTO} className={styles.fondoCurva} />
        <path d={banda(() => 0, (p) => p[0])} className={styles.blancas} />
        <path d={banda((p) => p[0], (p) => p[0] + p[1])} className={styles.tablas} />
        <path d={banda((p) => p[0] + p[1], () => 1)} className={styles.negras} />
        <line x1={0} x2={ANCHO} y1={ALTO / 2} y2={ALTO / 2} className={styles.mitad} />
      </svg>
      <figcaption className={styles.pie}>
        {ply === total - 1
          ? "Ganaron las negras: las blancas abandonaron."
          : "Cada jugada mueve la barra: quién gana según el modelo, con lo que se ve en ese momento."}
      </figcaption>
    </figure>
  );
}
