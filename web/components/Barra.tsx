"use client";

import { useEffect, useRef, useState } from "react";
import { useNumeroAnimado } from "@/lib/movimiento";
import styles from "./Barra.module.css";

export type Probabilidades = { blancas: number; tablas: number; negras: number };

type Props = {
  valores: Probabilidades | null;
  tamano?: "grande" | "normal" | "compacto";
  // Show a "▲ n" chip on the side that gained after a move.
  mostrarCambio?: boolean;
};

// Changes smaller than this are noise between consecutive plies; they get no chip.
const CAMBIO_VISIBLE = 0.04;

export function Barra({ valores, tamano = "normal", mostrarCambio = true }: Props) {
  const blancas = useNumeroAnimado(valores ? valores.blancas * 100 : 50);
  const tablas = useNumeroAnimado(valores ? valores.tablas * 100 : 0);
  const negras = useNumeroAnimado(valores ? valores.negras * 100 : 50);

  const anterior = useRef<Probabilidades | null>(null);
  const [cambio, setCambio] = useState<{ lado: "blancas" | "negras"; puntos: number; id: number } | null>(null);

  useEffect(() => {
    const previo = anterior.current;
    anterior.current = valores;
    if (!mostrarCambio || !previo || !valores) return;
    const delta = valores.blancas - previo.blancas;
    const deltaNegras = valores.negras - previo.negras;
    const lado = Math.abs(delta) >= Math.abs(deltaNegras) ? (delta > 0 ? "blancas" : "negras") : deltaNegras > 0 ? "negras" : "blancas";
    const puntos = Math.round(Math.abs(lado === "blancas" ? delta : deltaNegras) * 100);
    if (puntos / 100 >= CAMBIO_VISIBLE) setCambio({ lado, puntos, id: Date.now() });
  }, [valores, mostrarCambio]);

  const descripcion = valores
    ? `Blancas ${Math.round(valores.blancas * 100)} %, tablas ${Math.round(valores.tablas * 100)} %, negras ${Math.round(valores.negras * 100)} %`
    : "Todavía no hay predicción";

  return (
    <div className={`${styles.barra} ${tamano === "normal" ? "" : styles[tamano]}`}>
      <div className={styles.cifras} aria-hidden="true">
        <span className={styles.lado}>
          <span className="cifra">{valores ? Math.round(blancas) : "–"}</span>
          <span className={styles.porciento}>%</span>
          {cambio?.lado === "blancas" ? (
            <span key={cambio.id} className={styles.cambio}>
              ▲{cambio.puntos}
            </span>
          ) : null}
        </span>
        <span className={styles.tablas}>
          <span className="cifra">{valores ? Math.round(tablas) : "–"}</span> % tablas
        </span>
        <span className={`${styles.lado} ${styles.ladoNegras}`}>
          {cambio?.lado === "negras" ? (
            <span key={cambio.id} className={styles.cambio}>
              ▲{cambio.puntos}
            </span>
          ) : null}
          <span className="cifra">{valores ? Math.round(negras) : "–"}</span>
          <span className={styles.porciento}>%</span>
        </span>
      </div>
      <div className={styles.franja} role="img" aria-label={descripcion}>
        <div className={styles.segBlancas} style={{ flexBasis: `${valores ? valores.blancas * 100 : 50}%` }} />
        <div className={styles.segTablas} style={{ flexBasis: `${valores ? valores.tablas * 100 : 0}%` }} />
        <div className={styles.segNegras} style={{ flexBasis: `${valores ? valores.negras * 100 : 50}%` }} />
        <span className={styles.mitad} aria-hidden="true" />
      </div>
    </div>
  );
}
