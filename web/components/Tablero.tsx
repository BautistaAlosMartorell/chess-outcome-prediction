"use client";

import { Chessboard } from "react-chessboard";

type Props = {
  fen: string;
  orientacion?: "white" | "black";
  ultima?: { desde: string; hasta: string } | null;
  // Only the live game lets pieces move; the replay is read-only.
  onMover?: (desde: string, hasta: string) => boolean;
};

export function Tablero({ fen, orientacion = "white", ultima = null, onMover }: Props) {
  const resaltadas: Record<string, React.CSSProperties> = ultima
    ? {
        [ultima.desde]: { boxShadow: "inset 0 0 0 3px rgba(240, 180, 41, 0.9)" },
        [ultima.hasta]: { boxShadow: "inset 0 0 0 3px rgba(240, 180, 41, 0.9)" },
      }
    : {};

  return (
    <Chessboard
      options={{
        id: "tablero",
        position: fen,
        boardOrientation: orientacion,
        allowDragging: Boolean(onMover),
        darkSquareStyle: { backgroundColor: "var(--casilla-oscura)" },
        lightSquareStyle: { backgroundColor: "var(--casilla-clara)" },
        squareStyles: resaltadas,
        darkSquareNotationStyle: { color: "var(--casilla-clara)" },
        lightSquareNotationStyle: { color: "var(--casilla-oscura)" },
        boardStyle: { borderRadius: "var(--radio)", border: "1.5px solid var(--tinta)" },
        onPieceDrop: ({ sourceSquare, targetSquare }) =>
          Boolean(onMover && targetSquare && onMover(sourceSquare, targetSquare)),
      }}
    />
  );
}
