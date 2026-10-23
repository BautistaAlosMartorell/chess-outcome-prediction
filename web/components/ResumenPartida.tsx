"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Analisis } from "@/lib/api";
import { prefiereMenosMovimiento } from "@/lib/movimiento";
import { posicionEn, relojesEn } from "@/lib/partida";
import { escenasResumen } from "@/lib/resumenPartida";
import { Marcador } from "./Marcador";
import { Tablero } from "./Tablero";
import shared from "./Partida.module.css";
import styles from "./ResumenPartida.module.css";

export function ResumenPartida({
  analisis: a,
  onCerrar,
}: {
  analisis: Analisis;
  onCerrar: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const escenas = useMemo(() => escenasResumen(a), [a]);
  const [escena, setEscena] = useState(0);
  const [tick, setTick] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(
    () => !prefiereMenosMovimiento(),
  );
  const actual = escenas[escena];
  const ply = Math.min(actual.ply, actual.desde + Math.floor(tick / 2));
  const posicion = useMemo(() => posicionEn(a.jugadas, ply), [a, ply]);
  const punto =
    !actual.final && ply <= 120
      ? (a.curva.find((p) => p.ply === ply) ?? null)
      : null;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    if (!reproduciendo) return;
    const timer = window.setTimeout(() => {
      if (tick < 19) setTick(tick + 1);
      else if (escena + 1 < escenas.length) {
        setEscena(escena + 1);
        setTick(0);
      } else setReproduciendo(false);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [reproduciendo, tick, escena, escenas.length]);
  function ir(index: number) {
    setEscena(index);
    setTick(prefiereMenosMovimiento() ? 19 : 0);
    setReproduciendo(false);
  }
  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby="titulo-resumen"
      onCancel={onCerrar}
    >
      <div className={styles.cabecera}>
        <span>Tu partida en momentos</span>
        <button autoFocus className={shared.boton} onClick={onCerrar}>
          Cerrar resumen
        </button>
      </div>
      <h2 id="titulo-resumen">{actual.titulo}</h2>
      <p aria-live="polite">{actual.texto}</p>
      <p className={styles.nota}>
        Escena {escena + 1}/{escenas.length} ·{" "}
        {escena > 0 ? "Salto a otro momento de la partida" : "Inicio"}
      </p>
      <Marcador
        compacto
        blancas={{
          nombre: a.partida.blancas.usuario,
          rating: a.contexto.elo_blancas_previo,
        }}
        negras={{
          nombre: a.partida.negras.usuario,
          rating: a.contexto.elo_negras_previo,
        }}
        relojes={relojesEn(a, ply)}
        activo={actual.final ? null : ply % 2 ? "negras" : "blancas"}
        punto={punto}
        final={actual.final ? a.partida.resultado : null}
        mostrarCambio={false}
      />
      <div className={styles.tablero}>
        <Tablero {...posicion} />
      </div>
      <div
        className={styles.controles}
        role="group"
        aria-label="Controles del resumen"
      >
        <button
          className={shared.boton}
          disabled={escena === 0}
          onClick={() => ir(escena - 1)}
        >
          Anterior
        </button>
        <button
          className={shared.principal}
          onClick={() => {
            if (
              !reproduciendo &&
              escena === escenas.length - 1 &&
              tick === 19
            ) {
              setEscena(0);
              setTick(0);
            }
            setReproduciendo(!reproduciendo);
          }}
        >
          {reproduciendo ? "Pausar" : "Continuar"}
        </button>
        <button
          className={shared.boton}
          disabled={escena === escenas.length - 1}
          onClick={() => ir(escena + 1)}
        >
          Siguiente
        </button>
        <button className={shared.boton} onClick={() => ir(0)}>
          Reiniciar
        </button>
      </div>
    </dialog>
  );
}
