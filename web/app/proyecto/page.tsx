import Link from "next/link";
import { DemoEnVivo } from "@/components/DemoEnVivo";
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
                app muestra probabilidades, y el error caro es mostrarlas muy seguras y equivocadas. F1 macro y el recall
                de tablas se miran al lado, para que la clase chica (las tablas) no desaparezca.
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
              <h3>El ajuste del elegido</h3>
              <p>
                Grilla con los mismos pedazos ({modelo.grilla.length} combinaciones). La mejor:{" "}
                {Object.entries(modelo.mejores_hiperparametros)
                  .map(([k, v]) => `${k} = ${v}`)
                  .join(", ")}
                . Balancear las tablas sube su recall de {decimal(modelo.balanceo.recall_empate_sin)} a{" "}
                {decimal(modelo.balanceo.recall_empate_con)}, pero empeora la log-loss en{" "}
                {decimal(modelo.balanceo.diferencia, 4)} ± {decimal(modelo.balanceo.desvio, 4)}: no se balancea.
              </p>
              <h3>El resultado en el test</h3>
              <p>
                Log-loss {decimal(test.log_loss)} contra {decimal(test["log_loss piso"])} del piso (
                {pct(portada.mejora_test)} menos), F1 macro {decimal(test.f1_macro)}. El período de test ya se había
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
