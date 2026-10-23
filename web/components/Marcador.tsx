"use client";

import type { Punto } from "@/lib/api";
import { Barra } from "./Barra";
import styles from "./Marcador.module.css";

export type Jugador = {
  nombre: string;
  rating?: number | null;
  avatar?: string | null;
  forma?: ("G" | "P" | "T")[];
};

type Props = {
  blancas: Jugador;
  negras: Jugador;
  // Remaining time in milliseconds; null when unknown (a game without clocks).
  relojes: { blancas: number | null; negras: number | null };
  activo: "blancas" | "negras" | null;
  punto: Punto | null;
  // Set once the game is over: replaces the remaining-moves line.
  final?: string | null;
  // The "▲ n" chip is for changes caused by a move, not by the setup (time control, players).
  mostrarCambio?: boolean;
  compacto?: boolean;
  ocultarPronostico?: boolean;
};

// Under this, the running clock turns to the time-trouble color.
const APURO_MS = 20_000;

export function formatoReloj(ms: number | null): string {
  if (ms === null) return "–";
  const seconds = Math.max(0, ms) / 1000;
  if (seconds < 20) return seconds.toFixed(1);
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

const NOMBRE_RESULTADO = { G: "Ganó", P: "Perdió", T: "Tablas" } as const;

function Placa({ jugador, lado, reloj, activo }: { jugador: Jugador; lado: "blancas" | "negras"; reloj: number | null; activo: boolean }) {
  const apuro = reloj !== null && reloj < APURO_MS;
  return (
    <div className={`${styles.placa} ${styles[lado]}`}>
      <div className={styles.identidad}>
        {jugador.avatar ? (
          // Chess.com serves avatars from its CDN at any size: a plain img is enough.
          <img className={styles.avatar} src={jugador.avatar} alt="" width={36} height={36} />
        ) : (
          <span className={styles.pieza} aria-hidden="true" />
        )}
        <div className={styles.datos}>
          <span className={styles.nombre}>{jugador.nombre}</span>
          <span className={styles.rating}>{jugador.rating ? `${jugador.rating}` : "Sin rating"}</span>
        </div>
      </div>
      {jugador.forma && jugador.forma.length > 0 ? (
        <ol className={styles.forma} aria-label="Últimas partidas, de la más reciente a la más vieja">
          {jugador.forma.slice(0, 5).map((r, i) => (
            <li key={i} className={styles[`forma${r}`]} title={NOMBRE_RESULTADO[r]}>
              {r}
            </li>
          ))}
        </ol>
      ) : null}
      <div
        className={`cifra ${styles.reloj} ${activo ? styles.relojActivo : ""} ${activo && apuro ? styles.relojApuro : ""}`}
        aria-label={`Reloj de ${lado}: ${formatoReloj(reloj)}`}
      >
        {formatoReloj(reloj)}
      </div>
    </div>
  );
}

export function Marcador({ blancas, negras, relojes, activo, punto, final, mostrarCambio = true, compacto = false, ocultarPronostico = false }: Props) {
  const restantes = punto?.plies_restantes;
  return (
    <section className={`${styles.marcador} ${compacto ? styles.compacto : ""}`} aria-label="Marcador">
      <Placa jugador={blancas} lado="blancas" reloj={relojes.blancas} activo={activo === "blancas"} />
      <div className={styles.centro}>
        {ocultarPronostico ? <p className={styles.pie}>Pronóstico oculto hasta la revelación</p> : <Barra
          valores={punto ? { blancas: punto.gana_blancas, tablas: punto.empate, negras: punto.gana_negras } : null}
          mostrarCambio={mostrarCambio}
          tamano={compacto ? "compacto" : "normal"}
        />}
        <p className={`${styles.pie} ${final ? styles.pieFinal : ""}`} aria-live="polite">
          {final
            ? final
            : restantes !== undefined
              ? `Faltan unas ${Math.max(1, Math.round(restantes / 2))} jugadas por bando`
              : " "}
        </p>
      </div>
      <Placa jugador={negras} lado="negras" reloj={relojes.negras} activo={activo === "negras"} />
    </section>
  );
}
