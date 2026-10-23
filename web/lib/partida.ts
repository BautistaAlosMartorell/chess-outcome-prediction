import { Chess } from "chess.js";
import type { Analisis, Punto } from "./api";

export function posicionEn(jugadas: string[], ply: number) {
  const chess = new Chess();
  let ultima: { desde: string; hasta: string } | null = null;
  for (const san of jugadas.slice(0, ply)) {
    const move = chess.move(san);
    ultima = { desde: move.from, hasta: move.to };
  }
  let jaque: string | null = null;
  if (chess.inCheck())
    for (const fila of chess.board())
      for (const c of fila) {
        if (c?.type === "k" && c.color === chess.turn()) jaque = c.square;
      }
  return { fen: chess.fen(), ultima, jaque };
}

export function relojesEn(analisis: Analisis, ply: number) {
  const ultimo = (paridad: number) => {
    for (let k = ply; k >= 1; k--)
      if (k % 2 === paridad) {
        const value = analisis.relojes_seg[k - 1];
        return value == null ? null : value * 1000;
      }
    return analisis.partida.tiempo_base_seg * 1000;
  };
  return { blancas: ultimo(1), negras: ultimo(0) };
}

export const RESULTADOS = ["Gana Blancas", "Empate", "Gana Negras"] as const;

export function controlTiempo(base: number, incremento: number): string {
  const inicial = base % 60 === 0 ? `${base / 60} min` : `${base.toLocaleString("es-AR")} s`;
  return `${inicial} + ${incremento.toLocaleString("es-AR")} s`;
}
export type Resultado = (typeof RESULTADOS)[number];
export const NOMBRES = {
  "Gana Blancas": "Blancas",
  Empate: "Tablas",
  "Gana Negras": "Negras",
};
export function favorito(punto: Punto): Resultado {
  const values = [punto.gana_blancas, punto.empate, punto.gana_negras];
  return RESULTADOS[values.indexOf(Math.max(...values))];
}
