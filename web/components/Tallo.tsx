import type { ReactNode } from "react";
import { Despliegues } from "./Despliegues";
import { GraficoAltair } from "./GraficoAltair";
import styles from "./Tallo.module.css";

// One change of direction: what we had, and what we did because of that.
export type Cambio = { cuando: string; teniamos: ReactNode; porEso: ReactNode };

type CapituloProps = {
  id: string;
  // Which stage it closes, as the assignment names it: "Los datos", "Lo que encontramos", "El modelo".
  etapa: string;
  // What the chapter claims: the largest type on the page.
  titulo: string;
  bajada: ReactNode;
  // How the project got here, in order.
  cambios: Cambio[];
  children: ReactNode;
};

// A chapter of the guided part. It opens with the claim and the path that led to it;
// the steps inside prove it one chart at a time.
export function Capitulo({ id, etapa, titulo, bajada, cambios, children }: CapituloProps) {
  return (
    <section className={styles.capitulo} aria-labelledby={id} id={`seccion-${id}`}>
      <header className={styles.apertura}>
        <div className={styles.ancho}>
          <p className={styles.etapa}>{etapa}</p>
          <h2 id={id} className={styles.afirmacion}>
            {titulo}
          </h2>
          <p className={styles.bajada}>{bajada}</p>
          <ol className={styles.cambios}>
            {cambios.map((c) => (
              <li key={c.cuando}>
                <p className={styles.cuando}>{c.cuando}</p>
                <p className={styles.teniamos}>
                  <strong>Teníamos</strong> {c.teniamos}
                </p>
                <p className={styles.porEso}>
                  <strong>Por eso</strong> {c.porEso}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </header>
      <div className={styles.pasos}>{children}</div>
    </section>
  );
}

type PasoProps = {
  id: string;
  // The sentence that takes the reader from the previous step to this one.
  giro?: string;
  // A short question or claim: what the chart below answers.
  titulo: string;
  // Optional: a step can make its case with its own component instead of a chart.
  grafico?: string;
  descripcionGrafico?: string;
  // How to read the chart, in one line above it (the encoding, not the finding).
  comoSeLee?: ReactNode;
  // Why the chart is here and what it says: always visible, next to it.
  porQue: ReactNode;
  queDice: ReactNode;
  // Anything that replaces or goes with the chart.
  children?: ReactNode;
  // The technical evidence, collapsed by default.
  evidencia?: ReactNode;
};

// One step of a chapter: the question, the chart that answers it, why it is here and what it says.
export function Paso({ id, giro, titulo, grafico, descripcionGrafico, comoSeLee, porQue, queDice, children, evidencia }: PasoProps) {
  return (
    <article className={styles.paso} aria-labelledby={id} id={`seccion-${id}`}>
      <div>
        {giro ? <p className={styles.giro}>{giro}</p> : null}
        <h3 id={id} className={styles.pregunta}>
          {titulo}
        </h3>
      </div>
      <div className={styles.cuerpo}>
        <div className={styles.prueba}>
          {comoSeLee ? <p className={styles.comoSeLee}>{comoSeLee}</p> : null}
          {grafico ? <GraficoAltair src={grafico} descripcion={descripcionGrafico ?? ""} /> : null}
          {children}
        </div>
        <div className={styles.notas}>
          <section>
            <h4>Por qué lo miramos</h4>
            {porQue}
          </section>
          <section>
            <h4>Qué nos dice</h4>
            {queDice}
          </section>
        </div>
      </div>
      {evidencia ? (
        <Despliegues
          items={[{ id: "prueba", titulo: "Cómo lo sabemos", icono: "prueba", contenido: <div className={styles.evidencia}>{evidencia}</div> }]}
        />
      ) : null}
    </article>
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
