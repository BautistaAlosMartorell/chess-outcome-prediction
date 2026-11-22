"use client";

import { useLayoutEffect, useRef, useState } from "react";

// True once the element has entered the viewport, and stays true. `listo` flips first, before paint,
// so the hidden starting state is only applied when the script runs: without it the page is fully visible.
// With prefers-reduced-motion nothing is armed and `animar` stays false.
export function useVisto<T extends HTMLElement>(umbral = 0.15) {
  const ref = useRef<T>(null);
  const [estado, setEstado] = useState({ listo: false, visto: false });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setEstado({ listo: true, visto: false });
    const observador = new IntersectionObserver(
      ([entrada]) => {
        if (!entrada.isIntersecting) return;
        setEstado({ listo: true, visto: true });
        observador.disconnect();
      },
      { threshold: umbral, rootMargin: "0px 0px -6% 0px" },
    );
    observador.observe(el);
    return () => observador.disconnect();
  }, [umbral]);

  return { ref, ...estado };
}
