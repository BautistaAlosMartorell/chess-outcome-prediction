import Link from "next/link";
import { DemoEnVivo } from "@/components/DemoEnVivo";
import { GraficoAltair } from "@/components/GraficoAltair";
import { Cifra } from "@/components/Cifra";
import { Indice } from "@/components/Indice";
import { Recorrido } from "@/components/Recorrido";
import { SeccionTallo, SeccionTexto, Tabla } from "@/components/Tallo";
import { ValorPiezas } from "@/components/ValorPiezas";
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
  const lider = (tramo: string) =>
    modelo.importancia_por_tramo
      .filter((f) => f.tramo === tramo)
      .reduce((a, b) => (b.log_loss > a.log_loss ? b : a));
  // First band where the material leads the model (by log-loss).
  const cruce = modelo.tramos.find((t) => lider(t).columna === "balance_material") ?? tramoFinal.tramo;
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
            Quién gana una partida se adivina un poco antes de mover, y mucho mejor a medida que avanza.
          </h1>
          <dl className={styles.cifras}>
            <div>
              <dt>partidas reales de Chess.com, de {portada.cuentas} jugadores</dt>
              <dd className="cifra">
                <Cifra valor={entero(portada.partidas)} />
              </dd>
            </div>
            <div>
              <dt>menos error que el piso antes de la primera jugada</dt>
              <dd className="cifra">
                <Cifra valor={pct(portada.mejora_antes_de_mover)} />
              </dd>
            </div>
            <div>
              <dt>menos error que el piso a las 30 jugadas (ply 60)</dt>
              <dd className="cifra">
                <Cifra valor={pct(portada.mejora_ply_60)} />
              </dd>
            </div>
          </dl>
          <p className={styles.aclaracion}>
            Dice cómo suelen terminar partidas así entre personas, con el reloj corriendo. No evalúa quién juega
            mejor: no es un motor de ajedrez.
          </p>
        </div>
        <DemoEnVivo />
      </section>

      <Indice
        capitulos={[
          { id: "seccion-recorrido", titulo: "Cómo cambió el proyecto" },
          { id: "seccion-los-datos", titulo: "Los datos" },
          { id: "seccion-lo-que-encontramos", titulo: "Lo que encontramos" },
          { id: "seccion-el-modelo", titulo: "El modelo" },
          { id: "seccion-acierta", titulo: "Cuántas acierta" },
          { id: "seccion-se-equivoca", titulo: "Por qué falla" },
          { id: "seccion-en-que-se-fija", titulo: "En qué se fija" },
          { id: "seccion-hipotesis", titulo: "Las hipótesis" },
        ]}
      />

      <div className={styles.tallo}>
        <SeccionTexto
          id="recorrido"
          etapa="El recorrido"
          pregunta="¿Cómo llegamos hasta acá?"
          titulo="Cuatro entregas, cuatro correcciones. Cada tarjeta dice qué teníamos, qué cambiamos y por qué."
        >
          <Recorrido />
        </SeccionTexto>

        <SeccionTallo
          id="los-datos"
          etapa="Los datos"
          pregunta="¿Con qué datos trabajamos?"
          cifras={[
            { valor: entero(portada.partidas), texto: "partidas reales de Chess.com" },
            { valor: String(portada.cuentas), texto: "cuentas, en seis bandas de nivel" },
            { valor: entero(datos.filas_cortes), texto: "filas: cada partida, en cada corte de plies" },
          ]}
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
          porQue={
            <p>
              Antes de mostrar nada del modelo hay que saber de qué partidas habla. Si no se ve que las partidas se van
              terminando, un número del ply 120 parece describir a todas y describe sólo a las más largas.
            </p>
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
          pregunta="¿Qué separa al ganador, antes de modelar?"
          cifras={[
            { valor: pct(material60, 0), texto: "del resultado explica el material a las 30 jugadas" },
            { valor: pct(reloj60.eta2_controlado, 0), texto: "explica el reloj, a igual material" },
            { valor: "40 a 60", texto: "plies en que las dos superan el umbral de señal débil" },
          ]}
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
          porQue={
            <p>
              Antes de entrenar algo queríamos saber si el material y el reloj tienen alguna relación con quién gana. Si
              no la tuvieran, ningún modelo podría usarlos. Esta es la prueba, y el umbral de 0,05 se fijó antes de
              mirar.
            </p>
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
          pregunta="¿Le gana el modelo a no saber nada?"
          cifras={[
            { valor: pct(portada.mejora_antes_de_mover, 0), texto: "menos error que el piso antes de mover" },
            { valor: pct(portada.mejora_ply_60, 0), texto: "menos error que el piso a las 30 jugadas" },
            { valor: `${decimal(test.log_loss)} contra ${decimal(test["log_loss piso"])}`, texto: "error en test: modelo contra piso" },
          ]}
          titulo={`Sí, en cada momento de la partida: ${pct(portada.mejora_antes_de_mover, 0)} menos error antes de mover y ${pct(portada.mejora_ply_60, 0)} menos a las 30 jugadas. Antes de mover es poco porque casi no hay información.`}
          grafico="/app/graficos/modelo.json"
          descripcionGrafico="Arriba, log-loss en test del modelo y del piso en cada corte de 0 a 120 plies: el modelo queda siempre por debajo. Abajo, el porcentaje de error del piso que el modelo evita en cada corte."
          queMirar={
            <>
              <p>
                Arriba está el error tal cual, sin retocar: menos es mejor. La distancia entre las dos líneas es lo que
                aporta el modelo. Antes de mover sólo sabe el ritmo y el nivel de cada uno; la distancia se abre cuando
                aparecen las diferencias de material y de reloj.
              </p>
              <p>
                Al final sube el error del piso: predice siempre las proporciones de todas las partidas, y las que
                llegan lejos terminan distinto (más tablas). Las barras de abajo leen lo mismo como lo que importa: qué
                parte de ese error evita el modelo.
              </p>
            </>
          }
          porQue={
            <p>
              Un número de error solo no dice si es bueno o malo. El piso es el error de no saber nada, y es la vara.
              Mostramos los dos juntos y en crudo: el modelo queda por debajo del piso en todos los cortes, con poca
              distancia antes de mover y mucha a la mitad de la partida.
            </p>
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
                la matriz de confusión leída como recall y como precisión (en «¿Acertó?»), la comparación entre cortes
                sobre las mismas partidas, y las familias tramo por tramo (arriba).
              </p>
            </>
          }
        />

        <SeccionTallo
          id="acierta"
          etapa="¿Acertó?"
          pregunta="Cuando elige un resultado, ¿cuántas veces acierta?"
          cifras={[
            { valor: pct(tramoInicial.accuracy, 0), texto: "aciertos antes de mover (el piso, siempre blancas: " + pct(tramoInicial["accuracy piso"], 0) + ")" },
            { valor: pct(tramoFinal.accuracy, 0), texto: `aciertos entre los plies ${tramoFinal.tramo}` },
            { valor: pct(tramoFinal["accuracy regla material"], 0), texto: "aciertos de elegir siempre al que va arriba en material, al final" },
          ]}
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
                Cada número es un porcentaje de filas de test de ese tramo: {pct(tramoInicial.accuracy, 0)} quiere decir
                que de cada 100 posiciones antes de mover, el modelo elige bien el resultado en {Math.round(tramoInicial.accuracy * 100)}.
              </p>
              <p>
                Antes de mover el modelo le saca {decimal((tramoInicial.accuracy - tramoInicial["accuracy piso"]) * 100, 1)}{" "}
                puntos al piso, sólo con el rating y el contexto. Al final, la regla del material llega al{" "}
                {pct(tramoFinal["accuracy regla material"], 0)}: lo que le falta para alcanzar al modelo lo ponen el reloj y
                el rating.
              </p>
            </>
          }
          porQue={
            <p>
              La log-loss mide probabilidades y cuesta leerla. Esta pregunta es más simple: si el modelo tuviera que
              decir un solo resultado, ¿acertaría? Lo comparamos con dos reglas sin modelo (decir siempre blancas, o que
              gana el que va arriba en material) para ver cuánto agrega.
            </p>
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
          }
        />

        <SeccionTallo
          id="se-equivoca"
          etapa="Los errores"
          pregunta="¿Por qué sigue fallando 3 de cada 10 al final?"
          titulo={`Entre los plies ${tramoFinal.tramo} el modelo se equivoca en ${pct(1 - tramoFinal.accuracy, 0)} de las posiciones. Más de la mitad de esos errores son partidas que terminaron en tablas, y con el material parejo acierta menos.`}
          cifras={[
            { valor: pct(erroresEnTablas, 0), texto: `de los errores entre los plies ${tramoFinal.tramo} terminaron en tablas (en los aciertos, ${pct(aciertosEnTablas, 0)})` },
            { valor: `${pct(parejo.accuracy, 0)} contra ${pct(ventajaGrande.accuracy, 0)}`, texto: "aciertos con el material parejo, contra los de una ventaja grande" },
            { valor: pct(parejo.parte, 0), texto: `de las posiciones del tramo final tienen el material parejo (hasta 2 puntos)` },
          ]}
          grafico="/app/graficos/situaciones.json"
          descripcionGrafico="Mapa de calor con el porcentaje de aciertos del modelo por tramo de plies y por situación: la ventaja de material o la de reloj, a elección. Cuanto más verde, más acierta."
          queMirar={
            <>
              <p>
                Cada celda es un tipo de posición en un tramo de la partida; el color y el número son el porcentaje de
                aciertos. Con el material, parejo es hasta 2 puntos de diferencia, ventaja chica de 3 a 5 y grande 6 o
                más; con el reloj, parejo es menos del 10 % del tiempo base de diferencia y grande, más del 30 %. Las columnas de la izquierda tienen casi todo parejo; hacia la derecha se abren las ventajas.
                Cambiá el eje con el menú para ver el material o el reloj.
              </p>
              <p>
                En las ventajas grandes acierta más de 8 de cada 10. Con el material parejo baja al{" "}
                {pct(parejo.accuracy, 0)}, y esas posiciones son la mayoría del tramo.
              </p>
            </>
          }
          porQue={
            <>
              <p>
                El acierto cambia según la situación, de {pct(parejo.accuracy, 0)} con el material parejo a{" "}
                {pct(ventajaGrande.accuracy, 0)} con una ventaja grande. El mapa ubica dónde se pierde, que es el paso
                previo a decidir qué mejorar.
              </p>
              <p>
                Al final queda una mayoría de posiciones parejas ({pct(parejo.parte, 0)} del tramo). Con piezas y
                relojes parecidos, el tablero no muestra una ventaja clara. Falta comprobar si otras columnas ayudarían
                ahí.
              </p>
            </>
          }
          extras={[
            {
              src: "/app/graficos/como_terminan.json",
              descripcion:
                "Barras agrupadas con cómo terminaron las partidas del tramo final cuando el modelo acertó y cuando se equivocó: por mate, abandono, tiempo o tablas.",
              leyenda: (
                <>
                  <h3>Cómo terminaron las partidas donde acertó y donde falló</h3>
                  <p>
                    Las tablas son {pct(aciertosEnTablas, 0)} de los aciertos y {pct(erroresEnTablas, 0)} de los errores.
                    El modelo reconoce el {pct(test.recall_empate, 0)} de las tablas, y es ahí donde más pierde. Al
                    predecir no conoce el final.{" "}
                    <Link href="/explora">Verlas partida por partida en Explorá →</Link>
                  </p>
                </>
              ),
            },
          ]}
          evidencia={
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
          }
        />

        <SeccionTallo
          id="en-que-se-fija"
          etapa="En qué se fija"
          pregunta="¿En qué se fija el modelo?"
          antesDelGrafico={<ValorPiezas />}
          cifras={[
            { valor: lider(tramoInicial.tramo).nombre.split(" (")[0], texto: "lo que más pesa antes de mover" },
            { valor: lider(tramoFinal.tramo).nombre.split(" (")[0], texto: `lo que más pesa entre los plies ${tramoFinal.tramo}` },
            { valor: importancia("diferencia_reloj_seg", tramoFinal.tramo).nombre.split(" (")[0], texto: "la que más sube después del material" },
          ]}
          titulo={`Antes de mover, en el rating; desde los plies ${cruce}, en el material, y después en el reloj. Cada columna tiene su propio gráfico, todos a la misma escala.`}
          grafico="/app/graficos/importancia.json"
          descripcionGrafico="Cinco gráficos de área apilados, uno por columna, con la misma escala: importancia por permutación en cada tramo de plies. La diferencia de rating baja y el material y el reloj suben."
          queMirar={
            <>
              <p>
                Cada gráfico es una columna; cuanto más alta la mancha en un tramo, más se apoya el modelo en ella. La
                diferencia de rating es lo único que pesa antes de mover (
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
          porQue={
            <p>
              Cada columna tiene su gráfico y todos comparten escala, así que la altura compara cuánto pesa cada una
              y la forma muestra cuándo. El modelo usa lo que un jugador miraría: al principio, quién es más fuerte;
              después, quién va arriba en piezas y quién tiene más tiempo.
            </p>
          }
          evidencia={
            <>
              <h3>Cómo se mide</h3>
              <p>
                Importancia por permutación, dentro de cada tramo, sobre 5.000 filas de test por tramo: se desordena una
                columna, se vuelve a predecir y se mide cuánto empeora el error (esa es la importancia). Es lo que usa el modelo, no una causa. Las
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
          pregunta="¿Qué pasó con las hipótesis del principio?"
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
                lado). Las hipótesis sobre la duración no aparecen: el proyecto se concentra en quién gana y la duración no se modela.
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
