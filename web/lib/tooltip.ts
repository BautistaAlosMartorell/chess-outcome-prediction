// The bubble that follows the mouse over a chart. Vega hands it the tooltip fields as {title: text};
// the chart specs (src/app_charts.py) decide which fields exist, this only lays them out.

type Valores = Record<string, unknown>;
type Limpiar = (texto: string) => string;

const OK = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>`;
const MAL = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>`;

// How a game ended, as chess.com names it (Termination), in the words of the app.
const FINAL: Record<string, string> = {
  checkmate: "jaque mate",
  resignation: "abandono",
  time: "tiempo",
  abandoned: "partida abandonada",
  repetition: "triple repetición",
  agreement: "acuerdo",
  stalemate: "rey ahogado",
  insufficient_material: "material insuficiente",
  timeout_vs_insufficient_material: "tiempo, sin material para ganar",
  "50-move_rule": "regla de las 50 jugadas",
};

// "Gana Negras" -> "ganaron las negras".
function frase(resultado: string): string {
  if (resultado === "Empate") return "tablas";
  return `ganaron las ${resultado.replace("Gana ", "").toLowerCase()}`;
}

const CLASE_RESULTADO: Record<string, string> = { "Gana Blancas": "blancas", Empate: "tablas", "Gana Negras": "negras" };

function porcentaje(texto: unknown): number {
  const n = parseFloat(String(texto).replace(",", ".").replace("%", ""));
  return Number.isFinite(n) ? n : 0;
}

// Explorá: one game at one cut, with what the model said about it.
function partida(v: Valores, l: Limpiar): string {
  const texto = (clave: string) => l(String(v[clave] ?? "–"));
  const real = String(v["Resultado real"] ?? "");
  const elige = String(v["El modelo elige"] ?? "");
  const acerto = real === elige;
  const filas = [
    ["Gana Blancas", "Modelo: gana blancas"],
    ["Empate", "Modelo: tablas"],
    ["Gana Negras", "Modelo: gana negras"],
  ] as const;
  const barras = filas
    .map(([resultado, clave]) => {
      const p = porcentaje(v[clave]);
      const marca = resultado === elige ? " tt-elegida" : "";
      return `<div class="tt-barra${marca}"><span>${l(resultado.replace("Gana ", ""))}</span><i class="tt-pista"><b class="tt-${CLASE_RESULTADO[resultado]}" style="width:${p}%"></b></i><em class="cifra">${p.toFixed(0)} %</em></div>`;
    })
    .join("");
  const motivo = String(v["Terminó por"] ?? "");
  const final = motivo ? ` (${l(FINAL[motivo] ?? motivo)})` : "";
  const veredicto = acerto
    ? `<div class="tt-veredicto tt-bien">${OK}<span>Acertó: <strong>${l(frase(real))}</strong>${final}</span></div>`
    : `<div class="tt-veredicto tt-mal">${MAL}<span>Eligió <strong>${l(elige === "Empate" ? "tablas" : elige.replace("Gana ", "").toLowerCase())}</strong>; <strong>${l(frase(real))}</strong>${final}</span></div>`;
  const jugada = Number(v["Plies jugados"]) / 2;
  return `<div class="tt tt-partida">
    <div class="tt-cab"><i class="tt-punto tt-${CLASE_RESULTADO[real] ?? "tablas"}"></i><strong>${texto("Blancas")}</strong><span>contra</span><strong>${texto("Negras")}</strong></div>
    <div class="tt-sub">${texto("Ritmo")} · ${texto("Nivel")} · ${texto("Plies jugados")} plies${jugada ? ` (jugada ${jugada})` : ""} · material ${texto("Material (bl − ng)")} · reloj ${texto("Reloj (bl − ng)")}</div>
    <div class="tt-barras">${barras}</div>
    ${veredicto}
  </div>`;
}

// Any other chart: a title row (the first field) and the rest as label and value.
function filas(v: Valores, l: Limpiar): string {
  const entradas = Object.entries(v).filter(([, valor]) => valor !== undefined && valor !== null && valor !== "");
  if (entradas.length === 0) return "";
  const [[tituloClave, tituloValor], ...resto] = entradas;
  const cuerpo = resto
    .map(([k, valor]) => `<div class="tt-fila"><span>${l(k)}</span><strong class="cifra">${l(String(valor))}</strong></div>`)
    .join("");
  return `<div class="tt"><div class="tt-cab"><span>${l(tituloClave)}</span><strong>${l(String(tituloValor))}</strong></div>${cuerpo}</div>`;
}

export function formatearTooltip(valor: unknown, sanitizar: Limpiar): string {
  if (typeof valor !== "object" || valor === null) return sanitizar(String(valor));
  const v = valor as Valores;
  return "Modelo: gana blancas" in v ? partida(v, sanitizar) : filas(v, sanitizar);
}

// Passed to vega-embed as its `tooltip` option.
export const OPCIONES_TOOLTIP = { formatTooltip: formatearTooltip, offsetX: 16, offsetY: 16 };
