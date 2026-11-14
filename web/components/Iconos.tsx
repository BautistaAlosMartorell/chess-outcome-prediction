// A small set of drawn icons (24 px grid, one stroke weight, currentColor) for the chips.
const TRAZOS = {
  ver: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  porque: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M9.1 9.2a3 3 0 0 1 5.8 1c0 2-2.9 2.6-2.9 4", "M12 17.5h.01"],
  prueba: ["M9 3h6", "M10 3v6L4.6 18.5A1.6 1.6 0 0 0 6 21h12a1.6 1.6 0 0 0 1.4-2.5L14 9V3", "M7.6 15h8.8"],
  ajustes: ["M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3", "M1 14h6M9 8h6M17 16h6"],
  error: ["M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z", "M12 9.5v4", "M12 17.5h.01"],
  filtro: ["M22 3H2l8 9.5V19l4 2v-8.5L22 3z"],
  puntero: ["M4 4l7.1 17 2.5-7.4L21 11.1z"],
  info: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 16v-4.5", "M12 8h.01"],
  flecha: ["M6 9l6 6 6-6"],
} as const;

export type NombreIcono = keyof typeof TRAZOS;

export function Icono({ nombre, tamano = 20, className }: { nombre: NombreIcono; tamano?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {TRAZOS[nombre].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
