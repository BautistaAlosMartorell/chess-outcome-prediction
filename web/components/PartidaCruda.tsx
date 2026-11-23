import demo from "@/public/app/demo.json";
import styles from "./PartidaCruda.module.css";

type Fila = { corte_ply: number; balance_material: number; reloj_blancas_seg: number; reloj_negras_seg: number; resultado: string };

function reloj(segundos: number) {
  const s = Math.round(segundos);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function conSigno(n: number) {
  return n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "0";
}

// The raw PGN with its clocks picked out: they are where the model's clock comes from.
function Jugadas({ pgn }: { pgn: string }) {
  return pgn.split(/(\{\[%clk [^\]]+\]\})/).map((parte, i) => (parte.startsWith("{[%clk") ? <mark key={i}>{parte}</mark> : parte));
}

// The game of the cover as Chess.com sends it, and the rows it becomes (src/build_app.py, partida_cruda).
export function PartidaCruda() {
  const { crudo, filas } = demo as { crudo: typeof demo.crudo; filas: Fila[] };
  return (
    <div className={styles.cruda}>
      <figure>
        <figcaption>Así llega una partida de Chess.com (recortada)</figcaption>
        <pre className={styles.json}>
          {"{\n  \"time_control\": \""}
          {crudo.time_control}
          {"\",\n  \"white\": { "}
          <del>{`"rating": ${crudo.white.rating}`}</del>
          {`, "result": "${crudo.white.result}" },\n  "black": { `}
          <del>{`"rating": ${crudo.black.rating}`}</del>
          {`, "result": "${crudo.black.result}" },\n  "pgn": "`}
          <Jugadas pgn={crudo.pgn} />
          {" …\"\n}"}
        </pre>
        <p className={styles.leyenda}>
          <del>Tachado</del>: el rating que informa ya incluye el resultado. No lo usamos.
          <br />
          <mark>Marcado</mark>: el reloj después de cada jugada. Sólo está en el texto de la partida.
        </p>
      </figure>
      <figure>
        <figcaption>Así queda en la tabla: una fila por momento</figcaption>
        <div className={styles.scroll}>
          <table>
            <thead>
              <tr>
                <th scope="col">Ply</th>
                <th scope="col">Material</th>
                <th scope="col">Reloj blancas</th>
                <th scope="col">Reloj negras</th>
                <th scope="col">Terminó</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.corte_ply}>
                  <td>{f.corte_ply}</td>
                  <td>{conSigno(f.balance_material)}</td>
                  <td>{reloj(f.reloj_blancas_seg)}</td>
                  <td>{reloj(f.reloj_negras_seg)}</td>
                  <td>{f.resultado}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className={styles.leyenda}>
          El material es lo que suman las piezas blancas menos las negras: peón 1, caballo y alfil 3, torre 5, dama 9.
        </p>
      </figure>
    </div>
  );
}
