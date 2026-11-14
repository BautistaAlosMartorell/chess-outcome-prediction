"use client";

import { useEffect, useRef, useState } from "react";
import { useVisto } from "@/lib/useVisto";

// Numbers as the app writes them (es-AR): 1.559.622 or 0,791. Each one is animated on its own.
const NUMERO = /\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?/g;
const DURACION_MS = 1100;

function aTexto(token: string, progreso: number): string {
  const decimales = token.includes(",") ? token.split(",")[1].length : 0;
  const final = Number(token.replace(/\./g, "").replace(",", "."));
  const miles = token.includes(".") || final >= 10000;
  return (final * progreso).toLocaleString("es-AR", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
    useGrouping: miles,
  });
}

function enProgreso(valor: string, progreso: number): string {
  return valor.replace(NUMERO, (token) => aTexto(token, progreso));
}

// Counts up from zero to `valor` the first time it is seen. The text keeps its format and, being tabular,
// does not shift while it runs. Screen readers get the final value, never the intermediate ones.
export function Cifra({ valor }: { valor: string }) {
  const { ref, listo, visto } = useVisto<HTMLSpanElement>(0.5);
  const [texto, setTexto] = useState(valor);
  const marco = useRef(0);

  useEffect(() => {
    if (!listo || !NUMERO.test(valor)) return;
    NUMERO.lastIndex = 0;
    if (!visto) {
      setTexto(enProgreso(valor, 0));
      return;
    }
    const inicio = performance.now();
    const paso = (ahora: number) => {
      const t = Math.min(1, (ahora - inicio) / DURACION_MS);
      // Exponential ease-out: most of the climb happens early, the last digits settle slowly.
      setTexto(t === 1 ? valor : enProgreso(valor, 1 - Math.pow(2, -10 * t)));
      if (t < 1) marco.current = requestAnimationFrame(paso);
    };
    marco.current = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(marco.current);
  }, [listo, visto, valor]);

  return (
    <>
      <span ref={ref} aria-hidden="true">
        {texto}
      </span>
      <span className="solo-lectura">{valor}</span>
    </>
  );
}
