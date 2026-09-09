# Guía de estudio — Pandas, EDA e Hipótesis

**Basada en los notebooks:**
- `Intro_a_Pandas.ipynb`
- `EDA_del_dataset_canonico.ipynb`
- `Hipotesis_sobre_el_canonico.ipynb`

> **Objetivo de esta guía:** aprender principalmente la **teoría y el razonamiento** detrás de lo que se hace en los notebooks. El código aparece como apoyo práctico, pero la idea es que puedas explicar **qué estás haciendo, por qué lo hacés, qué significa el resultado y qué decisión tomarías**.

---

# 1. El mapa general de todo el tema

Los tres notebooks forman una secuencia bastante clara:

1. **Pandas:** aprender a manipular una tabla de datos.
2. **EDA (Análisis Exploratorio de Datos):** entender qué contiene el dataset, cómo se distribuyen las variables, qué relaciones aparecen y qué problemas de calidad existen.
3. **Hipótesis:** transformar observaciones del EDA en afirmaciones concretas, medirlas con un número y tomar una decisión.

La lógica completa puede resumirse así:

```text
Cargar datos
    ↓
Entender estructura y tipos
    ↓
Explorar cada variable
    ↓
Cruzar variables
    ↓
Detectar problemas de calidad
    ↓
Entender la dimensión temporal
    ↓
Generar preguntas
    ↓
Formular hipótesis
    ↓
Elegir una medida adecuada
    ↓
Calcular un número
    ↓
Usar el gráfico para explicar ese número
    ↓
Tomar una decisión
```

Una de las ideas más importantes de los notebooks es:

> **El número decide; el gráfico explica.**

No se confirma una hipótesis porque “el gráfico parece mostrar algo”. Primero se define qué se espera encontrar, luego se calcula una medida y recién después el gráfico ayuda a entender qué está ocurriendo.

---

# 2. Pandas: fundamentos

## 2.1. ¿Qué es un DataFrame?

Un **DataFrame** es una estructura tabular de pandas.

Se puede pensar como:

- una hoja de Excel,
- una tabla SQL,
- una tabla de R.

Tiene:

- **filas:** observaciones;
- **columnas:** variables o atributos;
- **índice:** etiqueta de cada fila;
- **nombres de columnas:** etiquetas de las variables.

Además, un DataFrame puede contener columnas de tipos distintos:

- números,
- texto,
- booleanos,
- fechas,
- categorías, etc.

Ejemplo conceptual:

| jugador | edad | posición | overall |
|---|---:|---|---:|
| A | 24 | CM | 80 |
| B | 30 | GK | 82 |

Cada fila representa una observación y cada columna una característica.

---

## 2.2. ¿Qué es un CSV?

Un archivo **CSV** (*Comma-Separated Values*) guarda información tabular en texto plano.

Normalmente:

- cada línea representa una fila;
- cada valor representa una columna;
- los campos se separan por coma, aunque también pueden usarse `;` o tabulaciones.

En pandas se carga con:

```python
pd.read_csv("archivo.csv")
```

Parámetros destacados en el notebook:

```python
pd.read_csv(
    "archivo.csv",
    sep=",",
    header=0,
    na_values=["NA"],
    dtype={...},
    usecols=[...]
)
```

### Idea importante

**Cargar correctamente los datos ya es parte del análisis.**

Un CSV mal interpretado puede producir:

- columnas desplazadas,
- tipos incorrectos,
- valores faltantes no detectados,
- decimales mal leídos.

---

# 3. Inspección inicial de un DataFrame

Después de cargar un dataset no conviene empezar directamente con gráficos o modelos.

Primero hay que entender qué llegó.

## `head()`

```python
df.head()
```

Permite revisar las primeras filas.

Sirve para detectar rápidamente:

- encabezados incorrectos,
- formatos extraños,
- columnas inesperadas,
- valores faltantes,
- problemas de codificación.

## `shape`

```python
df.shape
```

Devuelve:

```text
(filas, columnas)
```

En el dataset canónico del notebook de EDA se trabaja con:

- **18.936 jugadores**
- **90 columnas**

## `columns`

```python
df.columns
```

Muestra los nombres de las columnas.

## `dtypes`

```python
df.dtypes
```

Muestra cómo interpretó pandas cada columna.

---

# 4. Índices y columnas

## 4.1. Índice de filas

Todo DataFrame tiene un índice:

```python
df.index
```

Por defecto suele ser:

```text
0, 1, 2, 3, ...
```

El índice sirve para:

- identificar filas,
- seleccionar observaciones,
- alinear datos,
- reorganizar información.

En el notebook se cambia el índice por el nombre completo del jugador:

```python
df_named = df.set_index("long_name")
```

Luego se puede acceder así:

```python
df_named.loc["Ángel Di María"]
```

---

## 4.2. `loc` vs `iloc`

### `.loc`

Selecciona utilizando **etiquetas**.

```python
df.loc["Ángel Di María"]
```

### `.iloc`

Selecciona utilizando **posiciones numéricas**.

```python
df.iloc[:5, :3]
```

Significa:

- primeras 5 filas;
- primeras 3 columnas.

Regla sencilla:

```text
loc  → labels / nombres
iloc → posiciones
```

---

# 5. Series

Una **Series** es una estructura unidimensional de pandas.

Puede pensarse como:

> una columna o una fila con etiquetas.

Ejemplo:

```python
velocidad = df["movement_sprint_speed"]
```

`velocidad` es una `Series`.

Una Series tiene:

- valores;
- índice;
- nombre.

## Una columna devuelve una Series

```python
df["age"]
```

## Una sola fila también puede devolver una Series

```python
df_named.loc["Leandro Paredes"]
```

En ese caso:

- el índice de la Series son los nombres de las columnas;
- los valores son los datos del jugador.

Si queremos conservar formato DataFrame:

```python
df_named.loc[["Leandro Paredes"]]
```

---

# 6. Cómputo vectorizado

Este es uno de los conceptos fundamentales de pandas.

## ¿Qué significa vectorizar?

En lugar de recorrer cada fila manualmente con un `for`, operamos directamente sobre una columna completa.

Ejemplo:

```python
df["attacking_finishing"] + 10
```

Esto suma 10 a todos los valores de la columna.

No hace falta escribir:

```python
for jugador in ...
```

## Ventajas señaladas en el notebook

- código más rápido;
- código más claro;
- menos repetición;
- menor posibilidad de errores;
- análisis expresado en términos de columnas completas.

---

## 6.1. Operaciones aritméticas

```python
df["attacking_finishing"] - df["defending_standing_tackle"]
```

Las operaciones se realizan elemento por elemento.

---

## 6.2. Operaciones booleanas

