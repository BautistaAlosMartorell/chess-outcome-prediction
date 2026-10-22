"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Punto } from "@/lib/api";
import type { Momento } from "@/lib/movimiento";
import styles from "./Curva.module.css";

type Props = {
  curva: Punto[];
  // Ply currently shown on the board (replay) or the latest one (live game).
  actual?: number;
  momentos?: Momento[];
  onElegir?: (ply: number) => void;
  // Changing this key replays the left-to-right reveal (a newly opened game).
  revelar?: string;
};

const ALTO = 240;
const MARGEN = { izq: 40, der: 78, arriba: 18, abajo: 30 };
// The x axis starts this wide so the first moves don't stretch across the whole chart.
const PLIES_MINIMOS = 40;

const BANDAS = [
  { clave: "blancas", nombre: "Blancas", clase: styles.bandaBlancas },
  { clave: "tablas", nombre: "Tablas", clase: styles.bandaTablas },
  { clave: "negras", nombre: "Negras", clase: styles.bandaNegras },
] as const;

function pct(p: number) {
  return `${Math.round(p * 100)} %`;
}

function nombreJugada(ply: number) {
  if (ply === 0) return "Antes de mover";
  return `Jugada ${Math.ceil(ply / 2)} de las ${ply % 2 ? "blancas" : "negras"}`;
}

export function Curva({ curva, actual, momentos = [], onElegir, revelar }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const recorte = useId();
  const [ancho, setAncho] = useState(640);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setAncho(Math.max(280, entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const dibujable = curva.length >= 2;
  const ultimo = curva.length ? curva[curva.length - 1].ply : 0;
  const dominio = Math.max(ultimo, PLIES_MINIMOS);
  const anchoUtil = ancho - MARGEN.izq - MARGEN.der;
  const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo;
  const x = (ply: number) => MARGEN.izq + (ply / dominio) * anchoUtil;
  const y = (p: number) => ALTO - MARGEN.abajo - p * altoUtil;

  // Cumulative bounds from the bottom: white, then draw, then black up to 1.
  const limites = curva.map((p) => [0, p.gana_blancas, p.gana_blancas + p.empate, 1]);
  const area = (banda: number) => {
    if (!dibujable) return "";
    const arriba = curva.map((p, i) => `${x(p.ply)},${y(limites[i][banda + 1])}`);
    const abajo = curva.map((p, i) => `${x(p.ply)},${y(limites[i][banda])}`).reverse();
    return `M${arriba.join("L")}L${abajo.join("L")}Z`;
  };

  const puntoHover = hover !== null ? curva.find((p) => p.ply === hover) : undefined;

  function plyDesdeEvento(event: React.MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    // The SVG scales to its box: convert screen pixels back to chart units.
    const px = (event.clientX - rect.left) * (ancho / rect.width);
    const ply = Math.round(((px - MARGEN.izq) / anchoUtil) * dominio);
    return Math.min(Math.max(ply, curva[0]?.ply ?? 0), ultimo);
  }

  const ticks = Array.from({ length: Math.floor(dominio / 20) + 1 }, (_, i) => i * 20);
  const final = dibujable ? limites[limites.length - 1] : null;

  return (
    <figure className={styles.figura}>
      <figcaption className={styles.titulo}>
        <span>Cómo se movió la partida</span>
        <ul className={styles.leyenda}>
          {BANDAS.map((b) => (
            <li key={b.clave}>
              <span className={`${styles.muestra} ${b.clase}`} aria-hidden="true" />
              {b.nombre}
            </li>
          ))}
          {momentos.length ? (
            <li>
              <span className={styles.muestraMomento} aria-hidden="true" />
              Momento clave
            </li>
          ) : null}
        </ul>
      </figcaption>
      <div ref={contenedor} className={styles.lienzo}>
        <svg
          viewBox={`0 0 ${ancho} ${ALTO}`}
          role="img"
          aria-label="Área apilada: probabilidad de que ganen las blancas, de tablas y de que ganen las negras en cada jugada. Los valores están en la planilla."
          onPointerMove={(e) => dibujable && setHover(plyDesdeEvento(e))}
          onPointerLeave={() => setHover(null)}
          onClick={(e) => dibujable && onElegir?.(plyDesdeEvento(e))}
          className={onElegir ? styles.clicable : undefined}
        >
          <defs>
            <clipPath id={recorte}>
              <rect key={revelar} x={MARGEN.izq} y={0} width={anchoUtil} height={ALTO} className={revelar ? styles.revelado : undefined} />
            </clipPath>
          </defs>
          <rect x={MARGEN.izq} y={MARGEN.arriba} width={anchoUtil} height={altoUtil} rx={6} className={styles.vacio} />
          <g clipPath={`url(#${recorte})`}>
            {BANDAS.map((b, i) => (
              <path key={b.clave} d={area(i)} className={`${b.clase} ${styles.banda}`} />
            ))}
          </g>
          <line x1={MARGEN.izq} x2={ancho - MARGEN.der} y1={y(0.5)} y2={y(0.5)} className={styles.mitad} />
          <rect x={MARGEN.izq} y={MARGEN.arriba} width={anchoUtil} height={altoUtil} rx={6} className={styles.marco} />
          {[0, 0.5, 1].map((p) => (
            <text key={p} x={MARGEN.izq - 8} y={y(p) + 4} className={styles.ejeY}>
              {p * 100}
            </text>
          ))}
          {ticks.map((t) => (
            <text key={t} x={x(t)} y={ALTO - 8} className={styles.ejeX}>
              {t / 2}
            </text>
          ))}
          {final
            ? BANDAS.map((b, i) => {
                if (final[i + 1] - final[i] < 0.07) return null; // too thin to label beside its band
                return (
                  <text key={b.clave} x={ancho - MARGEN.der + 10} y={y((final[i] + final[i + 1]) / 2) + 4} className={styles.etiqueta}>
                    {b.nombre}
                  </text>
                );
              })
            : null}
          {dibujable
            ? momentos.map((m) => (
                <g key={m.ply} className={styles.momento}>
                  <line x1={x(m.ply)} x2={x(m.ply)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} />
                  <circle cx={x(m.ply)} cy={MARGEN.arriba - 8} r={5} />
                </g>
              ))
            : null}
          {actual !== undefined && dibujable ? (
            <line x1={x(actual)} x2={x(actual)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} className={styles.actual} />
          ) : null}
          {puntoHover ? (
            <line x1={x(puntoHover.ply)} x2={x(puntoHover.ply)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} className={styles.guia} />
          ) : null}
        </svg>
        {puntoHover ? (
          <div className={styles.tooltip} style={{ left: Math.min(x(puntoHover.ply) + 14, ancho - 200), top: MARGEN.arriba + 6 }}>
            <strong>{nombreJugada(puntoHover.ply)}</strong>
            <span>
              <i className={styles.bandaBlancas} /> Blancas {pct(puntoHover.gana_blancas)}
            </span>
            <span>
              <i className={styles.bandaTablas} /> Tablas {pct(puntoHover.empate)}
            </span>
            <span>
              <i className={styles.bandaNegras} /> Negras {pct(puntoHover.gana_negras)}
            </span>
          </div>
        ) : null}
        {!dibujable ? <p className={styles.vacioTexto}>La curva se dibuja a medida que avanza la partida.</p> : null}
      </div>
      <p className={styles.ejeTitulo}>Número de jugada</p>
    </figure>
  );
}
