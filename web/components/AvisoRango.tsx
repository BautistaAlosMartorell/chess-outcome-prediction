import styles from "./Partida.module.css";

// Chess.com pairs players within about ±200 points (notebook 02, matchmaking annex): twice
// that is a game the model never saw.
const DIFERENCIA_EMPAREJADA = 400;

type Lado = { nombre: string; rating: number | null | undefined };

type Props = {
  blancas: Lado;
  negras: Lado;
  // Lowest and highest prior rating seen in training, from the model file.
  rango: [number, number] | null;
};

// Elo expected score of white: points it would take on average (win = 1, draw = ½).
export function puntajeEsperado(blancas: number, negras: number): number {
  return 1 / (1 + 10 ** ((negras - blancas) / 400));
}

function porcentaje(p: number): string {
  if (p > 0.999) return "más del 99,9 %";
  if (p < 0.001) return "menos del 0,1 %";
  return `${(p * 100).toLocaleString("es-AR", { maximumFractionDigits: 1 })} %`;
}

// Says when the pre-game bar is an extrapolation, and what the Elo formula expects instead.
export function AvisoRango({ blancas, negras, rango }: Props) {
  const conRating = [blancas, negras].filter((l): l is Lado & { rating: number } => typeof l.rating === "number");
  if (conRating.length === 0) return null;

  const fueraDeRango = rango ? conRating.filter((l) => l.rating < rango[0] || l.rating > rango[1]) : [];
  const ambos = conRating.length === 2;
  const diferencia = ambos ? Math.abs((blancas.rating as number) - (negras.rating as number)) : 0;
  const lejos = diferencia > DIFERENCIA_EMPAREJADA;
  if (!ambos && fueraDeRango.length === 0) return null;

  const motivos: string[] = [];
  if (lejos) {
    motivos.push(`Se entrenó con partidas que arma Chess.com, con rivales a unos 200 puntos, y acá hay ${diferencia} de diferencia.`);
  }
  if (rango && fueraDeRango.length) {
    const quienes = fueraDeRango.map((l) => `${l.nombre} (${l.rating})`).join(" y ");
    motivos.push(`Vio ratings de ${Math.round(rango[0])} a ${Math.round(rango[1])}; ${quienes} queda afuera.`);
  }

  return (
    <aside className={styles.aviso} aria-label="Sobre la predicción antes de mover">
      {motivos.length ? (
        <p>
          <strong>Fuera de lo que vio el modelo.</strong> {motivos.join(" ")} Antes de mover, la barra no sabe qué hacer
          con esto: durante la partida, lo que pesa es el tablero y los relojes.
        </p>
      ) : null}
      {ambos ? (
        <p className={styles.elo}>
          Según la fórmula del ELO, sin mirar el tablero, <strong>{blancas.nombre}</strong> se llevaría en promedio{" "}
          <strong>{porcentaje(puntajeEsperado(blancas.rating as number, negras.rating as number))}</strong> de los puntos
          (ganar vale 1 y las tablas, ½). Es una referencia aparte, no lo que predice el modelo.
        </p>
      ) : null}
    </aside>
  );
}
