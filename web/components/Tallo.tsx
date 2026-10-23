import type { ReactNode } from "react";
import { GraficoAltair } from "./GraficoAltair";
import styles from "./Tallo.module.css";

type Props = {
  id: string;
  // Which stage it closes: "Los datos", "Lo que encontramos", "El modelo".
  etapa: string;
  // A title that states the finding, not the topic.
  titulo: string;
  grafico: string;
  descripcionGrafico: string;
  // A few lines on what to look at in the chart.
  queMirar: ReactNode;
  // The technical evidence, collapsed by default.
  evidencia: ReactNode;
};

// One section of the guided part: a claim, the chart that proves it and how we know.
export function SeccionTallo({ id, etapa, titulo, grafico, descripcionGrafico, queMirar, evidencia }: Props) {
  return (
    <section className={styles.seccion} aria-labelledby={id}>
      <p className={styles.etapa}>{etapa}</p>
      <h2 id={id} className={styles.titulo}>
        {titulo}
      </h2>
      <GraficoAltair src={grafico} descripcion={descripcionGrafico} />
      <div className={styles.queMirar}>{queMirar}</div>
      <details className={styles.comoLoSabemos}>
        <summary>Cómo lo sabemos</summary>
        <div className={styles.evidencia}>{evidencia}</div>
      </details>
    </section>
  );
}

type Columna<T> = { titulo: string; valor: (fila: T) => ReactNode; numerica?: boolean };

// A small table for the evidence: numbers right-aligned, header in the soft color.
export function Tabla<T>({ filas, columnas, resaltar }: { filas: T[]; columnas: Columna<T>[]; resaltar?: (fila: T) => boolean }) {
  return (
    <div className={styles.tablaScroll}>
      <table className={styles.tabla}>
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c.titulo} className={c.numerica ? styles.numerica : undefined} scope="col">
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, i) => (
            <tr key={i} className={resaltar?.(fila) ? styles.resaltada : undefined}>
              {columnas.map((c) => (
                <td key={c.titulo} className={c.numerica ? styles.numerica : undefined}>
                  {c.valor(fila)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
