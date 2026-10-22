"use client";

import { useState } from "react";
import { ApiError, traerFicha, type Ficha, type Ritmo } from "@/lib/api";
import styles from "./Partida.module.css";

type Props = {
  lado: "Blancas" | "Negras";
  ritmo: Ritmo;
  ficha: Ficha | null;
  onFicha: (ficha: Ficha | null) => void;
};

// Optional: link a Chess.com account to a side, for its rating and recent form.
export function ImportarJugador({ lado, ritmo, ficha, onFicha }: Props) {
  const [usuario, setUsuario] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function traer(event: React.FormEvent) {
    event.preventDefault();
    if (!usuario.trim()) return;
    setCargando(true);
    setError(null);
    try {
      onFicha(await traerFicha(usuario));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo traer el usuario.");
      onFicha(null);
    } finally {
      setCargando(false);
    }
  }

  if (ficha) {
    const rating = ficha.ratings[ritmo];
    const ultimas = ficha.forma[ritmo].ultimas.slice(0, 5);
    return (
      <div className={styles.grupo}>
        <span className={styles.etiqueta}>{lado}</span>
        <div className={styles.ficha}>
          {ficha.avatar ? <img src={ficha.avatar} alt="" /> : null}
          <div className={styles.fichaDatos}>
            <strong>
              {ficha.titulo ? `${ficha.titulo} ` : ""}
              {ficha.usuario}
            </strong>
            <span className={styles.nota}>
              {rating ? `${rating} en ${ritmo}` : `Sin rating en ${ritmo}`}
              {ultimas.length ? `. Últimas: ${ultimas.join(" ")}` : ""}
            </span>
          </div>
          <button type="button" className={styles.quitar} onClick={() => onFicha(null)}>
            Quitar
          </button>
        </div>
      </div>
    );
  }

  return (
    <form className={styles.grupo} onSubmit={traer}>
      <label htmlFor={`usuario-${lado}`} className={styles.etiqueta}>
        {lado} <span className={styles.nota}>(usuario de Chess.com, opcional)</span>
      </label>
      <div className={styles.campo}>
        <input
          id={`usuario-${lado}`}
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
          placeholder="por ejemplo, hikaru"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit" className={styles.boton} disabled={cargando || !usuario.trim()}>
          {cargando ? "Trayendo…" : "Traer ficha"}
        </button>
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
    </form>
  );
}
