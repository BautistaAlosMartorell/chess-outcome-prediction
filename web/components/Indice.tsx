import styles from "./Indice.module.css";

type Capitulo = { id: string; titulo: string };

// The map of the page: one link per chapter, in reading order.
export function Indice({ capitulos }: { capitulos: Capitulo[] }) {
  return (
    <nav aria-label="Capítulos del proyecto" className={styles.indice}>
      <p>El recorrido</p>
      <ol>
        {capitulos.map((c, i) => (
          <li key={c.id}>
            <a href={`#${c.id}`}>
              <span className="cifra" aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </span>
              {c.titulo}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
