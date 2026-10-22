"use client";

import { Chess } from "chess.js";
import { useCallback, useEffect, useRef, useState } from "react";
import { Curva } from "@/components/Curva";
import { ImportarJugador } from "@/components/ImportarJugador";
import { Marcador, type Jugador } from "@/components/Marcador";
import styles from "@/components/Partida.module.css";
import { Planilla } from "@/components/Planilla";
import { Tablero } from "@/components/Tablero";
import { ApiError, predecir, type Ficha, type Punto, type Ritmo } from "@/lib/api";

const RITMOS = [
  { nombre: "1 minuto", base: 60, inc: 0 },
  { nombre: "3 + 2", base: 180, inc: 2 },
  { nombre: "5 minutos", base: 300, inc: 0 },
  { nombre: "10 minutos", base: 600, inc: 0 },
];

type Lado = "blancas" | "negras";
type Fase = "preparando" | "jugando" | "terminada";

// Same rule as the API (and Chess.com): estimated length = base + 40 × increment.
function ritmoDe(base: number, inc: number): Ritmo {
  const estimado = base + 40 * inc;
  return estimado < 180 ? "bullet" : estimado < 600 ? "blitz" : "rapid";
}

function motivoFinal(chess: Chess): string {
  if (chess.isCheckmate()) return `Ganan las ${chess.turn() === "w" ? "negras" : "blancas"} por jaque mate`;
  if (chess.isStalemate()) return "Tablas por rey ahogado";
  if (chess.isThreefoldRepetition()) return "Tablas por triple repetición";
  if (chess.isInsufficientMaterial()) return "Tablas por material insuficiente";
  return "Tablas por la regla de las 50 jugadas";
}

function jugador(lado: Lado, ficha: Ficha | null, ritmo: Ritmo): Jugador {
  if (!ficha) return { nombre: lado === "blancas" ? "Blancas" : "Negras" };
  return { nombre: ficha.usuario, rating: ficha.ratings[ritmo], avatar: ficha.avatar, forma: ficha.forma[ritmo].ultimas };
}

