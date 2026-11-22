"use client";

import { useId, useState, type ReactNode } from "react";
import { Icono, type NombreIcono } from "./Iconos";
import styles from "./Despliegues.module.css";

export type ItemDespliegue = {
  id: string;
  titulo: string;
  icono: NombreIcono;
  contenido: ReactNode;
};

type Props = {
  items: ItemDespliegue[];
  // Smaller chips, for a spot inside a card.
  compacto?: boolean;
};

// A row of chips with a drawn icon; each one opens its own panel below, one at a time.
// Closed by default: the page shows the question, the numbers and the chart, and the text on request.
export function Despliegues({ items, compacto = false }: Props) {
  const base = useId();
  const [abierto, setAbierto] = useState<string | null>(null);
  const activo = items.find((i) => i.id === abierto);

  return (
    <div className={compacto ? styles.compacto : styles.despliegues}>
      <div className={styles.fila}>
        {items.map((item) => {
          const seleccionado = item.id === abierto;
          return (
            <button
              key={item.id}
              type="button"
              id={`${base}-${item.id}-boton`}
              className={styles.ficha}
              aria-expanded={seleccionado}
              aria-controls={`${base}-panel`}
              onClick={() => setAbierto(seleccionado ? null : item.id)}
            >
              <span className={styles.icono}>
                <Icono nombre={item.icono} tamano={compacto ? 16 : 20} />
              </span>
              <span className={styles.titulo}>{item.titulo}</span>
              <Icono nombre="flecha" tamano={18} className={styles.flecha} />
            </button>
          );
        })}
      </div>
      <div className={styles.panel} data-abierto={activo ? "true" : "false"}>
        <div
          id={`${base}-panel`}
          role="region"
          aria-labelledby={activo ? `${base}-${activo.id}-boton` : undefined}
          className={styles.interior}
          inert={!activo}
        >
          <div className={styles.contenido}>{activo?.contenido}</div>
        </div>
      </div>
    </div>
  );
}