```python
df["movement_sprint_speed"] > 70
```

El resultado es otra Series:

```text
True
False
True
...
```

A esto se lo puede utilizar como una **máscara booleana**.

---

## 6.3. Strings vectorizados

Para trabajar con texto se utiliza `.str`.

```python
df["club_name"].str.upper()
```

```python
df["player_url"].str.replace(
    "https://sofifa.com/player/",
    ""
)
```

---

# 7. Agregaciones

Una agregación toma muchos valores y devuelve un resumen.

Ejemplos:

```python
df["age"].mean()
df["age"].median()
df["age"].std()
df["age"].min()
df["age"].max()
df["age"].count()
df["best_position"].nunique()
```

Funciones clave:

| Función | Significado |
|---|---|
| `mean()` | media |
| `median()` | mediana |
| `std()` | desviación estándar |
| `min()` | mínimo |
| `max()` | máximo |
| `sum()` | suma |
| `count()` | valores no nulos |
| `nunique()` | valores distintos |

---

# 8. `.apply()`

Cuando una transformación no está disponible directamente de forma vectorizada, puede utilizarse:

```python
serie.apply(funcion)
```

Ejemplo del notebook:

```python
def clasificar_tamano(h):
    if h < 170:
        return "tamaño bajo"
    elif h < 176:
        return "tamaño medio-bajo"
    ...
```

Y después:

```python
df["height_cm"].apply(clasificar_tamano)
```

### Conceptualmente

`.apply()` permite aplicar una función personalizada sobre los elementos de una Series sin escribir explícitamente un `for`.

---

# 9. Filtrado

Filtrar significa quedarse sólo con las filas que cumplen una condición.

## Una condición

```python
df[df["movement_sprint_speed"] > 80]
```

Primero:

```python
df["movement_sprint_speed"] > 80
```

produce una máscara de `True` y `False`.

Después pandas conserva las filas donde el valor es `True`.

---

## Varias condiciones

### AND

```python
(df["attacking_finishing"] > 65) &
(df["movement_sprint_speed"] > 80)
```

### OR

```python
(df["best_position"] == "ST") |
(df["best_position"] == "CB")
```

### NOT

```python
~condicion
```

Es importante utilizar paréntesis alrededor de cada condición.

---

# 10. `isin`

Cuando queremos preguntar si un valor pertenece a una lista:

```python
df["best_position"].isin(["ST", "CB", "GK"])
```

Es preferible a escribir muchos `|`.

Para negar:

```python
~df["best_position"].isin(["GK", "CB"])
```

---

# 11. Valores nulos al filtrar

Un valor faltante se representa normalmente como `NaN`.

Para detectarlo:

```python
df["player_traits"].isna()
```

Para preguntar cuáles **no** son nulos:

```python
df["player_traits"].notna()
```

Esto es importante porque una comparación normal puede excluir nulos sin que uno lo note.

---

# 12. `.query()`

Otra forma de filtrar es:

```python
df.query("movement_sprint_speed > 80")
```

Ejemplo:

```python
df.query(
    "best_position == 'ST' and attacking_finishing > 65"
)
```

Variables externas se referencian con `@`:

```python
df.query("best_position in @posiciones_elegidas")
```

### Ventaja

La expresión puede ser más legible y parecida a una condición SQL.

---

# 13. Selección y ordenamiento

## Una columna

```python
df["age"]
```

## Varias columnas

```python
df[["age", "overall", "best_position"]]
```

## Ordenar filas

```python
df.sort_values(
    by="movement_sprint_speed",
    ascending=False
)
```

También se puede ordenar por varias columnas:

```python
df.sort_values(
    by=["best_position", "attacking_finishing"],
    ascending=[False, True]
)
```

---

# 14. Crear nuevas columnas

## Operaciones numéricas

```python
df["atk_def_ratio"] = (
    df["attacking_finishing"] /
    df["defending_standing_tackle"]
)
```

## Operaciones de texto

```python
df["perfil_completo"] = (
    df["best_position"]
    + "_"
    + df["player_traits"].fillna("none")
)
```

## `.assign()`

Permite crear columnas dentro de un encadenamiento:

```python
df.assign(
    velocidad_al_cuadrado=df["movement_sprint_speed"] ** 2
)
```

En pipelines se suele usar:

```python
.assign(
    velocidad_norm=lambda d:
        d["movement_sprint_speed"] /
        d["movement_sprint_speed"].max()
)
```

---

# 15. `groupby`: Split – Apply – Combine

`groupby()` es uno de los mecanismos fundamentales de análisis.

La lógica es:

1. **Split:** dividir el dataset en grupos.
2. **Apply:** calcular algo en cada grupo.
3. **Combine:** reunir los resultados.

Ejemplo:

```python
df.groupby("best_position")[
    "attacking_finishing"
].mean()
```

Pregunta respondida:

> ¿Cuál es el promedio de definición en cada posición?

---

## 15.1. El objeto `GroupBy`

Esto:

```python
grupo = df.groupby("best_position")
```

todavía no calcula el promedio.

Representa los grupos.

Después se aplica una operación:

```python
grupo.mean()
grupo.count()
grupo.max()
```

---

## 15.2. `.agg()`

Permite calcular varios indicadores al mismo tiempo:

```python
df.groupby("best_position").agg(
    ataque_promedio=("attacking_finishing", "mean"),
    velocidad_max=("movement_sprint_speed", "max"),
    cantidad=("best_position", "count")
)
```

---

## 15.3. ¿Por qué la categoría pasa al índice?

Después de:

```python
df.groupby("best_position")["attacking_finishing"].mean()
```

`best_position` queda como índice.

Para volverlo una columna normal:

```python
.reset_index()
```

---

## 15.4. Agrupar por varias columnas

```python
df.groupby(
    ["best_position", "preferred_foot"]
)["attacking_finishing"].mean()
```

Esto genera un **MultiIndex**.

---

# 16. Visualización básica

Los gráficos no son solamente decoración.

Cada gráfico responde mejor a un tipo de pregunta.

| Gráfico | Principal utilidad |
|---|---|
| Barras | comparar categorías |
| Histograma | estudiar distribución |
| Scatter | relación entre dos numéricas |
| Línea | evolución/tendencia |
| Boxplot | comparar distribuciones y detectar extremos |

---

# 17. Histograma

Un histograma divide una variable numérica en intervalos y cuenta cuántas observaciones caen en cada uno.

```python
df["movement_sprint_speed"].plot(
    kind="hist",
    bins=20
)
```

Sirve para observar:

- forma;
- concentración;
- asimetría;
- posibles poblaciones mezcladas.

---

# 18. Scatter plot

