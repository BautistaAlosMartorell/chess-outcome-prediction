import type { Metadata } from "next";
import Link from "next/link";
import { GraficoAltair } from "@/components/GraficoAltair";
import { RESUMEN, entero } from "@/lib/resumen";
import styles from "./explora.module.css";

export const metadata: Metadata = { title: "Explorá · Ajedrez en vivo" };

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
            <strong>Mové el deslizador</strong> para avanzar la partida: al principio todo se amontona en el centro, y
            los puntos se separan a medida que aparecen las diferencias.
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
