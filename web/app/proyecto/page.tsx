import Link from "next/link";
import { DemoEnVivo } from "@/components/DemoEnVivo";
import { GraficoAltair } from "@/components/GraficoAltair";
import { SeccionTallo, Tabla } from "@/components/Tallo";
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

function porNombre(filas: Record<string, unknown>[], clave: string, prefijo: string) {
  const fila = filas.find((f) => String(f[clave]).startsWith(prefijo));
  if (!fila) throw new Error(`Falta ${prefijo} en resumen.json`);
  return fila as Record<string, string>;
}

export default function Proyecto() {
  const material60 = enCorte(hallazgos.eta2_material, 60).eta2;
  const reloj60 = enCorte(hallazgos.eta2_reloj, 60);
  const reloj40 = enCorte(hallazgos.eta2_reloj, 40);
  const sostuvo = porNombre(hallazgos.hipotesis_durante, "hipotesis", "H2′");
  const noSostuvo = porNombre(hallazgos.hipotesis_durante, "hipotesis", "H3′");
  const test = modelo.test;
  const elegido = modelo.comparacion.find((f) => f.variante === modelo.familia);
  const errores = modelo.errores_desde_ply_60;

  // Professor's feedback on Entrega 3: fixed decision and importance, band by band.
  const tramos = modelo.test_por_tramo;
  const tramoInicial = tramos[0];
  const tramoFinal = tramos[tramos.length - 1];
  const recall = (tramo: string, clase: string) =>
    modelo.confusion_por_tramo.find((f) => f.tramo === tramo && f.real === clase && f.predicho === clase)?.porcentaje_fila ?? 0;
  const importancia = (columna: string, tramo: string) => {
    const fila = modelo.importancia_por_tramo.find((f) => f.columna === columna && f.tramo === tramo);
    if (!fila) throw new Error(`Falta la importancia de ${columna} en ${tramo}`);
    return fila;
  };
  const lider = (tramo: string) =>
    modelo.importancia_por_tramo
      .filter((f) => f.tramo === tramo)
      .reduce((a, b) => (b.log_loss > a.log_loss ? b : a));
  // First band where the material leads the model (by log-loss).
  const cruce = modelo.tramos.find((t) => lider(t).columna === "balance_material") ?? tramoFinal.tramo;
  const color = porNombre(hallazgos.hipotesis_durante, "hipotesis", "H4′");

  return (
    <div className={styles.inicio}>
      <Link href="/">← Volver al inicio</Link>
      <section className={styles.hero} aria-labelledby="idea">
        <div className={styles.texto}>
          <p className={styles.pregunta}>
            ¿Qué tan bien se puede predecir quién gana una partida de ajedrez online, antes de que empiece y a medida
            que avanza?
          </p>
          <h1 id="idea" className={styles.titulo}>
            Antes de mover, el resultado apenas se adivina mejor que contando cuántas ganan las blancas; con el
            material y los relojes, el modelo acierta cada vez mejor.
          </h1>
          <dl className={styles.cifras}>
            <div>
              <dt>partidas reales de Chess.com, de {portada.cuentas} jugadores</dt>
              <dd className="cifra">{entero(portada.partidas)}</dd>
            </div>
            <div>
              <dt>menos error que el piso antes de la primera jugada</dt>
              <dd className="cifra">{pct(portada.mejora_antes_de_mover)}</dd>
            </div>
            <div>
              <dt>menos error que el piso a las 30 jugadas (ply 60)</dt>
              <dd className="cifra">{pct(portada.mejora_ply_60)}</dd>
            </div>
          </dl>
          <p className={styles.aclaracion}>
            No es un motor: no dice quién juega mejor, sino cómo suelen terminar partidas así entre personas, con el
            reloj corriendo. Abajo, cómo llegamos a esto; después, explorá los datos y probá el modelo.
          </p>
        </div>
        <DemoEnVivo />
      </section>

      <div className={styles.tallo}>
        <SeccionTallo
          id="los-datos"
          etapa="Los datos"
          titulo={`Seguimos ${entero(portada.partidas)} partidas jugada a jugada, y se van terminando: a las 30 jugadas sigue en juego el ${pct(datos.siguen_al_ply_60_total, 0)}; a las 60, el ${pct(datos.siguen_al_ply_120_total, 0)}.`}
          grafico="/app/graficos/datos.json"
          descripcionGrafico="Líneas por ritmo: porcentaje de partidas que siguen en juego en cada corte de plies, de 0 a 120."
          queMirar={
            <>
              <p>
                Cada partida aporta una fila por corte, cada 5 medio-movimientos (plies), mientras sigue en juego. Una
                jugada completa son dos plies: el ply 60 es la jugada 30.
              </p>
              <p>
                Por eso los cortes tardíos describen sólo a las partidas largas. Las de rapid terminan antes, contadas
                en jugadas: más tiempo para pensar, menos partidas que se estiran.
              </p>
            </>
          }
          evidencia={
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
          }
        />

        <SeccionTallo
          id="lo-que-encontramos"
          etapa="Lo que encontramos"
          titulo={`Al principio, ni el material ni el reloj separan al ganador; a las 30 jugadas cada uno explica alrededor del ${pct(material60, 0)} del resultado, y el reloj suma aunque el material esté parejo.`}
          grafico="/app/graficos/hallazgos.json"
          descripcionGrafico="Dos líneas, material y reloj, con la parte del resultado que explica cada una (η²) en los plies 10 a 60."
          queMirar={
            <>
              <p>
                Las dos líneas arrancan cerca de cero y recién pasan el umbral de señal débil entre el ply 40 y el 60:
                al 60, el material explica el {pct(material60)} y el reloj, a igual material, el{" "}
                {pct(reloj60.eta2_controlado)}.
              </p>
              <p>
                Antes del 40 el reloj va adelante ({pct(reloj40.eta2_controlado)} contra{" "}
                {pct(enCorte(hallazgos.eta2_material, 40).eta2)}): las diferencias de tiempo aparecen antes que las de
                material.
              </p>
            </>
          }
          evidencia={
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
                η² es la parte de la variación de una columna que explica el resultado (gana blancas, tablas o gana
                negras): 0 si no lo distingue, 1 si lo determina. Se calcula sobre la misma población en todos los
                cortes, las {entero(hallazgos.poblacion_comun.partidas)} partidas que llegan al ply 60, para que el
                gráfico no mezcle &quot;la partida avanzó&quot; con &quot;sólo quedaron las largas&quot;. El reloj es la diferencia
                de tiempo restante como fracción del tiempo base, y su η² se calcula dentro de cinco bandas de material
                (&quot;a igual material&quot;). El umbral de 0,05 es el del análisis exploratorio, fijado antes de mirar.
              </p>
            </>
          }
        />

        <SeccionTallo
          id="el-modelo"
          etapa="El modelo"
          titulo={`El modelo le gana al piso en cada momento de la partida: ${pct(portada.mejora_antes_de_mover, 0)} menos error antes de mover y ${pct(portada.mejora_ply_60, 0)} menos a las 30 jugadas.`}
          grafico="/app/graficos/modelo.json"
          descripcionGrafico="Log-loss en test del modelo y del piso en cada corte de 0 a 120 plies; el modelo queda siempre por debajo."
          queMirar={
            <>
              <p>
                La distancia entre las dos líneas es lo que aporta el modelo. Antes de mover sólo sabe el ritmo y el
                nivel de cada uno; la distancia se abre cuando aparecen las diferencias de material y de reloj.
              </p>
              <p>
                El piso empeora al final porque predice siempre las proporciones de todas las partidas, y las que
                llegan lejos terminan distinto (más tablas).
              </p>
            </>
          }
          evidencia={
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
                Casi nunca predice tablas (recall {pct(test.recall_empate)}): rara vez son el resultado más probable,
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
                El modelo casi nunca veía los ratings de los dos jugadores a la vez. Ahora el historial suma el rating
                de los rivales que ya traían los archivos descargados, y el modelo usa la diferencia y el promedio de
                rating: {modelo.columnas_finales} columnas en total.
              </p>
            </>
          }
        />

        <SeccionTallo
          id="acierta"
          etapa="¿Acertó?"
          titulo={`Si se queda con lo más probable, acierta el ${pct(tramoInicial.accuracy, 0)} antes de mover y el ${pct(tramoFinal.accuracy, 0)} después del ply 95; mirar sólo el material nunca lo alcanza.`}
          grafico="/app/graficos/acierto.json"
          descripcionGrafico="Tres líneas por tramo de plies: aciertos del modelo, de la regla del material y del piso; el modelo queda siempre arriba."
          queMirar={
            <>
              <p>
                Acá no importan las probabilidades: el modelo dice un resultado (el más probable) y se cuenta si acertó.
                El piso dice siempre {modelo.clase_piso.toLowerCase()}; la regla del material, que gana el que va arriba
                en material (y blancas si están iguales).
              </p>
              <p>
                Antes de mover el modelo le saca {decimal((tramoInicial.accuracy - tramoInicial["accuracy piso"]) * 100, 1)}{" "}
                puntos al piso, sólo con el rating y el contexto. Al final, la regla del material llega al{" "}
                {pct(tramoFinal["accuracy regla material"], 0)}: lo que le falta para alcanzar al modelo lo ponen el reloj y
                el rating.
              </p>
            </>
          }
          evidencia={
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
                descripcion="Matriz de confusión del tramo elegido en el menú: de cada resultado real, qué porcentaje predijo el modelo."
              />
              <p>
                Antes de mover, cuando casi no tiene información, el modelo se inclina por blancas: reconoce el{" "}
                {decimal(recall(tramoInicial.tramo, "Gana Blancas"), 1)} % de sus victorias y el{" "}
                {decimal(recall(tramoInicial.tramo, "Gana Negras"), 1)} % de las de negras. Al final se emparejan (
                {decimal(recall(tramoFinal.tramo, "Gana Blancas"), 1)} % y {decimal(recall(tramoFinal.tramo, "Gana Negras"), 1)}{" "}
                %). Las tablas casi nunca son la opción más probable: recién entre los plies {tramoFinal.tramo} reconoce el{" "}
                {decimal(recall(tramoFinal.tramo, "Empate"), 1)} % de ellas.
              </p>
            </>
          }
        />

        <SeccionTallo
          id="en-que-se-fija"
          etapa="En qué se fija"
          titulo={`Antes de mover, el modelo se fija en el rating; desde los plies ${cruce}, en el material, y después en el reloj.`}
          grafico="/app/graficos/importancia.json"
          descripcionGrafico="Importancia por permutación de cinco columnas en cada tramo de plies: la diferencia de rating baja y el material y el reloj suben."
          queMirar={
            <>
              <p>
                Cada línea dice cuánto empeora el modelo si esa columna se desordena en ese tramo: cuanto más alta, más
                se apoya en ella. La diferencia de rating es lo único que pesa antes de mover (
                {decimal(importancia("diferencia_elo_previa", tramoInicial.tramo).log_loss, 4)}) y se apaga al final (
                {decimal(importancia("diferencia_elo_previa", tramoFinal.tramo).log_loss, 4)}).
              </p>
              <p>
                El material y el reloj arrancan en cero, porque al principio son iguales para los dos, y terminan
                adelante: {decimal(importancia("balance_material", tramoFinal.tramo).log_loss, 4)} y{" "}
                {decimal(importancia("diferencia_reloj_seg", tramoFinal.tramo).log_loss, 4)} entre los plies{" "}
                {tramoFinal.tramo}.
              </p>
            </>
          }
          evidencia={
            <>
              <h3>Cómo se mide</h3>
              <p>
                Importancia por permutación, dentro de cada tramo, sobre 5.000 filas de test por tramo: se desordena una
                columna, se vuelve a predecir y se mide cuánto empeora. Es lo que usa el modelo, no una causa. Las
                columnas parecidas (el material de cada lado y su diferencia) se reparten la importancia.
              </p>
              <h3>Lo mismo, en aciertos</h3>
              <Tabla
                filas={modelo.tramos}
                columnas={[
                  { titulo: "Tramo", valor: (t) => plies(t) },
                  ...["diferencia_elo_previa", "balance_material", "diferencia_reloj_seg"].map((c) => ({
                    titulo: `${importancia(c, tramoInicial.tramo).nombre}: aciertos que se pierden`,
                    valor: (t: string) => `${decimal(importancia(c, t).accuracy * 100, 1)} pts`,
                    numerica: true,
                  })),
                ]}
              />
            </>
          }
        />

        <SeccionTallo
          id="hipotesis"
          etapa="Las hipótesis, de punta a punta"
          titulo="Las hipótesis del análisis exploratorio, vistas otra vez con el modelo: cuáles pesan y en qué momento de la partida."
          queMirar={
            <>
              <p>
                Cada hipótesis sobre el resultado pasó por tres momentos: el análisis exploratorio (Entrega 2) la
                midió con una sola variable a la vez; el modelo (Entrega 3) la puso junto a todo lo demás; y la
                importancia por tramo (Entrega 4) dice cuándo importa.
              </p>
              <Tabla
                filas={hallazgos.en_el_modelo}
                columnas={[
                  { titulo: "Hipótesis", valor: (h) => <strong>{h.hipotesis}</strong> },
                  { titulo: "Exploratorio (Entrega 2)", valor: (h) => `${h.decision}. ${h.medida}.` },
                  {
                    titulo: "En el modelo (Entrega 3)",
                    valor: (h) => {
                      const puesto = modelo.importancia.findIndex((f) => f.columna === h.columna) + 1;
                      return puesto > 0
                        ? `${ordinal(puesto)} columna más importante de ${modelo.columnas_finales} (${h.nombre.toLowerCase()})`
                        : `Fuera de las 10 más importantes (${h.nombre.toLowerCase()})`;
                    },
                  },
                  {
                    titulo: "Tramo por tramo (Entrega 4)",
                    valor: (h) => `${ordinal(h.puesto[tramoInicial.tramo])} antes de mover → ${ordinal(h.puesto[tramoFinal.tramo])} entre los plies ${tramoFinal.tramo}`,
                  },
                ]}
              />
              <p>
                <strong>{color.hipotesis}.</strong> {color.decision}. En el modelo aparece en cómo decide sin
                información: antes de mover, el piso dice siempre {ETIQUETA_RESULTADO[modelo.clase_piso]} y acierta el{" "}
                {pct(tramoInicial["accuracy piso"])}, y el modelo reconoce más victorias de blancas que de negras hasta
                que la posición lo desempata.
              </p>
            </>
          }
          evidencia={
            <>
              <h3>Cómo leer los puestos</h3>
              <p>
                El puesto de la Entrega 3 es entre todas las columnas del modelo, en todo el test. El de cada tramo es
                entre las cinco columnas que lideran en algún momento (rating, material, reloj y los relojes de cada
                lado). Las hipótesis sobre la duración no aparecen: la duración quedó como objetivo secundario.
              </p>
            </>
          }
        />
      </div>

      <section className={styles.copa} aria-labelledby="tu-turno">
        <h2 id="tu-turno">Ahora, vos</h2>
        <div className={styles.copaOpciones}>
          <Link href="/trivia" className={styles.copaTarjeta}>
            <strong>¿Quién gana? Jugá la trivia →</strong>
            <span>Tres posiciones reales. Primero tu intuición, después el modelo y al final la verdad.</span>
          </Link>
          <Link href="/explora" className={styles.copaTarjeta}>
            <strong>Explorá las partidas</strong>
            <span>
              {entero(RESUMEN.explora.partidas)} partidas de test, en cualquier momento, con lo que dijo el modelo de
              cada una.
            </span>
          </Link>
          <Link href="/jugar" className={styles.copaTarjeta}>
            <strong>Probá el modelo jugando</strong>
            <span>Dos personas en la misma compu, con reloj: la barra se mueve con cada jugada.</span>
          </Link>
          <Link href="/analizar" className={styles.copaTarjeta}>
            <strong>Probalo con una partida tuya</strong>
            <span>Cualquier usuario de Chess.com: trae sus últimas partidas y las repasa con el modelo.</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
