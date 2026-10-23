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
FONDO_TEXTO = "#eaf2ee"
TEXTO_SUAVE = "#9fb7b1"
LINEA = "#24474b"
COLOR_RESULTADO = {"Gana Blancas": "#f6f1e7", "Empate": "#7fa3a0", "Gana Negras": "#0a0f10"}
BORDE_PUNTO = "#3e6366"
RITMOS = ["bullet", "blitz", "rapid"]
COLOR_RITMO = {"bullet": "#ff6b5b", "blitz": "#ffb547", "rapid": "#6fc2b0"}
COLOR_MODELO, COLOR_PISO = "#ffb547", "#9fb7b1"
COLOR_VARIABLE = {"Material": "#f6f1e7", "Reloj, a igual material": "#ffb547"}

ESCALA_RESULTADO = alt.Scale(domain=RESULT_ORDER, range=[COLOR_RESULTADO[r] for r in RESULT_ORDER])
ESCALA_RITMO = alt.Scale(domain=RITMOS, range=[COLOR_RITMO[r] for r in RITMOS])
ESCALA_SERIE = alt.Scale(domain=["Modelo", "Piso"], range=[COLOR_MODELO, COLOR_PISO])
ESCALA_VARIABLE = alt.Scale(domain=list(COLOR_VARIABLE), range=list(COLOR_VARIABLE.values()))
# Vega-Lite only sizes single and layered views to their container: the web resizes the
# two views of Explorá itself, starting from this width.
ANCHO_EXPLORA = 640
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


def partidas_vivas(vivas: pd.DataFrame) -> alt.Chart:
    """Los datos: qué parte de las partidas sigue en juego en cada corte, por ritmo.

    ``vivas`` tiene una fila por (ritmo, corte_ply) con ``siguen`` (fracción, 0 a 1).
    """
    base = alt.Chart(vivas).encode(
        x=alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[0, 120])),
        y=alt.Y("siguen:Q", title="Partidas que siguen en juego", axis=alt.Axis(format="%")),
        color=alt.Color("TimeClass:N", title="Ritmo", scale=ESCALA_RITMO),
    )
    lineas = base.mark_line(strokeWidth=2.5)
    puntos = base.mark_point(filled=True, size=40).encode(
        tooltip=[alt.Tooltip("TimeClass:N", title="Ritmo"), alt.Tooltip("corte_ply:Q", title="Plies"),
                 alt.Tooltip("siguen:Q", title="Siguen", format=".1%"),
                 alt.Tooltip("partidas:Q", title="Partidas", format=",")],
    )
    return con_tema((lineas + puntos).properties(height=300))


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


def modelo_contra_piso(curva: pd.DataFrame) -> alt.Chart:
    """El modelo: log-loss en test del modelo y del piso en cada corte (menor es mejor).

    ``curva`` tiene una fila por (serie, corte_ply) con ``log_loss``, ``mejora`` (fracción
    sobre el piso, repetida en las dos series) y ``partidas``.
    """
    base = alt.Chart(curva).encode(
        x=alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[0, 120])),
        y=alt.Y("log_loss:Q", title="Error de las probabilidades (log-loss, menor es mejor)",
                scale=alt.Scale(zero=False)),
        color=alt.Color("serie:N", title=None, scale=ESCALA_SERIE),
    )
    lineas = base.mark_line(strokeWidth=2.5)
    puntos = base.mark_point(filled=True, size=40).encode(
        tooltip=[alt.Tooltip("serie:N", title="Serie"), alt.Tooltip("corte_ply:Q", title="Plies"),
                 alt.Tooltip("log_loss:Q", title="Log-loss", format=".3f"),
                 alt.Tooltip("mejora:Q", title="Mejora sobre el piso", format=".1%"),
                 alt.Tooltip("partidas:Q", title="Partidas de test", format=",")],
    )
    return con_tema((lineas + puntos).properties(height=320))