Se utiliza para dos variables numéricas.

```python
df.plot.scatter(
    x="overall",
    y="value_eur"
)
```

Sirve para observar:

- relación positiva o negativa;
- linealidad;
- curvaturas;
- grupos;
- valores extremos.

---

# 19. Boxplot

Resume una distribución mediante:

- Q1;
- mediana;
- Q3;
- extremos sin outliers;
- valores atípicos.

Ejemplo:

```python
df.boxplot(
    column="height_cm",
    by="best_position"
)
```

Es particularmente útil para comparar una variable numérica entre categorías.

---

# 20. Pipelines en pandas

Un pipeline encadena transformaciones.

En vez de:

```python
a = ...
b = ...
c = ...
```

se puede construir:

```python
(
    df
    .query(...)
    .assign(...)
    .groupby(...)
    .agg(...)
    .sort_values(...)
    .reset_index()
)
```

## Ventajas señaladas en el notebook

- mayor legibilidad;
- trazabilidad;
- reproducibilidad;
- menos variables intermedias;
- refleja el análisis como una secuencia.

---

# 21. `.pipe()`

`.pipe()` permite insertar una función personalizada dentro de un pipeline.

```python
df.pipe(funcion)
```

Ejemplo:

```python
def seleccionar_y_ordenar(df):
    return (
        df[
            [
                "best_position",
                "attacking_finishing",
                "defending_standing_tackle"
            ]
        ]
        .sort_values(
            "attacking_finishing",
            ascending=False
        )
    )
```

Luego:

```python
df.pipe(seleccionar_y_ordenar)
```

La idea importante es:

> Si una transformación no queda cómoda como método encadenado, se puede encapsular en una función e insertarla con `.pipe()`.

---

# 22. ¿Qué es un EDA?

EDA significa **Análisis Exploratorio de Datos**.

No es simplemente “hacer gráficos”.

El notebook organiza el EDA en **seis fases**:

1. Inspección inicial.
2. Análisis univariado.
3. Análisis bivariado.
4. Calidad de datos.
5. Análisis temporal.
6. Generación de hipótesis.

El objetivo es pasar de:

> “Tengo un archivo con datos”

a:

> “Entiendo qué representa, qué problemas tiene, cómo se comportan sus variables, qué relaciones podrían existir y qué preguntas vale la pena investigar.”

---

# 23. Fase 1 — Inspección inicial

Antes de calcular estadísticas hay que construir un **mapa mental**.

Preguntas básicas:

- ¿Cuántas filas hay?
- ¿Cuántas columnas?
- ¿Qué representa una fila?
- ¿Qué representa cada familia de columnas?
- ¿Qué tipos de variables existen?
- ¿Es un dataset histórico o una foto en un momento?

En el dataset canónico:

> **Una fila representa un jugador en un momento dado.**

---

# 24. Los tipos de variables

El notebook distingue cuatro grandes familias:

## 24.1. Numéricas

Representan cantidades.

Pueden ser:

### Continuas

Conceptualmente pueden tomar valores dentro de un intervalo.

### Discretas

Toman valores separados o contables.

---

## 24.2. Categóricas

Representan grupos.

### Nominales

No tienen un orden natural.

Ejemplo:

```text
GK, CB, CM, ST
```

### Ordinales

Sí tienen un orden.

Ejemplo del dataset:

```text
international_reputation
```

Toma cinco valores ordenados.

---

## 24.3. Temporales

Representan fechas o instantes.

Ejemplo:

```text
club_joined_date
```

---

## 24.4. Texto libre

Tienen muchísimos valores distintos y no se comportan como categorías tradicionales.

Ejemplo:

```text
player_traits
```

---

# 25. Cardinalidad como pista del tipo de variable

Una forma útil de inspeccionar variables:

```python
df[columnas].nunique()
```

La cantidad de valores distintos ayuda a detectar su naturaleza.

Según el notebook:

- `international_reputation`: pocos valores ordenados → ordinal;
- `best_position`: 15 valores sin orden → nominal;
- `player_traits`: más de 2.000 valores → texto libre.

---

# 26. Snapshot vs serie temporal

Esta distinción es fundamental.

En el dataset del notebook hay columnas con un único valor para las 18.936 filas.

Eso indica que el dataset es un:

> **snapshot**

Es decir:

> una fotografía del estado del sistema en una fecha.

No es una película de cómo fue cambiando cada jugador.

### Consecuencia

No podemos afirmar cómo evolucionó un jugador en el tiempo porque sólo tenemos una observación actual de cada uno.

Esto limita qué análisis temporales son válidos.

---

# 27. Fase 2 — Análisis univariado

“Univariado” significa:

> analizar **una variable por vez**.

Se estudian:

- tendencia central;
- dispersión;
- forma;
- valores extremos;
- frecuencias en categorías.

---

# 28. Medidas de resumen

`describe()` proporciona varias estadísticas:

```python
df[numericas].describe()
```

Incluye:

- count;
- mean;
- std;
- min;
- 25 %;
- 50 %;
- 75 %;
- max.

## Media

Promedio.

## Mediana

Valor central cuando los datos se ordenan.

En `describe()` corresponde al percentil 50.

## Desviación estándar

Resume cuánto se dispersan los valores alrededor de la media.

## Cuartiles

Dividen los datos ordenados.

- Q1 = 25 %
- Q2 = 50 % = mediana
- Q3 = 75 %

---

# 29. Asimetría

La **asimetría** (`skew`) indica hacia qué lado se extiende una distribución.

```python
df[numericas].agg(["skew"])
```

Interpretación utilizada en el notebook:

- cerca de `0`: distribución aproximadamente simétrica;
- positiva: cola larga hacia valores altos;
- negativa: cola larga hacia valores bajos.

Ejemplo destacado:

```text
value_eur → asimetría 8,54
```

Eso indica una cola derecha muy larga:

> unos pocos jugadores valen muchísimo más que la mayoría.

---

# 30. Curtosis

La **curtosis** estudia cuánto pesan las colas en comparación con una distribución normal.

Pandas la presenta centrada en `0`.

Interpretación del notebook:

- cerca de `0`: colas similares a una normal;
- alta: aparecen muchos más valores extremos que los esperables bajo una normal.

Ejemplo:

```text
value_eur → curtosis 107
```

Es una distribución extremadamente pesada en la cola.

---

# 31. Una media puede ocultar poblaciones distintas

El ejemplo más claro es:

```text
goalkeeping_reflexes
```

Su histograma muestra dos poblaciones:

- arqueros;
- jugadores de campo.

En ese caso:

> la media global cae entre ambas poblaciones y no describe bien a ninguna.

Esto enseña una regla muy importante:

