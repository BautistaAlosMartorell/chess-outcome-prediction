import Link from "next/link";
import { DemoEnVivo } from "@/components/DemoEnVivo";
import { GraficoAltair } from "@/components/GraficoAltair";
import { PartidaCruda } from "@/components/PartidaCruda";
import { Capitulo, Paso, Tabla } from "@/components/Tallo";
import mosaico from "@/public/app/mosaico.json";
import { RESUMEN, decimal, enCorte, entero, pct } from "@/lib/resumen";
import styles from "./page.module.css";

const { portada, datos, hallazgos, modelo } = RESUMEN;

// Why each excluded column would leak the answer (notebook 04, LEAKY).
const MOTIVO_FUGA: Record<string, string> = {
  WhiteElo: "rating que informa Chess.com después de la partida",
  BlackElo: "rating que informa Chess.com después de la partida",
  diferencia_elo: "sale del rating posterior",
  elo_promedio: "sale del rating posterior",
  nivel_promedio: "sale del rating posterior",
  es_sorpresa: "usa el resultado",
  Termination: "se conoce al terminar",
  cantidad_jugadas: "se conoce al terminar",
  EndTime: "se conoce al terminar",
  ECO: "Chess.com la etiqueta con la apertura completa, al final",
  Opening: "Chess.com la etiqueta con la apertura completa, al final",
  familia_apertura: "sale de la etiqueta ECO final",
};

const ETIQUETA_RESULTADO: Record<string, string> = { "Gana Blancas": "blancas", Empate: "tablas", "Gana Negras": "negras" };

function plies(tramo: string) {
  return tramo === "0" ? "antes de mover" : `plies ${tramo}`;
}

function ordinal(n: number) {
  return `${n}.º`;
}

// The exploratory hypotheses in plain words (keyed by the id before the " · " in resumen.json).
// The measures themselves stay in the "Cómo lo sabemos" table, straight from the data.
const HIPOTESIS_CLARA: Record<string, { nombre: string; veredicto: string }> = {
  H1: {
    nombre: "La diferencia de rating separa al ganador",
    veredicto: "Inconclusa: da una señal moderada y no se aclara ni separando por nivel de los jugadores.",
  },
  "H1′": {
    nombre: "El material separa al ganador",
    veredicto: "Parcialmente confirmada: separa, pero tarde en la partida y con fuerza moderada.",
  },
  "H2′": {
    nombre: "El reloj suma, aunque el material esté parejo",
    veredicto: "Se sostiene: aporta información propia, no repite la del material, y pesa mucho más en bullet que en rapid.",
  },
};

function hipotesisClara(h: { hipotesis: string }) {
  const clave = h.hipotesis.split(" · ")[0];
  const clara = HIPOTESIS_CLARA[clave];
  if (!clara) throw new Error(`Falta la explicación de ${h.hipotesis}`);
  return clara;
}

// What the page quotes from the mosaic: of the games in that cut with that advantage, how many ended that way.
function celda(variable: "material" | "reloj", corte: number, ventaja: string, resultado: string) {
  const fila = mosaico.filas.find(
    (f) => f.variable.includes(variable === "material" ? "arriba en material" : "más reloj") && f.corte_ply === corte
      && f.ventaja.startsWith(ventaja) && f.resultado === resultado,
  );
  if (!fila) throw new Error(`Falta ${variable} ${corte} ${ventaja} en mosaico.json`);
  return fila.parte;
}

function deCien(p: number) {
  return Math.round(p * 100);
}

function porNombre(filas: Record<string, unknown>[], clave: string, prefijo: string) {
  const fila = filas.find((f) => String(f[clave]).startsWith(prefijo));
  if (!fila) throw new Error(`Falta ${prefijo} en resumen.json`);
  return fila as Record<string, string>;
}

