import Link from "next/link";
import { DemoEnVivo } from "@/components/DemoEnVivo";
import styles from "./page.module.css";

export default function Inicio() {
  return (
    <div className={styles.inicio}>
      <section className={styles.hero}>
        <div className={styles.texto}>
          <h1 className={styles.titulo}>Quién gana, jugada a jugada</h1>
          <p className={styles.bajada}>
            Un modelo entrenado con 80.697 partidas reales de Chess.com mira el tablero y los relojes y estima, en
            cada jugada, la probabilidad de que ganen las blancas, de que sean tablas o de que ganen las negras.
          </p>
          <p className={styles.aclaracion}>
            No es un motor: no dice quién juega mejor, sino cómo suelen terminar partidas así entre personas, con
            el reloj corriendo.
          </p>
          <div className={styles.acciones}>
            <Link className={styles.principal} href="/jugar">
              Jugar una partida
            </Link>
            <Link className={styles.secundario} href="/analizar">
              Analizar una de Chess.com
            </Link>
          </div>
        </div>
        <DemoEnVivo />
      </section>

      <section className={styles.mira} aria-labelledby="que-mira">
        <h2 id="que-mira">Qué mira el modelo</h2>
        <dl>
          <div>
            <dt>El tablero</dt>
            <dd>Cuánto material tiene cada uno, si hay un rey en jaque, cuántas jugadas tiene el que mueve.</dd>
          </div>
          <div>
            <dt>Los relojes</dt>
            <dd>Cuánto tiempo le queda a cada uno y cuánto gastó en las últimas jugadas. Después del material, es lo que más pesa.</dd>
          </div>
          <div>
            <dt>El ritmo y el nivel</dt>
            <dd>Bullet, blitz o rapid, y el rating de cada jugador si se conoce. Antes de mover, casi no alcanza para predecir.</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