> **Antes de interpretar una media, mirar la forma de la distribución.**

---

# 32. Outliers: no siempre son errores

Un boxplot puede marcar observaciones como atípicas.

Pero:

> **atípico no significa incorrecto.**

En `value_eur`, los valores extremos son jugadores estrella.

Son observaciones legítimas.

Por lo tanto, no se deben eliminar outliers automáticamente.

Primero hay que preguntarse:

> ¿es un error de datos o un caso raro pero real?

---

# 33. Transformación logarítmica

`value_eur` tiene una distribución extremadamente sesgada.

En escala lineal:

- la mayoría queda aplastada abajo;
- unos pocos valores dominan el gráfico.

Una escala logarítmica permite ver mejor el cuerpo de la distribución.

```python
plt.yscale("log")
```

Más adelante el notebook muestra otra razón todavía más importante:

> El logaritmo puede transformar una relación multiplicativa y curva en una relación mucho más cercana a una recta.

---

# 34. Variables categóricas

Para variables categóricas no tiene sentido calcular media o desviación estándar.

Se estudian mediante:

## Frecuencia absoluta

```python
df["best_position"].value_counts()
```

## Frecuencia relativa

```python
df["best_position"].value_counts(
    normalize=True
)
```

## Moda

La categoría más frecuente.

También es importante revisar las categorías menos frecuentes porque:

> un promedio calculado sobre un grupo con muy pocos casos es mucho menos sólido.

---

# 35. Fase 3 — Análisis bivariado

“Bivariado” significa analizar **dos variables juntas**.

Los dos cruces centrales del notebook son:

1. numérica vs categórica;
2. numérica vs numérica.

---

# 36. Numérica vs categórica

Ejemplo:

```text
height_cm vs best_position
```

Se puede analizar mediante:

```python
df.groupby(
    "best_position"
)["height_cm"].median()
```

Y con un boxplot.

La mediana resume el centro de cada grupo y el boxplot permite ver:

- dispersión;
- solapamiento;
- valores extremos.

---

# 37. Numérica vs numérica

Ejemplo:

```text
overall vs value_eur
```

Primero puede mirarse con scatter.

Pero para cuantificar la relación se utiliza correlación.

---

# 38. Pearson

El coeficiente de **Pearson** mide qué tan bien la relación entre dos variables se parece a una **recta**.

Su signo muestra dirección:

- positivo → suben juntas;
- negativo → una sube mientras la otra baja.

Su magnitud indica intensidad.

El notebook utiliza el valor absoluto para decidir la zona del semáforo.

---

# 39. Spearman

**Spearman** trabaja con el orden o ranking de los valores.

No exige que la relación sea una recta.

Pregunta aproximadamente:

> cuando una variable aumenta, ¿la otra tiende a aumentar también de forma ordenada?

Por eso puede detectar relaciones:

- fuertes;
- monótonas;
- pero curvas.

---

# 40. Pearson vs Spearman

Ejemplo central del notebook:

```text
overall vs value_eur

Pearson  ≈ 0,55
Spearman ≈ 0,88
```

Conclusión:

> existe una relación fuerte y ordenada, pero no es lineal.

El scatter muestra que el valor aumenta cada vez más rápido para los jugadores de mayor overall.

---

# 41. La brecha Pearson–Spearman

En el notebook se calcula:

```python
brecha = spearman - pearson
```

Una brecha grande actúa como señal de:

> **curvatura**

Si Spearman es muy superior a Pearson:

- el orden se conserva;
- la relación existe;
- pero una recta la representa mal.

Importante:

> Los cortes de la brecha usados en el notebook son una regla adoptada para la materia, no una convención estadística universal.

---

# 42. Correlación no significa “todo”

Uno de los aprendizajes más importantes del material es que una correlación global puede esconder relaciones.

En H2:

```text
edad vs valor
```

da aproximadamente:

```text
Pearson = 0,029
```

Mirado superficialmente:

> “la edad no tiene relación con el valor”.

Pero eso es incorrecto porque `overall` afecta a ambas variables.

Cuando se controla el nivel:

```text
corr(edad, log(valor)) ≈ -0,50 a -0,82
```

según la franja.

La relación estaba **oculta por una tercera variable**.

---

# 43. Correlación vs causalidad

Los notebooks no desarrollan una teoría completa de causalidad, pero sí enseñan algo esencial:

> una relación entre dos columnas puede cambiar cuando se controla una tercera.

Por eso no alcanza con calcular una correlación y sacar una conclusión automática.

Hay que preguntarse:

- ¿hay otra variable que influye en ambas?
- ¿estoy mezclando poblaciones?
- ¿la relación es curva?

---

# 44. Matriz de correlación

```python
df[columnas].corr()
```

Permite calcular todas las correlaciones entre variables numéricas.

Ejemplo destacado:

```text
passing vs dribbling ≈ 0,86
```

Esto sugiere posible **redundancia**.

También:

```text
defending vs shooting ≈ -0,38
```

No necesariamente indica error.

Puede reflejar perfiles opuestos de jugadores.

---

# 45. η² — razón de correlación

Cuando tenemos:

```text
variable numérica
        vs
variable categórica
```

Pearson no corresponde.

El notebook utiliza **η² (eta cuadrado / razón de correlación)**.

Pregunta:

> ¿Qué proporción de la variación de la variable numérica se explica por saber a qué categoría pertenece cada fila?

Su rango es:

```text
0 ≤ η² ≤ 1
```

Interpretación:

```text
η² = 0
```

Saber el grupo no explica nada.

```text
η² = 1
```

El grupo explica completamente la variación.

---

## Fórmula implementada en el notebook

Conceptualmente:

```text
η² = variación entre grupos / variación total
```

En el código:

```python
def eta2(numerica, categoria):
    g = numerica.groupby(categoria)
    m = numerica.mean()

    entre = (
        g.count()
        * (g.mean() - m) ** 2
    ).sum()

    total = (
        (numerica - m) ** 2
    ).sum()

    return entre / total
```

---

# 46. Cómo interpretar η² en este material

Cortes utilizados:

| η² | Zona |
|---:|---|
| `< 0,05` | rojo |
| `0,05 – 0,25` | amarillo |
| `> 0,25` | verde |

Interpretación dada en el notebook:

- menos de 5 % de varianza explicada → casi nada;
- más de 25 % → efecto importante para este tipo de datos.

---

# 47. Fase 4 — Calidad de datos

Que un pipeline termine correctamente:

> **no significa que los datos sean correctos.**

El notebook revisa:

- nulos;
- duplicados;
- inconsistencias;
- formatos mezclados;
- ceros con significados diferentes.

---

# 48. Valores faltantes: no alcanza con contar

