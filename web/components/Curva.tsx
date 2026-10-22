"use client";

import { useEffect, useRef, useState } from "react";
import type { Punto } from "@/lib/api";
import styles from "./Curva.module.css";

type Props = {
  curva: Punto[];
  // Ply currently shown on the board (replay) or the latest one (live game).
  actual?: number;
  onElegir?: (ply: number) => void;
};

const ALTO = 220;
const MARGEN = { izq: 40, der: 74, arriba: 8, abajo: 28 };
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

export function Curva({ curva, actual, onElegir }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [ancho, setAncho] = useState(640);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setAncho(Math.max(280, entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const ultimo = curva.length ? curva[curva.length - 1].ply : 0;
  const dominio = Math.max(ultimo, PLIES_MINIMOS);
  const x = (ply: number) => MARGEN.izq + (ply / dominio) * (ancho - MARGEN.izq - MARGEN.der);
  const y = (p: number) => ALTO - MARGEN.abajo - p * (ALTO - MARGEN.arriba - MARGEN.abajo);

  // Cumulative bounds from the bottom: white, then draw, then black up to 1.
  const limites = curva.map((p) => [0, p.gana_blancas, p.gana_blancas + p.empate, 1]);
  const dibujable = curva.length >= 2;
  const area = (banda: number) => {
    if (!dibujable) return "";
    const arriba = curva.map((p, i) => `${x(p.ply)},${y(limites[i][banda + 1])}`);
    const abajo = curva.map((p, i) => `${x(p.ply)},${y(limites[i][banda])}`).reverse();
    return `M${arriba.join("L")}L${abajo.join("L")}Z`;
  };

  const elegido = hover ?? null;
  const puntoHover = elegido !== null ? curva.find((p) => p.ply === elegido) : undefined;

  function plyDesdeEvento(event: React.MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const ply = Math.round(((px - MARGEN.izq) / (ancho - MARGEN.izq - MARGEN.der)) * dominio);
    return Math.min(Math.max(ply, curva[0]?.ply ?? 0), ultimo);
  }

  const ticks = Array.from({ length: Math.floor(dominio / 20) + 1 }, (_, i) => i * 20);
  const final = dibujable ? limites[limites.length - 1] : null;

  return (
    <figure className={styles.figura}>
      <figcaption className={styles.titulo}>
        <span>Probabilidad de cada resultado, jugada a jugada</span>
        <ul className={styles.leyenda}>
          {BANDAS.map((b) => (
            <li key={b.clave}>
              <span className={`${styles.muestra} ${b.clase}`} aria-hidden="true" />
              {b.nombre}
            </li>
          ))}
        </ul>
      </figcaption>
      <div ref={contenedor} className={styles.lienzo}>
        <svg
          width={ancho}
          height={ALTO}
          role="img"
          aria-label="Área apilada: probabilidad de que ganen las blancas, de tablas y de que ganen las negras en cada jugada. Los valores están en la planilla."
          onPointerMove={(e) => curva.length && setHover(plyDesdeEvento(e))}
          onPointerLeave={() => setHover(null)}
          onClick={(e) => curva.length && onElegir?.(plyDesdeEvento(e))}
          className={onElegir ? styles.clicable : undefined}
        >
          <rect
            x={MARGEN.izq}
            y={MARGEN.arriba}
            width={ancho - MARGEN.izq - MARGEN.der}
            height={ALTO - MARGEN.arriba - MARGEN.abajo}
            className={styles.vacio}
          />
          {BANDAS.map((b, i) => (
            <path key={b.clave} d={area(i)} className={b.clase} />
          ))}
          <line x1={MARGEN.izq} x2={ancho - MARGEN.der} y1={y(0.5)} y2={y(0.5)} className={styles.mitad} />
          <rect
            x={MARGEN.izq}
            y={MARGEN.arriba}
            width={ancho - MARGEN.izq - MARGEN.der}
            height={ALTO - MARGEN.arriba - MARGEN.abajo}
            className={styles.marco}
          />
          {[0, 0.5, 1].map((p) => (
            <text key={p} x={MARGEN.izq - 6} y={y(p) + 4} className={styles.ejeY}>
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
                const alto = final[i + 1] - final[i];
                if (alto < 0.07) return null; // too thin to label next to its band
                return (
                  <text key={b.clave} x={ancho - MARGEN.der + 8} y={y((final[i] + final[i + 1]) / 2) + 4} className={styles.etiqueta}>
                    {b.nombre}
                  </text>
                );
              })
            : null}
          {actual !== undefined && dibujable ? (
            <line x1={x(actual)} x2={x(actual)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} className={styles.actual} />
          ) : null}
          {puntoHover ? (
            <line x1={x(puntoHover.ply)} x2={x(puntoHover.ply)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} className={styles.guia} />
          ) : null}
        </svg>
        {puntoHover ? (
          <div
            className={styles.tooltip}
            style={{ left: Math.min(x(puntoHover.ply) + 12, ancho - 170), top: MARGEN.arriba + 4 }}
          >
            <strong>{puntoHover.ply === 0 ? "Antes de mover" : `Jugada ${Math.ceil(puntoHover.ply / 2)}${puntoHover.ply % 2 ? " (blancas)" : " (negras)"}`}</strong>
            <span>Blancas {pct(puntoHover.gana_blancas)}</span>
            <span>Tablas {pct(puntoHover.empate)}</span>
            <span>Negras {pct(puntoHover.gana_negras)}</span>
          </div>
        ) : null}
        {!dibujable ? <p className={styles.vacioTexto}>La curva se dibuja a medida que avanza la partida.</p> : null}
      </div>
      <p className={styles.ejeTitulo}>Número de jugada</p>
    </figure>
  );
}
