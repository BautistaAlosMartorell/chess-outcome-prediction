"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "@/app/layout.module.css";

const ENLACES = [
  { href: "/jugar", texto: "Jugar" },
  { href: "/analizar", texto: "Analizar una partida" },
];

export function Navegacion() {
  const ruta = usePathname();
  return (
    <nav className={styles.nav} aria-label="Modos">
      {ENLACES.map((e) => (
        <Link key={e.href} href={e.href} aria-current={ruta.startsWith(e.href) ? "page" : undefined}>
          {e.texto}
        </Link>
      ))}
    </nav>
  );
}