Primero:

```python
df.isna().sum()
```

Pero la pregunta importante es:

> **¿por qué falta ese valor?**

Ejemplo:

```text
club_loan_end_date
```

Es nulo para jugadores que no están cedidos.

Eso no significa “dato perdido”.

Significa:

> “no corresponde”.

Otro ejemplo:

```text
player_traits
```

Los nulos coinciden con jugadores con cero `playstyles`.

El nulo representa:

> “no tiene rasgos especiales”.

### Consecuencia

Imputar automáticamente esos valores sería inventar información.

---

# 49. Duplicados: primero definir qué significa “igual”

Se puede buscar duplicados con:

```python
df.duplicated()
```

o utilizando una clave:

```python
df.duplicated(
    subset=["player_id"]
)
```

El notebook muestra que la cantidad cambia según la clave.

Por ejemplo:

```text
short_name + club_name
```

puede considerar duplicadas a personas distintas que comparten nombre abreviado y club.

Regla:

> **Antes de deduplicar hay que definir la clave correcta.**

No se deduplica “porque pandas dice duplicate”.

---

# 50. Identificadores vs nombres

Uno de los problemas más peligrosos del dataset:

```text
league_name
```

no identifica unívocamente una liga.

Hay:

- 52 `league_id`
- 43 `league_name`

Por ejemplo, `"Super League"` agrupa varias ligas diferentes.

Si se agrupa por nombre:

```python
df.groupby("league_name")
```

se pueden mezclar entidades diferentes y obtener un promedio completamente plausible pero incorrecto.

Regla del notebook:

> **Se agrupa por identificadores, no por nombres.**

---

# 51. Formatos mezclados

Una columna puede contener más de una pieza de información.

Ejemplo:

```text
body_type
```

incluye contextura y un rango de altura.

El notebook contrasta ese rango con:

```text
height_cm
```

y encuentra inconsistencias.

Lección:

> Si una información aparece repetida en varias columnas, no asumir que coincide: verificarla.

---

# 52. Cero no siempre significa cero

Un `0` puede significar:

1. cero real;
2. valor faltante codificado como cero;
3. “no corresponde”.

Ejemplo:

```text
value_eur = 0
```

para once jugadores mayores.

El notebook interpreta que el juego no les asigna valor de transferencia.

No equivale a:

> “su valor económico real es cero”.

En cambio:

```text
release_clause_eur = 0
```

en muchos casos está relacionado con contratos que finalizan en el año del snapshot.

Dos columnas pueden usar el mismo `0` con significados diferentes.

Regla:

> **Nunca interpretar un valor especial sin investigar su causa.**

---

# 53. Fase 5 — Análisis temporal

Primera pregunta:

> ¿tenemos realmente una serie temporal?

El dataset FIFA es un snapshot.

Por eso no podemos estudiar:

```text
cómo cambió el overall de un jugador con los años
```

porque no hay varias observaciones temporales del mismo jugador.

---

# 54. Fechas que sí existen

Sí existen atributos temporales del jugador:

```text
club_joined_date
club_contract_valid_until_year
```

Se pueden convertir fechas con:

```python
pd.to_datetime(...)
```

Después se extraen componentes:

```python
fecha.dt.year
fecha.dt.month
```

---

# 55. Tendencia

Una tendencia es un patrón general a través del tiempo.

El notebook cuenta incorporaciones por año:

```python
incorporacion.dt.year.value_counts()
```

Aparecen más incorporaciones recientes.

Pero el notebook advierte:

> eso no demuestra que actualmente haya más pases.

¿Por qué?

Porque el dataset sólo guarda el **club actual**.

Los pases antiguos aparecen únicamente si el jugador todavía sigue en ese club.

### Idea clave

> Una tendencia puede ser consecuencia de cómo se construyó el dataset y no del fenómeno real.

---

# 56. Estacionalidad

La estacionalidad es un patrón que se repite dentro de un período fijo.

El notebook agrupa incorporaciones por mes:

```python
incorporacion.dt.month.value_counts()
```

Encuentra grandes concentraciones en:

- enero;
- julio.

Esto coincide con ventanas de transferencias.

La idea general es:

> Buscar ciclos repetitivos dentro del año.

---

# 57. Inconsistencias temporales

También pueden aparecer fechas aparentemente imposibles.

En el snapshot de 2026 aparecen algunos contratos con fecha de finalización en 2025.

No es necesariamente un error del pipeline:

> puede ser un problema del dato de origen.

Antes de derivar variables como:

```text
años de contrato restantes
```

hay que decidir cómo tratar esos casos.

---

# 58. Fase 6 — El EDA debe terminar en preguntas

El EDA no termina con:

> “estos son los gráficos”.

Termina con:

> **preguntas que ahora podemos formular mejor.**

El notebook llega, entre otras, a preguntas como:

- ¿qué variables distinguen mejor las posiciones?
- ¿`passing` y `dribbling` son redundantes?
- ¿qué explica `value_eur`?
- ¿conviene analizar arqueros aparte?
- ¿la tendencia temporal observada viene del fútbol o del dataset?

Pero todavía no son hipótesis.

---

# 59. Pregunta vs hipótesis

Una pregunta:

> ¿los jóvenes valen más?

Una hipótesis:

> **A igual nivel, un jugador más joven tiene mayor valor de mercado.**

La hipótesis debe poder resultar falsa.

Además tiene que incluir:

- qué esperamos observar;
- cómo lo vamos a medir;
- qué decisión tomaremos según el resultado.

---

# 60. Dos tipos de preguntas

El notebook separa dos objetivos.

## 60.1. “Qué queremos responder”

Es una pregunta de negocio.

Ejemplo:

> ¿qué determina el valor de un jugador?

Termina en:

> una conclusión.

---

## 60.2. “Qué queremos predecir”

Es una pregunta de modelado.

Ejemplo:

> queremos predecir la posición.

Termina en:

> una decisión sobre features.

Una misma columna puede tener distinto rol según la pregunta.

Ejemplo:

```text
value_eur
```

Puede ser:

- objetivo de un análisis de negocio;
- una feature candidata en otro problema.

---

# 61. Regla del orden

Una hipótesis y el resultado esperado se escriben:

> **antes de calcular la medida.**

No vale mirar un gráfico y después escribir:

> “mi hipótesis era justamente eso”.

Eso no pone a prueba una idea.

Sólo describe algo que ya vimos.

---

# 62. Las tres plantillas de hipótesis

Los notebooks reducen la mayoría de las preguntas a tres formas.

| Plantilla | Forma | Medida |
|---|---|---|
| Comparación | X difiere entre A y B | separación estandarizada |
| Comparación múltiple | X difiere entre varios grupos | η² |
| Asociación | X se mueve junto con Y | Pearson + Spearman |
| Composición | C está sobrerrepresentada en G | proporciones |