def explora(filas: pd.DataFrame, partidas: pd.DataFrame, niveles: list[str]) -> dict:
    """Explorá: las partidas de test en un corte, y la curva del modelo de la que se elija.

    ``filas`` tiene una fila por (id, corte_ply) con la posición y las tres probabilidades
    del modelo; ``partidas``, una por id con los datos de la partida. Los controles son
    params de Altair: el deslizador elige el corte; los menús, el ritmo y el nivel.

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
        ventaja="datum.p_blancas - datum.p_negras",
    ).mark_circle(size=38, opacity=0.85, stroke=BORDE_PUNTO, strokeWidth=0.6).encode(
        x=alt.X("material_visible:Q", title="Material de blancas − negras (puntos)",
                scale=alt.Scale(domain=[-15, 15], clamp=True)),
        y=alt.Y("ventaja:Q", title="Lo que dice el modelo: P(blancas) − P(negras)",
                scale=alt.Scale(domain=[-1, 1]), axis=alt.Axis(format="+.0%")),
        color=alt.Color("resultado:N", title="Cómo terminó", scale=ESCALA_RESULTADO),
        size=alt.condition(elegida, alt.value(160), alt.value(38)),
        tooltip=[
            alt.Tooltip("blancas:N", title="Blancas"), alt.Tooltip("negras:N", title="Negras"),
            alt.Tooltip("TimeClass:N", title="Ritmo"), alt.Tooltip("nivel_promedio:N", title="Nivel"),
            alt.Tooltip("corte_ply:Q", title="Plies jugados"),
            alt.Tooltip("balance_material:Q", title="Material (bl − ng)"),
            alt.Tooltip("p_blancas:Q", title="Modelo: gana blancas", format=".0%"),
            alt.Tooltip("p_empate:Q", title="Modelo: tablas", format=".0%"),
            alt.Tooltip("p_negras:Q", title="Modelo: gana negras", format=".0%"),
            alt.Tooltip("resultado:N", title="Resultado real"), alt.Tooltip("final:N", title="Terminó por"),
        ],
    ).add_params(corte, ritmo, nivel, elegida).properties(height=380, width=ANCHO_EXPLORA)

    detalle_base = base.transform_filter(elegida).transform_fold(
        ["p_blancas", "p_empate", "p_negras"], as_=["clave", "probabilidad"],
    ).transform_calculate(
        prediccion="{'p_blancas': 'Gana Blancas', 'p_empate': 'Empate', 'p_negras': 'Gana Negras'}[datum.clave]",
        orden="{'p_blancas': 0, 'p_empate': 1, 'p_negras': 2}[datum.clave]",
    )
    curva = detalle_base.mark_area(opacity=0.95, interpolate="monotone").encode(
        x=alt.X("corte_ply:Q", axis=EJE_CORTE, scale=alt.Scale(domain=[0, 120])),
        y=alt.Y("probabilidad:Q", stack="normalize", title="Probabilidad según el modelo", axis=alt.Axis(format="%")),
        color=alt.Color("prediccion:N", scale=ESCALA_RESULTADO, legend=None),
        order=alt.Order("orden:Q"),
        tooltip=[alt.Tooltip("corte_ply:Q", title="Plies"), alt.Tooltip("prediccion:N", title="Resultado"),
                 alt.Tooltip("probabilidad:Q", title="Probabilidad", format=".0%")],
    )
    marca_corte = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=COLOR_MODELO, strokeWidth=2).encode(
        x=alt.X("c:Q", scale=alt.Scale(domain=[0, 120])),
    ).transform_calculate(c=corte.name)  # the slider's value, as a data field
    titulo = base.transform_filter(elegida).transform_filter(alt.datum.corte_ply == 0).mark_text(
        align="left", baseline="bottom", fontSize=13, dy=-8, color=FONDO_TEXTO,
    ).encode(x=alt.value(0), y=alt.value(0), text="titulo:N")
    detalle = (curva + marca_corte + titulo).properties(height=180, width=ANCHO_EXPLORA)
    # The 5,000-row guard is for notebooks; the build checks the file size instead.
    with alt.data_transformers.enable("default", max_rows=None):
        spec = alt.vconcat(panorama, detalle, spacing=36).configure(**TEMA).to_dict()
    spec["datasets"]["partidas"] = partidas.to_dict(orient="records")
    return spec
