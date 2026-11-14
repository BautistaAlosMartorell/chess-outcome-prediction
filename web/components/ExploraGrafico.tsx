"use client";

import { useEffect, useId, useState } from "react";
import { GraficoAltair, type VistaVega } from "./GraficoAltair";
import styles from "./ExploraControles.module.css";

type Opcion = { valor: string; etiqueta: string; punto?: "acierto" | "error" };

const RITMOS: Opcion[] = [
  { valor: "todos", etiqueta: "Todos" },
  { valor: "bullet", etiqueta: "Bullet" },
  { valor: "blitz", etiqueta: "Blitz" },
  { valor: "rapid", etiqueta: "Rapid" },
];

// The values are the ones the chart's `acierto` param declares (src/app_charts.py).
const ACIERTOS: Opcion[] = [
  { valor: "Todas", etiqueta: "Todas" },
  { valor: "Acertó", etiqueta: "Acertó", punto: "acierto" },
  { valor: "Se equivocó", etiqueta: "Se equivocó", punto: "error" },
];

const EJES: Opcion[] = [
  { valor: "Material", etiqueta: "Material" },
  { valor: "Reloj", etiqueta: "Reloj" },
];

const MARCAS = [0, 20, 40, 60, 80, 100, 120];
const PASO_MS = 450;

function nombreNivel(nivel: string) {
  const texto = nivel.replace(/_/g, " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function Segmentos({
  leyenda,
  opciones,
  valor,
  alCambiar,
  envuelve = false,
}: {
  leyenda: string;
  opciones: Opcion[];
  valor: string;
  alCambiar: (valor: string) => void;
  envuelve?: boolean;
}) {
  const nombre = useId();
  return (
    <fieldset className={envuelve ? `${styles.grupo} ${styles.ancho}` : styles.grupo}>
      <legend>{leyenda}</legend>
      <div className={envuelve ? styles.fichas : styles.segmentos}>
        {opciones.map((o) => (
          <label key={o.valor} className={styles.opcion}>
            <input type="radio" name={nombre} value={o.valor} checked={valor === o.valor} onChange={() => alCambiar(o.valor)} />
            <span>
              {o.punto ? <i className={o.punto === "acierto" ? styles.puntoAcierto : styles.puntoError} aria-hidden="true" /> : null}
              {o.etiqueta}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// Explorá's chart with the page's own controls instead of the ones Altair binds under it.
// React holds the four values and writes them into the chart's params; the chart is redrawn
// (a new width, for example) with the same values.
export function ExploraGrafico({ niveles }: { niveles: string[] }) {
  const [vista, setVista] = useState<VistaVega | null>(null);
  const [corte, setCorte] = useState(40);
  const [ritmo, setRitmo] = useState("todos");
  const [nivel, setNivel] = useState("todos");
  const [acierto, setAcierto] = useState("Todas");
  const [eje, setEje] = useState("Material");
  const [reproduciendo, setReproduciendo] = useState(false);
  const idCorte = useId();

  useEffect(() => {
    if (!vista) return;
    const valores: [string, unknown][] = [["corte", corte], ["ritmo", ritmo], ["nivel", nivel], ["acierto", acierto], ["eje_x", eje]];
    for (const [nombre, valor] of valores) {
      try {
        vista.signal(nombre, valor);
      } catch {
        // A chart built before this param existed (a cached older spec): leave that control without effect.
      }
    }
    vista.runAsync();
  }, [vista, corte, ritmo, nivel, acierto, eje]);

  // Play: the cut advances by itself, so the points can be watched reorganising as the game goes on.
  useEffect(() => {
    if (!reproduciendo) return;
    if (corte >= 120) {
      setReproduciendo(false);
      return;
    }
    const espera = window.setTimeout(() => setCorte((c) => Math.min(120, c + 5)), PASO_MS);
    return () => window.clearTimeout(espera);
  }, [reproduciendo, corte]);

  function reproducir() {
    if (reproduciendo) return setReproduciendo(false);
    if (corte >= 120) setCorte(0);
    setReproduciendo(true);
  }

  return (
    <>
      <div className={styles.panel}>
        <div className={styles.deslizador} style={{ "--avance": `${(corte / 120) * 100}%` } as React.CSSProperties}>
          <div className={styles.cabecera}>
            <label htmlFor={idCorte}>Plies jugados</label>
            <output htmlFor={idCorte} className={`${styles.valor} cifra`}>
              {corte}
            </output>
            <span className={styles.jugada}>{corte === 0 ? "antes de mover" : `jugada ${corte / 2}`}</span>
            <button type="button" className={styles.reproducir} onClick={reproducir} aria-pressed={reproduciendo}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                {reproduciendo ? <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" /> : <path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" />}
              </svg>
              {reproduciendo ? "Pausar" : corte >= 120 ? "Repetir" : "Reproducir"}
            </button>
          </div>
          <input
            id={idCorte}
            type="range"
            min={0}
            max={120}
            step={5}
            value={corte}
            aria-valuetext={corte === 0 ? "Antes de mover" : `${corte} plies, jugada ${corte / 2}`}
            onChange={(e) => {
              setReproduciendo(false);
              setCorte(Number(e.target.value));
            }}
          />
          <div className={`${styles.marcas} cifra`} aria-hidden="true">
            {MARCAS.map((m) => (
              <span key={m}>{m}</span>
            ))}
          </div>
        </div>
        <div className={styles.filtros}>
          <Segmentos leyenda="Eje horizontal" opciones={EJES} valor={eje} alCambiar={setEje} />
          <Segmentos leyenda="Ritmo" opciones={RITMOS} valor={ritmo} alCambiar={setRitmo} />
          <Segmentos leyenda="Partidas" opciones={ACIERTOS} valor={acierto} alCambiar={setAcierto} />
          <Segmentos
            leyenda="Nivel"
            envuelve
            opciones={[{ valor: "todos", etiqueta: "Todos" }, ...niveles.map((n) => ({ valor: n, etiqueta: nombreNivel(n) }))]}
            valor={nivel}
            alCambiar={setNivel}
          />
        </div>
      </div>
      <GraficoAltair
        src="/app/graficos/explora.json"
        ocultarControles
        onVista={setVista}
        descripcion="Dispersión de partidas de test: material contra la ventaja que da el modelo, coloreada por el resultado real, con la curva de probabilidades de la partida elegida. Los controles de arriba eligen el corte, el ritmo, el nivel y si se ven las partidas acertadas o falladas."
      />
    </>
  );
}
