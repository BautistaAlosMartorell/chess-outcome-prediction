import styles from "./ValorPiezas.module.css";

// The usual scale: how many points of material each piece is worth. The model's "material"
// column is the sum of the white pieces minus the sum of the black ones.
const PIEZAS = [
  { nombre: "Peón", valor: 1 },
  { nombre: "Caballo", valor: 3 },
  { nombre: "Alfil", valor: 3 },
  { nombre: "Torre", valor: 5 },
  { nombre: "Dama", valor: 9 },
];

export function ValorPiezas() {
  return (
    <figure className={styles.figura}>
      <figcaption>¿Qué es el material? Cuánto vale cada pieza, en puntos</figcaption>
      <ul>
        {PIEZAS.map((p) => (
          <li key={p.nombre}>
            <span className={styles.nombre}>{p.nombre}</span>
            <span className={styles.barra} aria-hidden="true" style={{ width: `${(p.valor / 9) * 100}%` }} />
            <span className={`${styles.valor} cifra`}>{p.valor}</span>
          </li>
        ))}
      </ul>
      <p>
        El material de una partida es lo que suman las piezas de las blancas menos lo que suman las de las negras: +3
        quiere decir que las blancas van arriba por un caballo.
      </p>
    </figure>
  );
}
