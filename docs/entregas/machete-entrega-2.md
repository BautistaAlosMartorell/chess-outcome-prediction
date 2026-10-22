# Machete — Entrega 2

Corrida vigente: `manual__2026-10-22T18:56:28`, 22/10/2026. Fuente: notebook 02
con salidas guardadas. La guía de defensa desarrolla los motivos; esto reúne los números.

## Perfil y calidad

- 120 cuentas: seis bandas × 20. Se mantienen las 100 originales al sumar élite.
- 101.094 registros → 100.396 partidas; retención 99,31 %; 35 columnas.
- Descartes: 273 duplicados y 425 con menos de 5 plies. Otros motivos: cero.
- Clave única; constantes: Event, Variant, Rated.
- Nulos: TournamentUrl 89.256 (88,90 %), cada tasa histórica 1.620 (1,61 %).
- Usuarios distintos incluyendo rivales: 54.998.
- Gana Blancas 48,80 % · Empate 6,81 % · Gana Negras 44,40 %.
- Duración: media 78,2; mediana 73; p25 53; p75 99; p95 142; rango 5–646 plies.
- Asimetrías: tiempo base 4,114; incremento 6,452; duración 0,801.
- Bandas: principiante 16,96 % · intermedio 17,51 % · avanzado 14,80 % · experto
  15,60 % · top_mundial 19,84 % · elite 15,29 %. Son cupos de muestra, no población.
- Rango 2013–2026. Cuentas: media 843,0; mediana 996; rango 16–1.204 apariciones.
  El tope de 1.000 limita la descarga propia; pueden entrar partidas por otro seleccionado.
- Límite UTC: 93 partidas del 1/9 (66 blitz, 15 rapid, 12 bullet) en archivos de agosto.

## Parte A

| Hipótesis | Medida nueva | Decisión |
|---|---|---|
| H1 · diferencia ELO → resultado | η² 0,116; controlado 0,126; por banda 0,078–0,190 | Inconclusa, todas amarillas |
| H2 · paridad → duración | Pearson −0,020; Spearman 0,056; brecha 0,076 | Refutada |
| H3 · ritmo → tiempo | η² 0,060; bullet 39,35 %, blitz 21,30 %, rapid 7,22 %, global 24,65 % | Inconclusa en los dos niveles bajos; refutada en las otras cuatro bandas |
| H4 · cerrada → más larga | separación 0,074; medias 80,1 vs. 77,5; η² familias 0,007 | Refutada |

H3 por nivel: 0,130 · 0,095 · 0,049 · 0,022 · 0,044 · 0,026.
En élite falta rapid; no se puede afirmar el orden de tres ritmos.
Las decisiones de la corrida anterior se mantienen, con magnitudes nuevas.

## Fugas (§9)

- Rating: 99,93 % de coincidencia con resultado actual (92.515 observaciones),
  52,78 % con el anterior (90.665).
- En |diferencia| ≤10: 51,92 % vs. 45,25 % victoria blanca; brecha 6,68 pp.
- Reconstrucción parcial: 100.112 partidas, η² 0,115 → 0,087 en el mismo subconjunto.
  Conserva fuga del rival; el modelo deja ese lado NaN.
- es_sorpresa: 100 % de identidad con una regla que usa el target.
- Regla oral: ¿existía esta información al predecir? Si revela el final, sale.

## Parte B

Tabla completa: 1.559.622 filas. Seis cortes de referencia: 547.555.
Corte 0: 100.396 · 10: 99.762 · 20: 98.026 · 30: 94.671 · 40: 88.287 · 60: 66.413.
Población común: 66.413 partidas. Dos gastos recientes vacíos en el corte 0.

| Hipótesis | Medida al ply 60 | Decisión |
|---|---|---|
| H1′ · material → resultado | η² 0,108; rapid 0,199 | Parcialmente confirmada, tardía |
| H2′ · reloj más allá del material | η² 0,097; controlado 0,101; bullet 0,146; rapid 0,023 | Candidata, con interacción por ritmo |
| H3′ · estado → duración | material Spearman −0,119; reloj 0,231, bullet 0,431 | Refutada para material; reloj depende del ritmo |
| H4′ · color | ventaja blanca 4,40 pp; top_mundial 6,58; elite 5,78 | Ventaja observada; no cambia de manera relevante por ritmo |

## Matchmaking

- Regla usada como referencia: ±200 bajo 2500 en bullet/blitz o 2000 en rapid.
- Sujetas: 61.719; fuera: 5.311 (8,61 %); cumplen: 91,39 %.
- Las diferencias van en la dirección esperada en los tres ritmos.
- Bootstrap por jugador: global [1,35; 14,05] pp y rapid [4,62; 33,14] excluyen cero;
  bullet y blitz no. Esta conclusión global cambió con la muestra nueva.
- Torneos: 11.140; explican 3.300 excepciones (62,1 %).
- Sin torneos: fuera 3,54 % sujetos vs. 10,37 % no sujetos; la diferencia no desaparece.

## Puente al modelado

Ritmo, base, incremento y torneo existen antes de mover. Rating previo, forma y estilo
requieren sólo historial ya terminado. Durante se suma posición y reloj hasta el corte.
La validación debe respetar tiempo y partida. El notebook 03 es exploratorio; el 04
elige familias y columnas por CV. El 04 calcula el historial dentro del Pipeline y
corrige la suposición de `shift()` que dejaba pasar cierres iguales o solapados.
