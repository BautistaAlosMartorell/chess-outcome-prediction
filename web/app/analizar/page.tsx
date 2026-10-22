"use client";

import { Chess } from "chess.js";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Curva } from "@/components/Curva";
import { Marcador } from "@/components/Marcador";
import styles from "@/components/Partida.module.css";
import { Planilla } from "@/components/Planilla";
import { Tablero } from "@/components/Tablero";
import { analizar, ApiError, traerFicha, traerPartidas, type Analisis, type Ficha, type ResumenPartida } from "@/lib/api";
import propios from "./analizar.module.css";

const FINALES: Record<string, string> = {
  "Gana Blancas": "Ganaron las blancas",
  "Gana Negras": "Ganaron las negras",
  Empate: "Tablas",
};

function resultadoPara(partida: ResumenPartida, usuario: string): string {
  if (partida.resultado === "Empate") return "Tablas";
  const ganador = partida.resultado === "Gana Blancas" ? partida.blancas : partida.negras;
  return ganador.usuario.toLowerCase() === usuario.toLowerCase() ? "Ganó" : "Perdió";
}

// Clock of each side at ply k: the time left after its last move up to k (the base time before it moved).
function relojesEn(analisis: Analisis, k: number) {
  const base = analisis.partida.tiempo_base_seg * 1000;
  const ultimo = (paridad: number) => {
    for (let ply = k; ply >= 1; ply--) {
      if (ply % 2 === paridad) {
        const s = analisis.relojes_seg[ply - 1];
        return s === null ? null : s * 1000;
      }
    }
    return base;
  };
  return { blancas: ultimo(1), negras: ultimo(0) };
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
  const [analisis, setAnalisis] = useState<Analisis | null>(null);
  const [ply, setPly] = useState(0);
  const [cargando, setCargando] = useState<"buscar" | "partida" | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    setCargando("partida");
    setError(null);
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

  // Links like /analizar?usuario=hikaru&partida=<url> search and open on their own.
  const inicial = useRef(false);
  useEffect(() => {
    if (inicial.current) return;
    inicial.current = true;
    const nombre = parametros.get("usuario")?.trim();
    const url = parametros.get("partida");
    if (!nombre) return;
    void buscarUsuario(nombre).then((ok) => {
      if (ok && url) void abrirPartida(nombre, url, Number(parametros.get("ply") ?? 0));
    });
    // Runs once, on the first render, with the link the page was opened with.
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
    return { fen: chess.fen(), ultima };
  }, [analisis, ply]);

  useEffect(() => {
    if (!analisis) return;
    const teclado = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "ArrowLeft") setPly((p) => Math.max(0, p - 1));
      if (event.key === "ArrowRight") setPly((p) => Math.min(total, p + 1));
      if (event.key === "Home") setPly(0);
      if (event.key === "End") setPly(total);
    };
    window.addEventListener("keydown", teclado);
    return () => window.removeEventListener("keydown", teclado);
  }, [analisis, total]);

  const punto = analisis?.curva.find((p) => p.ply === ply) ?? null;
  const final =
    analisis && ply === total
      ? `${FINALES[analisis.partida.resultado]}${analisis.final ? ` (${analisis.final})` : ""}`
      : null;

  return (
    <div className={styles.pagina}>
      <form className={propios.buscador} onSubmit={buscar}>
        <label htmlFor="usuario" className={styles.titulo}>
          Analizar una partida de Chess.com
        </label>
        <div className={styles.campo}>
          <input
            id="usuario"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            placeholder="Usuario de Chess.com"
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
        <>
          <Marcador
            blancas={{ nombre: analisis.partida.blancas.usuario, rating: analisis.contexto.elo_blancas_previo }}
            negras={{ nombre: analisis.partida.negras.usuario, rating: analisis.contexto.elo_negras_previo }}
            relojes={relojesEn(analisis, ply)}
            activo={ply === total ? null : ply % 2 === 0 ? "blancas" : "negras"}
            punto={punto}
            final={final}
          />
          <div className={styles.cuerpo}>
            <div className={styles.tablero}>
              <Tablero fen={posicion.fen} ultima={posicion.ultima} />
              <div className={propios.controles}>
                <button type="button" className={styles.boton} onClick={() => setPly(0)} aria-label="Ir al principio">
                  |◀
                </button>
                <button type="button" className={styles.boton} onClick={() => setPly((p) => Math.max(0, p - 1))} aria-label="Jugada anterior">
                  ◀
                </button>
                <input
                  type="range"
                  min={0}
                  max={total}
                  value={ply}
                  onChange={(e) => setPly(Number(e.target.value))}
                  aria-label="Jugada"
                  className={propios.deslizador}
                />
                <button type="button" className={styles.boton} onClick={() => setPly((p) => Math.min(total, p + 1))} aria-label="Jugada siguiente">
                  ▶
                </button>
                <button type="button" className={styles.boton} onClick={() => setPly(total)} aria-label="Ir al final">
                  ▶|
                </button>
              </div>
              <p className={styles.nota}>También con las flechas del teclado.</p>
            </div>
            <div className={styles.lateral}>
              <Planilla jugadas={analisis.jugadas} curva={analisis.curva} actual={ply} onElegir={setPly} />
              <button
                type="button"
                className={styles.boton}
                onClick={() => {
                  setAnalisis(null);
                  router.replace(`/analizar?usuario=${encodeURIComponent(buscado ?? "")}`);
                }}
              >
                Volver a las partidas de {buscado}
              </button>
            </div>
          </div>
          <Curva curva={analisis.curva} actual={Math.min(ply, total - 1)} onElegir={setPly} />
        </>
      ) : ficha ? (
        <section className={propios.listado} aria-label={`Partidas de ${ficha.usuario}`}>
          <h2 className={styles.titulo}>
            {ficha.usuario}
            {ficha.titulo ? ` (${ficha.titulo})` : ""}
          </h2>
          <p className={styles.nota}>
            Rating actual: bullet {ficha.ratings.bullet ?? "–"}, blitz {ficha.ratings.blitz ?? "–"}, rapid {ficha.ratings.rapid ?? "–"}.
          </p>
          {partidas.length === 0 ? (
            <p className={styles.texto}>No tiene partidas rated de bullet, blitz o rapid en los últimos meses.</p>
          ) : (
            <table className={propios.tabla}>
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">Ritmo</th>
                  <th scope="col">Blancas</th>
                  <th scope="col">Negras</th>
                  <th scope="col">Resultado</th>
                  <th scope="col">
                    <span className={propios.oculto}>Acción</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {partidas.map((p) => (
                  <tr key={p.url}>
                    <td>{new Date(p.fin * 1000).toLocaleDateString("es-AR", { day: "numeric", month: "short" })}</td>
                    <td>{p.ritmo}</td>
                    <td>
                      {p.blancas.usuario} <span className={styles.nota}>{p.blancas.rating}</span>
                    </td>
                    <td>
                      {p.negras.usuario} <span className={styles.nota}>{p.negras.rating}</span>
                    </td>
                    <td>{resultadoPara(p, ficha.usuario)}</td>
                    <td>
                      <button type="button" className={styles.boton} onClick={() => abrir(p)} disabled={cargando !== null}>
                        {cargando === "partida" ? "Analizando…" : "Analizar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}
    </div>
  );
}
