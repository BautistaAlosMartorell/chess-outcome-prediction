import type { ReactNode } from "react";
import { Despliegues, type ItemDespliegue } from "./Despliegues";
import { Cifra as NumeroAnimado } from "./Cifra";
import { GraficoAltair } from "./GraficoAltair";
import { Revelar } from "./Revelar";
import styles from "./Tallo.module.css";

export type Cifra = {
  // The number, already formatted.
  valor: string;
  // What it counts, in one line.
  texto: string;
};

type Props = {
  id: string;
  // Which stage it closes: "Los datos", "Lo que encontramos", "El modelo".
  etapa: string;
  // The question the section answers, short and large: it is what a reader scans for.
  pregunta: string;
  // The answer, stated as a finding with its numbers (not the topic).
  titulo: string;
  // Up to three numbers that carry the answer.
  cifras?: Cifra[];
  // Optional: a section can make its case with text and tables alone.
  grafico?: string;
  descripcionGrafico?: string;
  // Anything that helps read the chart (a legend of piece values, a how-to-read note), above it.
  antesDelGrafico?: ReactNode;
  // What the chart shows, in plain words.
  queMirar: ReactNode;
  // Why the chart is here: which question it answers and why that matters.
  porQue?: ReactNode;
  // Extra charts, each with its own short caption, after the main one.
  extras?: { src: string; descripcion: string; leyenda: ReactNode }[];
  // The technical evidence, collapsed by default.
  evidencia: ReactNode;
};

// One section of the guided part: a question, its answer, the chart that proves it and how we know.
export function SeccionTallo({
  id,
  etapa,
  pregunta,
  titulo,
  cifras,
  grafico,
  descripcionGrafico,
  antesDelGrafico,
  queMirar,
  porQue,
  extras,
  evidencia,
}: Props) {
  const items: ItemDespliegue[] = [
    { id: "ver", titulo: "Qué se ve", icono: "ver", contenido: <div className={styles.bloque}>{queMirar}</div> },
    ...(porQue ? [{ id: "porque", titulo: "Por qué está acá", icono: "porque" as const, contenido: <div className={styles.bloque}>{porQue}</div> }] : []),
    { id: "prueba", titulo: "Cómo lo sabemos", icono: "prueba", contenido: <div className={styles.evidencia}>{evidencia}</div> },
  ];
  return (
    <section className={styles.seccion} aria-labelledby={id} id={`seccion-${id}`}>
      <Revelar className={styles.encabezado}>
        <p className={styles.etapa}>{etapa}</p>
        <h2 id={id} className={styles.pregunta}>
          {pregunta}
        </h2>
      </Revelar>
      {cifras?.length ? (
        <dl className={styles.cifras}>
          {cifras.map((c) => (
            <div key={c.texto}>
              <dd className="cifra">
                <NumeroAnimado valor={c.valor} />
              </dd>
              <dt>{c.texto}</dt>
            </div>
          ))}
        </dl>
      ) : null}
      {antesDelGrafico}
      {grafico ? <GraficoAltair src={grafico} descripcion={descripcionGrafico ?? ""} /> : null}
      <p className={styles.respuesta}>{titulo}</p>
      {extras?.map((e) => (
        <div key={e.src} className={styles.extra}>
          <GraficoAltair src={e.src} descripcion={e.descripcion} />
          <Despliegues
            items={[{ id: "ver", titulo: "Cómo leer este gráfico", icono: "ver", contenido: <div className={styles.bloque}>{e.leyenda}</div> }]}
          />
        </div>
      ))}
      <Despliegues items={items} />
    </section>
  );
}

// A chapter with no chart of its own: same header as the others, the content is up to the caller.
export function SeccionTexto({
  id,
  etapa,
  pregunta,
  titulo,
  children,
}: {
  id: string;
  etapa: string;
  pregunta: string;
  titulo: string;
  children: ReactNode;
}) {
  return (
    <section className={styles.seccion} aria-labelledby={id} id={`seccion-${id}`}>
      <p className={styles.etapa}>{etapa}</p>
      <h2 id={id} className={styles.pregunta}>
        {pregunta}
      </h2>
      <p className={styles.respuesta}>{titulo}</p>
      {children}
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
