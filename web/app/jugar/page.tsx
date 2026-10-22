"use client";

import { Chess, type Square } from "chess.js";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Curva } from "@/components/Curva";
import { ImportarJugador } from "@/components/ImportarJugador";
import { Marcador, type Jugador } from "@/components/Marcador";
import styles from "@/components/Partida.module.css";
import { Planilla } from "@/components/Planilla";
import { Tablero, type Destino } from "@/components/Tablero";
import { AvisoRango } from "@/components/AvisoRango";
import { ApiError, predecir, salud, traerFicha, type Ficha, type Punto, type Ritmo } from "@/lib/api";
import { momentosClave } from "@/lib/movimiento";

const RITMOS = [
  { nombre: "1 min", detalle: "bullet", base: 60, inc: 0 },
  { nombre: "3 + 2", detalle: "blitz", base: 180, inc: 2 },
  { nombre: "5 min", detalle: "blitz", base: 300, inc: 0 },
  { nombre: "10 min", detalle: "rapid", base: 600, inc: 0 },
];

type Lado = "blancas" | "negras";
type Fase = "preparando" | "jugando" | "terminada";
type Final = { texto: string; ganador: Lado | null };

// Same rule as the API (and Chess.com): estimated length = base + 40 × increment.
function ritmoDe(base: number, inc: number): Ritmo {
  const estimado = base + 40 * inc;
  return estimado < 180 ? "bullet" : estimado < 600 ? "blitz" : "rapid";
}

function finalPorTablero(chess: Chess): Final {
  if (chess.isCheckmate()) {
    const ganador: Lado = chess.turn() === "w" ? "negras" : "blancas";
    return { texto: `Ganan las ${ganador} por jaque mate`, ganador };
  }
  if (chess.isStalemate()) return { texto: "Tablas por rey ahogado", ganador: null };
  if (chess.isThreefoldRepetition()) return { texto: "Tablas por triple repetición", ganador: null };
  if (chess.isInsufficientMaterial()) return { texto: "Tablas por material insuficiente", ganador: null };
  return { texto: "Tablas por la regla de las 50 jugadas", ganador: null };
}

// What the model said along the way: the winner's lowest point, or the draw's highest.
function resumen(curva: Punto[], ganador: Lado | null): string | null {
  if (curva.length < 2) return null;
  const valor = (p: Punto) => (ganador === "blancas" ? p.gana_blancas : ganador === "negras" ? p.gana_negras : p.empate);
  const extremo = curva.reduce((a, b) => (ganador ? (valor(b) < valor(a) ? b : a) : valor(b) > valor(a) ? b : a));
  const cuando = extremo.ply === 0 ? "antes de mover" : `en la jugada ${Math.ceil(extremo.ply / 2)}`;
  const pct = Math.round(valor(extremo) * 100);
  return ganador
    ? `Según el modelo, las ${ganador} llegaron a tener ${pct} % ${cuando}.`
    : `El modelo nunca le dio más de ${pct} % a las tablas (lo más alto fue ${cuando}).`;
}

function jugador(lado: Lado, ficha: Ficha | null, ritmo: Ritmo): Jugador {
  if (!ficha) return { nombre: lado === "blancas" ? "Blancas" : "Negras" };
  return { nombre: ficha.usuario, rating: ficha.ratings[ritmo], avatar: ficha.avatar, forma: ficha.forma[ritmo].ultimas };
}

function reyEnJaque(chess: Chess): string | null {
  if (!chess.inCheck()) return null;
  const color = chess.turn();
  for (const fila of chess.board()) {
    for (const casilla of fila) {
      if (casilla?.type === "k" && casilla.color === color) return casilla.square;
    }
  }
  return null;
}

export default function Pagina() {
  // useSearchParams needs a Suspense boundary so the rest of the page can be prerendered.
  return (
    <Suspense fallback={null}>
      <Jugar />
    </Suspense>
  );
}

