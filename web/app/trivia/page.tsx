"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Tablero } from "@/components/Tablero";
import { Marcador } from "@/components/Marcador";
import {
  favorito,
  NOMBRES,
  posicionEn,
  relojesEn,
  RESULTADOS,
  type Resultado,
} from "@/lib/partida";
import {
  cargarCaso,
  sortearCasos,
  type CasoTrivia,
  type IndiceTrivia,
  type RespuestaTrivia,
} from "@/lib/trivia";
import shared from "@/components/Partida.module.css";
import styles from "./trivia.module.css";

export default function Pagina() {
  return (
    <Suspense fallback={<p>Cargando trivia…</p>}>
      <Trivia />
    </Suspense>
  );
}
function Trivia() {
  const expo = useSearchParams().get("modo") === "expo";
  const [casos, setCasos] = useState<CasoTrivia[]>([]);
  const [respuestas, setRespuestas] = useState<RespuestaTrivia[]>([]);
  const [eleccion, setEleccion] = useState<Resultado | null>(null);
  const [indice, setIndice] = useState(0);
  const [revelado, setRevelado] = useState(0);
  const [terminado, setTerminado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const request = useRef(0);
  const titulo = useRef<HTMLHeadingElement>(null);
  async function empezar() {
    const current = ++request.current;
    setCargando(true);
    setError(null);
    try {
      const response = await fetch("/app/trivia/index.json");
      if (!response.ok)
        throw new Error("El banco de trivia no está disponible.");
      const index: IndiceTrivia = await response.json();
      const nuevos = await Promise.all(
        sortearCasos(index.casos, expo ? 1 : 3).map(cargarCaso),
      );
      if (current !== request.current) return;
      setCasos(nuevos);
      setRespuestas([]);
      setEleccion(null);
      setIndice(0);
      setRevelado(0);
      setTerminado(false);
    } catch (e) {
      if (current === request.current)
        setError(
          e instanceof Error ? e.message : "No se pudo iniciar la trivia.",
        );
    } finally {
      if (current === request.current) setCargando(false);
    }
  }
  useEffect(() => {
    void empezar();
    return () => {
      request.current++;
    };
  }, [expo]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    titulo.current?.focus();
  }, [respuestas.length, indice, terminado]);
  if (cargando) return <p role="status">Preparando posiciones reales…</p>;
  if (error)
    return (
      <div role="alert">
        <p>{error}</p>
        <button className={shared.boton} onClick={empezar}>
          Reintentar
        </button>
      </div>
    );
  const revisando = respuestas.length > indice;
  if (terminado) {
    const vos = respuestas.filter(
      (r) => r.eleccion === r.caso.analisis.partida.resultado,
    ).length;
    const modelo = respuestas.filter(
      (r) =>
        favorito(r.caso.analisis.curva.find((p) => p.ply === r.caso.ply)!) ===
        r.caso.analisis.partida.resultado,
    ).length;
    return (
      <section className={styles.final}>
        <p className={styles.etiqueta}>Ronda terminada</p>
        <h1 ref={titulo} tabIndex={-1}>
          {expo ? "El curso" : "Vos"}: {vos}/{casos.length} · Modelo: {modelo}/
          {casos.length}
        </h1>
        <p>
          Un punto por resultado acertado. Este marcador corresponde a esta
          ronda; la evaluación del modelo está en el recorrido del proyecto.
        </p>
        <div className={shared.acciones}>
          <button className={shared.principal} onClick={empezar}>
            Jugar otra vez
          </button>
          <Link href={expo ? "/trivia" : "/trivia?modo=expo"}>
            {" "}
            {expo ? "Trivia de tres preguntas" : "Modo exposición"}
          </Link>
        </div>
        {respuestas.map((r, i) => (
          <Link key={r.caso.id} href={`/analizar?caso=${r.caso.id}`}>
            Analizar partida {i + 1} y ver su resumen →
          </Link>
        ))}
      </section>
    );
  }
  const caso = casos[indice];
  if (!caso) return null;
  const a = caso.analisis;
  const punto = a.curva.find((p) => p.ply === caso.ply)!;
  const posicion = posicionEn(a.jugadas, caso.ply);
  return (
    <div className={`${styles.pagina} ${expo ? styles.expo : ""}`}>
      <header>
        <p className={styles.etiqueta}>
          {expo
            ? "Desafío para el curso · una posición"
            : revisando
              ? "El momento de la verdad"
              : "Tres posiciones. Tu intuición contra el modelo."}
        </p>
        <h1 ref={titulo} tabIndex={-1}>
          {`¿Quién gana? ${indice + 1}/${casos.length}`}
        </h1>
        <p>
          {revisando
            ? "Primero el pronóstico. Después, lo que pasó de verdad."
            : expo
              ? "Voten a mano alzada. El presentador registra la respuesta del curso."
              : "Elegí quién gana, descubrí qué dice el modelo y revelá el resultado. Después, otra posición."}
        </p>
      </header>
      <Marcador
        compacto
        ocultarPronostico={!(revisando && revelado >= 1)}
        blancas={{ nombre: "Blancas", rating: a.contexto.elo_blancas_previo }}
        negras={{ nombre: "Negras", rating: a.contexto.elo_negras_previo }}
        relojes={relojesEn(a, caso.ply)}
        activo={caso.ply % 2 ? "negras" : "blancas"}
        punto={revisando && revelado >= 1 ? punto : null}
        mostrarCambio={false}
      />
      <div className={styles.cuerpo}>
        <Tablero
          fen={caso.fen}
          ultima={posicion.ultima}
          jaque={posicion.jaque}
        />
        <section className={styles.panel} aria-label="Pregunta y revelaciones">
          <p className={styles.etiqueta}>
            {a.partida.ritmo} · {a.partida.tiempo_base_seg / 60} min +{" "}
            {a.partida.incremento_seg} s
          </p>
          <p>
            Jugada {Math.ceil(caso.ply / 2)} · Mueven{" "}
            {caso.ply % 2 ? "negras" : "blancas"} · Última:{" "}
            {a.jugadas[caso.ply - 1]}
          </p>
          {!revisando ? (
            <>
              <div
                className={styles.opciones}
                role="group"
                aria-label="Elegí quién gana"
              >
                {RESULTADOS.map((r) => (
                  <button
                    key={r}
                    className={styles.opcion}
                    aria-pressed={eleccion === r}
                    onClick={() => setEleccion(r)}
                  >
                    {NOMBRES[r]}
                  </button>
                ))}
              </div>
              <button
                className={shared.principal}
                disabled={!eleccion}
                onClick={() => {
                  if (!eleccion) return;
                  setRespuestas([...respuestas, { caso, eleccion }]);
                  setEleccion(null);
                }}
              >
                Confirmar respuesta
              </button>
              <p>
                El resultado está oculto. Podés mirar el tablero todo el tiempo
                que quieras.
              </p>
            </>
          ) : (
            <>
              <p>
                Tu elección:{" "}
                <strong>{NOMBRES[respuestas[indice].eleccion]}</strong>
              </p>
              {revelado === 0 && (
                <button
                  className={shared.principal}
                  onClick={() => setRevelado(1)}
                >
                  Ver pronóstico
                </button>
              )}
              {revelado >= 1 && (
                <div className={styles.revelacion}>
                  <h2>El modelo eligió {NOMBRES[favorito(punto)]}</h2>
                  <p>
                    Blancas {Math.round(punto.gana_blancas * 100)} % · Tablas{" "}
                    {Math.round(punto.empate * 100)} % · Negras{" "}
                    {Math.round(punto.gana_negras * 100)} %
                  </p>
                </div>
              )}
              {revelado === 1 && (
                <button
                  className={shared.principal}
                  onClick={() => setRevelado(2)}
                >
                  Ver resultado
                </button>
              )}
              {revelado === 2 && (
                <div className={styles.revelacion} role="status">
                  <h2>
                    {a.partida.resultado === "Empate"
                      ? "Terminó en tablas"
                      : `Ganaron las ${NOMBRES[a.partida.resultado].toLowerCase()}`}
                  </h2>
                  <p>Finalización: {a.final}</p>
                  <p>
                    {respuestas[indice].eleccion === a.partida.resultado
                      ? "¡Acertaste!"
                      : "Esta vez no acertaste."}{" "}
                    {favorito(punto) === a.partida.resultado
                      ? "El modelo acertó."
                      : "El modelo también puede equivocarse: esta vez falló."}
                  </p>
                  <button
                    className={shared.principal}
                    onClick={() => {
                      if (indice + 1 === casos.length) setTerminado(true);
                      else {
                        setIndice(indice + 1);
                        setRevelado(0);
                      }
                    }}
                  >
                    {indice + 1 === casos.length
                      ? "Ver marcador"
                      : "Siguiente posición"}
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
      <p className={styles.nota}>
        Partidas de test. Posiciones sorteadas sin filtrar por aciertos del
        modelo.{" "}
        <Link href={expo ? "/trivia" : "/trivia?modo=expo"}>
          {expo ? "Modo individual" : "Modo exposición"}
        </Link>
      </p>
    </div>
  );
}