---

# 63. Separación estandarizada

Si comparamos dos grupos no alcanza con restar promedios.

Ejemplo:

```text
8 cm
```

puede ser mucho o poco dependiendo de cuánto varíen las alturas.

La separación divide la diferencia de medias por una medida de dispersión.

Implementación:

```python
def separacion(x, y):
    return (
        abs(x.mean() - y.mean())
        /
        np.sqrt(
            (x.std()**2 + y.std()**2) / 2
        )
    )
```

El resultado queda expresado en:

> **desviaciones estándar**

Eso permite comparar efectos medidos en escalas diferentes.

---

# 64. Semáforo de separación

Cortes usados:

| Separación | Zona |
|---:|---|
| `< 0,2` | rojo |
| `0,2 – 0,8` | amarillo |
| `> 0,8` | verde |

Según el material:

- 0,2 → las distribuciones todavía se superponen aproximadamente 92 %;
- 0,8 → superposición aproximada de 69 %.

---

# 65. Semáforo de correlación

Cortes:

| \|correlación\| | Zona |
|---:|---|
| `< 0,2` | rojo |
| `0,2 – 0,6` | amarillo |
| `> 0,6` | verde |

Se utiliza el **valor absoluto** para medir intensidad.

El signo se interpreta aparte.

Ejemplo:

```text
-0,818
```

es:

- verde;
- fuerte;
- negativa.

---

# 66. Semáforo de brecha Pearson–Spearman

Cortes del notebook:

| \|brecha\| | Zona |
|---:|---|
| `< 0,05` | rojo |
| `0,05 – 0,15` | amarillo |
| `> 0,15` | verde |

Importante:

> **Estos cortes son una regla adoptada en la materia. No son una convención estadística universal.**

---

# 67. ¿Por qué usar tamaños de efecto y no sólo significancia?

El notebook tiene 18.936 observaciones.

Con una muestra tan grande:

> casi cualquier diferencia pequeña puede resultar estadísticamente significativa.

Pero:

> **estadísticamente real ≠ importante para una decisión.**

El semáforo intenta responder:

> ¿el efecto tiene una magnitud suficientemente grande como para importarnos?

Ese es el foco del material.

---

# 68. Cómo leer el semáforo

## Verde

El efecto es suficientemente claro.

```text
→ terminar la hipótesis
```

## Rojo

El efecto es demasiado pequeño.

```text
→ terminar la hipótesis
```

## Amarillo

El resultado no alcanza para decidir.

```text
→ se permite realizar un movimiento
```

---

# 69. Los tres movimientos

Cuando el resultado es amarillo se puede modificar el análisis.

El notebook define tres posibilidades.

## Movimiento 1 — Partir la población

Se utiliza cuando:

> distintos subgrupos parecen comportarse de manera diferente.

Ejemplo:

```text
arqueros vs jugadores de campo
```

---

## Movimiento 2 — Controlar una tercera variable

Se utiliza cuando otra variable puede estar afectando a las dos variables estudiadas.

Ejemplo de H2:

```text
edad
overall
valor
```

`overall` estaba ocultando la relación entre edad y valor.

---

## Movimiento 3 — Cambiar la escala

Se utiliza cuando la relación:

- es ordenada;
- pero es curva.

Ejemplo:

```text
overall vs value_eur
```

Transformación:

```python
np.log(value_eur)
```

---

# 70. Regla de máximo dos movimientos

Este punto es muy importante.

El notebook establece:

> **máximo dos movimientos por hipótesis.**

Si después de dos movimientos sigue amarillo:

```text
→ hipótesis inconclusa
```

¿Por qué?

Porque si seguimos recortando, transformando y probando cosas hasta conseguir un resultado favorable:

> estamos cazando resultados.

Con suficientes recortes casi siempre aparece algún subgrupo que parece confirmar nuestra idea.

---

# 71. La ficha de una hipótesis

Cada hipótesis debería tener seis partes:

1. **Afirmación**
2. **Qué espero ver**
3. **Medida y gráfico**
4. **Resultado y zona**
5. **Movimiento**, si fue amarillo
6. **Qué hago con eso**

Este formato obliga a conectar:

```text
pregunta → evidencia → decisión
```

---

# 72. Las seis hipótesis del notebook

---

## H1 — Unos pocos jugadores valen muchísimo más que el resto

### Afirmación

El valor no aumenta de manera uniforme con el overall.

Los puntos finales de overall aumentan el valor mucho más que los primeros.

### Medida

Asociación:

- Pearson;
- Spearman;
- brecha.

### Resultado inicial

```text
Pearson ≈ 0,550
brecha ≈ 0,333
```

Interpretación:

- la relación existe;
- es ordenada;
- pero es curva.

### Movimiento

Cambiar escala:

```python
np.log(value_eur)
```

### Resultado

```text
Pearson ≈ 0,896
```

La relación se vuelve aproximadamente lineal.

### Conclusión

Hipótesis confirmada.

La relación es esencialmente multiplicativa.

### Decisión práctica

Si se quisiera predecir valor:

> convendría modelar `log(value_eur)` en lugar de `value_eur` crudo.

---

# 73. H2 — A igual nivel, el joven vale más

### Afirmación

Entre jugadores del mismo nivel:

> el más joven debería valer más.

### Resultado inicial

```text
corr(age, value_eur) ≈ 0,029
```

Rojo.

A primera vista parecería no existir relación.

### ¿Qué mostraron los gráficos?

El valor:

- sube con la edad al principio;
- luego baja.

Y el overall también aumenta con la edad hasta cierto punto.

### Problema

`overall` afecta el análisis.

### Movimiento

Controlar el nivel.

Se crean franjas de overall.

### Resultado

Dentro de las franjas:

```text
corr(age, log(value)) ≈ -0,50 a -0,82
```

Todas fuertes y negativas.

### Conclusión

Hipótesis confirmada.

### Aprendizaje

> Una correlación global cercana a cero no significa necesariamente ausencia de relación.

Puede haber una tercera variable ocultando el efecto.

---

# 74. H3 — Los zurdos valen más

### Afirmación

Los zurdos tienen mayor valor de mercado.

### Medida

Separación estandarizada sobre:

```text
log(value_eur)
```

### Resultado

```text
separación ≈ 0,147
```

Rojo.

### Conclusión correcta

Hipótesis refutada.

El notebook después muestra deliberadamente qué pasaría si siguiéramos buscando recortes.

Controlar overall:

```text
separación ≈ 0,056
```

Recortar sólo extremos:

