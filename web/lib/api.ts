// Client for the Python API (api/main.py). All model work happens there.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Punto = {
  ply: number;
  gana_blancas: number;
  empate: number;
  gana_negras: number;
  plies_restantes?: number;
};

export type Ritmo = "bullet" | "blitz" | "rapid";

export type Ficha = {
  usuario: string;
  nombre: string | null;
  avatar: string | null;
  url: string | null;
  titulo: string | null;
  ratings: Record<Ritmo, number | null>;
  forma: Record<Ritmo, { ultimas: ("G" | "P" | "T")[]; racha: number }>;
};

export type Lado = { usuario: string; rating: number | null };

export type ResumenPartida = {
  url: string;
  fin: number;
  ritmo: Ritmo;
  tiempo_base_seg: number;
  incremento_seg: number;
  blancas: Lado;
  negras: Lado;
  resultado: "Gana Blancas" | "Empate" | "Gana Negras";
};

export type Analisis = {
  partida: ResumenPartida;
  contexto: { elo_blancas_previo: number | null; elo_negras_previo: number | null };
  final: string | null;
  jugadas: string[];
  relojes_seg: (number | null)[];
  curva: Punto[];
};

export class ApiError extends Error {}

async function pedir<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `No hay conexión con el modelo en ${API_URL}. Levantá la API con "uvicorn api.main:app" desde la raíz del repo.`,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Error ${response.status}`;
    throw new ApiError(detail);
  }
  return response.json() as Promise<T>;
}

export type PedidoJugar = {
  jugadas: string[];
  relojes_seg: number[];
  tiempo_base_seg: number;
  incremento_seg: number;
  elo_blancas_previo: number | null;
  elo_negras_previo: number | null;
  en_curso: boolean;
};

export function predecir(pedido: PedidoJugar): Promise<{ ritmo: Ritmo; curva: Punto[] }> {
  return pedir("/predecir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pedido),
  });
}

export function traerFicha(usuario: string): Promise<Ficha> {
  return pedir(`/jugadores/${encodeURIComponent(usuario.trim())}`);
}

export function traerPartidas(usuario: string): Promise<ResumenPartida[]> {
  return pedir(`/jugadores/${encodeURIComponent(usuario.trim())}/partidas?limite=25`);
}

export function analizar(usuario: string, url: string): Promise<Analisis> {
  return pedir(`/jugadores/${encodeURIComponent(usuario.trim())}/analisis?url=${encodeURIComponent(url)}`);
}
