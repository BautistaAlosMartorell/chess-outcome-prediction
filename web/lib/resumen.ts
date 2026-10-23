// The numbers the app's text cites, written by `python -m src.build_app` from the pipeline's
// data, notebooks 02 and 04 and the saved model. Imported at build time: nothing is typed
// by hand, and regenerating the build updates every number on the page.
import datos from "@/public/app/resumen.json";

type Fila = Record<string, string | number | boolean | null>;

export type Resumen = {
  portada: { partidas: number; cuentas: number; mejora_antes_de_mover: number; mejora_ply_60: number; mejora_test: number };
  datos: {
    fuente: string;
    hasta_mes: string;
    desde: string;
    hasta: string;
    filas_cortes: number;
    cortes: number[];
    embudo: { paso: string; filas: number }[];
    siguen_al_ply_60: Record<string, number>;
    siguen_al_ply_60_total: number;
    siguen_al_ply_120_total: number;
    por_ritmo: Record<string, number>;
    por_nivel: Record<string, number>;
    columnas_con_fuga: string[];
  };
  hallazgos: {
    poblacion_comun: { partidas: number; cortes: number[]; filas: number };
    hipotesis_antes: Fila[];
    hipotesis_durante: Fila[];
    eta2_material: { corte_ply: number; eta2: number }[];
    eta2_reloj: { corte_ply: number; eta2: number; eta2_controlado: number }[];
  };
  modelo: {
    familia: string;
    corrida: {
      partidas: number;
      filas_cortes: number;
      corte_temporal: string;
      partidas_train: number;
      partidas_test: number;
      filas_train: number;
      filas_test: number;
      folds: number;
      fraccion_cv: number;
    };
    comparacion: Fila[];
    decision: Fila[];
    grilla: Fila[];
    mejores_hiperparametros: Record<string, number | string>;
    balanceo: { diferencia: number; desvio: number; recall_empate_sin: number; recall_empate_con: number; se_balancea: boolean };
    ratings_rivales: Fila[];
    columnas_finales: number;
    test: Record<string, number>;
    test_por_corte: { corte_ply: number; partidas: number; modelo: number; piso: number; mejora: number }[];
    confusion_por_fila: Fila[];
    confusion_por_columna: Fila[];
    errores_desde_ply_60: { filas_decisivas: number; erradas: number; predicho_arriba_en_material: number; terminaron_por_tiempo: number };
    importancia: { columna: string; media: number; "desvío": number }[];
    duracion_test: Fila[];
    rango_rating: [number, number];
  };
  explora: { partidas: number; niveles: string[] };
};

export const RESUMEN = datos as unknown as Resumen;

export function entero(n: number): string {
  return Math.round(n).toLocaleString("es-AR");
}

export function decimal(n: number, digitos = 3): string {
  return n.toLocaleString("es-AR", { minimumFractionDigits: digitos, maximumFractionDigits: digitos });
}

// A share (0.0517) as a percentage with a decimal comma: "5,2 %".
export function pct(p: number, digitos = 1): string {
  return `${(p * 100).toLocaleString("es-AR", { minimumFractionDigits: digitos, maximumFractionDigits: digitos })} %`;
}

export function enCorte<T extends { corte_ply: number }>(filas: T[], corte: number): T {
  const fila = filas.find((f) => f.corte_ply === corte);
  if (!fila) throw new Error(`Falta el corte ${corte} en resumen.json`);
  return fila;
}
