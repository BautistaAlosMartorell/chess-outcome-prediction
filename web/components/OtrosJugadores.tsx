"use client";

import { useState } from "react";
import { ApiError, predecir, traerFicha, type Analisis, type Punto } from "@/lib/api";
import { Barra } from "./Barra";
import styles from "./Partida.module.css";
import propios from "./OtrosJugadores.module.css";

// Rapid games the model saw above this average rating are a handful (notebook 01 data):
// past it the hypothetical is mostly extrapolation.
const RAPID_POCO_VISTO = 2500;

type Lado = { nombre: string; rating: number };
type Hipotesis = { blancas: Lado; negras: Lado; curva: Punto[] };

type Props = { analisis: Analisis; ply: number };

function valores(punto: Punto | null | undefined) {
  return punto ? { blancas: punto.gana_blancas, tablas: punto.empate, negras: punto.gana_negras } : null;
}

function puntoEn(curva: Punto[], ply: number) {
  return ply <= 120 ? curva.find((p) => p.ply === ply) ?? null : null;
}

// A number is taken as a rating; anything else is a Chess.com user, rated in this game's time class.
async function resolver(texto: string, ritmo: Analisis["partida"]["ritmo"]): Promise<Lado> {
  const limpio = texto.trim();
  if (/^\d{2,4}$/.test(limpio)) return { nombre: `Rating ${limpio}`, rating: Number(limpio) };
  const ficha = await traerFicha(limpio);
  const rating = ficha.ratings[ritmo];
  if (rating == null) throw new ApiError(`${ficha.usuario} no tiene rating de ${ritmo} en Chess.com.`);
  return { nombre: ficha.usuario, rating };
}

// Same board and clocks, other players: only the prior ratings change.
export function OtrosJugadores({ analisis, ply }: Props) {
  const [blancas, setBlancas] = useState("");
  const [negras, setNegras] = useState("");
  const [hipotesis, setHipotesis] = useState<Hipotesis | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { partida } = analisis;

  async function comparar(event: React.FormEvent) {
    event.preventDefault();
    setCargando(true);
    setError(null);
    try {
      const [b, n] = await Promise.all([resolver(blancas, partida.ritmo), resolver(negras, partida.ritmo)]);
      const relojes = analisis.relojes_seg.every((r): r is number => r != null) ? analisis.relojes_seg : null;
      const { curva } = await predecir({
        jugadas: analisis.jugadas,
        relojes_seg: relojes,
        tiempo_base_seg: partida.tiempo_base_seg,
        incremento_seg: partida.incremento_seg,
        elo_blancas_previo: b.rating,
        elo_negras_previo: n.rating,
        en_curso: false,
      });
      setHipotesis({ blancas: b, negras: n, curva });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo calcular la comparación.");
    } finally {
      setCargando(false);
    }
  }

  const real = puntoEn(analisis.curva, ply);
  const otro = hipotesis ? puntoEn(hipotesis.curva, ply) : null;
  const pocoVisto =
    hipotesis && partida.ritmo === "rapid" && (hipotesis.blancas.rating + hipotesis.negras.rating) / 2 >= RAPID_POCO_VISTO;

  return (
    <section className={`${styles.panel} ${propios.panel}`} aria-label="La misma posición con otros jugadores">
      <h2 className={styles.titulo}>¿Y si la jugaran otros?</h2>
      <p className={styles.nota}>
        Mismo tablero y mismos relojes, otros jugadores. Escribí dos usuarios de Chess.com (se usa su rating actual de{" "}
        {partida.ritmo}) o directamente dos ratings.
      </p>
      <form onSubmit={comparar}>
        <div className={`${styles.campo} ${propios.campos}`}>
          <input value={blancas} onChange={(e) => setBlancas(e.target.value)} placeholder="Blancas: hikaru o 2800" aria-label="Jugador con blancas" autoComplete="off" spellCheck={false} />
          <input value={negras} onChange={(e) => setNegras(e.target.value)} placeholder="Negras: magnuscarlsen o 2900" aria-label="Jugador con negras" autoComplete="off" spellCheck={false} />
          <button type="submit" className={styles.principal} disabled={cargando || !blancas.trim() || !negras.trim()}>
            {cargando ? "Calculando…" : "Comparar"}
          </button>
        </div>
      </form>
      {error ? <p className={styles.error}>{error}</p> : null}

      {hipotesis ? (
        <div className={propios.comparacion}>
          <div>
            <p className={propios.quienes}>
              Partida real: <strong>{partida.blancas.usuario}</strong> contra <strong>{partida.negras.usuario}</strong>
            </p>
            <Barra valores={valores(real)} tamano="compacto" mostrarCambio={false} />
          </div>
          <div>
            <p className={propios.quienes}>
              <strong>{hipotesis.blancas.nombre}</strong> ({hipotesis.blancas.rating}) contra{" "}
              <strong>{hipotesis.negras.nombre}</strong> ({hipotesis.negras.rating})
            </p>
            <Barra valores={valores(otro)} tamano="compacto" mostrarCambio={false} />
          </div>
          <p className={styles.nota}>
            Solo cambia el rating previo de cada lado: la forma reciente de los jugadores nuevos no se usa. Es lo que el
            modelo asocia a ese nivel en esta posición, no cómo jugarían ellos desde acá.
            {pocoVisto ? " En rapid el modelo vio muy pocas partidas de este nivel: tomalo como una extrapolación." : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
