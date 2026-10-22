"use client";

import { useEffect, useRef, useState } from "react";
import type { Punto } from "./api";

export function prefiereMenosMovimiento(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// A number that runs to its new value instead of jumping (instant with reduced motion).
export function useNumeroAnimado(objetivo: number, duracionMs = 550): number {
  const [valor, setValor] = useState(objetivo);
  const desde = useRef(objetivo);

  useEffect(() => {
    if (prefiereMenosMovimiento()) {
      desde.current = objetivo;
      setValor(objetivo);
      return;
    }
    const inicio = performance.now();
    const origen = desde.current;
    let cuadro = 0;
    const paso = (ahora: number) => {
      const t = Math.min(1, (ahora - inicio) / duracionMs);
      const suavizado = 1 - Math.pow(1 - t, 3);
      const actual = origen + (objetivo - origen) * suavizado;
      desde.current = actual;
      setValor(actual);
      if (t < 1) cuadro = requestAnimationFrame(paso);
    };
    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  }, [objetivo, duracionMs]);

  return valor;
}

export type Momento = { ply: number; delta: number };

// Key moments: the plies where the white-win chance moved the most, at least `umbral`.
export function momentosClave(curva: Punto[], cuantos = 3, umbral = 0.1): Momento[] {
  const saltos: Momento[] = [];
  for (let i = 1; i < curva.length; i++) {
    const delta = curva[i].gana_blancas - curva[i - 1].gana_blancas;
    if (Math.abs(delta) >= umbral) saltos.push({ ply: curva[i].ply, delta });
  }
  return saltos.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, cuantos).sort((a, b) => a.ply - b.ply);
}
