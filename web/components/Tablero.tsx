"use client";

import { useEffect, useState } from "react";
import { Chessboard } from "react-chessboard";

export type Destino = { hasta: string; captura: boolean };

type Props = {
  fen: string;
  orientacion?: "white" | "black";
  ultima?: { desde: string; hasta: string } | null;
  // Square of the king in check, if any.
  jaque?: string | null;
  // Live game only: legal destinations from a square (empty when it can't move) and the move itself.
  destinosDesde?: (casilla: string) => Destino[];
  onMover?: (desde: string, hasta: string) => boolean;
};

const ULTIMA = { background: "rgba(255, 205, 96, 0.5)" };
const ELEGIDA = { boxShadow: "inset 0 0 0 4px rgba(255, 181, 71, 0.95)" };
const LIBRE = { background: "radial-gradient(circle, rgba(10, 15, 16, 0.38) 0 17%, transparent 19%)" };
const CAPTURA = { background: "radial-gradient(circle, transparent 0 62%, rgba(10, 15, 16, 0.38) 64% 76%, transparent 78%)" };
const JAQUE = { background: "radial-gradient(circle, rgba(255, 107, 91, 0.95) 0 30%, rgba(255, 107, 91, 0.35) 55%, transparent 72%)" };

// Moves by drag or by click: click a piece, its legal squares light up, click one of them.
export function Tablero({ fen, orientacion = "white", ultima = null, jaque = null, destinosDesde, onMover }: Props) {
  const [elegida, setElegida] = useState<string | null>(null);
  const destinos = elegida && destinosDesde ? destinosDesde(elegida) : [];

  // A new position (a move, or a jump in the replay) drops the selection.
  useEffect(() => setElegida(null), [fen]);

  const estilos: Record<string, React.CSSProperties> = {};
  if (ultima) {
    estilos[ultima.desde] = ULTIMA;
    estilos[ultima.hasta] = ULTIMA;
  }
  if (jaque) estilos[jaque] = { ...estilos[jaque], ...JAQUE };
  if (elegida) estilos[elegida] = { ...estilos[elegida], ...ELEGIDA };
  for (const d of destinos) estilos[d.hasta] = { ...estilos[d.hasta], ...(d.captura ? CAPTURA : LIBRE) };

  function clic(casilla: string) {
    if (!onMover || !destinosDesde) return;
    if (elegida && destinos.some((d) => d.hasta === casilla)) {
      onMover(elegida, casilla);
      setElegida(null);
      return;
    }
    setElegida(casilla !== elegida && destinosDesde(casilla).length ? casilla : null);
  }

  return (
    <Chessboard
      options={{
        id: "tablero",
        position: fen,
        boardOrientation: orientacion,
        allowDragging: Boolean(onMover),
        animationDurationInMs: 220,
        darkSquareStyle: { backgroundColor: "var(--casilla-oscura)" },
        lightSquareStyle: { backgroundColor: "var(--casilla-clara)" },
        darkSquareNotationStyle: { color: "var(--casilla-clara)", fontWeight: 600 },
        lightSquareNotationStyle: { color: "var(--casilla-oscura)", fontWeight: 600 },
        squareStyles: estilos,
        boardStyle: {
          borderRadius: "10px",
          overflow: "hidden",
          boxShadow: "0 0 0 1px var(--linea), 0 24px 50px rgba(0, 0, 0, 0.45)",
        },
        onSquareClick: ({ square }) => clic(square),
        onPieceDrop: ({ sourceSquare, targetSquare }) => {
          setElegida(null);
          return Boolean(onMover && targetSquare && onMover(sourceSquare, targetSquare));
        },
      }}
    />
  );
}
