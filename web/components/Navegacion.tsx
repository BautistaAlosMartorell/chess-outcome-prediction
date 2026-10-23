"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "@/app/layout.module.css";

// Keep the research narrative one click away from the welcome page.
const ENLACES = [
  { href: "/proyecto", texto: "El proyecto" },
  { href: "/trivia", texto: "¿Quién gana?" },
  { href: "/explora", texto: "Explorá" },
  { href: "/jugar", texto: "Jugá" },
  { href: "/analizar", texto: "Analizá" },
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
