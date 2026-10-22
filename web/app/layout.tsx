import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import Link from "next/link";
import { Navegacion } from "@/components/Navegacion";
import "./globals.css";
import styles from "./layout.module.css";

// One family; its width axis gives the condensed scoreboard figures and the regular text.
const archivo = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--font-archivo" });

export const metadata: Metadata = {
  title: "Ajedrez en vivo",
  description: "Quién gana una partida de ajedrez online, jugada a jugada, según un modelo entrenado con partidas reales.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={archivo.variable}>
      <body>
        <header className={styles.cabecera}>
          <Link href="/" className={styles.marca}>
            <span className={styles.marcaBarra} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            Ajedrez en vivo
          </Link>
          <Navegacion />
        </header>
        <main className={styles.contenido}>{children}</main>
      </body>
    </html>
  );
}
