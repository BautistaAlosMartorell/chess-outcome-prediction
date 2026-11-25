"""Gráficos de la app de la Entrega 4, hechos con Altair.

Cada función recibe una tabla ya calculada y devuelve un ``alt.Chart``: datos, mapeo,
marca, transformaciones y escalas quedan a la vista, uno por línea. Los colores y los
órdenes se definen una sola vez acá, así que un resultado o un ritmo tiene el mismo
color en todos los gráficos. Son los mismos tokens que usa la web
(``web/app/globals.css``: ``--blancas``, ``--tablas``, ``--negras``, ``--reloj``).

``src.build_app`` serializa los gráficos con ``chart.to_dict()`` y la web los dibuja con
vega-embed, sin cambiar nada.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from src.predict import RESULT_ORDER

# One palette for the whole app (web/app/globals.css).
FONDO_TEXTO = "#173b32"
TEXTO_SUAVE = "#52665c"
LINEA = "#d4ddcf"
COLOR_RESULTADO = {"Gana Blancas": "#f6f1e7", "Empate": "#78978a", "Gana Negras": "#202c28"}
# Outline keeps the ivory points visible on the light chart surface.
BORDE_PUNTO = "#78978a"
RITMOS = ["bullet", "blitz", "rapid"]
COLOR_RITMO = {"bullet": "#b63c29", "blitz": "#216653", "rapid": "#806320"}
COLOR_MODELO, COLOR_PISO = "#216653", "#52665c"
COLOR_VARIABLE = {"Material": "#d95640", "Reloj, a igual material": "#216653"}

ESCALA_RESULTADO = alt.Scale(domain=RESULT_ORDER, range=[COLOR_RESULTADO[r] for r in RESULT_ORDER])
ESCALA_RITMO = alt.Scale(domain=RITMOS, range=[COLOR_RITMO[r] for r in RITMOS])
ESCALA_SERIE = alt.Scale(domain=["Modelo", "Piso"], range=[COLOR_MODELO, COLOR_PISO])
ESCALA_VARIABLE = alt.Scale(domain=list(COLOR_VARIABLE), range=list(COLOR_VARIABLE.values()))
# Vega-Lite only sizes single and layered views to their container: the web resizes the
# two views of Explorá itself, starting from this width.
ANCHO_EXPLORA = 640
# The web gives each view of a vconcat the container's width, but never less than 260 px (Explorá needs it).
# These stacked charts stay readable narrower, so on a phone they fit instead of scrolling sideways.
ANCHO_MINIMO_ANGOSTO = {"anchoMinimo": 160}
# Charts with several groups side by side: below this width the page scrolls them inside their own box.
ANCHO_GRUPOS = {"anchoGrafico": 620}
EJE_CORTE = alt.Axis(title="Plies jugados", values=list(range(0, 121, 20)))

TEMA = {
    "background": "transparent",
    "view": {"stroke": None},
    "axis": {"labelColor": TEXTO_SUAVE, "titleColor": TEXTO_SUAVE, "gridColor": LINEA, "domainColor": LINEA,
             "tickColor": LINEA, "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": "normal"},
    "legend": {"labelColor": FONDO_TEXTO, "titleColor": TEXTO_SUAVE, "labelFontSize": 12, "titleFontWeight": "normal",
               "orient": "top"},
    "text": {"color": FONDO_TEXTO},
}


def con_tema(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """Mismo fondo, ejes y leyendas en todos los gráficos; ancho del contenedor."""
    return chart.properties(width="container").configure(**TEMA)


# Groups drawn side by side inside one view (one per rhythm, cut or band): a single view fills the
# container's width by itself, which Vega-Lite's facets don't.
def _rotulo(filas: pd.DataFrame, y: float, **estilo) -> alt.Chart:
    """Texto de cada grupo: una fila por grupo con ``x`` y ``texto``; ``y`` va en píxeles."""
    return alt.Chart(filas).mark_text(lineBreak="\n", **{"fontSize": 13, "color": FONDO_TEXTO, **estilo}).encode(
        x=alt.X("x:Q"), y=alt.value(y), text="texto:N")


SEPARACION_RITMO = 12
# Longer games exist (up to 646 plies): the bars are cut here so the rest can be read.
TOPE_PLIES = 160


def partidas_crudas(muestra: pd.DataFrame, siguen: dict[str, float]) -> alt.Chart:
    """Los datos en crudo: cada línea es una partida real y su altura, cuántos plies duró.

    ``muestra`` tiene una fila por partida (``TimeClass``, ``orden`` de la más corta a la más
    larga dentro de su ritmo, ``plies``, ``resultado``); ``siguen``, qué parte de cada ritmo
    tiene fila en el corte 60.
    """
    por_ritmo = int(muestra["orden"].max()) + 1
    inicio = {r: i * (por_ritmo + SEPARACION_RITMO) for i, r in enumerate(RITMOS)}
    ancho = inicio[RITMOS[-1]] + por_ritmo
    datos = muestra.assign(
        x=muestra["TimeClass"].map(inicio) + muestra["orden"],
        x2=muestra["TimeClass"].map(inicio) + muestra["orden"] + 0.7,
        visible=muestra["plies"].clip(upper=TOPE_PLIES), base=0,
        llega=muestra["plies"].gt(60).map({True: "sí", False: "no"}),
    )
    lineas = alt.Chart(datos).mark_rect().encode(
        x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[0, ancho], nice=False)), x2="x2:Q",
        y=alt.Y("base:Q", title="Plies que duró la partida", scale=alt.Scale(domain=[0, TOPE_PLIES + 30], nice=False),
                axis=alt.Axis(values=[0, 20, 40, 60, 80, 100, 120, 140, 160])),
        y2="visible:Q",
        color=alt.Color("TimeClass:N", legend=None, scale=ESCALA_RITMO),
        opacity=alt.Opacity("llega:O", legend=None, sort=["no", "sí"], scale=alt.Scale(domain=["no", "sí"], range=[0.28, 1])),
        tooltip=[alt.Tooltip("TimeClass:N", title="Ritmo"), alt.Tooltip("plies:Q", title="Duró (plies)"),
                 alt.Tooltip("resultado:N", title="Terminó"), alt.Tooltip("llega:N", title="Pasó el ply 60")],
    )
    regla = alt.Chart(pd.DataFrame({"y": [60]})).mark_rule(
        color=FONDO_TEXTO, strokeDash=[5, 4], strokeWidth=1.5).encode(y="y:Q")
    rotulos = pd.DataFrame({
        "x": [inicio[r] for r in RITMOS],
        "texto": [f"{r.capitalize()}: {siguen[r] * 100:.0f} de cada 100\npasan el ply 60" for r in RITMOS],
    })
    return con_tema((lineas + regla + _rotulo(rotulos, 2, align="left", baseline="top", fontWeight="bold"))
                    .properties(height=340, usermeta=ANCHO_GRUPOS))


SEPARACION_CORTES = 0.09


def mosaico_resultado(segmentos: pd.DataFrame, cortes: list[int]) -> dict:
    """Lo que encontramos: de las mismas partidas, cómo terminan según la ventaja, en tres cortes.

    ``segmentos`` tiene una fila por (variable, corte_ply, ventaja, resultado) con ``ancho``
    (parte de las partidas del corte con esa ventaja), ``x0`` (dónde empieza la columna, 0 a 1),
    ``parte`` (fracción con ese resultado), ``y0``/``y1`` (apilados) y ``partidas``. El ancho
    dice cuántas partidas hay; la altura, cómo terminaron.
    """
    inicio = {c: i * (1 + SEPARACION_CORTES) for i, c in enumerate(cortes)}
    total = inicio[cortes[-1]] + 1
    datos = segmentos.assign(x=segmentos["corte_ply"].map(inicio) + segmentos["x0"])
    datos["x2"] = datos["x"] + datos["ancho"]
    datos["centro"], datos["medio"] = (datos["x"] + datos["x2"]) / 2, (datos["y0"] + datos["y1"]) / 2
    datos["texto"] = [f"{p * 100:.0f}" for p in datos["parte"]]
    vistas = []
    for variable in datos["variable"].unique():
        base = alt.Chart(datos[datos["variable"] == variable])
        celdas = base.mark_rect(stroke=BORDE_PUNTO, strokeWidth=0.8).encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[0, total], nice=False)), x2="x2:Q",
            y=alt.Y("y0:Q", title="Cómo terminaron", scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format="%", values=[0, 0.5, 1])), y2="y1:Q",
            color=alt.Color("resultado:N", title=None, scale=ESCALA_RESULTADO),
            tooltip=[alt.Tooltip("corte_ply:Q", title="Plies jugados"), alt.Tooltip("ventaja:N", title="Ventaja"),
                     alt.Tooltip("resultado:N", title="Terminó"), alt.Tooltip("parte:Q", title="De esas partidas", format=".0%"),
                     alt.Tooltip("partidas:Q", title="Partidas", format=",")],
        )
        # Only where the number fits: narrow columns keep theirs in the tooltip.
        numeros = base.transform_filter((alt.datum.ancho > 0.06) & (alt.datum.resultado != "Empate")).mark_text(
            fontSize=11, fontWeight="bold").encode(
            x="centro:Q", y="medio:Q", text="texto:N",
            color=alt.condition(alt.datum.resultado == "Gana Negras", alt.value("#ffffff"), alt.value(FONDO_TEXTO)),
        )
        cabeceras = pd.DataFrame({"x": [inicio[c] + 0.5 for c in cortes],
                                  "texto": [f"Ply {c} (jugada {c // 2})" for c in cortes]})
        pies = pd.DataFrame({"x": [inicio[c] + 0.5 for c in cortes], "texto": ["negras arriba   |   blancas arriba"] * len(cortes)})
        vistas.append((celdas + numeros + _rotulo(cabeceras, -10, fontWeight="bold")
                       + _rotulo(pies, 204, fontSize=11, color=TEXTO_SUAVE)).properties(
            height=190, title=alt.TitleParams(variable, anchor="start", color=FONDO_TEXTO, fontSize=15,
                                              fontWeight="bold", offset=24)))
    return alt.vconcat(*vistas, spacing=34, usermeta=ANCHO_GRUPOS).configure(**TEMA).to_dict()


def senal_por_corte(eta2: pd.DataFrame) -> alt.Chart:
    """Lo que encontramos: cuánto separan al ganador el material y el reloj, según el corte.

    ``eta2`` tiene una fila por (variable, corte_ply) con ``eta2`` (0 a 1).
    """
    base = alt.Chart(eta2).encode(
        x=alt.X("corte_ply:Q", axis=alt.Axis(title="Plies jugados", values=[10, 20, 30, 40, 60]),
                scale=alt.Scale(domain=[5, 65])),
        y=alt.Y("eta2:Q", title="Variación del resultado que explica (η²)", axis=alt.Axis(format="%")),
        color=alt.Color("variable:N", title=None, scale=ESCALA_VARIABLE),
    )
    lineas = base.mark_line(strokeWidth=2.5) + base.mark_point(filled=True, size=50).encode(
        tooltip=[alt.Tooltip("variable:N", title="Variable"), alt.Tooltip("corte_ply:Q", title="Plies"),
                 alt.Tooltip("eta2:Q", title="η²", format=".3f")],
    )
    # The EDA's own threshold: below 0.05 the association counts as negligible (red zone).
    umbral = alt.Chart(pd.DataFrame({"eta2": [0.05], "texto": ["umbral de señal débil (0,05)"]}))
    regla = umbral.mark_rule(strokeDash=[4, 4], color=TEXTO_SUAVE).encode(y="eta2:Q")
    etiqueta = umbral.mark_text(align="left", dx=4, dy=-6, color=TEXTO_SUAVE, fontSize=11).encode(
        x=alt.value(0), y="eta2:Q", text="texto:N")
    return con_tema((regla + etiqueta + lineas).properties(height=300))


def modelo_contra_piso(curva: pd.DataFrame) -> dict:
    """El modelo: arriba cuánto error del piso evita (en %), abajo el error crudo de los dos.

    ``curva`` tiene una fila por (serie, corte_ply) con ``log_loss``, ``mejora`` (fracción
    sobre el piso, repetida en las dos series) y ``partidas``. Las barras de arriba van
    primero porque arrancan de cero y leen lo que importa: qué parte del error del piso se
    evita. Abajo, el error crudo se muestra tal cual (menor es mejor): el piso empeora al
    final porque las partidas largas terminan distinto, no porque el modelo falle.
    """
    pares = curva.pivot_table(index="corte_ply", columns="serie", values="log_loss").reset_index()
    # Same x domain as the bars above, so a cut sits below its own bar.
    x_corte = alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[-3, 123]))
    titulo_error = "Error (log-loss, menos es mejor)"
    # The gap is the message: one segment per cut, from the floor's error to the model's.
    distancia = alt.Chart(pares).mark_rule(color=COLOR_MODELO, opacity=0.35, strokeWidth=6).encode(
        x=x_corte, y=alt.Y("Modelo:Q", title=titulo_error, scale=alt.Scale(zero=False)), y2="Piso:Q")
    puntos = alt.Chart(curva).mark_point(filled=True, size=70, opacity=1).encode(
        x=x_corte, y=alt.Y("log_loss:Q", title=titulo_error, scale=alt.Scale(zero=False)),
        color=alt.Color("serie:N", title=None, scale=ESCALA_SERIE),
        tooltip=[alt.Tooltip("serie:N", title="Serie"), alt.Tooltip("corte_ply:Q", title="Plies"),
                 alt.Tooltip("log_loss:Q", title="Log-loss", format=".3f"),
                 alt.Tooltip("mejora:Q", title="Mejora sobre el piso", format=".1%"),
                 alt.Tooltip("partidas:Q", title="Partidas de test", format=",")],
    )
    barras = alt.Chart(curva[curva["serie"] == "Modelo"]).mark_bar(color=COLOR_MODELO, opacity=0.85, size=14).encode(
        x=alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[-3, 123])),
        y=alt.Y("mejora:Q", title="Error que evita el modelo", axis=alt.Axis(format="%", tickCount=4)),
        tooltip=[alt.Tooltip("corte_ply:Q", title="Plies"),
                 alt.Tooltip("mejora:Q", title="Menos error que el piso", format=".1%"),
                 alt.Tooltip("partidas:Q", title="Partidas de test", format=",")],
    )
    return alt.vconcat(barras.properties(height=150), (distancia + puntos).properties(height=200),
                       spacing=20, usermeta=ANCHO_MINIMO_ANGOSTO).configure(**TEMA).to_dict()


# Professor's feedback on Entrega 3: fixed-decision metrics and importance, band by band.
# Readable names for the columns that lead the importance in some band.
NOMBRE_COLUMNA = {
    "balance_material": "Material (blancas − negras)",
    "diferencia_reloj_seg": "Reloj (blancas − negras)",
    "diferencia_elo_previa": "Diferencia de rating previo",
    "reloj_blancas_seg": "Reloj de blancas",
    "reloj_negras_seg": "Reloj de negras",
}
COLOR_COLUMNA = dict(zip(NOMBRE_COLUMNA.values(), ["#d95640", "#216653", "#806320", "#78978a", "#202c28"]))
ESCALA_COLUMNA = alt.Scale(domain=list(COLOR_COLUMNA), range=list(COLOR_COLUMNA.values()))


def _eje_tramo(tramos: list[str]) -> alt.X:
    return alt.X("tramo:O", sort=tramos, title="Plies jugados (tramo)", axis=alt.Axis(labelAngle=0))


CATEGORIAS_ACIERTO = ["Aciertos que ya da decir siempre blancas", "Aciertos que suma el modelo", "Se equivoca"]
COLOR_CATEGORIA = [COLOR_RESULTADO["Empate"], COLOR_MODELO, "#f0b3a6"]
SEPARACION_CIEN = 1.6


def acierto_de_cien(tramos: pd.DataFrame) -> alt.Chart:
    """Decisión fija, contada de a una: de cada 100 posiciones de test de un tramo, cuántas acierta.

    ``tramos`` tiene una fila por tramo con ``accuracy`` y ``accuracy piso`` (0 a 1). Cada
    cuadrado es una posición de cada 100: las que acierta el piso, las que suma el modelo
    encima y las que falla. Son conteos: no dice que sean las mismas posiciones.
    """
    celdas, rotulos, aciertos = [], [], []
    for i, fila in enumerate(tramos.to_dict("records")):
        inicio = i * (10 + SEPARACION_CIEN)
        modelo, piso = round(fila["accuracy"] * 100), round(fila["accuracy piso"] * 100)
        for k in range(100):
            categoria = CATEGORIAS_ACIERTO[0 if k < piso else 1 if k < modelo else 2]
            x, y = inicio + k % 10, k // 10
            celdas.append({"x": x + 0.08, "x2": x + 0.92, "y": y + 0.08, "y2": y + 0.92, "categoria": categoria,
                           "tramo": fila["tramo"], "modelo": modelo, "piso": piso})
        rotulos.append({"x": inicio + 5, "texto": "antes de mover" if fila["tramo"] == "0" else f"plies {fila['tramo']}"})
        aciertos.append({"x": inicio + 5, "texto": str(modelo)})
    total = len(tramos) * 10 + (len(tramos) - 1) * SEPARACION_CIEN
    alto = 270
    cuadros = alt.Chart(pd.DataFrame(celdas)).mark_rect(cornerRadius=1).encode(
        x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[0, total], nice=False)), x2="x2:Q",
        # Room above the squares for the count and below for the band's name.
        y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-1.6, 12.4], nice=False)), y2="y2:Q",
        color=alt.Color("categoria:N", title=None, sort=CATEGORIAS_ACIERTO,
                        scale=alt.Scale(domain=CATEGORIAS_ACIERTO, range=COLOR_CATEGORIA),
                        legend=alt.Legend(labelLimit=0, symbolType="square", symbolSize=120)),
        tooltip=[alt.Tooltip("tramo:N", title="Plies"), alt.Tooltip("modelo:Q", title="Acierta el modelo, de cada 100"),
                 alt.Tooltip("piso:Q", title="Acierta decir siempre blancas")],
    )
    return con_tema((cuadros + _rotulo(pd.DataFrame(aciertos), 18, fontSize=28, fontWeight="bold", color=COLOR_MODELO)
                     + _rotulo(pd.DataFrame(rotulos), alto - 12, fontSize=12)).properties(height=alto, usermeta=ANCHO_GRUPOS))


VISTAS_CONFUSION = ["recall", "precision"]
NOMBRE_VISTA_CONFUSION = ["Recall: de cada resultado real, qué dijo", "Precisión: de lo que dijo, qué pasó"]


def confusion_por_tramo(filas: pd.DataFrame, tramos: list[str]) -> alt.Chart:
    """Matriz de confusión de un tramo, con dos menús: el tramo y la forma de leerla.

    - Recall: % de la fila. De cada resultado real, qué predijo el modelo.
    - Precisión: % de la columna. De cada predicción del modelo, qué pasó. Una clase que el
      modelo nunca predijo en el tramo no tiene precisión: la celda queda en "—".

    ``filas`` tiene una fila por (tramo, real, predicho) con ``filas``, ``porcentaje_fila`` y
    ``porcentaje_columna`` (``src.metricas_tramo.confusion_por_tramo``).
    """
    tramo = alt.param(name="tramo", value=tramos[0],
                      bind=alt.binding_select(options=tramos, name="Plies jugados "))
    vista = alt.param(name="vista", value=VISTAS_CONFUSION[0],
                      bind=alt.binding_radio(options=VISTAS_CONFUSION, labels=NOMBRE_VISTA_CONFUSION, name=" "))
    base = (
        alt.Chart(filas)
        .transform_filter(alt.datum.tramo == tramo)
        .transform_calculate(valor=f"{vista.name} === 'precision' ? datum.porcentaje_columna : datum.porcentaje_fila")
        .transform_calculate(medido="isValid(datum.valor) && isFinite(datum.valor)")
        .encode(
            x=alt.X("predicho:N", sort=RESULT_ORDER, title="Lo que dijo el modelo",
                    axis=alt.Axis(labelAngle=0, orient="top")),
            y=alt.Y("real:N", sort=RESULT_ORDER, title="Cómo terminó"),
        )
    )
    celdas = base.mark_rect(stroke="#ffffff", strokeWidth=2).encode(
        color=alt.condition(
            "datum.medido",
            alt.Color("valor:Q", title="%", legend=None, scale=alt.Scale(domain=[0, 100], range=["#f6f1e7", COLOR_MODELO])),
            alt.value(LINEA),
        ),
        tooltip=[alt.Tooltip("real:N", title="Real"), alt.Tooltip("predicho:N", title="Predicho"),
                 alt.Tooltip("porcentaje_fila:Q", title="% de la fila (recall)", format=".1f"),
                 alt.Tooltip("porcentaje_columna:Q", title="% de la columna (precisión)", format=".1f"),
                 alt.Tooltip("filas:Q", title="Filas", format=",")],
    )
    textos = base.transform_calculate(
        texto="datum.medido ? format(datum.valor, '.0f') : '—'"
    ).mark_text(fontSize=15).encode(
        text=alt.Text("texto:N"),
        color=alt.condition("datum.medido && datum.valor > 55", alt.value("#ffffff"), alt.value(FONDO_TEXTO)),
    )
    return con_tema((celdas + textos).add_params(tramo, vista).properties(height=240))


COLUMNAS_IMPORTANCIA = ["Diferencia de rating previo", "Material (blancas − negras)", "Reloj (blancas − negras)"]
# Two columns this close (in hits out of 100) count as tied for the lead.
EMPATE_PUNTOS = 0.05


def importancia_por_tramo(filas: pd.DataFrame, tramos: list[str]) -> alt.Chart:
    """En qué se fija: cuántos aciertos de cada 100 pierde el modelo si se le tapa cada columna.

    ``filas`` tiene una fila por (nombre, tramo) con ``accuracy`` (aciertos que se pierden al
    desordenar la columna, 0 a 1) y ``log_loss``. Una faceta por columna, las tres con el mismo
    eje y; la barra llena es la columna que más pesa en ese tramo, o las que empatan.
    """
    datos = filas[filas["nombre"].isin(COLUMNAS_IMPORTANCIA)].copy()
    datos["puntos"] = datos["accuracy"] * 100
    lider = datos.groupby("tramo")["puntos"].transform("max")
    datos["lidera"] = (datos["puntos"] >= lider - EMPATE_PUNTOS).map({True: "sí", False: "no"})
    inicio = {n: i * (len(tramos) + 1) for i, n in enumerate(COLUMNAS_IMPORTANCIA)}
    datos["x"] = datos["nombre"].map(inicio) + datos["tramo"].map({t: i for i, t in enumerate(tramos)}) + 0.1
    datos["x2"], datos["centro"], datos["cero"] = datos["x"] + 0.8, datos["x"] + 0.4, 0
    datos["desde"] = datos["tramo"].str.split("–").str[0]
    datos["texto"] = [f"{p:.1f}".replace(".", ",") if abs(p) >= 0.05 else "0" for p in datos["puntos"]]
    alto, base = 280, alt.Chart(datos)
    escala_y = alt.Scale(domain=[0, float(datos["puntos"].max()) * 1.35], nice=False)
    barras = base.mark_rect().encode(
        x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[0, len(tramos) * 3 + 2], nice=False)), x2="x2:Q",
        y=alt.Y("cero:Q", title="Aciertos que pierde, de cada 100", scale=escala_y, axis=alt.Axis(values=[0, 5, 10, 15])),
        y2="puntos:Q",
        color=alt.Color("nombre:N", legend=None, scale=ESCALA_COLUMNA),
        opacity=alt.Opacity("lidera:O", legend=None, sort=["no", "sí"], scale=alt.Scale(domain=["no", "sí"], range=[0.35, 1])),
        tooltip=[alt.Tooltip("nombre:N", title="Columna"), alt.Tooltip("tramo:O", title="Plies"),
                 alt.Tooltip("puntos:Q", title="Aciertos que pierde, de cada 100", format=".1f"),
                 alt.Tooltip("log_loss:Q", title="Error que suma (log-loss)", format=".4f")],
    )
    numeros = base.mark_text(dy=-8, fontSize=12, color=FONDO_TEXTO, fontWeight="bold").encode(
        x="centro:Q", y=alt.Y("puntos:Q", scale=escala_y), text="texto:N")
    desde = base.mark_text(dy=12, fontSize=11, color=TEXTO_SUAVE).encode(x="centro:Q", y="cero:Q", text="desde:N")
    titulos = pd.DataFrame({"x": [inicio[n] + 0.1 for n in COLUMNAS_IMPORTANCIA],
                            "texto": [n.split(" (")[0].replace(" previo", "") for n in COLUMNAS_IMPORTANCIA]})
    pies = pd.DataFrame({"x": [inicio[n] + len(tramos) / 2 for n in COLUMNAS_IMPORTANCIA], "texto": ["tramo, desde el ply"] * 3})
    return con_tema((barras + numeros + desde
                     + _rotulo(titulos, 4, align="left", baseline="top", fontSize=15, fontWeight="bold")
                     + _rotulo(pies, alto + 28, fontSize=11, color=TEXTO_SUAVE)).properties(height=alto, usermeta=ANCHO_GRUPOS))


EJES_SITUACION = ["Material", "Reloj"]


def acierto_por_situacion(filas: pd.DataFrame, tramos: list[str]) -> alt.Chart:
    """¿En qué situaciones acierta el modelo? Mapa de calor: tramo de jugadas por situación.

    ``filas`` tiene una fila por (eje, tramo, situacion) con ``orden`` (0 es la más pareja),
    ``rango`` (qué diferencia es), ``filas`` y ``accuracy``. Un menú cambia el eje de la situación: la ventaja de material
    o la de reloj. El color y el número son el % de aciertos; una celda vacía es una situación que no
    aparece en ese tramo (antes de mover el material siempre está parejo).
    """
    eje = alt.param(name="eje", value=EJES_SITUACION[0],
                    bind=alt.binding_radio(options=EJES_SITUACION, name="Situación según el "))
    base = alt.Chart(filas).transform_filter(alt.datum.eje == eje).transform_calculate(
        texto="format(datum.accuracy * 100, '.0f')",
    ).encode(
        x=alt.X("tramo:O", sort=tramos, title="Plies jugados (tramo)",
                axis=alt.Axis(labelAngle=0, orient="top", labelFontSize=11)),
        y=alt.Y("situacion:N", sort=alt.EncodingSortField("orden", order="ascending"), title=None,
                axis=alt.Axis(labelLimit=120)),
    )
    celdas = base.mark_rect(stroke="#ffffff", strokeWidth=2).encode(
        color=alt.Color("accuracy:Q", title="Aciertos", legend=None,
                        scale=alt.Scale(domain=[0.48, 0.86], range=["#f6f1e7", COLOR_MODELO], clamp=True)),
        tooltip=[alt.Tooltip("situacion:N", title="Situación"), alt.Tooltip("rango:N", title="Diferencia"),
                 alt.Tooltip("tramo:O", title="Plies"), alt.Tooltip("accuracy:Q", title="Aciertos", format=".1%"),
                 alt.Tooltip("filas:Q", title="Filas de test", format=","),
                 alt.Tooltip("parte:Q", title="Parte de las filas del tramo", format=".0%")],
    )
    textos = base.mark_text(fontSize=14).encode(
        text="texto:N",
        color=alt.condition("datum.accuracy > 0.67", alt.value("#ffffff"), alt.value(FONDO_TEXTO)),
    )
    return con_tema((celdas + textos).add_params(eje).properties(height=170))


COLOR_FINAL = {"Acertó": COLOR_MODELO, "Se equivocó": "#d95640"}


def como_terminan(filas: pd.DataFrame, finales: list[str]) -> alt.Chart:
    """Cómo terminaron las partidas en que el modelo acertó (izquierda) y en las que falló (derecha).

    ``filas`` tiene una fila por (decision, final) con ``parte`` (fracción de las filas de
    esa decisión, 0 a 1) y ``filas``. Las dos mitades comparten el eje del medio: un final
    cargado hacia la derecha es una de las razones del error.
    """
    aciertos, errores = list(COLOR_FINAL)
    datos = filas.assign(
        lado=filas["parte"].where(filas["decision"] == errores, -filas["parte"]), cero=0,
        texto=[f"{p * 100:.0f}" for p in filas["parte"]],
    )
    base = alt.Chart(datos).encode(
        y=alt.Y("final:N", sort=finales, title=None, axis=alt.Axis(labelFontSize=14, domain=False, ticks=False)))
    x = alt.X("lado:Q", title=None, axis=None, scale=alt.Scale(domain=[-0.62, 0.62], nice=False))
    barras = base.mark_bar(size=34).encode(
        x=x, x2="cero:Q",
        color=alt.Color("decision:N", legend=None, scale=alt.Scale(domain=list(COLOR_FINAL), range=list(COLOR_FINAL.values()))),
        tooltip=[alt.Tooltip("decision:N", title="El modelo"), alt.Tooltip("final:N", title="La partida terminó"),
                 alt.Tooltip("parte:Q", title="Parte del grupo", format=".1%"),
                 alt.Tooltip("filas:Q", title="Filas de test", format=",")],
    )
    numeros = [
        base.transform_filter(alt.datum.decision == decision).mark_text(
            align=align, dx=dx, fontSize=15, fontWeight="bold", color=FONDO_TEXTO).encode(x=x, text="texto:N")
        for decision, align, dx in [(aciertos, "right", -6), (errores, "left", 6)]
    ]
    titulos = [
        _rotulo(pd.DataFrame({"x": [0], "texto": [texto]}), -14, fontWeight="bold", align=align, dx=dx)
        for texto, align, dx in [("De cada 100 aciertos", "right", -12), ("De cada 100 errores", "left", 12)]
    ]
    eje = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=FONDO_TEXTO).encode(x="x:Q")
    return con_tema(alt.layer(barras, *numeros, *titulos, eje).properties(height=220))


# Explorá's third control: every game, or only those where the model's most probable class was right or wrong.
ACIERTO = ["Todas", "Acertó", "Se equivocó"]
# Explorá's horizontal axis: material (points) or clock (fraction of the base time).
EJES_X = ["Material", "Reloj", "Rating"]


def explora(filas: pd.DataFrame, partidas: pd.DataFrame, niveles: list[str]) -> dict:
    """Explorá: las partidas de test en un corte, y la curva del modelo de la que se elija.

    ``filas`` tiene una fila por (id, corte_ply) con la posición y las tres probabilidades
    del modelo; ``partidas``, una por id con los datos de la partida. Los controles son
    params de Altair: el deslizador elige el corte; los menús, el ritmo y el nivel; los botones,
    si se ven todas las partidas o sólo las que el modelo acertó o erró en ese corte.

    Devuelve la spec ya serializada: la tabla de partidas va una sola vez, como dataset
    con nombre, en lugar de repetirse adentro de cada vista que la consulta.
    """
    corte = alt.param(name="corte", value=40,
                      bind=alt.binding_range(min=0, max=120, step=5, name="Plies jugados "))
    ritmo = alt.param(name="ritmo", value="todos",
                      bind=alt.binding_select(options=["todos", *RITMOS], name="Ritmo "))
    nivel = alt.param(name="nivel", value="todos",
                      bind=alt.binding_select(options=["todos", *niveles], name="Nivel "))
    elegida = alt.selection_point(name="elegida", fields=["id"], on="click", clear="dblclick", empty=False)
    acierto = alt.param(name="acierto", value=ACIERTO[0],
                        bind=alt.binding_radio(options=ACIERTO, name="Partidas "))
    # What the horizontal axis shows: the model's answer stays on the vertical one.
    eje_x = alt.param(name="eje_x", value=EJES_X[0], bind=alt.binding_radio(options=EJES_X, name="Eje horizontal "))

    datos_partida = alt.LookupData(
        data=alt.Data(name="partidas"), key="id",
        fields=[c for c in partidas.columns if c != "id"],
    )
    base = alt.Chart(filas).transform_lookup(
        lookup="id", from_=datos_partida,
    )
    panorama = base.transform_filter(
        (alt.datum.corte_ply == corte)
        & ((ritmo == "todos") | (alt.datum.TimeClass == ritmo))
        & ((nivel == "todos") | (alt.datum.nivel_promedio == nivel))
    ).transform_calculate(
        # Material is an integer: a fixed per-game jitter (computed in the build) separates the points.
        material_visible="datum.balance_material + datum.desplazamiento",
        x_valor="eje_x == 'Reloj' ? datum.dif_reloj : (eje_x == 'Rating' ? datum.dif_rating : "
                "datum.balance_material + datum.desplazamiento)",
        # Not every game has both prior ratings: with the rating axis those points are left out.
        dif_rating_texto="isValid(datum.dif_rating) ? format(datum.dif_rating, '+d') : 'sin dato'",
        ventaja="datum.p_blancas - datum.p_negras",
        # The model's fixed decision, the most probable class (ties as numpy's argmax: white, draw, black).
        prediccion="datum.p_blancas >= datum.p_empate && datum.p_blancas >= datum.p_negras ? 'Gana Blancas' : "
                   "(datum.p_empate >= datum.p_negras ? 'Empate' : 'Gana Negras')",
    ).transform_calculate(
        acerto="datum.prediccion == datum.resultado",
    ).transform_filter(
        "isValid(datum.x_valor)"
    ).transform_filter(
        (acierto == ACIERTO[0]) | ((acierto == ACIERTO[1]) & alt.datum.acerto)
        | ((acierto == ACIERTO[2]) & ~alt.datum.acerto)
    ).mark_circle(size=38, opacity=0.85, stroke=BORDE_PUNTO, strokeWidth=0.8).encode(
        x=alt.X("x_valor:Q",
                # An axis title can't follow a param: one title that reads right for both axes.
                title="Ventaja de blancas sobre negras: material (puntos), reloj (% del tiempo base) o rating previo (puntos)",
                # nice=False: with a domain given as an expression Vega would round it up to ±20.
                scale=alt.Scale(domain=alt.ExprRef(expr="eje_x == 'Reloj' ? [-1, 1] : (eje_x == 'Rating' ? [-400, 400] : [-15, 15])"),
                                clamp=True, nice=False),
                axis=alt.Axis(labelExpr="eje_x == 'Reloj' ? (datum.value == 0 ? '0 %' : format(datum.value * 100, '+d') + ' %') : "
                                        "(eje_x == 'Rating' ? (datum.value == 0 ? '0' : format(datum.value, '+d')) : datum.label)")),
        y=alt.Y("ventaja:Q", title="Lo que dice el modelo: P(blancas) − P(negras)",
                scale=alt.Scale(domain=[-1, 1]), axis=alt.Axis(format="+.0%")),
        color=alt.Color("resultado:N", title="Cómo terminó", scale=ESCALA_RESULTADO),
        size=alt.condition(elegida, alt.value(160), alt.value(38)),
        tooltip=[
            alt.Tooltip("blancas:N", title="Blancas"), alt.Tooltip("negras:N", title="Negras"),
            alt.Tooltip("TimeClass:N", title="Ritmo"), alt.Tooltip("nivel_promedio:N", title="Nivel"),
            alt.Tooltip("corte_ply:Q", title="Plies jugados"),
            alt.Tooltip("balance_material:Q", title="Material (bl − ng)"),
            alt.Tooltip("dif_reloj:Q", title="Reloj (bl − ng)", format="+.0%"),
            alt.Tooltip("dif_rating_texto:N", title="Rating previo (bl − ng)"),
            alt.Tooltip("p_blancas:Q", title="Modelo: gana blancas", format=".0%"),
            alt.Tooltip("p_empate:Q", title="Modelo: tablas", format=".0%"),
            alt.Tooltip("p_negras:Q", title="Modelo: gana negras", format=".0%"),
            alt.Tooltip("prediccion:N", title="El modelo elige"),
            alt.Tooltip("resultado:N", title="Resultado real"), alt.Tooltip("final:N", title="Terminó por"),
        ],
    ).add_params(corte, ritmo, nivel, acierto, eje_x, elegida).properties(height=380, width=ANCHO_EXPLORA)

    detalle_base = base.transform_filter(elegida).transform_fold(
        ["p_blancas", "p_empate", "p_negras"], as_=["clave", "probabilidad"],
    ).transform_calculate(
        prediccion="{'p_blancas': 'Gana Blancas', 'p_empate': 'Empate', 'p_negras': 'Gana Negras'}[datum.clave]",
        orden="{'p_blancas': 0, 'p_empate': 1, 'p_negras': 2}[datum.clave]",
    )
    curva = detalle_base.mark_area(opacity=0.95, interpolate="monotone").encode(
        x=alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[0, 120])),
        y=alt.Y("probabilidad:Q", stack="normalize", title="Probabilidad según el modelo", axis=alt.Axis(format="%")),
        # Without its own title and pinned to the right end of the strip above the view: the chosen
        # game's title takes the rest of that strip, so the two never overlap.
        color=alt.Color("prediccion:N", title=None, scale=ESCALA_RESULTADO,
                        legend=alt.Legend(orient="none", direction="horizontal", legendX=alt.ExprRef(expr="width - 270"),
                                          legendY=-34)),
        order=alt.Order("orden:Q"),
        tooltip=[alt.Tooltip("corte_ply:Q", title="Plies"), alt.Tooltip("prediccion:N", title="Resultado"),
                 alt.Tooltip("probabilidad:Q", title="Probabilidad", format=".0%")],
    )
    marca_corte = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=COLOR_MODELO, strokeWidth=2).encode(
        x=alt.X("c:Q", scale=alt.Scale(domain=[0, 120])),
    ).transform_calculate(c=corte.name)  # the slider's value, as a data field
    titulo = base.transform_filter(elegida).transform_filter(alt.datum.corte_ply == 0).mark_text(
        align="left", baseline="bottom", fontSize=13, dy=-8, color=FONDO_TEXTO,
        # Leave the legend its corner on wide charts.
        limit=alt.ExprRef(expr="width > 640 ? width - 290 : width"),
    ).encode(x=alt.value(0), y=alt.value(0), text="titulo:N")
    # Until a game is chosen, the lower view says how to choose one (the selection's store is empty).
    aviso = alt.Chart(pd.DataFrame({"texto": ["Elegí una partida de arriba\npara ver sus probabilidades"]})).transform_filter(
        "length(data('elegida_store')) == 0"
    ).mark_text(fontSize=14, color=TEXTO_SUAVE, lineBreak="\n", x=alt.ExprRef(expr="width / 2"), y=90).encode(text="texto:N")
    detalle = (curva + marca_corte + titulo + aviso).properties(height=180, width=ANCHO_EXPLORA)
    # The 5,000-row guard is for notebooks; the build checks the file size instead.
    with alt.data_transformers.enable("default", max_rows=None):
        # Two legends on purpose: above, how each game ended; below, what the model said.
        spec = alt.vconcat(panorama, detalle, spacing=36).resolve_legend(color="independent").configure(**TEMA).to_dict()
    # A missing value (a game without both prior ratings) travels as null, never as NaN (invalid JSON for the web).
    spec["datasets"]["partidas"] = partidas.astype(object).where(partidas.notna(), None).to_dict(orient="records")
    return spec


# Probabilities of one game, as the API sends them (one row per ply).
CLAVE_RESULTADO = {"gana_blancas": "Gana Blancas", "empate": "Empate", "gana_negras": "Gana Negras"}
# The x axis starts this wide so the first moves don't stretch across the whole chart.
PLIES_MINIMOS = 40


def curva_partida() -> dict:
    """Jugar y Analizar: cómo se movieron las tres probabilidades del modelo en una partida.

    La spec no trae datos: la web llena tres datasets con nombre en cada jugada, sin
    volver a dibujar el gráfico. ``curva`` son las filas que devuelve la API
    (``ply``, ``gana_blancas``, ``empate``, ``gana_negras``); ``momentos``, los plies donde
    más se movió la probabilidad de blancas; ``actual``, el ply que muestra el tablero.
    El param ``ply_maximo`` estira el eje x hasta el último ply (al menos 40).
    ``hover`` es el ply más cercano al mouse: la web lo lee al hacer clic para mover el tablero.
    """
    ply_maximo = alt.param(name="ply_maximo", value=PLIES_MINIMOS)
    hover = alt.selection_point(name="hover", fields=["ply"], on="pointerover", clear="pointerout", empty=False)
    eje_x = alt.X("ply:Q", title="Número de jugada",
                  scale=alt.Scale(domainMin=0, domainMax=alt.ExprRef(expr="ply_maximo"), nice=False),
                  # One move is two plies: the axis counts moves, with ticks every 10 or 20 plies
                  # so that labels are whole moves.
                  axis=alt.Axis(labelExpr="datum.value / 2", grid=False, values=alt.ExprRef(
                      expr="sequence(0, ply_maximo + 1, ply_maximo > 120 ? 20 : 10)")))
    base = alt.Chart(alt.Data(name="curva"))

    areas = base.transform_fold(
        list(CLAVE_RESULTADO), as_=["clave", "probabilidad"],
    ).transform_calculate(
        resultado=f"{CLAVE_RESULTADO}[datum.clave]",
        # White at the bottom, black at the top, as on the bar above the board.
        orden="{'gana_blancas': 0, 'empate': 1, 'gana_negras': 2}[datum.clave]",
    ).mark_area(stroke=BORDE_PUNTO, strokeWidth=0.6).encode(
        x=eje_x,
        y=alt.Y("probabilidad:Q", stack="zero", title="Probabilidad según el modelo",
                scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", values=[0, 0.5, 1])),
        color=alt.Color("resultado:N", title=None, scale=ESCALA_RESULTADO),
        order=alt.Order("orden:Q"),
    )
    mitad = alt.Chart(alt.Data(values=[{"y": 0.5}])).mark_rule(
        color=FONDO_TEXTO, strokeDash=[2, 5], opacity=0.7,
    ).encode(y="y:Q")
    momentos = alt.Chart(alt.Data(name="momentos")).mark_rule(
        color=COLOR_MODELO, strokeDash=[3, 3],
    ).encode(x=alt.X("ply:Q"), tooltip=[alt.Tooltip("descripcion:N", title="Momento clave")])
    actual = alt.Chart(alt.Data(name="actual")).mark_rule(color=COLOR_MODELO, strokeWidth=3).encode(x=alt.X("ply:Q"))

    # One invisible full-height bar per ply picks the ply under the mouse and carries the
    # tooltip; the rule shows which one it is.
    por_jugada = base.transform_calculate(
        jugada="datum.ply == 0 ? 'Antes de mover' : 'Jugada ' + ceil(datum.ply / 2) + "
               "' de las ' + (datum.ply % 2 ? 'blancas' : 'negras')",
        desde="datum.ply - 0.5", hasta="datum.ply + 0.5",
    )
    guia = base.transform_filter(hover).mark_rule(color=FONDO_TEXTO, opacity=0.8).encode(x=alt.X("ply:Q"))
    selector = por_jugada.mark_rect(opacity=0).encode(
        x=alt.X("desde:Q"), x2="hasta:Q",
        tooltip=[alt.Tooltip("jugada:N", title="Momento"),
                 alt.Tooltip("gana_blancas:Q", title="Gana blancas", format=".0%"),
                 alt.Tooltip("empate:Q", title="Tablas", format=".0%"),
                 alt.Tooltip("gana_negras:Q", title="Gana negras", format=".0%")],
    ).properties(name="jugadas").add_params(hover)  # a fixed name keeps the spec stable between builds
    capas = alt.layer(areas, mitad, momentos, actual, guia, selector).add_params(ply_maximo)
    return con_tema(capas.properties(height=240)).to_dict()


def entre_cortes(filas: pd.DataFrame, todas: str, comun: str) -> alt.Chart:
    """Comparación entre cortes: aciertos del modelo en cada corte, con su IC 95 %.

    ``filas`` tiene una fila por (serie, corte_ply) con ``accuracy``, ``accuracy bajo`` y
    ``accuracy alto`` (bootstrap por partida). Las dos series son el mismo modelo sobre dos
    poblaciones: todas las partidas que siguen en juego, y siempre las mismas (las que
    llegan al ply 60). Por eso van del color del modelo y se distinguen por el trazo.
    """
    base = alt.Chart(filas).encode(
        x=alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[0, 120])),
    )
    trazo = alt.StrokeDash("serie:N", title=None, scale=alt.Scale(domain=[comun, todas], range=[[1, 0], [6, 4]]),
                           legend=alt.Legend(labelLimit=0, symbolType="stroke", symbolStrokeColor=COLOR_MODELO))
    eje_y = alt.Y("accuracy:Q", title="Aciertos del modelo (IC 95 %)", axis=alt.Axis(format="%"),
                  scale=alt.Scale(domain=[0.45, 0.75]))
    # The band shares the line's y scale (and its domain), so it never pulls the axis to zero.
    banda = base.mark_area(opacity=0.18, color=COLOR_MODELO).encode(
        y=alt.Y("accuracy bajo:Q", scale=alt.Scale(domain=[0.45, 0.75]), title=None), y2="accuracy alto:Q",
        detail="serie:N",
    )
    linea = base.mark_line(strokeWidth=2.5, color=COLOR_MODELO).encode(y=eje_y, strokeDash=trazo)
    puntos = base.mark_point(filled=True, size=40, color=COLOR_MODELO).encode(
        y="accuracy:Q",
        tooltip=[alt.Tooltip("serie:N", title="Partidas"), alt.Tooltip("corte_ply:Q", title="Plies jugados"),
                 alt.Tooltip("partidas:Q", title="Partidas de test", format=","),
                 alt.Tooltip("accuracy:Q", title="Aciertos", format=".1%"),
                 alt.Tooltip("accuracy bajo:Q", title="IC 95 %: desde", format=".1%"),
                 alt.Tooltip("accuracy alto:Q", title="IC 95 %: hasta", format=".1%"),
                 alt.Tooltip("puntos sobre piso:Q", title="Puntos sobre el piso", format=".1f")],
    )
    return con_tema((banda + linea + puntos).properties(height=300))


# The chosen model keeps the model's color and the floor the floor's; the other two get their own.
COLOR_LOGISTICA, COLOR_BOOSTING = "#3f6fa3", "#7a5c99"


def familias_por_tramo(filas: pd.DataFrame, modelos: list[str], tramos: list[str]) -> alt.Chart:
    """Las familias del notebook 04, tramo por tramo, en validación cruzada (notebook 05).

    ``filas`` tiene una fila por (modelo, tramo) con ``log_loss`` y ``± log_loss``: media y
    desvío de los pedazos. ``modelos`` va en orden: piso, logística, elegido, el otro ensamble.
    """
    escala = alt.Scale(domain=modelos, range=[COLOR_PISO, COLOR_LOGISTICA, COLOR_MODELO, COLOR_BOOSTING])
    base = alt.Chart(filas).transform_calculate(
        bajo="datum.log_loss - datum['± log_loss']", alto="datum.log_loss + datum['± log_loss']",
    ).encode(
        x=_eje_tramo(tramos),
        xOffset=alt.XOffset("modelo:N", sort=modelos),
        color=alt.Color("modelo:N", title=None, scale=escala, sort=modelos),
    )
    barras = base.mark_rule(strokeWidth=1.5).encode(y="bajo:Q", y2="alto:Q")
    puntos = base.mark_point(filled=True, size=60).encode(
        y=alt.Y("log_loss:Q", title="Log-loss en validación (media ± desvío; menos es mejor)",
                scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("modelo:N", title="Modelo"), alt.Tooltip("tramo:O", title="Plies"),
                 alt.Tooltip("log_loss:Q", title="Log-loss", format=".4f"),
                 alt.Tooltip("± log_loss:Q", title="Desvío", format=".4f"),
                 alt.Tooltip("accuracy:Q", title="Aciertos", format=".1%")],
    )
    return con_tema((barras + puntos).properties(height=320))