export default function Proyecto() {
  const material60 = enCorte(hallazgos.eta2_material, 60).eta2;
  const reloj60 = enCorte(hallazgos.eta2_reloj, 60);
  const sostuvo = porNombre(hallazgos.hipotesis_durante, "hipotesis", "H2′");
  const noSostuvo = porNombre(hallazgos.hipotesis_durante, "hipotesis", "H3′");
  const test = modelo.test;
  const elegido = modelo.comparacion.find((f) => f.variante === modelo.familia);
  const errores = modelo.errores_desde_ply_60;

  // Professor's feedback on Entrega 3: compare the cuts, and the models at different cuts.
  const comun = modelo.entre_cortes.filter((f) => f.serie.startsWith("Las mismas"));
  const comunEn = (corte: number) => enCorte(comun, corte);
  const saltoTotal = modelo.saltos_entre_cortes.find((s) => s.desde === 0 && s.hasta === modelo.ply_comun);
  const saltosConsecutivos = modelo.saltos_entre_cortes.filter((s) => !(s.desde === 0 && s.hasta === modelo.ply_comun));
  const primerSalto = saltosConsecutivos[0];
  const [, simpleCv, elegidoCv, otroCv] = modelo.familias;
  const contraSimple = modelo.familias_diferencias.filter(
    (d) => d.metrica === "log_loss" && d.modelo === elegidoCv && d.referencia === simpleCv,
  );
  const ganaDesde = contraSimple.find((d) => d["le gana"]);
  const otroContraElegido = modelo.familias_diferencias.filter(
    (d) => d.metrica === "log_loss" && d.modelo === otroCv && d.referencia === elegidoCv,
  );
  const otroSeDistingue = otroContraElegido.some((d) => d["le gana"] || d.pierde);
  const ultimaContraSimple = contraSimple[contraSimple.length - 1];

  // Professor's feedback on Entrega 3: fixed decision and importance, band by band.
  const tramos = modelo.test_por_tramo;
  const tramoInicial = tramos[0];
  const tramoFinal = tramos[tramos.length - 1];
  const recall = (tramo: string, clase: string) =>
    modelo.confusion_por_tramo.find((f) => f.tramo === tramo && f.real === clase && f.predicho === clase)?.porcentaje_fila ?? 0;
  // Of the times the model said `clase`, how often it happened; null if it never said it in the band.
  const precision = (tramo: string, clase: string) =>
    modelo.confusion_por_tramo.find((f) => f.tramo === tramo && f.real === clase && f.predicho === clase)
      ?.porcentaje_columna ?? null;
  // First band where the model predicts a draw at least once.
  const primerTramoTablas = modelo.tramos.find((t) => precision(t, "Empate") !== null);
  const importancia = (columna: string, tramo: string) => {
    const fila = modelo.importancia_por_tramo.find((f) => f.columna === columna && f.tramo === tramo);
    if (!fila) throw new Error(`Falta la importancia de ${columna} en ${tramo}`);
    return fila;
  };
  // Hits out of 100 that the model loses without a column, in a band.
  const pierde = (columna: string, tramo: string) => decimal(importancia(columna, tramo).accuracy * 100, 1);
  const tramoEmpate = modelo.tramos[2];
  const color = porNombre(hallazgos.hipotesis_durante, "hipotesis", "H4′");

  // Where the model misses in the last band: by how the position looked and how the game ended.
  const situacion = (eje: string, orden: number, tramo: string) => {
    const fila = modelo.situaciones.find((f) => f.eje === eje && f.orden === orden && f.tramo === tramo);
    if (!fila) throw new Error(`Falta la situación ${eje} ${orden} en ${tramo}`);
    return fila;
  };
  const parejo = situacion("Material", 0, tramoFinal.tramo);
  const ventajaGrande = situacion("Material", 2, tramoFinal.tramo);
  const termino = (decision: string, final: string) => {
    const fila = modelo.como_terminan.find((f) => f.decision === decision && f.final === final);
    if (!fila) throw new Error(`Falta ${decision} / ${final} en resumen.json`);
    return fila.parte;
  };
  const erroresEnTablas = termino("Se equivocó", "Tablas");
  const aciertosEnTablas = termino("Acertó", "Tablas");

  const evidenciaDatos = (
            <>
              <h3>De dónde salen</h3>
              <p>
                De la {datos.fuente}, sin autenticación. Un DAG de Airflow elige {portada.cuentas} cuentas (seis bandas
                de nivel, 20 por banda) de las listas públicas de titulados, de jugadores por país y de los rankings, y
                descarga sus partidas rated de bullet, blitz y rapid hasta {datos.hasta_mes}. Las partidas van del{" "}
                {datos.desde} al {datos.hasta}. La lista de cuentas queda congelada en el repositorio, así que una
                corrida nueva reproduce el mismo dataset.
              </p>
              <h3>Qué es una fila</h3>
              <p>
                Una partida en un momento dado: partida × corte, del ply 0 (antes de mover) al 120, cada 5. En total,{" "}
                {entero(datos.filas_cortes)} filas. La tabla base tiene una fila por partida.
              </p>
              <h3>Cómo se construyó el gráfico</h3>
              <p>
                En cada ritmo se ordenan todas las partidas por duración y se dibujan 100 tomadas a intervalos iguales:
                la forma es la de todas. Las que pasan los 160 plies se cortan ahí (la más larga dura 646).
              </p>
              <h3>Qué se filtró, paso por paso</h3>
              <Tabla
                filas={datos.embudo.map((p, i) => ({ ...p, sale: i === 0 ? null : datos.embudo[i - 1].filas - p.filas }))}
                columnas={[
                  { titulo: "Paso", valor: (p) => p.paso },
                  { titulo: "Filas que quedan", valor: (p) => entero(p.filas), numerica: true },
                  { titulo: "Salen", valor: (p) => (p.sale === null ? "" : entero(p.sale)), numerica: true },
                ]}
              />
              <p>
                Las repetidas son partidas entre dos cuentas de la muestra, que aparecen en los dos archivos. Las de
                menos de 5 medio-movimientos son abandonos o resultados administrativos: no son partidas jugadas. Los
                demás filtros no sacan nada porque la descarga ya pide sólo partidas rated de ajedrez estándar.
              </p>
              <h3>Qué columnas se descartaron por fuga</h3>
              <ul>
                {datos.columnas_con_fuga.map((c) => (
                  <li key={c}>
                    <code>{c}</code>: {MOTIVO_FUGA[c] ?? "se conoce después de empezar"}.
                  </li>
                ))}
              </ul>
              <p>
                En su lugar, el rating de cada jugador se reconstruye con sus partidas terminadas antes del inicio.
              </p>
            </>
  );

  const evidenciaHallazgos = (
            <>
              <h3>Una hipótesis que se sostuvo</h3>
              <p>
                <strong>{sostuvo.hipotesis}.</strong> {sostuvo.medida}. {sostuvo.decision}.
              </p>
              <h3>Una que no</h3>
              <p>
                <strong>{noSostuvo.hipotesis}.</strong> {noSostuvo.medida}. {noSostuvo.decision}.
              </p>
              <h3>Cómo se construyó el gráfico</h3>
              <p>
                Son siempre las mismas {entero(hallazgos.poblacion_comun.partidas)} partidas, las que llegan al ply 60:
                así el gráfico no mezcla &quot;la partida avanzó&quot; con &quot;sólo quedaron las largas&quot;. El reloj
                es la diferencia de tiempo restante como fracción del tiempo base, y sólo se mira en las partidas con el
                material parejo (hasta 2 puntos), para que no repita al material.
              </p>
              <h3>Lo mismo, en un número por corte</h3>
              <p>
                η² es la parte de la variación de una columna que explica el resultado: 0 si no lo distingue, 1 si lo
                determina. El umbral de señal débil (0,05) se fijó antes de mirar, y las dos lo pasan recién entre el ply
                40 y el 60: ahí el material llega al {pct(material60)} y el reloj, a igual material, al{" "}
                {pct(reloj60.eta2_controlado)}.
              </p>
              <GraficoAltair
                src="/app/graficos/eta2.json"
                descripcion="Parte del resultado que explican el material y el reloj (η²) en los plies 10 a 60, con el umbral de señal débil."
              />
              <h3>Otras hipótesis que no se sostuvieron</h3>
              <Tabla
                filas={hallazgos.hipotesis_antes}
                columnas={[
                  { titulo: "Antes de la partida", valor: (h) => String(h["Hipótesis"]) },
                  { titulo: "Medida", valor: (h) => String(h.Medida) },
                  { titulo: "Decisión", valor: (h) => String(h["Decisión"]) },
                ]}
              />
            </>
  );

  const evidenciaHipotesis = (
            <>
              <h3>Las medidas del análisis exploratorio</h3>
              <p>
                Lo que dijo cada hipótesis en la Entrega 2, con el número que la sostiene y la decisión tal como se
                escribió entonces. η² es la parte del resultado que explica cada variable.
              </p>
              <Tabla
                filas={[...hallazgos.en_el_modelo, color]}
                columnas={[
                  { titulo: "Hipótesis", valor: (h) => <strong>{String(h.hipotesis)}</strong> },
                  { titulo: "Medida", valor: (h) => String(h.medida) },
                  { titulo: "Decisión del análisis", valor: (h) => String(h.decision) },
                ]}
              />
              <h3>Cómo leer los puestos</h3>
              <p>
                El puesto de la Entrega 3 es entre todas las columnas del modelo, en todo el test. El de cada tramo es
                entre las cinco columnas que lideran en algún momento (rating, material, reloj y los relojes de cada
                lado). Las hipótesis sobre la duración no aparecen: el proyecto se concentra en quién gana y la duración no se modela.
              </p>
            </>
  );

  const evidenciaModelo = (
            <>
              <h3>La métrica y por qué</h3>
              <p>
                Log-loss: mide qué tan buenas son las probabilidades, no sólo si el resultado más probable acertó. La
                app muestra probabilidades, y el error caro es mostrarlas muy seguras y equivocadas. Al lado se informa
                siempre la accuracy, la métrica de decisión fija (el modelo dijo esto, ¿acertó?), con la matriz de
                confusión. F1 macro y el recall de tablas se miran para que la clase chica (las tablas) no desaparezca.
              </p>
              <h3>El piso</h3>
              <p>
                Predecir siempre las proporciones de resultados de train (un DummyClassifier). Todo modelo tiene que
                bajar su log-loss para valer algo.
              </p>
              <h3>Cómo se armó la validación</h3>
              <p>
                Corte temporal: train son las {entero(modelo.corrida.partidas_train)} partidas que terminaron antes del{" "}
                {modelo.corrida.corte_temporal.slice(0, 10)} y test, las {entero(modelo.corrida.partidas_test)} que
                empezaron después. Para comparar modelos, {modelo.corrida.folds} pedazos temporales por partida sobre el{" "}
                {pct(modelo.corrida.fraccion_cv, 0)} de las partidas de train: todas las filas de una partida caen en el
                mismo pedazo, y se valida siempre con partidas posteriores.
              </p>
              <h3>Comparación (media ± desvío en los {modelo.corrida.folds} pedazos)</h3>
              <Tabla
                filas={modelo.comparacion}
                resaltar={(f) => f.variante === modelo.familia}
                columnas={[
                  { titulo: "Modelo", valor: (f) => String(f.variante) },
                  { titulo: "Log-loss", valor: (f) => `${decimal(Number(f.log_loss))} ± ${decimal(Number(f["± log_loss"]))}`, numerica: true },
                  { titulo: "Antes de mover", valor: (f) => `${decimal(Number(f["log_loss corte 0"]))} ± ${decimal(Number(f["± corte 0"]))}`, numerica: true },
                  { titulo: "F1 macro", valor: (f) => decimal(Number(f.f1_macro)), numerica: true },
                  { titulo: "Recall tablas", valor: (f) => decimal(Number(f.recall_empate)), numerica: true },
                ]}
              />
              <p>
                Regla fijada antes: un modelo más complejo reemplaza a la logística sólo si le gana por más que el
                desvío de la diferencia pedazo a pedazo.{" "}
                {modelo.decision.map((d) => (
                  <span key={String(d.modelo)}>
                    {String(d.modelo)}: {decimal(Number(d["diferencia media contra la logística"]), 4)} ±{" "}
                    {decimal(Number(d["desvío de la diferencia"]), 4)}
                    {d["le gana por más que el desvío"] ? " (le gana). " : " (no alcanza). "}
                  </span>
                ))}
                Quedó el {modelo.familia.toLowerCase()}
                {elegido ? `, con ${decimal(Number(elegido.log_loss))} en validación` : ""}.
              </p>
              <h3>Las familias, tramo por tramo</h3>
              <p>
                La comparación de arriba promedia todos los cortes. Separada por tramo, con los mismos pedazos y los
                ajustes de la búsqueda de abajo (sólo describe: no vuelve a elegir):
              </p>
              <GraficoAltair
                src="/app/graficos/familias.json"
                descripcion="Log-loss en validación de cada familia de modelos por tramo de plies, con su desvío entre pedazos: el piso, la regresión logística y los dos ensambles ajustados."
              />
              <p>
                {ganaDesde ? (
                  <>
                    Antes de los {plies(ganaDesde.tramo)} el {elegidoCv.toLowerCase()} no se distingue de la logística:
                    con poca posición para leer, el rating y el contexto le sirven igual a un modelo simple. Desde los{" "}
                    {plies(ganaDesde.tramo)} el {elegidoCv.toLowerCase()} le gana por más que el desvío, y la ventaja crece hasta{" "}
                    {decimal(-ultimaContraSimple.diferencia, 4)} ± {decimal(ultimaContraSimple["± diferencia"], 4)} menos de
                    log-loss entre los {plies(ultimaContraSimple.tramo)}.{" "}
                  </>
                ) : null}
                {otroSeDistingue
                  ? `El ${otroCv.toLowerCase()} se separa del elegido en algún tramo; el modelo se eligió con toda la partida.`
                  : `El ${otroCv.toLowerCase()} no se distingue del elegido en ningún tramo: la elección no cambiaría en ninguno.`}
              </p>
              <h3>El ajuste de hiperparámetros</h3>
              <p>
                Búsqueda aleatoria (RandomizedSearchCV) con los mismos pedazos, en los dos ensambles:{" "}
                {modelo.busqueda_iteraciones} combinaciones sorteadas por familia, más la mejor configuración de la
                Entrega 3 y el boosting por defecto como candidatos fijos ({modelo.grilla.length} en total). Queda el{" "}
                {modelo.familia.toLowerCase()} con{" "}
                {Object.entries(modelo.mejores_hiperparametros)
                  .map(([k, v]) => `${k} = ${v}`)
                  .join(", ")}
                . Balancear las tablas sube su recall de {decimal(modelo.balanceo.recall_empate_sin)} a{" "}
                {decimal(modelo.balanceo.recall_empate_con)}, pero empeora la log-loss en{" "}
                {decimal(modelo.balanceo.diferencia, 4)} ± {decimal(modelo.balanceo.desvio, 4)}: no se balancea.
              </p>
              <h3>La calibración</h3>
              <p>
                Los ensambles de árboles tienden a achatar las probabilidades extremas: con una ventaja grande, el
                modelo daba menos de lo que pasaba en la realidad. Se probaron tres calibradores, cada uno ajustado con
                predicciones de partidas anteriores a las que se mide. Quedó: {modelo.calibracion.elegida.toLowerCase()}.
              </p>
              <Tabla
                filas={modelo.calibracion.tabla}
                resaltar={(f) => f.variante === modelo.calibracion.elegida}
                columnas={[
                  { titulo: "Calibrador", valor: (f) => String(f.variante) },
                  { titulo: "Log-loss", valor: (f) => decimal(Number(f.log_loss), 4), numerica: true },
                  { titulo: "Diferencia", valor: (f) => `${decimal(Number(f["Δ global"]), 4)} ± ${decimal(Number(f["± Δ global"]), 4)}`, numerica: true },
                  { titulo: "Antes de mover", valor: (f) => `${decimal(Number(f["Δ corte 0"]), 4)} ± ${decimal(Number(f["± Δ corte 0"]), 4)}`, numerica: true },
                ]}
              />
              <h3>Una regla del juego: sin material para dar mate no se gana</h3>
              <p>
                Al probar la app apareció un error: con dama, torre y alfil contra el rey solo, pero 1,3 segundos en el
                reloj, el modelo le daba 17 % de ganar al rey solo. Eso es imposible: sin material para dar mate no se
                gana ni por tiempo; si se cae la bandera del rival, son tablas. Ahora cada corte sabe si a cada lado le
                alcanza el material para dar mate (mirando sólo el tablero de ese momento), y atrás del bosque va esa
                regla: la victoria imposible queda en 0. En las {entero(modelo.regla_mate.filas)} filas de test donde un
                solo lado puede dar mate, la log-loss baja de {decimal(modelo.regla_mate.log_loss_sin_regla, 3)} a{" "}
                {decimal(modelo.regla_mate.log_loss_con_regla, 3)}.
              </p>
              <Tabla
                filas={modelo.regla_mate.tabla}
                columnas={[
                  { titulo: "Reloj del que puede ganar", valor: (f) => String(f["reloj del que puede ganar"]) },
                  { titulo: "Filas", valor: (f) => entero(Number(f.filas)), numerica: true },
                  { titulo: "Real: gana / tablas", valor: (f) => `${decimal(Number(f["real: gana el que puede"]), 1)} % / ${decimal(Number(f["real: tablas"]), 1)} %`, numerica: true },
                  { titulo: "Sin regla: gana el que no puede", valor: (f) => `${decimal(Number(f["sin regla: gana el que no puede"]), 1)} %`, numerica: true },
                  { titulo: "Con regla: gana / tablas", valor: (f) => `${decimal(Number(f["con regla: gana el que puede"]), 1)} % / ${decimal(Number(f["con regla: tablas"]), 1)} %`, numerica: true },
                ]}
              />
              <h3>El resultado en el test</h3>
              <p>
                Log-loss {decimal(test.log_loss)} contra {decimal(test["log_loss piso"])} del piso (
                {pct(portada.mejora_test)} menos), F1 macro {decimal(test.f1_macro)}. Acierta el {pct(test.accuracy)} de
                las filas, contra {pct(test["accuracy piso"])} del piso. El período de test ya se había
                mirado en la exploración: no es un holdout nuevo.
              </p>
              <h3>Dónde se equivoca</h3>
              <Tabla
                filas={modelo.confusion_por_fila}
                columnas={[
                  { titulo: "Real \\ predicho (% de la fila)", valor: (f) => String(f.real) },
                  { titulo: "Gana Blancas", valor: (f) => decimal(Number(f["Gana Blancas"]), 1), numerica: true },
                  { titulo: "Empate", valor: (f) => decimal(Number(f.Empate), 1), numerica: true },
                  { titulo: "Gana Negras", valor: (f) => decimal(Number(f["Gana Negras"]), 1), numerica: true },
                ]}
              />
              <p>
                Reconoce pocas tablas (recall {pct(test.recall_empate)}): rara vez son el resultado más probable,
                aunque sus probabilidades suben en las partidas con cara de tablas. Desde el ply 60 erra el ganador en{" "}
                {pct(errores.erradas / errores.filas_decisivas)} de las filas de partidas decisivas; en el{" "}
                {pct(errores.predicho_arriba_en_material, 0)} de esos errores eligió al que iba arriba en material, y
                el {pct(errores.terminaron_por_tiempo, 0)} de esos terminó por tiempo.
              </p>
              <h3>En qué se apoya</h3>
              <Tabla
                filas={modelo.importancia.slice(0, 6)}
                columnas={[
                  { titulo: "Columna", valor: (f) => <code>{f.columna}</code> },
                  { titulo: "Cuánto empeora la log-loss al desordenarla", valor: (f) => `${decimal(f.media, 4)} ± ${decimal(f["desvío"], 4)}`, numerica: true },
                ]}
              />
              <h3>Qué cambió desde la Entrega 3</h3>
              <p>
                El modelo tenía los ratings de los dos jugadores en 185 de 80.314 partidas de entrenamiento. Ahora el historial suma el rating
                de los rivales que ya traían los archivos descargados, y el modelo usa la diferencia y el promedio de
                rating: {modelo.columnas_finales} columnas en total.
              </p>
              <p>
                Además, la regla de mate de arriba, y lo que pidió la devolución: las métricas por tramo de jugadas con
                la matriz de confusión leída como recall y como precisión (en «De cada 100 posiciones»), la comparación entre cortes
                sobre las mismas partidas, y las familias tramo por tramo (arriba).
              </p>
            </>
  );

  const evidenciaAcierta = (
            <>
              <h3>Por tramo de jugadas</h3>
              <Tabla
                filas={tramos}
                columnas={[
                  { titulo: "Tramo", valor: (f) => plies(f.tramo) },
                  { titulo: "Filas", valor: (f) => entero(f.filas), numerica: true },
                  { titulo: "Aciertos del modelo", valor: (f) => pct(f.accuracy), numerica: true },
                  { titulo: "Regla del material", valor: (f) => pct(f["accuracy regla material"]), numerica: true },
                  { titulo: "Piso", valor: (f) => pct(f["accuracy piso"]), numerica: true },
                  { titulo: "Log-loss", valor: (f) => decimal(f.log_loss), numerica: true },
                  { titulo: "Recall tablas", valor: (f) => pct(f.recall_empate), numerica: true },
                ]}
              />
              <p>
                Los tramos tardíos sólo tienen partidas largas: entre los plies {tramoFinal.tramo} quedan{" "}
                {entero(tramoFinal.partidas)} de las {entero(tramoInicial.partidas)} partidas de test. Por eso el piso
                baja: en las partidas largas ganan menos las blancas y hay más tablas.
              </p>
              <h3>La matriz de confusión, tramo por tramo</h3>
              <GraficoAltair
                src="/app/graficos/confusion.json"
                descripcion="Matriz de confusión del tramo elegido en el menú, leída como recall (de cada resultado real, qué porcentaje predijo el modelo) o como precisión (de cada predicción, qué porcentaje pasó)."
              />
              <p>
                Antes de mover, cuando casi no tiene información, el modelo se inclina por blancas: reconoce el{" "}
                {decimal(recall(tramoInicial.tramo, "Gana Blancas"), 1)} % de sus victorias y el{" "}
                {decimal(recall(tramoInicial.tramo, "Gana Negras"), 1)} % de las de negras. Al final se emparejan (
                {decimal(recall(tramoFinal.tramo, "Gana Blancas"), 1)} % y {decimal(recall(tramoFinal.tramo, "Gana Negras"), 1)}{" "}
                %). El modelo reconoce las tablas recién entre los plies {tramoFinal.tramo}: el{" "}
                {decimal(recall(tramoFinal.tramo, "Empate"), 1)} % de ellas.
              </p>
              <p>
                La precisión lee la matriz al revés: de las veces que el modelo dijo algo, cuántas pasó. Antes de mover,
                cuando dice que ganan blancas acierta el {decimal(precision(tramoInicial.tramo, "Gana Blancas") ?? 0, 1)} %
                de las veces, y cuando dice negras, el {decimal(precision(tramoInicial.tramo, "Gana Negras") ?? 0, 1)} %.
                Al final sube a {decimal(precision(tramoFinal.tramo, "Gana Blancas") ?? 0, 1)} % y{" "}
                {decimal(precision(tramoFinal.tramo, "Gana Negras") ?? 0, 1)} %.
                {primerTramoTablas ? (
                  <>
                    {" "}
                    Las tablas no tienen precisión hasta los plies {primerTramoTablas}, porque antes el modelo nunca las
                    elige. Cuando las elige entre los plies {tramoFinal.tramo}, acierta el{" "}
                    {decimal(precision(tramoFinal.tramo, "Empate") ?? 0, 1)} %: rara vez las dice, pero cuando lo hace no
                    es al azar.
                  </>
                ) : null}
              </p>
              <h3>¿La mejora es del modelo o de las partidas que quedan?</h3>
              <p>
                En cada corte quedan sólo las partidas que siguen en juego, y las largas tienen menos victorias blancas y
                más tablas. Para separar las dos cosas se mide también sobre las mismas{" "}
                {entero(comunEn(0).partidas)} partidas de test (las que llegan al ply {modelo.ply_comun}), en todos sus
                cortes hasta ese ply. Las bandas son intervalos de 95 %: se sortean partidas con reposición mil veces.
              </p>
              <GraficoAltair
                src="/app/graficos/cortes.json"
                descripcion="Aciertos del modelo en cada corte con su intervalo de 95 %, sobre todas las partidas que siguen en juego y sobre las mismas partidas hasta el ply 60."
              />
              <p>
                Sobre las mismas partidas, los aciertos pasan de {pct(comunEn(0).accuracy)} antes de mover a{" "}
                {pct(comunEn(modelo.ply_comun).accuracy)} en el ply {modelo.ply_comun}
                {saltoTotal ? (
                  <>
: +{decimal(saltoTotal.cambio * 100, 1)} puntos [{decimal(saltoTotal.bajo * 100, 1)};{" "}
                    {decimal(saltoTotal.alto * 100, 1)}]
                  </>
                ) : null}
                . La mejora es del modelo, no de las partidas que quedan. Antes de mover ya le saca{" "}
                {decimal(comunEn(0)["puntos sobre piso"], 1)} puntos al piso [{decimal(comunEn(0)["puntos sobre piso bajo"], 1)};{" "}
                {decimal(comunEn(0)["puntos sobre piso alto"], 1)}].
                {primerSalto && !primerSalto["distinto de cero"]
                  ? ` El salto de ${primerSalto.desde} a ${primerSalto.hasta} plies no se distingue de cero; desde ahí, cada uno supera su intervalo.`
                  : ""}
              </p>
              <Tabla
                filas={modelo.saltos_entre_cortes}
                columnas={[
                  { titulo: "Desde el ply", valor: (f) => String(f.desde), numerica: true },
                  { titulo: "Hasta el ply", valor: (f) => String(f.hasta), numerica: true },
                  { titulo: "Cambio en aciertos (puntos)", valor: (f) => `${f.cambio > 0 ? "+" : ""}${decimal(f.cambio * 100, 1)}`, numerica: true },
                  { titulo: "IC 95 %", valor: (f) => `[${decimal(f.bajo * 100, 1)}; ${decimal(f.alto * 100, 1)}]`, numerica: true },
                  { titulo: "¿Distinto de cero?", valor: (f) => (f["distinto de cero"] ? "sí" : "no") },
                ]}
              />
            </>
  );

  const evidenciaFija = (
            <>
              <h3>Cómo se mide</h3>
              <p>
                Importancia por permutación, dentro de cada tramo, sobre 5.000 filas de test por tramo: se desordena una
                columna, se vuelve a predecir y se mide cuánto empeora el error (esa es la importancia). Es lo que usa el modelo, no una causa. Las
                columnas parecidas (el material de cada lado y su diferencia) se reparten la importancia.
              </p>
              <p>
                La barra llena marca la columna que más aciertos se lleva en ese tramo, o las que empatan (a menos de 0,05
                de cada 100). Los relojes de cada lado por separado también entran al modelo: como mucho, cada uno se
                lleva {decimal(Math.max(...modelo.importancia_por_tramo.filter((f) => f.columna === "reloj_blancas_seg" || f.columna === "reloj_negras_seg").map((f) => f.accuracy)) * 100, 1)} de cada 100.
              </p>
              <h3>Lo mismo, en error (log-loss) y en aciertos</h3>
              <Tabla
                filas={modelo.tramos}
                columnas={[
                  { titulo: "Tramo", valor: (t) => plies(t) },
                  ...["diferencia_elo_previa", "balance_material", "diferencia_reloj_seg"].map((c) => ({
                    titulo: `${importancia(c, tramoInicial.tramo).nombre}: aciertos que se pierden (log-loss)`,
                    valor: (t: string) => `${decimal(importancia(c, t).accuracy * 100, 1)} pts (${decimal(importancia(c, t).log_loss, 4)})`,
                    numerica: true,
                  })),
                ]}
              />
            </>
  );

  const evidenciaErrores = (
            <>
              <h3>Cómo se armó</h3>
              <p>
                Sobre las filas de test del tramo {tramoFinal.tramo}. La situación se describe sólo con lo que se sabe en
                ese corte: la diferencia de material (en valor absoluto) y la diferencia de reloj como fracción del
                tiempo base. Cómo terminó la partida (mate, abandono, tiempo, tablas) viene del campo Termination de
                Chess.com, que se conoce sólo al final: sirve para explicar los errores, nunca como dato del modelo.
              </p>
              <Tabla
                filas={modelo.situaciones.filter((f) => f.eje === "Material" && f.tramo === tramoFinal.tramo)}
                columnas={[
                  { titulo: "Situación (material)", valor: (f) => `${f.situacion}: ${f.rango}` },
                  { titulo: "Filas de test", valor: (f) => entero(f.filas), numerica: true },
                  { titulo: "Parte del tramo", valor: (f) => pct(f.parte, 0), numerica: true },
                  { titulo: "Aciertos", valor: (f) => pct(f.accuracy), numerica: true },
                ]}
              />
              <p>
                Las tablas incluyen repetición, ahogado, acuerdo, material insuficiente y la regla de 50 jugadas. «Por
                tiempo» es una bandera caída con material suficiente para ganar.
              </p>
            </>
  );

  return (
    <div className={styles.inicio}>
      <section className={styles.hero} aria-labelledby="idea" id="portada">
        <div className={styles.texto}>
          <p className={styles.pregunta}>
            ¿Qué tan bien se puede predecir quién gana una partida de ajedrez online, antes de que empiece y a medida
            que avanza?
          </p>
          <h1 id="idea" className={styles.titulo}>
            Quién gana una partida se adivina un poco antes de mover, y mucho mejor a medida que avanza.
          </h1>
          <dl className={styles.cifras}>
            <div>
              <dd className="cifra">{entero(portada.partidas)}</dd>
              <dt>partidas reales de Chess.com, de {portada.cuentas} cuentas</dt>
            </div>
            <div>
              <dd className="cifra">{deCien(tramoInicial.accuracy)} de 100</dd>
              <dt>aciertos antes de mover. Decir siempre «blancas» acierta {deCien(tramoInicial["accuracy piso"])}</dt>
            </div>
            <div>
              <dd className="cifra">{deCien(tramoFinal.accuracy)} de 100</dd>
              <dt>
                aciertos entre las jugadas 48 y 60. Decir siempre «blancas» acierta {deCien(tramoFinal["accuracy piso"])}
              </dt>
            </div>
          </dl>
          <p className={styles.aclaracion}>
            No es un motor de ajedrez: no busca la mejor jugada. Dice cómo suelen terminar partidas así entre personas,
            con el reloj corriendo.
          </p>
        </div>
        <DemoEnVivo />
      </section>

      <Capitulo
        id="los-datos"
        etapa="Los datos"
        titulo="Antes de mover no sabíamos casi nada. Por eso seguimos la partida jugada a jugada."
        bajada={
          <>
            De {entero(portada.partidas)} partidas armamos {entero(datos.filas_cortes)} filas: una foto de cada partida
            cada 5 plies. Un ply es el movimiento de un solo lado; el ply 60 es la jugada 30.
          </>
        }
        cambios={[
          {
            cuando: "Agosto: el tema",
            teniamos: "lesiones de fútbol, después neumáticos de Fórmula 1, después ajedrez con Lichess, que bloqueaba la descarga.",
            porEso: "pasamos a la API pública de Chess.com, que no pide clave y trae cada jugada con su reloj.",
          },
          {
            cuando: "Septiembre: a quién miramos",
            teniamos: "7.204 partidas de 8 cuentas elegidas a mano, casi todas de nivel alto.",
            porEso: "un DAG elige 20 cuentas por banda de nivel, de listas públicas y con semilla fija.",
          },
          {
            cuando: "Fin de septiembre: qué es una fila",
            teniamos: "una fila por partida, y lo único fuerte antes de empezar era un rating que se actualiza después de jugar.",
            porEso: "una fila es una partida en un momento: lo que se ve en el ply 0, 5, 10… hasta el 120.",
          },
          {
            cuando: "Octubre: la misma muestra para todos",
            teniamos: "listas distintas en cada computadora: convivían 80.145 y 76.803 partidas.",
            porEso: `congelamos la lista en el repositorio. Con la banda élite quedaron ${portada.cuentas} cuentas y ${entero(portada.partidas)} partidas.`,
          },
        ]}
      >
        <Paso
          id="crudo"
          titulo="¿Cómo es el dato antes de tocarlo?"
          porQue={
            <p>
              Todo lo que sigue sale de este texto. Es la partida de la portada, tal como la manda Chess.com, y las filas
              en que la convertimos.
            </p>
          }
          queDice={
            <>
              <p>
                Antes de mover (ply 0) la fila no dice nada: mismo material, mismo reloj. Lo que podría ayudar, el
                rating, ya viene contaminado con el resultado.
              </p>
              <p>
                En el ply 60 las negras van 6 puntos arriba aunque tienen menos reloj, y ganaron. Esa información
                aparece recién jugando.
              </p>
            </>
          }
        >
          <PartidaCruda />
        </Paso>
        <Paso
          id="duracion"
          giro="Una partida ya es una historia. Ahora, muchas juntas."
          titulo={`Cada línea es una partida: a la jugada 30 siguen vivas ${deCien(datos.siguen_al_ply_60_total)} de cada 100`}
          grafico="/app/graficos/datos.json"
          descripcionGrafico="Seiscientas partidas reales, una línea cada una, ordenadas por duración y separadas por ritmo: bullet, blitz y rapid. La línea punteada marca el ply 60."
          comoSeLee="Cada línea vertical es una partida real y su altura es cuánto duró. Las más claras terminaron antes del ply 60."
          porQue={
            <p>
              Antes de creerle un número al modelo hay que saber de qué partidas habla. Un resultado del ply 120 parece
              hablar de todas y habla sólo de las más largas.
            </p>
          }
          queDice={
            <>
              <p>
                A la jugada 30 sigue viva el {pct(datos.siguen_al_ply_60_total, 0)} y a la 60, el{" "}
                {pct(datos.siguen_al_ply_120_total, 0)}. Las de rapid terminan antes, contadas en jugadas.
              </p>
              <p>Por eso cada comparación importante se repite sobre las mismas partidas.</p>
            </>
          }
          evidencia={evidenciaDatos}
        />
      </Capitulo>

      <Capitulo
        id="lo-que-encontramos"
        etapa="Lo que encontramos"
        titulo="Todas las partidas arrancan iguales. Las separan primero el reloj y después el material."
        bajada="Antes de entrenar nada queríamos saber si había algo que aprender. Si el tablero y el reloj no se relacionaran con quién gana, ningún modelo podría usarlos."
        cambios={[
          {
            cuando: "Primero, la partida entera",
            teniamos: "cuatro hipótesis sobre la partida completa (rating, duración, ritmo, apertura): dos refutadas y dos con señal floja.",
            porEso: "dejamos de mirar la partida entera y empezamos a mirar qué pasa adentro.",
          },
          {
            cuando: "Una trampa",
            teniamos: "un rating que predecía todo: su cambio coincide con el resultado en el 99,9 % de las partidas.",
            porEso: "lo sacamos y reconstruimos el rating previo con las partidas que cada uno ya había terminado.",
          },
          {
            cuando: "Después, el durante",
            teniamos: "la pregunta puesta sólo antes de empezar, donde casi no hay información.",
            porEso: "planteamos hipótesis nuevas sobre lo que se ve jugando: material, reloj y color.",
          },
          {
            cuando: "Lo que no anduvo",
            teniamos: "la idea de que el cruce de aperturas ayudaba a saber quién gana.",
            porEso: "lo armamos sin mirar el futuro y lo medimos: no bajó el error (+0,0017 ± 0,0011). Quedó afuera.",
          },
        ]}
      >
        <Paso
          id="separa"
          titulo="¿Qué separa al que gana del que pierde?"
          grafico="/app/graficos/hallazgos.json"
          descripcionGrafico="Mosaico de las mismas partidas en los plies 10, 30 y 60. El ancho de cada columna es cuántas partidas tienen esa ventaja y la altura, cómo terminaron. Arriba según el material; abajo según el reloj, con el material parejo."
          comoSeLee="El ancho de cada columna dice cuántas partidas están así; la altura de cada color, cómo terminaron. A la izquierda van mejor las negras; a la derecha, las blancas."
          porQue={
            <p>
              Son los datos, sin modelo: las mismas {entero(hallazgos.poblacion_comun.partidas)} partidas miradas en tres
              momentos. Si las columnas fueran todas iguales, no habría nada que predecir.
            </p>
          }
          queDice={
            <>
              <p>
                En el ply 10 casi todas están en el medio y ganan blancas o negras casi por igual. En el 60, con 6 puntos
                o más de material, ganan las blancas {deCien(celda("material", 60, "Blancas, 6", "Gana Blancas"))} de cada
                100 veces.
              </p>
              <p>
                Y el reloj no repite al material: con las piezas parejas, quien tiene más del 30 % de tiempo de ventaja
                gana unas {deCien(celda("reloj", 60, "Blancas, más", "Gana Blancas"))} de cada 100.
              </p>
            </>
          }
          evidencia={evidenciaHallazgos}
        />
        <Paso
          id="hipotesis"
          giro="Eso son los datos solos. Después, el modelo juntó todo y nos contestó."
          titulo="¿Qué pasó con lo que creíamos al principio?"
          porQue={
            <p>
              En la Entrega 2 medimos cada idea por separado. El modelo las juntó después y dijo cuánto pesa cada una y en
              qué momento.
            </p>
          }
          queDice={
            <>
              <p>
                Ninguna alcanzaba sola. Juntas sí, y se turnan: el rating manda al principio; el material y el reloj, al
                final.
              </p>
              <p>
                Una se cayó entera: creíamos que con menos piezas en el tablero faltaba menos para el final, y en los
                datos es al revés.
              </p>
            </>
          }
          evidencia={evidenciaHipotesis}
        >
          <Tabla
            filas={hallazgos.en_el_modelo}
            columnas={[
              { titulo: "Lo que creíamos", valor: (h) => <strong>{hipotesisClara(h).nombre}</strong> },
              { titulo: "Qué dijeron los datos", valor: (h) => hipotesisClara(h).veredicto },
              {
                titulo: "Puesto en el modelo",
                valor: (h) => `${ordinal(h.puesto[tramoInicial.tramo])} antes de mover, ${ordinal(h.puesto[tramoFinal.tramo])} al final`,
              },
            ]}
          />
          <p className={styles.pieTabla}>
            Además, las blancas ganan un poco más que las negras, y eso no cambia con el ritmo. Por eso, sin información,
            lo mejor es decir siempre {ETIQUETA_RESULTADO[modelo.clase_piso]}: acierta el{" "}
            {pct(tramoInicial["accuracy piso"], 0)}. Esa es la vara que tiene que superar el modelo.
          </p>
        </Paso>
      </Capitulo>

      <Capitulo
        id="el-modelo"
        etapa="El modelo"
        titulo="Le gana a no saber nada en cada momento, y sabemos por qué acierta y por qué falla."
        bajada={`Un ${modelo.familia.toLowerCase()} (200 árboles de decisión que votan) con ${modelo.columnas_finales} columnas. Aprende de ${entero(modelo.corrida.partidas_train)} partidas y se lo mide en ${entero(modelo.corrida.partidas_test)} posteriores que nunca vio.`}
        cambios={[
          {
            cuando: "Le faltaban los ratings",
            teniamos: "el rating previo de los dos jugadores en sólo 185 de 80.314 partidas de entrenamiento, y respondía al revés.",
            porEso: "usamos el rating del rival que ya venía en los archivos: 33.496 partidas con los dos.",
          },
          {
            cuando: "Se quedaba corto",
            teniamos: "un modelo que, con una dama de ventaja, apenas movía la probabilidad.",
            porEso: "buscamos hiperparámetros al azar: la dama pasó de mover entre 6 y 12 puntos a mover 24.",
          },
          {
            cuando: "Decía imposibles",
            teniamos: "un rey solo con 17 % de chances de ganar, porque al rival le quedaba poco reloj.",
            porEso: "sumamos una regla del juego: sin piezas para dar mate, la chance es cero.",
          },
          {
            cuando: "Hacía dos cosas",
            teniamos: "quién gana y cuánto falta para terminar; y del resultado mostrábamos el error, no los aciertos.",
            porEso: "nos quedamos con quién gana y lo medimos tramo por tramo.",
          },
        ]}
      >
        <Paso
          id="le-gana"
          titulo="¿Le gana a no saber nada?"
          grafico="/app/graficos/modelo.json"
          descripcionGrafico="Arriba, barras con el porcentaje de error del piso que el modelo evita en cada corte de 0 a 120 plies. Abajo, el error crudo del piso y del modelo en cada corte, unidos por un segmento."
          comoSeLee="Arriba: qué parte del error evita el modelo. Abajo, el error crudo: el punto gris es el piso, el verde es el modelo, y el segmento entre los dos es lo que se gana."
          porQue={
            <p>
              Un error solo no dice si es mucho o poco. El piso es el error de no saber nada: repetir siempre las
              proporciones generales de resultados.
            </p>
          }
          queDice={
            <>
              <p>
                Antes de mover evita el {pct(portada.mejora_antes_de_mover, 0)} del error: hay poco para leer. A la jugada
                30 evita el {pct(portada.mejora_ply_60, 0)}.
              </p>
              <p>
                El error crudo no baja parejo porque el piso empeora al final: las partidas largas terminan más en
                tablas. Lo mostramos igual, sin retocar.
              </p>
              <p>
                El error es la log-loss: castiga estar muy seguro y equivocado. Vale {decimal(test.log_loss)} contra{" "}
                {decimal(test["log_loss piso"])} del piso.
              </p>
            </>
          }
          evidencia={evidenciaModelo}
        />
        <Paso
          id="acierta"
          giro="«Evitar error» es abstracto. Pidámosle que elija un solo resultado."
          titulo="De cada 100 posiciones, ¿cuántas acierta?"
          grafico="/app/graficos/acierto.json"
          descripcionGrafico="Seis cuadrículas de cien cuadrados, una por tramo de la partida: los aciertos que ya da decir siempre blancas, los que suma el modelo y los que falla."
          comoSeLee="Cada cuadrícula son 100 posiciones de ese tramo. El número de arriba es cuántas acierta el modelo."
          porQue={
            <p>
              Es la pregunta que haría cualquiera. Y separa lo que aporta el modelo de lo que se acierta gratis: decir
              siempre «blancas» ya acierta casi la mitad.
            </p>
          }
          queDice={
            <>
              <p>
                Antes de mover acierta {deCien(tramoInicial.accuracy)}: {deCien(tramoInicial.accuracy) - deCien(tramoInicial["accuracy piso"])} más que decir blancas.
                Al final, {deCien(tramoFinal.accuracy)}: {deCien(tramoFinal.accuracy) - deCien(tramoFinal["accuracy piso"])} más.
              </p>
              <p>
                Mirar sólo quién va arriba en piezas llega a {deCien(tramoFinal["accuracy regla material"])}. Los{" "}
                {deCien(tramoFinal.accuracy) - deCien(tramoFinal["accuracy regla material"])} que faltan los ponen el
                resto de las columnas, sobre todo el reloj.
              </p>
              <p>
                No es que queden las fáciles: sobre las mismas {entero(comunEn(0).partidas)} partidas pasa de{" "}
                {deCien(comunEn(0).accuracy)} a {deCien(comunEn(modelo.ply_comun).accuracy)} en la jugada 30.
              </p>
            </>
          }
          evidencia={evidenciaAcierta}
        />
        <Paso
          id="en-que-se-fija"
          giro="Ya sabemos cuánto acierta. Para saber por qué, le tapamos una columna y miramos cuánto pierde."
          titulo="¿En qué se fija para decidir?"
          grafico="/app/graficos/importancia.json"
          descripcionGrafico="Tres gráficos de barras con la misma escala, uno por columna: rating, material y reloj. Cada barra es cuántos aciertos de cada 100 pierde el modelo en ese tramo si se le tapa esa columna."
          comoSeLee="Una faceta por columna, todas a la misma escala. La barra dice cuántos aciertos de cada 100 pierde el modelo si no la tiene; la llena es la que más pesa en ese tramo."
          porQue={
            <p>
              Que acierte no alcanza: queremos ver si se apoya en lo mismo que miraría un jugador, y si eso cambia a
              medida que la partida avanza.
            </p>
          }
          queDice={
            <>
              <p>
                Antes de mover sólo tiene el rating: sin él pierde {pierde("diferencia_elo_previa", tramoInicial.tramo)}{" "}
                aciertos. Al final, {pierde("diferencia_elo_previa", tramoFinal.tramo)}.
              </p>
              <p>
                Entre los plies {tramoEmpate} las tres valen lo mismo ({pierde("balance_material", tramoEmpate)}). Ahí
                cambia de manos: después manda el material, que al final vale {pierde("balance_material", tramoFinal.tramo)}{" "}
                aciertos, y lo sigue el reloj con {pierde("diferencia_reloj_seg", tramoFinal.tramo)}.
              </p>
            </>
          }
          evidencia={evidenciaFija}
        />
        <Paso
          id="se-equivoca"
          giro="Se fija en lo que miraría un jugador. Entonces, ¿por qué al final sigue fallando 3 de cada 10?"
          titulo="¿Dónde y por qué se equivoca?"
          grafico="/app/graficos/situaciones.json"
          descripcionGrafico="Mapa de calor con cuántas posiciones de cada 100 acierta el modelo, por tramo de plies y por situación: material o reloj parejo, ventaja chica o ventaja grande."
          comoSeLee="Cada casilla es un tipo de posición en un tramo; el número, cuántas acierta de cada 100. Abajo, cómo terminaron las partidas del último tramo."
          porQue={
            <p>
              Un porcentaje de error no dice qué mejorar. Estos dos gráficos ubican el error: en qué posiciones aparece y
              cómo terminaron esas partidas.
            </p>
          }
          queDice={
            <>
              <p>
                Con una ventaja grande acierta {deCien(ventajaGrande.accuracy)} de 100; con el material parejo,{" "}
                {deCien(parejo.accuracy)}. Y parejas son {deCien(parejo.parte)} de cada 100 posiciones del final.
              </p>
              <p>
                De cada 100 errores, {deCien(erroresEnTablas)} son partidas que terminaron en tablas. Entre los aciertos
                son {deCien(aciertosEnTablas)}. Las tablas casi nunca son lo más probable, así que casi nunca las elige.
              </p>
            </>
          }
          evidencia={evidenciaErrores}
        >
          <GraficoAltair
            src="/app/graficos/como_terminan.json"
            descripcion="Barras enfrentadas: de cada 100 aciertos y de cada 100 errores del tramo final, cuántas partidas terminaron por mate, abandono, tiempo o tablas."
          />
        </Paso>
      </Capitulo>

      <section className={styles.copa} aria-labelledby="tu-turno" id="seccion-tu-turno">
        <h2 id="tu-turno">Ahora probalo vos</h2>
        <ul className={styles.copaOpciones}>
          <li>
            <Link href="/analizar">Analizá una partida de Chess.com</Link>
            <span>Cualquier usuario: trae sus últimas partidas y el modelo las sigue jugada a jugada.</span>
          </li>
          <li>
            <Link href="/jugar">Jugá y mirá cómo cambia</Link>
            <span>Dos personas, con reloj: la barra se mueve con cada jugada.</span>
          </li>
          <li>
            <Link href="/explora">Explorá las partidas</Link>
            <span>{entero(RESUMEN.explora.partidas)} partidas que el modelo no vio, con lo que dijo de cada una.</span>
          </li>
          <li>
            <Link href="/trivia">¿Quién gana?</Link>
            <span>Tres posiciones reales: tu intuición contra la del modelo.</span>
          </li>
        </ul>
      </section>

      <section className={styles.cierre} aria-labelledby="sin-responder" id="seccion-sin-responder">
        <h2 id="sin-responder">Qué quedó sin responder</h2>
        <dl>
          <div>
            <dt>¿Se pueden anticipar las tablas?</dt>
            <dd>
              Reconoce {deCien(test.recall_empate)} de cada 100 en toda la partida y {deCien(tramoFinal.recall_empate)} al
              final. Balancear las clases las encuentra más, pero arruina las probabilidades.
            </dd>
          </div>
          <div>
            <dt>¿Qué decide una posición pareja?</dt>
            <dd>
              Ahí acierta {deCien(parejo.accuracy)} de 100. No probamos sumar la calidad de las jugadas con un motor de
              ajedrez: podría ser lo que falta.
            </dd>
          </div>
          <div>
            <dt>¿Cuánto vale estar casi sin reloj?</dt>
            <dd>
              Con el 2 % del tiempo o menos y el material parejo, el modelo le da 77 % al que tiene más reloj, y gana el
              90 %. Es más prudente que la realidad.
            </dd>
          </div>
          <div>
            <dt>¿Cuánto mejoraría con el rating de todos?</dt>
            <dd>
              Sólo {entero(RESUMEN.explora.partidas_con_rating)} de las {entero(RESUMEN.explora.partidas)} partidas de
              Explorá tienen el rating previo de los dos. Es el techo de la predicción antes de mover.
            </dd>
          </div>
          <div>
            <dt>¿Vale para cualquier jugador?</dt>
            <dd>
              Son {portada.cuentas} cuentas elegidas por nivel, no al azar. No es una muestra de todo Chess.com, y el
              período de prueba ya lo habíamos mirado al explorar.
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
