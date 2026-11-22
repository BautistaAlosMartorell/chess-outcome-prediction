import type { Metadata } from "next";
import Link from "next/link";
import { Despliegues } from "@/components/Despliegues";
import { ExploraGrafico } from "@/components/ExploraGrafico";
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
        <Despliegues
          items={[
            {
              id: "panorama",
              titulo: "Empezá por el panorama",
              icono: "ver",
              contenido: (
                <p>
                  Con el deslizador en 0, antes de mover nadie tiene material de más: todos los puntos están en la misma
                  columna y los colores se mezclan. Llevalo a {guia.corte} plies: los puntos se abren a los costados y,
                  cuanto más lejos del centro, más se separan los colores. Eso es lo que aprende el modelo.
                </p>
              ),
            },
            {
              id: "errores",
              titulo: "Dónde se equivoca",
              icono: "error",
              contenido: (
                <p>
                  En {guia.corte} plies acierta el {pct(guia.acierto, 0)} de estas {entero(guia.partidas_en_corte)}{" "}
                  partidas. Elegí «Se equivocó»: el {pct(guia.errores_tablas, 0)} de los errores son tablas (reconoce
                  el {pct(RESUMEN.modelo.test.recall_empate, 0)} de ellas), y en el{" "}
                  {pct(guia.errores_eligio_mas_material, 0)} de las demás eligió al que iba arriba en material y perdió
                  igual.
                </p>
              ),
            },
            {
              id: "filtros",
              titulo: "Eje, ritmo y nivel",
              icono: "filtro",
              contenido: (
                <p>
                  Elegí un ritmo o un nivel para quedarte con esas partidas. Con «Eje horizontal» pasás del material al
                  reloj y el modelo queda fijo arriba: si se apoya en el reloj, los puntos se ordenan igual. Con
                  «Reproducir», el corte avanza solo y ves cómo se abren los puntos a medida que la partida sigue.
                </p>
              ),
            },
            {
              id: "mouse",
              titulo: "Mouse y clic",
              icono: "puntero",
              contenido: (
                <p>
                  Pasá el mouse por un punto para ver la partida y lo que dijo el modelo. Hacé clic para ver abajo cómo
                  cambiaron sus probabilidades de principio a fin (doble clic para soltarla).
                </p>
              ),
            },
          ]}
        />
      </header>

      <section className={styles.grafico} aria-label="Partidas de test y probabilidades del modelo">
        <ExploraGrafico niveles={RESUMEN.explora.niveles} />
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
