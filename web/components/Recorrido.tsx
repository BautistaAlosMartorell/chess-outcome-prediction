import { Despliegues } from "./Despliegues";
import { Revelar } from "./Revelar";
import styles from "./Recorrido.module.css";

type Paso = {
  entrega: string;
  titulo: string;
  antes: string;
  ahora: string;
  porque: string;
};

// How the project changed, delivery by delivery: what we had, what we do now and why.
// Sources: README ("Limitación del rating", "Estado del modelo") and docs/entregas/devolucion-entrega-3.md.
const PASOS: Paso[] = [
  {
    entrega: "Entrega 1",
    titulo: "Conseguir los datos",
    antes: "Una fila por partida, bajada de la PubAPI de Chess.com con una lista de jugadores sorteada en cada corrida.",
    ahora: "Un DAG de Airflow que elige las cuentas una vez y las congela en el repositorio, así que todos tenemos el mismo dataset.",
    porque: "Cada integrante terminaba con su propia lista y sus propias cifras. Sin una muestra común no hay nada que comparar.",
  },
  {
    entrega: "Entrega 2",
    titulo: "Mirar los datos antes de modelar",
    antes: "Chess.com informa el rating de cada jugador después de la partida: el cambio de rating coincide con el resultado en el 99,9 %.",
    ahora: "Ese rating y todo lo derivado quedan afuera. El rating previo se reconstruye con las partidas que el jugador terminó antes de empezar.",
    porque: "Con ese rating el modelo habría trampeado. Antes de la partida casi no hay datos limpios: por eso el punto de partida es modesto.",
  },
  {
    entrega: "Entrega 3",
    titulo: "El primer modelo",
    antes: "Dos objetivos, quién gana y cuánto falta para terminar. Los dos ratings estaban juntos en 185 de 80.314 partidas de entrenamiento.",
    ahora: "El historial suma el rating de los rivales que ya estaban en los archivos descargados, y el modelo lee la diferencia entre los dos.",
    porque: "Sin los dos ratings, el modelo respondía al revés a la diferencia de nivel. El error estaba en los datos.",
  },
  {
    entrega: "Entrega 4",
    titulo: "Explicar el modelo y llevarlo a una app",
    antes: "Una sola cifra de error para toda la partida, y la duración restante como objetivo secundario.",
    ahora: "Sólo quién gana, medido tramo por tramo, con la importancia de cada columna y una regla de mate dentro del modelo.",
    porque: "Un modelo con rey solo que ganaba 17 % por reloj mostró que faltaba una regla del juego. La duración distraía de la pregunta principal.",
  },
];

export function Recorrido() {
  return (
    <ol className={styles.lista}>
      {PASOS.map((p, i) => (
        <li key={p.entrega} className={styles.item}>
          <Revelar retraso={i * 110} className={styles.paso}>
          <p className={styles.entrega}>{p.entrega}</p>
          <h3>{p.titulo}</h3>
          <dl>
            <div>
              <dt>Antes teníamos</dt>
              <dd>{p.antes}</dd>
            </div>
            <div>
              <dt>Ahora</dt>
              <dd>{p.ahora}</dd>
            </div>
          </dl>
          <div className={styles.porque}>
            <Despliegues compacto items={[{ id: "porque", titulo: "Por qué cambió", icono: "info", contenido: <p>{p.porque}</p> }]} />
          </div>
          </Revelar>
        </li>
      ))}
    </ol>
  );
}