```text
separación ≈ 0,156
```

Sigue rojo.

### Aprendizaje principal

> No hay que seguir manipulando el análisis hasta que la hipótesis dé el resultado que queremos.

---

# 75. H4 — Passing y dribbling miden casi lo mismo

### Afirmación

`passing` y `dribbling` aportan información redundante para predecir posición.

### Primera medida

Correlación entre ambas:

```text
Pearson ≈ 0,864
```

Se mueven muy juntas.

Pero eso no demuestra todavía que sean redundantes para **el objetivo**.

### Segunda medida

η² contra posición:

```text
passing    ≈ 0,286
dribbling  ≈ 0,316
promedio   ≈ 0,303
```

Combinar ambas no supera a la mejor.

### Conclusión

Hipótesis confirmada.

### Decisión

```text
entra dribbling
sale passing
```

### Aprendizaje

Dos features pueden estar fuertemente correlacionadas, pero para hablar de redundancia interesa además comprobar:

> si combinarlas agrega información para el problema que queremos resolver.

---

# 76. H5 — `player_positions` es demasiado buena

### Afirmación

`player_positions` debería ser extremadamente informativa para predecir `best_position`.

### Medida

Composición:

- ¿contiene `best_position`?
- ¿es la primera posición?

### Resultado

```text
contiene el objetivo ≈ 85,7 %
es la primera       ≈ 74,9 %
```

### Problema

Esto no es una excelente feature.

Es:

> **fuga de información**

La columna prácticamente contiene la respuesta que queremos predecir.

### Otra columna revisada

`club_position` coincide con `best_position` en aproximadamente 37 % de las filas tácticas.

También filtra información del objetivo.

### Decisión

Ambas deben salir de las features.

---

# 77. Fuga de información

Una de las ideas más importantes de todo el material.

Hay fuga cuando una feature contiene información que:

- revela directamente el objetivo;
- o no estaría disponible realmente en el momento de hacer la predicción.

El modelo puede obtener un desempeño espectacular.

Pero:

> no aprendió el fenómeno que queríamos modelar.

Pregunta fundamental antes de usar una columna:

> **¿Esta información existiría en el momento en que tengo que predecir?**

Y también:

> **¿Esta columna contiene la respuesta escrita de otra forma?**

Si sí:

```text
→ debe salir
```

---

# 78. H6 — La edad sirve para predecir posición

### Afirmación

La edad ayuda a diferenciar posiciones.

### Medida

η²:

```text
η² ≈ 0,054
```

Amarillo.

### Movimiento 1

Controlar overall:

```text
η² ≈ 0,077
```

Sigue amarillo.

### Movimiento 2

Excluir arqueros:

```text
η² ≈ 0,066
```

Incluso baja.

### Resultado

Después de dos movimientos sigue amarillo.

### Decisión

```text
INCONCLUSA
```

La edad queda como feature candidata débil.

La decisión final deberá realizarse posteriormente comparando modelos:

- con edad;
- sin edad.

### Aprendizaje

> “Inconclusa” es una respuesta válida.

Es mejor que forzar una conclusión que los datos no permiten sostener.

---

# 79. La relación entre variación dentro y entre grupos

H6 permite entender intuitivamente η².

Si las posiciones tienen medianas diferentes pero cada posición tiene una enorme dispersión interna:

```text
variación dentro de grupos
>
variación entre grupos
```

entonces η² será bajo.

Por eso:

> mirar únicamente las medianas de los boxplots puede hacer parecer que existe un efecto mucho mayor del que realmente existe.

---

# 80. El rol correcto de los gráficos

Los notebooks insisten en esta separación:

## El número

Sirve para:

- medir;
- comparar con un criterio;
- decidir zona;
- sostener una conclusión.

## El gráfico

Sirve para:

- entender la forma;
- detectar curvaturas;
- descubrir poblaciones distintas;
- detectar una tercera variable sospechosa;
- decidir qué movimiento tiene sentido.

La frase para recordar:

> **El número decide; el gráfico explica.**

---

# 81. Flujo mental para resolver una hipótesis

Cuando te den un problema, pensalo así:

```text
1. ¿Qué quiero responder?
2. ¿Qué afirmación concreta hago?
3. ¿Qué espero observar si es cierta?
4. ¿Qué tipo de variables tengo?
5. ¿Comparación, asociación o composición?
6. ¿Qué medida corresponde?
7. Calculo la medida.
8. ¿Rojo, amarillo o verde?
9. Miro el gráfico para explicar el resultado.
10. Si es amarillo, elijo UN movimiento justificado.
11. Vuelvo a medir.
12. Máximo dos movimientos.
13. Escribo qué decisión tomo.
```

---

# 82. Cómo elegir una medida rápidamente

## Dos grupos + una numérica

Ejemplo:

```text
valor de zurdos vs diestros
```

Usar:

```text
separación estandarizada
```

---

## Varios grupos + una numérica

Ejemplo:

```text
edad según posición
```

Usar:

```text
η²
```

---

## Dos variables numéricas

Ejemplo:

```text
overall vs valor
```

Usar:

```text
Pearson + Spearman
```

---

## Categorías/proporciones

Ejemplo:

```text
¿best_position aparece dentro de player_positions?
```

Usar:

```text
proporciones
```

---

# 83. Resumen de cortes del semáforo

| Medida | Rojo | Amarillo | Verde |
|---|---:|---:|---:|
| Separación | `< 0,2` | `0,2 – 0,8` | `> 0,8` |
| η² | `< 0,05` | `0,05 – 0,25` | `> 0,25` |
| \|Correlación\| | `< 0,2` | `0,2 – 0,6` | `> 0,6` |
| \|Brecha Spearman−Pearson\| | `< 0,05` | `0,05 – 0,15` | `> 0,15` |

**Recordar:** los cortes de la brecha son propios del criterio utilizado en esta materia.

---

# 84. Resumen de los tres movimientos

| Problema observado | Movimiento |
|---|---|
| Subgrupos se comportan distinto | Partir población |
| Una tercera variable contamina la relación | Controlarla |
| Relación ordenada pero curva | Cambiar escala |

Nunca:

```text
probar los tres y quedarse con el que dé mejor
```

El movimiento debe surgir de una razón observable.

---

# 85. Código práctico mínimo que deberías reconocer

## Cargar

```python
df = pd.read_csv("archivo.csv")
```

## Inspeccionar

```python
df.head()
df.shape
df.columns
df.dtypes
df.describe()
```

## Nulos

```python
df.isna().sum()
df["col"].isna()
df["col"].notna()
```

## Valores únicos

```python
df["col"].nunique()
df["col"].value_counts()
```

## Filtrar

```python
df[df["age"] > 25]
```

