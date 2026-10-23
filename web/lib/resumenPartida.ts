import type { Analisis } from "./api";
export type EscenaResumen = {
  ply: number;
  desde: number;
  titulo: string;
  texto: string;
  final: boolean;
};

export function escenasResumen(a: Analisis): EscenaResumen[] {
  const total = a.jugadas.length;
  const saltos = a.curva
    .slice(1)
    .flatMap((p, i) => {
      const previo = a.curva[i];
      const delta = p.gana_blancas - previo.gana_blancas;
      return p.ply <= 120 && p.ply < total && Math.abs(delta) >= 0.1
        ? [
            {
              ply: p.ply,
              delta,
              previo: previo.gana_blancas,
              actual: p.gana_blancas,
            },
          ]
        : [];
    })
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  const elegidos: typeof saltos = [];
  for (const salto of saltos) {
    if (elegidos.every((s) => Math.abs(s.ply - salto.ply) >= 6))
      elegidos.push(salto);
    if (elegidos.length === 3) break;
  }
  return [
    {
      ply: 0,
      desde: 0,
      titulo: "Antes de mover",
      texto: "El pronóstico con el contexto previo a la partida.",
      final: false,
    },
    ...elegidos
      .sort((a, b) => a.ply - b.ply)
      .map((s) => ({
        ply: s.ply,
        desde: Math.max(0, s.ply - 4),
        titulo: `Cambió el pronóstico · jugada ${Math.ceil(s.ply / 2)}`,
        texto: `El pronóstico de blancas pasó de ${Math.round(s.previo * 100)} % a ${Math.round(s.actual * 100)} %.`,
        final: false,
      })),
    {
      ply: total,
      desde: total,
      titulo: "Así terminó",
      texto: `${a.partida.resultado}${a.final ? ` · ${a.final}` : ""}. Este es el resultado real.`,
      final: true,
    },
  ];
}
