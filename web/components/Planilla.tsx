"use client";

import { useEffect, useRef } from "react";
import type { Punto } from "@/lib/api";
import styles from "./Planilla.module.css";

type Props = {
  jugadas: string[];
  curva: Punto[];
  // Ply highlighted (the position on the board); the scoresheet follows it.
  actual?: number;
  onElegir?: (ply: number) => void;
};

// The scoresheet doubles as the chart's table view: each move with the white-win chance after it.
export function Planilla({ jugadas, curva, actual, onElegir }: Props) {
  const lista = useRef<HTMLDivElement>(null);
  const porPly = new Map(curva.map((p) => [p.ply, p]));

  useEffect(() => {
    const fila = lista.current?.querySelector<HTMLElement>(`[data-ply="${actual}"]`);
    fila?.scrollIntoView({ block: "nearest" });
  }, [actual, jugadas.length]);

  const filas = [];
  for (let i = 0; i < jugadas.length; i += 2) {
    filas.push([i + 1, i + 2]);
  }

  const celda = (ply: number) => {
    if (ply > jugadas.length) return <td colSpan={2} />;
    const punto = porPly.get(ply);
    const contenido = (
      <>
        <span className={styles.san}>{jugadas[ply - 1]}</span>
        <span className={styles.prob}>{punto ? `${Math.round(punto.gana_blancas * 100)}` : ""}</span>
      </>
    );
    return (
      <td colSpan={2} data-ply={ply} className={ply === actual ? styles.actual : undefined}>
        {onElegir ? (
          <button type="button" onClick={() => onElegir(ply)} className={styles.boton}>
            {contenido}
          </button>
        ) : (
          <span className={styles.boton}>{contenido}</span>
        )}
      </td>
    );
  };

  return (
    <div className={styles.planilla} ref={lista}>
      <table>
        <caption>
          Planilla. Al lado de cada jugada, la probabilidad de que ganen las blancas (%) después de ella.
        </caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col" colSpan={2}>
              Blancas
            </th>
            <th scope="col" colSpan={2}>
              Negras
            </th>
          </tr>
        </thead>
        <tbody>
          {filas.length === 0 ? (
            <tr>
              <td colSpan={5} className={styles.vacia}>
                Todavía no hay jugadas.
              </td>
            </tr>
          ) : (
            filas.map(([w, b]) => (
              <tr key={w}>
                <th scope="row">{(w + 1) / 2}</th>
                {celda(w)}
                {celda(b)}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
