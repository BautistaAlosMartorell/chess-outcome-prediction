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
          <h1 id="bienvenida">
            ¿Vos cómo
            <br />
            la ves?
          </h1>
          <p className={styles.bajada}>
            Una posición real, dos relojes y tres resultados posibles.
          </p>
          <p className={styles.descripcion}>
            Elegí quién gana. Descubrí qué pronostica el modelo. Y mirá qué pasó
            de verdad.
          </p>
          <div className={styles.acciones}>
            <Link href="/trivia" className={styles.principal}>
              Jugar la trivia
            </Link>
            <Link href="/proyecto" className={styles.secundario}>
              Conocer el proyecto
            </Link>
          </div>
        </div>
        <div className={styles.escena}>
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
        <h2 id="descubri" className={styles.encabezado}>
          También podés
        </h2>
        <div className={styles.opciones}>
          <Link href="/analizar" className={styles.tarjeta}>
            <h3>Analizar tus partidas</h3>
            <p>Traé una partida de Chess.com y mirá qué decía el modelo en cada jugada.</p>
          </Link>
          <Link href="/explora" className={styles.tarjeta}>
            <h3>Explorar los datos</h3>
            <p>Dos mil partidas que el modelo no vio, con lo que dijo de cada una.</p>
          </Link>
          <Link href="/proyecto" className={styles.tarjeta}>
            <h3>Leer cómo llegamos hasta acá</h3>
            <p>La pregunta, los datos, lo que encontramos y dónde se equivoca el modelo.</p>
          </Link>
        </div>
      </section>
    </div>
  );
}
