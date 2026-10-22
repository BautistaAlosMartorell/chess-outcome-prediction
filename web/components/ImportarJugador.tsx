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

  return (
    <form className={styles.grupo} onSubmit={traer}>
      <label htmlFor={`usuario-${lado}`}>
        {lado}: usuario de Chess.com <span className={styles.nota}>(opcional)</span>
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
          {cargando ? "Trayendo…" : "Traer"}
        </button>
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
      {ficha ? (
        <p className={styles.nota}>
          {ficha.usuario}
          {ficha.ratings[ritmo] ? `, ${ficha.ratings[ritmo]} en ${ritmo}` : `, sin rating en ${ritmo}`}
          {ficha.forma[ritmo].ultimas.length
            ? `. Últimas: ${ficha.forma[ritmo].ultimas.slice(0, 5).join(" ")}`
            : ""}
          .{" "}
          <button type="button" className={styles.nota} onClick={() => onFicha(null)} style={{ border: "none", background: "none", textDecoration: "underline", padding: 0 }}>
            Quitar
          </button>
        </p>
      ) : null}
    </form>
  );
}
