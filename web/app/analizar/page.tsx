"use client";

import { Chess } from "chess.js";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { ResumenPartida as VisorResumen } from "@/components/ResumenPartida";
import { cargarCaso } from "@/lib/trivia";
import { relojesEn } from "@/lib/partida";
import { Curva } from "@/components/Curva";
import { Marcador } from "@/components/Marcador";
import styles from "@/components/Partida.module.css";
import { Planilla } from "@/components/Planilla";
import { Tablero } from "@/components/Tablero";
import { analizar, ApiError, traerFicha, traerPartidas, type Analisis, type Ficha, type ResumenPartida } from "@/lib/api";
import { momentosClave } from "@/lib/movimiento";
import propios from "./analizar.module.css";

const FINALES: Record<string, string> = {
  "Gana Blancas": "Ganaron las blancas",
  "Gana Negras": "Ganaron las negras",
  Empate: "Tablas",
};
const PASO_REPRODUCCION_MS = 900;
const CLASE_RESULTADO = { Ganó: "chipGano", Perdió: "chipPerdio", Tablas: "chipTablas" } as const;

function resultadoPara(partida: ResumenPartida, usuario: string): "Ganó" | "Perdió" | "Tablas" {
  if (partida.resultado === "Empate") return "Tablas";
  const ganador = partida.resultado === "Gana Blancas" ? partida.blancas : partida.negras;
  return ganador.usuario.toLowerCase() === usuario.toLowerCase() ? "Ganó" : "Perdió";
}

export default function Pagina() {
  // useSearchParams needs a Suspense boundary so the rest of the page can be prerendered.
  return (
    <Suspense fallback={null}>
      <Analizar />
    </Suspense>
  );
}

