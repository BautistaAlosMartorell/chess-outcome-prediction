import type { Punto } from "@/lib/api";
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
  // Set once the game is over: replaces the prediction text.
  final?: string | null;
};

export function formatoReloj(ms: number | null): string {
  if (ms === null) return "–";
  const seconds = Math.max(0, ms) / 1000;
  if (seconds < 20) return seconds.toFixed(1);
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

function porcentaje(p: number): number {
  return Math.round(p * 100);
}

function Placa({ jugador, lado, reloj, activo }: { jugador: Jugador; lado: "blancas" | "negras"; reloj: number | null; activo: boolean }) {
  return (
    <div className={`${styles.placa} ${styles[lado]}`}>
      <div className={styles.identidad}>
        <span className={styles.ficha} aria-hidden="true" />
        <span className={styles.nombre}>{jugador.nombre}</span>
        {jugador.rating ? <span className={styles.rating}>{jugador.rating}</span> : null}
      </div>
      {jugador.forma && jugador.forma.length > 0 ? (
        <ol className={styles.forma} aria-label="Últimas partidas, de la más reciente a la más vieja">
          {jugador.forma.slice(0, 5).map((r, i) => (
            <li key={i} className={styles[`forma${r}`]} title={{ G: "Ganó", P: "Perdió", T: "Tablas" }[r]}>
              {r}
            </li>
          ))}
        </ol>
      ) : null}
      <div className={`cifra ${styles.reloj} ${activo ? styles.relojActivo : ""}`} aria-live="off">
        {formatoReloj(reloj)}
      </div>
    </div>
  );
}

export function Marcador({ blancas, negras, relojes, activo, punto, final }: Props) {
  const pb = punto ? porcentaje(punto.gana_blancas) : null;
  const pt = punto ? porcentaje(punto.empate) : null;
  const pn = punto ? porcentaje(punto.gana_negras) : null;
  const descripcion = punto
    ? `Blancas ${pb} %, tablas ${pt} %, negras ${pn} %`
    : "Todavía no hay predicción";
  const restantes = punto?.plies_restantes;

  return (
    <section className={styles.marcador} aria-label="Marcador">
      <Placa jugador={blancas} lado="blancas" reloj={relojes.blancas} activo={activo === "blancas"} />
      <div className={styles.centro}>
        <div className={styles.cifras} aria-hidden="true">
          <span className="cifra">{pb ?? "–"}</span>
          <span className={styles.cifraTablas}>
            <span className="cifra">{pt ?? "–"}</span> tablas
          </span>
          <span className="cifra">{pn ?? "–"}</span>
        </div>
        <div className={styles.franja} role="img" aria-label={descripcion}>
          <div className={styles.segBlancas} style={{ flexBasis: `${punto ? punto.gana_blancas * 100 : 50}%` }} />
          <div className={styles.segTablas} style={{ flexBasis: `${punto ? punto.empate * 100 : 0}%` }} />
          <div className={styles.segNegras} style={{ flexBasis: `${punto ? punto.gana_negras * 100 : 50}%` }} />
        </div>
        <p className={styles.pie} aria-live="polite">
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
