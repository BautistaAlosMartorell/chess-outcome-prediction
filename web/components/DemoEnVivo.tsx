"use client";

import { useEffect, useState } from "react";
import { PARTIDA_EJEMPLO } from "@/lib/ejemplo";
import { prefiereMenosMovimiento } from "@/lib/movimiento";
import { Barra } from "./Barra";
import { Curva } from "./Curva";
import styles from "./DemoEnVivo.module.css";

const PASO_MS = 700;

// The home page demo plays once; users can pause or replay it.
export function DemoEnVivo() {
  const total = PARTIDA_EJEMPLO.length;
  const [cuadro, setCuadro] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(true);

  useEffect(() => {
    if (prefiereMenosMovimiento()) { setCuadro(total - 1); setReproduciendo(false); }
  }, [total]);

  useEffect(() => {
    if (!reproduciendo) return;
    if (cuadro >= total - 1) { setReproduciendo(false); return; }
    const intervalo = window.setTimeout(() => setCuadro(cuadro + 1), PASO_MS);
    return () => window.clearTimeout(intervalo);
  }, [total, reproduciendo, cuadro]);

  const ply = Math.min(cuadro, total - 1);
  const [blancas, tablas, negras] = PARTIDA_EJEMPLO[ply];
  const visibles = PARTIDA_EJEMPLO.slice(0, ply + 1).map(([gana_blancas, empate, gana_negras], i) => ({
    ply: i, gana_blancas, empate, gana_negras,
  }));

  return (
    <figure className={styles.demo}>
      <div className={styles.encabezado}>
        <span className={styles.envivo}>
          <span className={styles.punto} aria-hidden="true" /> Partida real de blitz
        </span>
        <span className="cifra">{ply === 0 ? "Antes de mover" : `Jugada ${Math.ceil(ply / 2)}`}</span>
      </div>
      <Barra valores={{ blancas, tablas, negras }} tamano="grande" />
      <Curva curva={visibles} actual={ply} compacta />
      <button type="button" className={styles.control} onClick={() => {
        if (cuadro >= total - 1) setCuadro(0);
        setReproduciendo(!reproduciendo);
      }}>{reproduciendo ? "Pausar demo" : cuadro >= total - 1 ? "Repetir demo" : "Continuar demo"}</button>
      <figcaption className={styles.pie}>
        {ply === total - 1
          ? "Ganaron las negras: las blancas abandonaron."
          : "Cada jugada mueve la barra: quién gana según el modelo, con lo que se ve en ese momento."}
      </figcaption>
    </figure>
  );
}