function Analizar() {
  const router = useRouter();
  const parametros = useSearchParams();
  const [usuario, setUsuario] = useState(parametros.get("usuario") ?? "");
  const [buscado, setBuscado] = useState<string | null>(null);
  const [ficha, setFicha] = useState<Ficha | null>(null);
  const [partidas, setPartidas] = useState<ResumenPartida[]>([]);
  const [verResumen, setVerResumen] = useState(false);
  const [analisis, setAnalisis] = useState<Analisis | null>(null);
  const [ply, setPly] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [cargando, setCargando] = useState<"buscar" | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const espacio = useRef<HTMLElement>(null);
  const [altoCabecera, setAltoCabecera] = useState(72);

  // The header wraps on small screens; sticky replay follows its actual height.
  useEffect(() => {
    const header = document.querySelector("body > header");
    if (!header) return;
    const measure = () => setAltoCabecera(header.getBoundingClientRect().height);
    const observer = new ResizeObserver(measure);
    observer.observe(header);
    measure();
    return () => observer.disconnect();
  }, []);

  // Opening another game brings its controls into view, without scrolling on each move.
  useEffect(() => {
    if (analisis) espacio.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }, [analisis]);

  async function buscarUsuario(nombre: string) {
    setCargando("buscar");
    setError(null);
    setAnalisis(null);
    try {
      const [f, p] = await Promise.all([traerFicha(nombre), traerPartidas(nombre)]);
      setFicha(f);
      setPartidas(p);
      setBuscado(nombre);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo buscar el usuario.");
      return false;
    } finally {
      setCargando(null);
    }
  }

  async function abrirPartida(nombre: string, url: string, desdePly = 0) {
    setCargando(url);
    setError(null);
    setReproduciendo(false);
    try {
      const a = await analizar(nombre, url);
      setAnalisis(a);
      setPly(Math.min(Math.max(0, desdePly), a.jugadas.length));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo analizar la partida.");
    } finally {
      setCargando(null);
    }
  }

  // Links like /analizar?usuario=hikaru&partida=<url>&ply=40 search and open on their own.
  const inicial = useRef(false);
  useEffect(() => {
    if (inicial.current) return;
    inicial.current = true;
    const caso = parametros.get("caso");
    if (caso) {
      setCargando(caso);
      cargarCaso(caso).then(c => { setAnalisis(c.analisis); setPly(c.ply); })
        .catch(e => setError(e instanceof Error ? e.message : "No se pudo cargar el caso."))
        .finally(() => setCargando(null));
      return;
    }
    const nombre = parametros.get("usuario")?.trim();
    const url = parametros.get("partida");
    if (!nombre) return;
    void buscarUsuario(nombre).then((ok) => {
      if (ok && url) void abrirPartida(nombre, url, Number(parametros.get("ply") ?? 0));
    });
    // Runs once, with the link the page was opened with.
  }, []);

  async function buscar(event: React.FormEvent) {
    event.preventDefault();
    const nombre = usuario.trim();
    if (!nombre) return;
    router.replace(`/analizar?usuario=${encodeURIComponent(nombre)}`);
    await buscarUsuario(nombre);
  }

  async function abrir(partida: ResumenPartida) {
    if (!buscado) return;
    router.replace(`/analizar?usuario=${encodeURIComponent(buscado)}&partida=${encodeURIComponent(partida.url)}`);
    await abrirPartida(buscado, partida.url);
  }

  const total = analisis?.jugadas.length ?? 0;

  // Position and last move at the chosen ply, replayed with chess.js.
  const posicion = useMemo(() => {
    const chess = new Chess();
    let ultima: { desde: string; hasta: string } | null = null;
    for (const san of analisis?.jugadas.slice(0, ply) ?? []) {
      const jugada = chess.move(san);
      ultima = { desde: jugada.from, hasta: jugada.to };
    }
    let jaque: string | null = null;
    if (chess.inCheck()) {
      for (const fila of chess.board()) {
        for (const c of fila) if (c?.type === "k" && c.color === chess.turn()) jaque = c.square;
      }
    }
    return { fen: chess.fen(), ultima, jaque };
  }, [analisis, ply]);

  // Autoplay: one move every PASO_REPRODUCCION_MS, stops at the end.
  useEffect(() => {
    if (!reproduciendo) return;
    if (ply >= total) {
      setReproduciendo(false);
      return;
    }
    const t = window.setTimeout(() => setPly((p) => Math.min(total, p + 1)), PASO_REPRODUCCION_MS);
    return () => window.clearTimeout(t);
  }, [reproduciendo, ply, total]);

  useEffect(() => {
    if (!analisis) return;
    const teclado = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [contenteditable=true]")) return;
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) event.preventDefault();
      if (event.key === "ArrowLeft") setPly((p) => Math.max(0, p - 1));
      if (event.key === "ArrowRight") setPly((p) => Math.min(total, p + 1));
      if (event.key === "Home") setPly(0);
      if (event.key === "End") setPly(total);
      if (event.key === " " && !(event.target instanceof HTMLElement && event.target.closest("button, a"))) {
        event.preventDefault();
        setReproduciendo((r) => !r);
      }
    };
    window.addEventListener("keydown", teclado);
    return () => window.removeEventListener("keydown", teclado);
  }, [analisis, total]);

  const momentos = useMemo(() => (analisis ? momentosClave(analisis.curva) : []), [analisis]);
  const punto = ply <= 120 ? analisis?.curva.find((p) => p.ply === ply) ?? null : null;
  const final =
    analisis && ply === total ? `${FINALES[analisis.partida.resultado]}${analisis.final ? ` (${analisis.final})` : ""}` : null;

  function irA(nuevo: number) {
    setReproduciendo(false);
    setPly(nuevo);
  }

  return (
    <div className={styles.pagina}>
      {verResumen && analisis ? <VisorResumen analisis={analisis} onCerrar={() => setVerResumen(false)} /> : null}
      <form className={`${styles.panel} ${propios.buscador}`} onSubmit={buscar}>
        <label htmlFor="usuario" className={styles.titulo}>
          Analizar una partida de Chess.com
        </label>
        <div className={styles.campo}>
          <input
            id="usuario"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            placeholder="Usuario de Chess.com, por ejemplo hikaru"
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" className={styles.principal} disabled={cargando !== null || !usuario.trim()}>
            {cargando === "buscar" ? "Buscando…" : "Buscar partidas"}
          </button>
        </div>
        <p className={styles.nota}>Trae sus últimas partidas rated de bullet, blitz y rapid. Funciona con cualquier cuenta pública.</p>
      </form>
      {error ? <p className={styles.error}>{error}</p> : null}

      {analisis ? (
        <section
          ref={espacio}
          className={propios.analisis}
          aria-label="Análisis de la partida"
          style={{ "--alto-cabecera": `${altoCabecera}px` } as React.CSSProperties}
        >
          <div className={propios.visor}>
            <Marcador
              compacto
              blancas={{ nombre: analisis.partida.blancas.usuario, rating: analisis.contexto.elo_blancas_previo }}
              negras={{ nombre: analisis.partida.negras.usuario, rating: analisis.contexto.elo_negras_previo }}
              relojes={relojesEn(analisis, ply)}
              activo={ply === total ? null : ply % 2 === 0 ? "blancas" : "negras"}
              punto={punto}
              final={final}
            />
            <div className={propios.navegacion}>
              <button type="button" className={styles.principal} onClick={() => { setReproduciendo(false); setVerResumen(true); }}>Ver resumen animado</button>
              <div className={propios.controles} role="group" aria-label="Controles de reproducción">
                <button type="button" className={styles.boton} onClick={() => irA(0)} disabled={ply === 0} aria-label="Ir al principio">
                  ⏮
                </button>
                <button type="button" className={styles.boton} onClick={() => irA(Math.max(0, ply - 1))} disabled={ply === 0} aria-label="Jugada anterior">
                  ◀
                </button>
                <button
                  type="button"
                  className={`${styles.principal} ${propios.reproducir}`}
                  onClick={() => {
                    if (ply >= total) setPly(0);
                    setReproduciendo((r) => !r);
                  }}
                  aria-label={reproduciendo ? "Pausar" : "Reproducir la partida"}
                >
                  {reproduciendo ? "Pausar" : "Reproducir"}
                </button>
                <button type="button" className={styles.boton} onClick={() => irA(Math.min(total, ply + 1))} disabled={ply === total} aria-label="Jugada siguiente">
                  ▶
                </button>
                <button type="button" className={styles.boton} onClick={() => irA(total)} disabled={ply === total} aria-label="Ir al final">
                  ⏭
                </button>
              </div>
              <input
                type="range"
                min={0}
                max={total}
                value={ply}
                onChange={(e) => irA(Number(e.target.value))}
                aria-label="Jugada"
                aria-valuetext={ply === 0 ? "Posición inicial" : `${Math.ceil(ply / 2)}${ply % 2 ? "." : "…"} ${analisis.jugadas[ply - 1]}`}
                className={propios.deslizador}
                style={{ "--avance": `${total ? (ply / total) * 100 : 0}%` } as React.CSSProperties}
              />
              <div className={propios.estado}>
                <strong aria-live="polite">{ply === 0 ? "Posición inicial" : `${Math.ceil(ply / 2)}${ply % 2 ? "." : "…"} ${analisis.jugadas[ply - 1]}`}</strong>
                <span className={propios.ayudaTeclado}>← → para moverte · espacio para reproducir</span>
                <span>{ply} / {total}</span>
              </div>
            </div>
          </div>
          <div className={`${styles.cuerpo} ${propios.cuerpoAnalisis}`}>
            <div className={styles.tablero}>
              <Tablero fen={posicion.fen} ultima={posicion.ultima} jaque={posicion.jaque} />
            </div>
            <div className={styles.lateral}>
              <Planilla jugadas={analisis.jugadas} curva={analisis.curva} actual={ply} momentos={momentos} onElegir={irA} />
              <button
                type="button"
                className={styles.boton}
                onClick={() => {
                  setAnalisis(null);
                  router.replace(`/analizar?usuario=${encodeURIComponent(buscado ?? "")}`);
                }}
              >
                {buscado ? `Volver a las partidas de ${buscado}` : "Buscar otra partida"}
              </button>
            </div>
          </div>
          <Curva
            curva={analisis.curva}
            actual={Math.min(ply, total - 1)}
            momentos={momentos}
            onElegir={irA}
            revelar={analisis.partida.url}
          />
        </section>
      ) : ficha ? (
        <section className={`${styles.panel} ${propios.listado}`} aria-label={`Partidas de ${ficha.usuario}`}>
          <div className={propios.perfil}>
            {ficha.avatar ? <img src={ficha.avatar} alt="" width={56} height={56} /> : null}
            <div>
              <h2 className={styles.titulo}>
                {ficha.titulo ? `${ficha.titulo} ` : ""}
                {ficha.usuario}
              </h2>
              <p className={styles.nota}>
                Rating actual: bullet {ficha.ratings.bullet ?? "–"}, blitz {ficha.ratings.blitz ?? "–"}, rapid {ficha.ratings.rapid ?? "–"}
              </p>
            </div>
          </div>
          {partidas.length === 0 ? (
            <p className={styles.texto}>No tiene partidas rated de bullet, blitz o rapid en los últimos meses.</p>
          ) : (
            <ul className={propios.partidas}>
              {partidas.map((p, i) => {
                const resultado = resultadoPara(p, ficha.usuario);
                const conBlancas = p.blancas.usuario.toLowerCase() === ficha.usuario.toLowerCase();
                const rival = conBlancas ? p.negras : p.blancas;
                return (
                  <li key={p.url} style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}>
                    <button type="button" className={propios.fila} onClick={() => abrir(p)} disabled={cargando !== null}>
                      <span className={`${propios.chip} ${propios[CLASE_RESULTADO[resultado]]}`}>{resultado}</span>
                      <span className={propios.rival}>
                        <span className={`${propios.color} ${conBlancas ? propios.colorBlancas : propios.colorNegras}`} aria-label={conBlancas ? "jugó con blancas" : "jugó con negras"} />
                        contra <strong>{rival.usuario}</strong> <span className={styles.nota}>{rival.rating}</span>
                      </span>
                      <span className={propios.meta}>
                        {p.ritmo}, {new Date(p.fin * 1000).toLocaleDateString("es-AR", { day: "numeric", month: "short" })}
                      </span>
                      <span className={propios.ir}>{cargando === p.url ? "Analizando…" : "Analizar"}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      ) : null}
    </div>
  );
}
