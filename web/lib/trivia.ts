import type { Analisis } from "./api";
import type { Resultado } from "./partida";
export type CasoTrivia = {
  id: string;
  ply: number;
  fen: string;
  analisis: Analisis;
};
export type RespuestaTrivia = { caso: CasoTrivia; eleccion: Resultado };
export type IndiceTrivia = { casos: string[]; criterio: string };

export async function cargarCaso(id: string): Promise<CasoTrivia> {
  if (!/^caso-\d{3}$/.test(id)) throw new Error("Caso de trivia inválido.");
  const response = await fetch(`/app/trivia/${id}.json`);
  if (!response.ok)
    throw new Error("No se pudo cargar la partida. Intentá de nuevo.");
  return response.json();
}

// The in-memory deck survives route changes and avoids repeats during this visit.
let disponibles: string[] = [];
let firma = "";
export function sortearCasos(ids: string[], cantidad: number): string[] {
  if (ids.length < cantidad)
    throw new Error("Todavía no hay suficientes partidas para jugar.");
  if (firma !== ids.join(",")) {
    disponibles = [];
    firma = ids.join(",");
  }
  const elegidos: string[] = [];
  while (elegidos.length < cantidad) {
    if (!disponibles.length) {
      disponibles = [...ids];
      for (let i = disponibles.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [disponibles[i], disponibles[j]] = [disponibles[j], disponibles[i]];
      }
    }
    const index = disponibles.findIndex((id) => !elegidos.includes(id));
    if (index < 0)
      throw new Error("No se pudo sortear una ronda sin repeticiones.");
    elegidos.push(disponibles.splice(index, 1)[0]);
  }
  return elegidos;
}
