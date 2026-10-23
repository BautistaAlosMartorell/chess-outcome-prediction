import Link from "next/link";
import { Tablero } from "@/components/Tablero";
import { posicionEn, relojesEn } from "@/lib/partida";
import type { CasoTrivia } from "@/lib/trivia";
import caso from "@/public/app/trivia/caso-001.json";
import styles from "./page.module.css";

const muestra = caso as CasoTrivia;
const posicion = posicionEn(muestra.analisis.jugadas, muestra.ply);
const relojes = relojesEn(muestra.analisis, muestra.ply);
function reloj(ms: number | null) {
  if (ms === null) return "–";
  const segundos = Math.floor(ms / 1000);
  return `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, "0")}`;
}

export default function Inicio() {
  return (
    <div className={styles.inicio}>
      <section className={styles.bienvenida} aria-labelledby="bienvenida">
        <div className={styles.texto}>
          <p className={styles.etiqueta}>
            <span aria-hidden="true">♞</span> Ajedrez, intuición y datos
          </p>
          <h1 id="bienvenida">
            ¿Vos cómo
            <br />
            la <span>ves?</span>
          </h1>
          <p className={styles.bajada}>
            Un tablero, dos relojes y un final que todavía no conocés.
          </p>
          <p className={styles.descripcion}>
            Elegí quién gana. Descubrí qué pronostica el modelo. Y mirá qué pasó
            de verdad.
          </p>
          <div className={styles.acciones}>
            <Link href="/trivia" className={styles.principal}>
              Jugar la trivia <span aria-hidden="true">↗</span>
            </Link>
            <Link href="/proyecto" className={styles.secundario}>
              Conocer el proyecto <span aria-hidden="true">→</span>
            </Link>
          </div>
          <p className={styles.detalle}>
            Tres posiciones reales. Un pronóstico a la vez.
          </p>
        </div>
        <div className={styles.escena}>
          <div className={styles.destacado}>
            <span aria-hidden="true">✦</span> El reloj también juega.
          </div>
          <div className={styles.tarjetaTablero}>
            <div className={styles.cabeceraTablero}>
              <span>Negras</span>
              <strong>{reloj(relojes.negras)}</strong>
            </div>
            <Tablero
              fen={muestra.fen}
              ultima={posicion.ultima}
              jaque={posicion.jaque}
            />
            <div className={styles.cabeceraTablero}>
              <span>Blancas</span>
              <strong>{reloj(relojes.blancas)}</strong>
            </div>
          </div>
          <p className={styles.pieTablero}>
            Una posición real de {muestra.analisis.partida.ritmo}. ¿Quién te
            parece que gana?
          </p>
        </div>
      </section>
      <section className={styles.descubri} aria-labelledby="descubri">
        <div className={styles.encabezado}>
          <p className={styles.etiqueta}>Seguí la curiosidad</p>
          <h2>Hay más de una forma de entrar en la partida.</h2>
        </div>
        <div className={styles.opciones}>
          <Link href="/analizar" className={styles.tarjeta}>
            <span className={styles.numero}>01 / Tus partidas</span>
            <span className={styles.icono} aria-hidden="true">
              ↺
            </span>
            <h3>Volvé a ese momento.</h3>
            <p>
              Traé una partida de Chess.com y revivila con su resumen animado.
            </p>
            <strong>Analizar una partida →</strong>
          </Link>
          <Link href="/explora" className={styles.tarjeta}>
            <span className={styles.numero}>02 / Los datos</span>
            <span className={styles.icono} aria-hidden="true">
              ♙
            </span>
            <h3>Cada partida cuenta algo.</h3>
            <p>
              Explorá posiciones, resultados y cómo cambian las probabilidades.
            </p>
            <strong>Explorar las partidas →</strong>
          </Link>
          <Link href="/proyecto" className={styles.tarjeta}>
            <span className={styles.numero}>03 / La historia</span>
            <span className={styles.icono} aria-hidden="true">
              ✳
            </span>
            <h3>¿Cómo llegamos hasta acá?</h3>
            <p>
              Conocé la pregunta, los datos y lo que encontramos al intentar
              anticipar el final.
            </p>
            <strong>Conocer el proyecto →</strong>
          </Link>
        </div>
      </section>
    </div>
  );
}