function Jugar() {
  const parametros = useSearchParams();
  const [ritmoElegido, setRitmoElegido] = useState(RITMOS[1]);
  const [fichas, setFichas] = useState<Record<Lado, Ficha | null>>({ blancas: null, negras: null });
  const [fase, setFase] = useState<Fase>("preparando");
  const [fen, setFen] = useState(new Chess().fen());
  const [jugadas, setJugadas] = useState<string[]>([]);
  const [ultima, setUltima] = useState<{ desde: string; hasta: string } | null>(null);
  const [relojes, setRelojes] = useState<Record<Lado, number>>({ blancas: 180_000, negras: 180_000 });
  const [curva, setCurva] = useState<Punto[]>([]);
  const [final, setFinal] = useState<Final | null>(null);
  const [verResultado, setVerResultado] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [orientacion, setOrientacion] = useState<"white" | "black">("white");
  const [partidaId, setPartidaId] = useState(0);
  const [rango, setRango] = useState<[number, number] | null>(null);

  // The ratings the model saw in training, to warn when a game falls outside them.
  useEffect(() => {
    salud()
      .then((s) => setRango(s.rango_rating))
      .catch(() => setRango(null));
  }, []);

  // Links like /jugar?blancas=hikaru&negras=magnuscarlsen&ritmo=3+2 import both cards on their own.
  useEffect(() => {
    const elegido = RITMOS.find((r) => r.nombre.replace(/\s/g, "") === parametros.get("ritmo")?.replace(/\s/g, ""));
    if (elegido) setRitmoElegido(elegido);
    for (const lado of ["blancas", "negras"] as const) {
      const usuario = parametros.get(lado)?.trim();
      if (usuario) {
        traerFicha(usuario)
          .then((ficha) => setFichas((s) => ({ ...s, [lado]: ficha })))
          .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo traer el usuario."));
      }
    }
    // Runs once, with the link the page was opened with.
  }, []);

  const chess = useRef(new Chess());
  // The ticking clock lives in refs so the interval and the move handler see the same values.
  const relojesRef = useRef<Record<Lado, number>>({ blancas: 180_000, negras: 180_000 });
  const relojesSeg = useRef<number[]>([]);
  const ultimoTick = useRef(0);
  const pedido = useRef(0);
  const inicioPartida = useRef(new Date().toISOString());

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
          usuario_blancas: fichas.blancas?.usuario,
          usuario_negras: fichas.negras?.usuario,
          inicio_partida: inicioPartida.current,
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

  const terminar = useCallback((resultado: Final) => {
    setFase("terminada");
    setFinal(resultado);
    setVerResultado(true);
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
      if (restante <= 0) {
        const ganador: Lado = lado === "blancas" ? "negras" : "blancas";
        terminar({ texto: `Ganan las ${ganador} por tiempo`, ganador });
      }
    }, 100);
    return () => window.clearInterval(intervalo);
  }, [fase, terminar]);

  function reiniciarTablero() {
    inicioPartida.current = new Date().toISOString();
    chess.current = new Chess();
    relojesSeg.current = [];
    setFen(chess.current.fen());
    setJugadas([]);
    setUltima(null);
    setFinal(null);
  }

  function empezar() {
    reiniciarTablero();
    const inicio = ritmoElegido.base * 1000;
    relojesRef.current = { blancas: inicio, negras: inicio };
    setRelojes(relojesRef.current);
    setPartidaId((n) => n + 1);
    setFase("jugando");
    void pedirPrediccion([], true);
  }

  function nuevaPartida() {
    reiniciarTablero();
    setCurva([]);
    setFase("preparando");
  }

  const destinosDesde = useCallback(
    (casilla: string): Destino[] =>
      chess.current
        .moves({ square: casilla as Square, verbose: true })
        .map((m) => ({ hasta: m.to, captura: Boolean(m.captured) })),
    // The position lives in a ref; fen changes with every move and re-creates the callback.
    [fen],
  );

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
      terminar(finalPorTablero(chess.current));
    } else {
      void pedirPrediccion(lista, true);
    }
    return true;
  }

  const blancas = jugador("blancas", fichas.blancas, ritmo);
  const negras = jugador("negras", fichas.negras, ritmo);
  const punto = curva.length ? curva[curva.length - 1] : null;
  const momentos = momentosClave(curva);
  const resumenFinal = final ? resumen(curva, final.ganador) : null;

  return (
    <div className={styles.pagina}>
      <Marcador
        blancas={blancas}
        negras={negras}
        relojes={fase === "preparando" ? { blancas: ritmoElegido.base * 1000, negras: ritmoElegido.base * 1000 } : relojes}
        activo={fase === "jugando" ? turno : null}
        punto={punto}
        final={final?.texto}
        mostrarCambio={fase !== "preparando"}
      />
      <AvisoRango
        blancas={{ nombre: blancas.nombre, rating: blancas.rating }}
        negras={{ nombre: negras.nombre, rating: negras.rating }}
        rango={rango}
      />
      {error ? <p className={styles.error}>{error}</p> : null}
      <div className={styles.cuerpo}>
        <div className={styles.tablero}>
          <Tablero
            fen={fen}
            orientacion={orientacion}
            ultima={ultima}
            jaque={reyEnJaque(chess.current)}
            destinosDesde={fase === "jugando" ? destinosDesde : undefined}
            onMover={fase === "jugando" ? mover : undefined}
          />
          {final && verResultado ? (
            <div className={styles.resultado}>
              <div className={styles.resultadoTarjeta} role="status">
                <h2>{final.texto}</h2>
                {resumenFinal ? <p className={styles.texto}>{resumenFinal}</p> : null}
                <div className={styles.acciones} style={{ justifyContent: "center" }}>
                  <button type="button" className={styles.principal} onClick={nuevaPartida}>
                    Jugar otra
                  </button>
                  <button type="button" className={styles.boton} onClick={() => setVerResultado(false)}>
                    Ver el tablero
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
        <div className={styles.lateral}>
          {fase === "preparando" ? (
            <div className={styles.panel}>
              <div className={styles.grupo}>
                <h1 className={styles.titulo}>Nueva partida</h1>
                <p className={styles.texto}>Dos personas, una computadora. Cada uno mueve en su turno y su reloj corre mientras piensa.</p>
              </div>
              <fieldset className={styles.grupo}>
                <legend>Ritmo</legend>
                <div className={styles.segmentos}>
                  {RITMOS.map((r) => (
                    <button
                      key={r.nombre}
                      type="button"
                      className={styles.segmento}
                      aria-pressed={r.nombre === ritmoElegido.nombre}
                      onClick={() => setRitmoElegido(r)}
                    >
                      <strong>{r.nombre}</strong>
                      <small>{r.detalle}</small>
                    </button>
                  ))}
                </div>
              </fieldset>
              <ImportarJugador lado="Blancas" ritmo={ritmo} ficha={fichas.blancas} onFicha={(f) => setFichas((s) => ({ ...s, blancas: f }))} />
              <ImportarJugador lado="Negras" ritmo={ritmo} ficha={fichas.negras} onFicha={(f) => setFichas((s) => ({ ...s, negras: f }))} />
              <p className={styles.nota}>
                Antes de mover, la ventaja predictiva es modesta: Chess.com empareja jugadores parecidos, así que la barra
                arranca cerca de las proporciones de siempre y se mueve con el material y los relojes.
              </p>
              <button type="button" className={styles.principal} onClick={empezar}>
                Empezar partida
              </button>
            </div>
          ) : (
            <>
              <Planilla jugadas={jugadas} curva={curva} actual={jugadas.length} momentos={momentos} />
              <div className={styles.acciones}>
                {fase === "jugando" ? (
                  <>
                    <button
                      type="button"
                      className={styles.boton}
                      onClick={() => {
                        const ganador: Lado = turno === "blancas" ? "negras" : "blancas";
                        terminar({ texto: `Ganan las ${ganador}: abandonaron las ${turno}`, ganador });
                      }}
                    >
                      Abandonar ({turno})
                    </button>
                    <button type="button" className={styles.boton} onClick={() => terminar({ texto: "Tablas de común acuerdo", ganador: null })}>
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
      <Curva curva={curva} actual={punto?.ply} momentos={momentos} revelar={fase === "preparando" ? undefined : `partida-${partidaId}`} />
    </div>
  );
}