export default function Jugar() {
  const [ritmoElegido, setRitmoElegido] = useState(RITMOS[1]);
  const [fichas, setFichas] = useState<Record<Lado, Ficha | null>>({ blancas: null, negras: null });
  const [fase, setFase] = useState<Fase>("preparando");
  const [fen, setFen] = useState(new Chess().fen());
  const [jugadas, setJugadas] = useState<string[]>([]);
  const [ultima, setUltima] = useState<{ desde: string; hasta: string } | null>(null);
  const [relojes, setRelojes] = useState<Record<Lado, number>>({ blancas: 180_000, negras: 180_000 });
  const [curva, setCurva] = useState<Punto[]>([]);
  const [final, setFinal] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [orientacion, setOrientacion] = useState<"white" | "black">("white");

  const chess = useRef(new Chess());
  // The ticking clock lives in refs so the interval and the move handler see the same values.
  const relojesRef = useRef<Record<Lado, number>>({ blancas: 180_000, negras: 180_000 });
  const relojesSeg = useRef<number[]>([]);
  const ultimoTick = useRef(0);
  const pedido = useRef(0);

  const ritmo = ritmoDe(ritmoElegido.base, ritmoElegido.inc);
  const turno: Lado = chess.current.turn() === "w" ? "blancas" : "negras";

  const pedirPrediccion = useCallback(
    async (lista: string[], enCurso: boolean) => {
      const id = ++pedido.current;
      try {
        const respuesta = await predecir({
          jugadas: lista,
          relojes_seg: relojesSeg.current,
          tiempo_base_seg: ritmoElegido.base,
          incremento_seg: ritmoElegido.inc,
          elo_blancas_previo: fichas.blancas?.ratings[ritmo] ?? null,
          elo_negras_previo: fichas.negras?.ratings[ritmo] ?? null,
          en_curso: enCurso,
        });
        if (id === pedido.current) {
          setCurva(respuesta.curva);
          setError(null);
        }
      } catch (e) {
        if (id === pedido.current) setError(e instanceof ApiError ? e.message : "No se pudo pedir la predicción.");
      }
    },
    [ritmoElegido, fichas, ritmo],
  );

  // Before the game: the prediction at ply 0, which moves with the time control and the ratings.
  useEffect(() => {
    if (fase === "preparando") {
      relojesSeg.current = [];
      void pedirPrediccion([], true);
    }
  }, [fase, pedirPrediccion]);

  const terminar = useCallback((motivo: string) => {
    setFase("terminada");
    setFinal(motivo);
  }, []);

  // Clock: the side to move loses time; at zero, the other side wins on time.
  useEffect(() => {
    if (fase !== "jugando") return;
    ultimoTick.current = performance.now();
    const intervalo = window.setInterval(() => {
      const ahora = performance.now();
      const lado: Lado = chess.current.turn() === "w" ? "blancas" : "negras";
      const restante = relojesRef.current[lado] - (ahora - ultimoTick.current);
      ultimoTick.current = ahora;
      relojesRef.current = { ...relojesRef.current, [lado]: Math.max(0, restante) };
      setRelojes(relojesRef.current);
      if (restante <= 0) terminar(`Ganan las ${lado === "blancas" ? "negras" : "blancas"} por tiempo`);
    }, 100);
    return () => window.clearInterval(intervalo);
  }, [fase, terminar]);

  function empezar() {
    chess.current = new Chess();
    const inicio = ritmoElegido.base * 1000;
    relojesRef.current = { blancas: inicio, negras: inicio };
    relojesSeg.current = [];
    setRelojes(relojesRef.current);
    setFen(chess.current.fen());
    setJugadas([]);
    setUltima(null);
    setFinal(null);
    setFase("jugando");
  }

  function nuevaPartida() {
    chess.current = new Chess();
    setFen(chess.current.fen());
    setJugadas([]);
    setUltima(null);
    setFinal(null);
    setCurva([]);
    setFase("preparando");
  }

  function mover(desde: string, hasta: string): boolean {
    if (fase !== "jugando") return false;
    let jugada;
    try {
      jugada = chess.current.move({ from: desde, to: hasta, promotion: "q" });
    } catch {
      return false; // illegal: the piece goes back
    }
    const lado: Lado = jugada.color === "w" ? "blancas" : "negras";
    // Charge the time since the last tick, then add the increment, as a real clock does.
    const ahora = performance.now();
    const restante = relojesRef.current[lado] - (ahora - ultimoTick.current) + ritmoElegido.inc * 1000;
    ultimoTick.current = ahora;
    relojesRef.current = { ...relojesRef.current, [lado]: restante };
    relojesSeg.current = [...relojesSeg.current, Math.max(0, restante) / 1000];
    setRelojes(relojesRef.current);

    const lista = chess.current.history();
    setJugadas(lista);
    setFen(chess.current.fen());
    setUltima({ desde: jugada.from, hasta: jugada.to });
    if (chess.current.isGameOver()) {
      terminar(motivoFinal(chess.current));
    } else {
      void pedirPrediccion(lista, true);
    }
    return true;
  }

  const blancas = jugador("blancas", fichas.blancas, ritmo);
  const negras = jugador("negras", fichas.negras, ritmo);
  const punto = curva.length ? curva[curva.length - 1] : null;

  return (
    <div className={styles.pagina}>
      <Marcador
        blancas={blancas}
        negras={negras}
        relojes={fase === "preparando" ? { blancas: ritmoElegido.base * 1000, negras: ritmoElegido.base * 1000 } : relojes}
        activo={fase === "jugando" ? turno : null}
        punto={punto}
        final={final}
      />
      {error ? <p className={styles.error}>{error}</p> : null}
      <div className={styles.cuerpo}>
        <div className={styles.tablero}>
          <Tablero fen={fen} orientacion={orientacion} ultima={ultima} onMover={fase === "jugando" ? mover : undefined} />
        </div>
        <div className={styles.lateral}>
          {fase === "preparando" ? (
            <>
              <h1 className={styles.titulo}>Nueva partida</h1>
              <p className={styles.texto}>
                Dos personas, una computadora. Cada uno mueve en su turno y su reloj corre mientras piensa.
              </p>
              <fieldset className={styles.grupo}>
                <legend>Ritmo</legend>
                <div className={styles.opciones}>
                  {RITMOS.map((r) => (
                    <button
                      key={r.nombre}
                      type="button"
                      className={styles.opcion}
                      aria-pressed={r.nombre === ritmoElegido.nombre}
                      onClick={() => setRitmoElegido(r)}
                    >
                      {r.nombre}
                    </button>
                  ))}
                </div>
              </fieldset>
              <ImportarJugador lado="Blancas" ritmo={ritmo} ficha={fichas.blancas} onFicha={(f) => setFichas((s) => ({ ...s, blancas: f }))} />
              <ImportarJugador lado="Negras" ritmo={ritmo} ficha={fichas.negras} onFicha={(f) => setFichas((s) => ({ ...s, negras: f }))} />
              <p className={styles.nota}>
                Antes de mover, el modelo casi no puede predecir nada: en sus datos, Chess.com empareja jugadores
                parecidos. La barra empieza a moverse con el material y los relojes.
              </p>
              <div className={styles.acciones}>
                <button type="button" className={styles.principal} onClick={empezar}>
                  Empezar partida
                </button>
              </div>
            </>
          ) : (
            <>
              <Planilla jugadas={jugadas} curva={curva} actual={jugadas.length} />
              <div className={styles.acciones}>
                {fase === "jugando" ? (
                  <>
                    <button type="button" className={styles.boton} onClick={() => terminar(`Ganan las ${turno === "blancas" ? "negras" : "blancas"}: abandonaron las ${turno}`)}>
                      Abandonar ({turno})
                    </button>
                    <button type="button" className={styles.boton} onClick={() => terminar("Tablas de común acuerdo")}>
                      Tablas de común acuerdo
                    </button>
                  </>
                ) : (
                  <button type="button" className={styles.principal} onClick={nuevaPartida}>
                    Jugar otra
                  </button>
                )}
                <button type="button" className={styles.boton} onClick={() => setOrientacion((o) => (o === "white" ? "black" : "white"))}>
                  Girar tablero
                </button>
              </div>
            </>
          )}
        </div>
      </div>
      <Curva curva={curva} actual={curva.length ? curva[curva.length - 1].ply : undefined} />
    </div>
  );
}
