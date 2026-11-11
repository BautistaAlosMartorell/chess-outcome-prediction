import type { Metadata } from "next";
import Link from "next/link";
import { GraficoAltair } from "@/components/GraficoAltair";
import { RESUMEN, entero, pct } from "@/lib/resumen";
import styles from "./explora.module.css";

export const metadata: Metadata = { title: "Explorá · Ajedrez en vivo" };

const guia = RESUMEN.explora;

export default function Explora() {
  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <h1>Explorá las partidas</h1>
        <p>
          Cada punto es una partida de test, que el modelo nunca vio al entrenar, en el momento que elijas. A la
          izquierda, las negras tienen más material; arriba, el modelo le da más chances a las blancas. El color es
          cómo terminó de verdad.
        </p>
        <ul className={styles.pasos}>
          <li>
            <strong>Empezá por el panorama, con el deslizador en 0:</strong> antes de mover nadie tiene material de
            más, así que todos los puntos están en la misma columna y los colores se mezclan. Llevalo a{" "}
            {guia.corte} plies: los puntos se abren a los costados y, cuanto más lejos del centro, más se separan los
            colores. Eso es lo que aprende el modelo.
          </li>
          <li>
            <strong>Mirá dónde se equivoca:</strong> en {guia.corte} plies acierta el {pct(guia.acierto, 0)} de estas{" "}
            {entero(guia.partidas_en_corte)} partidas. Elegí «Se equivocó»: el {pct(guia.errores_tablas, 0)} de los
            errores son tablas, que casi nunca elige, y en el {pct(guia.errores_eligio_mas_material, 0)} de las demás
            eligió al que iba arriba en material y perdió igual.
          </li>
          <li>
            <strong>Elegí un ritmo o un nivel</strong> para quedarte con esas partidas.
          </li>
          <li>
            <strong>Pasá el mouse</strong> por un punto para ver la partida y lo que dijo el modelo;{" "}
            <strong>hacé clic</strong> para ver abajo cómo cambiaron sus probabilidades de principio a fin (doble clic
            para soltarla).
          </li>
        </ul>
      </header>

      <section className={styles.grafico} aria-label="Partidas de test y probabilidades del modelo">
        <GraficoAltair
          src="/app/graficos/explora.json"
          descripcion="Dispersión de partidas de test: material contra la ventaja que da el modelo, coloreada por el resultado real, con controles de corte, ritmo y nivel, y la curva de probabilidades de la partida elegida."
        />
      </section>

      <p className={styles.nota}>
        Son {entero(RESUMEN.explora.partidas)} partidas sorteadas entre las de test, en la misma proporción por ritmo y
        nivel, con todas sus filas: así la página carga rápido. Las probabilidades son las del modelo guardado, las mismas
        que mide el notebook 04. ¿Querés probar con una partida nueva?{" "}
        <Link href="/analizar">Analizá una de Chess.com</Link> o <Link href="/jugar">jugá una</Link>.
      </p>
    </div>
  );
}
