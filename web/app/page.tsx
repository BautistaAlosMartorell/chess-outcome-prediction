import Link from "next/link";
import styles from "./page.module.css";

export default function Inicio() {
  return (
    <div className={styles.inicio}>
      <h1 className={styles.titulo}>Quién gana, jugada a jugada</h1>
      <p className={styles.bajada}>
        Un modelo entrenado con 80.697 partidas reales de Chess.com estima, en cada jugada, la probabilidad de que
        ganen las blancas, de que sean tablas o de que ganen las negras. Mira la posición y los relojes. No es un
        motor: no dice quién juega mejor, sino cómo suelen terminar partidas así entre personas.
      </p>
      <div className={styles.modos}>
        <section>
          <h2>Jugar</h2>
          <p>Dos personas en la misma computadora, cada una con su reloj. La barra se mueve después de cada jugada.</p>
          <Link className={styles.accion} href="/jugar">
            Empezar una partida
          </Link>
        </section>
        <section>
          <h2>Analizar una partida</h2>
          <p>Escribí un usuario de Chess.com, elegí una de sus últimas partidas y mirala de nuevo con la barra.</p>
          <Link className={styles.accion} href="/analizar">
            Buscar un usuario
          </Link>
        </section>
      </div>
    </div>
  );
}
