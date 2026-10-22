"use client";

import { useEffect, useRef } from "react";
import type { Punto } from "@/lib/api";
import type { Momento } from "@/lib/movimiento";
import styles from "./Planilla.module.css";

type Props = {
  jugadas: string[];
  curva: Punto[];
  // Ply highlighted (the position on the board); the scoresheet follows it.
  actual?: number;
  momentos?: Momento[];
  onElegir?: (ply: number) => void;
};

// The scoresheet doubles as the chart's table view: each move with the white-win chance after it.
export function Planilla({ jugadas, curva, actual, momentos = [], onElegir }: Props) {
  const lista = useRef<HTMLDivElement>(null);
  const porPly = new Map(curva.map((p) => [p.ply, p]));
  const clave = new Map(momentos.map((m) => [m.ply, m]));

  const anterior = useRef<number | undefined>(undefined);
  useEffect(() => {
    const contenedor = lista.current;
    const celda = contenedor?.querySelector<HTMLElement>(`[data-ply="${actual}"]`);
    const previo = anterior.current;
    anterior.current = actual;
    if (!contenedor || !celda) return;
    // Scroll the list itself, never the page: center the current move. One step glides; a jump is instant.
    const desplazamiento = celda.getBoundingClientRect().top - contenedor.getBoundingClientRect().top;
    const arriba = contenedor.scrollTop + desplazamiento - contenedor.clientHeight / 2;
    const salto = previo === undefined || actual === undefined || Math.abs(actual - previo) > 2;
    contenedor.scrollTo({ top: Math.max(0, arriba), behavior: salto ? "auto" : "smooth" });
  }, [actual, jugadas.length]);

  const filas = [];
  for (let i = 0; i < jugadas.length; i += 2) filas.push([i + 1, i + 2]);

  const celda = (ply: number) => {
    if (ply > jugadas.length) return <td />;
    const punto = porPly.get(ply);
    const momento = clave.get(ply);
    const contenido = (
      <>
        <span className={styles.san}>{jugadas[ply - 1]}</span>
        {momento ? (
          <span className={styles.salto} title="Momento clave: la jugada que más movió la probabilidad">
            {momento.delta > 0 ? "▲" : "▼"}
            {Math.round(Math.abs(momento.delta) * 100)}
          </span>
        ) : null}
        <span className={styles.prob}>{punto ? Math.round(punto.gana_blancas * 100) : ""}</span>
      </>
    );
    const clases = [ply === actual ? styles.actual : "", momento ? styles.clave : ""].join(" ");
    return (
      <td data-ply={ply} className={clases}>
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
    <div className={styles.planilla}>
      <div className={styles.cabecera}>
        <span>Planilla</span>
        <span className={styles.ayuda}>% de que ganen las blancas después de cada jugada</span>
      </div>
      <div className={styles.lista} ref={lista}>
        <table>
          <thead>
            <tr>
              <th scope="col">
                <span className={styles.oculto}>Número</span>
              </th>
              <th scope="col">Blancas</th>
              <th scope="col">Negras</th>
            </tr>
          </thead>
          <tbody>
            {filas.length === 0 ? (
              <tr>
                <td colSpan={3} className={styles.vacia}>
                  Las jugadas aparecen acá.
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
    </div>
  );
}