```python
df.query("age > 25")
```

## Varias condiciones

```python
df[
    (df["age"] > 25)
    & (df["overall"] > 70)
]
```

## Pertenencia

```python
df[df["position"].isin(["GK", "CB"])]
```

## Agrupar

```python
df.groupby("position")["age"].mean()
```

## Varias agregaciones

```python
df.groupby("position").agg(
    edad_media=("age", "mean"),
    cantidad=("position", "count")
)
```

## Correlación

```python
df["x"].corr(df["y"])
```

```python
df["x"].corr(
    df["y"],
    method="spearman"
)
```

## Conversión de fecha

```python
fecha = pd.to_datetime(df["fecha"])
fecha.dt.year
fecha.dt.month
```

---

# 86. Errores conceptuales que deberías evitar

## Error 1

> “Hay outliers, entonces los borro.”

No.

Primero determinar si son errores o casos reales.

---

## Error 2

> “Tiene muchos nulos, entonces elimino la columna.”

No.

Primero entender qué significan esos nulos.

---

## Error 3

> “Pearson dio casi cero, entonces no hay relación.”

No necesariamente.

Puede haber:

- curvatura;
- tercera variable;
- subgrupos.

---

## Error 4

> “El gráfico parece distinto, entonces la hipótesis está confirmada.”

No.

El gráfico explica.

La medida decide.

---

## Error 5

> “El modelo da 99 %, entonces la feature es buenísima.”

Puede existir fuga de información.

---

## Error 6

> “Voy a seguir recortando grupos hasta encontrar algo.”

Eso es cazar resultados.

El notebook limita a dos movimientos.

---

## Error 7

> “Si dos filas tienen el mismo nombre, son duplicados.”

No.

Hay que definir una clave válida.

---

## Error 8

> “Agrupar por nombre es lo mismo que agrupar por ID.”

No.

Un mismo nombre puede representar entidades distintas.

---

## Error 9

> “Un cero siempre representa cero.”

No.

Puede ser:

- cero real;
- faltante;
- “no corresponde”.

---

# 87. Qué deberías poder explicar oralmente

Sin mirar código, deberías poder contestar:

### ¿Qué es un DataFrame?

Una tabla etiquetada de filas y columnas que permite trabajar con datos heterogéneos.

### ¿Qué es una Series?

Una estructura unidimensional con valores e índice; normalmente una columna o una fila de un DataFrame.

### ¿Qué significa vectorización?

Aplicar operaciones a columnas completas sin recorrer cada elemento manualmente.

### ¿Qué hace `groupby`?

Divide los datos en grupos, aplica una operación a cada grupo y combina los resultados.

### ¿Qué es EDA?

El proceso de comprender estructura, distribuciones, relaciones, calidad y dimensión temporal de un dataset antes de formular conclusiones o modelar.

### ¿Qué diferencia hay entre análisis univariado y bivariado?

- univariado → una variable;
- bivariado → relación entre dos.

### ¿Qué mide Pearson?

Qué tan lineal es la asociación entre dos variables numéricas.

### ¿Qué mide Spearman?

Qué tan ordenada o monótona es la asociación, aunque no sea lineal.

### ¿Qué indica una gran diferencia entre Spearman y Pearson?

Que puede existir una relación fuerte pero curva.

### ¿Qué mide η²?

Qué proporción de la variación de una numérica se explica por pertenecer a distintos grupos categóricos.

### ¿Por qué no alcanza con significancia estadística?

Porque con muchísimas observaciones diferencias diminutas pueden ser reales estadísticamente pero irrelevantes para tomar decisiones.

### ¿Qué es fuga de información?

Usar una feature que contiene la respuesta o información que no estaría disponible cuando haya que predecir.

### ¿Qué significa una hipótesis inconclusa?

Que con las medidas y los dos movimientos permitidos no existe evidencia suficientemente clara para confirmarla ni refutarla.

---

# 88. Resumen ultra corto para memorizar

```text
PANDAS
DataFrame = tabla
Series = columna/fila etiquetada
Vectorización = operar columnas completas
Filtrado = máscara booleana
groupby = split → apply → combine
pipeline = transformaciones encadenadas
```

```text
EDA
1. Inspección
2. Univariado
3. Bivariado
4. Calidad
5. Temporal
6. Hipótesis
```

```text
UNIVARIADO
Centro → media / mediana
Dispersión → std / cuartiles
Forma → skew / kurtosis
Categorías → value_counts
```

```text
BIVARIADO
Numérica + numérica → Pearson / Spearman
Numérica + categórica → η²
Dos grupos → separación
```

```text
HIPÓTESIS
Afirmación antes del resultado
Medida → número
Número → decide
Gráfico → explica
```

```text
SEMAFORO
Rojo → terminar
Verde → terminar
Amarillo → movimiento
Máximo 2 movimientos
Después → inconclusa
```

```text
MOVIMIENTOS
Partir población
Controlar tercera variable
Cambiar escala
```

```text
CALIDAD
Nulo ≠ siempre error
0 ≠ siempre cero
Outlier ≠ siempre error
Nombre ≠ identificador
Duplicado depende de la clave
```

```text
MODELADO
No alcanza con una feature predictiva:
preguntar si existiría al momento de predecir.
Si contiene la respuesta → fuga.
```

---

# 89. Las seis hipótesis en una sola tabla

| H | Hipótesis | Medida principal | Resultado | Decisión |
|---|---|---|---|---|
| H1 | Unos pocos jugadores valen muchísimo más | Pearson/Spearman + log | `0,55 → 0,896` con log | Confirmada; usar log(valor) |
| H2 | A igual nivel, el joven vale más | Correlación controlando overall | `−0,50` a `−0,82` | Confirmada |
| H3 | Los zurdos valen más | Separación | `0,147` | Refutada |
| H4 | Passing y dribbling son redundantes | Pearson + η² | `0,864`; combinar no mejora | Sale passing |
| H5 | player_positions es la mejor feature | Composición | contiene objetivo `85,7 %` | Es fuga; sale |
| H6 | La edad predice posición | η² | `0,054 → 0,077 → 0,066` | Inconclusa |

---

# 90. Idea final de toda la unidad

Lo más importante de estos notebooks no es memorizar métodos de pandas.

Es aprender este criterio:

> **Primero entiendo el dato. Después formulo una pregunta. La convierto en una afirmación que puede ser falsa. Elijo de antemano una medida que corresponda al tipo de pregunta. Calculo el número. Uso el gráfico para interpretar por qué dio eso. Y recién entonces tomo una decisión.**

Ese es el puente entre:

```text
“sé usar pandas”
```

y:

```text
“sé analizar datos”.
```
