---
titulo: "Análisis Exploratorio de Datos (EDA)"
materia: "Ciencia de Datos · UTN FRM · Clase 3"
fuente: "Resumen_EDA_Ciencia_de_Datos.docx"
convertido: "docx → md con pandoc, formato preservado"
---

**Análisis Exploratorio de Datos (EDA)**

Ciencia de Datos — Clase 3 · Resumen de estudio

# **1. Resumen ejecutivo**

El Análisis Exploratorio de Datos (EDA) es la fase en la que se observa y se entiende un dataset antes de aplicar cualquier modelo. En lugar de partir de un modelo predefinido, se explora para descubrir patrones, anomalías y relaciones que orienten el análisis posterior. El material se organiza en tres bloques: los objetivos del EDA, las fases del proceso y las herramientas conceptuales (estadística descriptiva y visualización).

La idea de fondo es que el EDA no es un fin en sí mismo: sirve para evitar conclusiones apresuradas, detectar problemas de calidad en los datos, generar hipótesis fundadas y elegir las técnicas adecuadas para el modelado.

# **2. Puntos clave**

- **Definición (Behrens, Encyclopedia of Database Systems):** el EDA emplea diversas técnicas para observar qué parecen indicar los datos, descubrir estructuras subyacentes, aislar variables importantes, detectar valores atípicos y anomalías, y sugerir modelos adecuados de la estadística convencional.

- **Origen:** el término se popularizó con John Tukey en la década de 1970, aunque explorar datos para entenderlos es una práctica tan antigua como la estadística misma.

- **Cuatro objetivos:** comprender la naturaleza del dataset, identificar patrones y relaciones iniciales, detectar problemas y anomalías, y guiar el modelado posterior.

- **Los datos rara vez llegan limpios:** faltantes, outliers, inconsistencias de codificación ("Argentina" vs "ARG") y duplicados son hallazgos esperables del EDA.

- **Lo que más importa de los faltantes no es cuántos hay, sino si faltan al azar:** un faltante sistemático (por ejemplo, sueldos altos que siempre faltan) sesga medias, medianas y correlaciones, y puede producir relaciones espurias.

- **Las técnicas estadísticas identifican outliers, pero no deciden si son errores:** esa decisión requiere conocimiento del dominio.

- **El proceso va de menor a mayor complejidad:** inspección inicial → univariado → bivariado → calidad de datos → análisis temporal → generación de hipótesis.

- **El cierre del EDA son hipótesis y oportunidades de proyecto,** no solo gráficos: cada caso del material termina proponiendo un modelo concreto a construir.

# **3. Bloque 1 — Objetivos del EDA**

## **3.1 Comprender la naturaleza del dataset**

Antes de cualquier análisis avanzado hay que saber qué datos se tienen:

- Cuántas filas y columnas hay.

- Qué representa cada columna y qué unidades o categorías usa.

- Qué tipos de variables hay: numéricas, categóricas, fechas, texto.

- Contexto de obtención: cómo y cuándo fueron recolectados los datos.

### **Tipos de variable y qué hacer con cada una**

| **Tipo**    | **Qué se analiza**                                                                                                                                                                            |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Numéricas   | Continuas o discretas. Medidas de tendencia central y dispersión, forma de la distribución, y detección de valores extremos para decidir si se mantienen o se tratan.                         |
| Categóricas | Nominales u ordinales. Frecuencias absolutas y relativas, representadas con gráficos de barras o tablas de frecuencia.                                                                        |
| Temporales  | Validez del formato fecha/hora, extracción de componentes (año, mes, día, hora, día de la semana), tendencias, estacionalidad y patrones cíclicos, y huecos o irregularidades en el registro. |
| Texto libre | Longitud y estructura, búsqueda de patrones o palabras clave, y estandarización de formato.                                                                                                   |

## **3.2 Identificar patrones y relaciones**

- **Distribuciones:** ¿la variable es simétrica, sesgada, multimodal?

- **Relación entre variables:** ¿a mayor edad hay mayor ingreso?, ¿los productos más caros se venden menos?

- **Diferencias entre grupos:** por ejemplo, si el promedio de ventas difiere entre regiones.

> *Estos hallazgos son los que orientan qué preguntas vale la pena investigar en profundidad.*

## **3.3 Detectar problemas y anomalías**

- **Valores faltantes** y su impacto (sesgo, calidad de los modelos).

- **Valores extremos (outliers)** que podrían ser errores o casos especiales.

- **Inconsistencias de formato o codificación,** como "Argentina" y "ARG" conviviendo como valores distintos en la misma columna.

- **Duplicados.**

### **Valores faltantes en detalle**

| **Eje**            | **Contenido**                                                                                                                                                                                                                                                                       |
|--------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Casos a revisar    | Porcentaje de renglones con faltante; registros con alto porcentaje de faltantes; si los faltantes se correlacionan con otra variable (p. ej., siempre faltan en el local de Mendoza); y si la distribución de faltantes no es aleatoria (p. ej., los sueldos altos suelen faltar). |
| Impactos           | Eliminar filas sin sesgo solo reduce el tamaño de la muestra; eliminarlas con sesgo impacta medias, medianas y correlaciones, y puede generar relaciones espurias. Además, hay algoritmos que directamente no toleran faltantes.                                                    |
| Estrategias de EDA | Mapas de calor de valores faltantes; gráficos de barras con el porcentaje por variable; y comparar la distribución de otras variables entre el total y el subconjunto con faltantes.                                                                                                |

### **Valores extremos (outliers)**

- **Valores imposibles:** requieren conocimiento del dominio para preguntarse si ese valor podría ocurrir en la práctica (edad negativa o mayor a 150 años; violación de límites físicos, lógicos o de reglas de negocio).

- **Técnicas estadísticas:** z-score, boxplots, rango intercuartílico (IQR). Por ejemplo, puntos a más de 3 desvíos estándar de la media. Los identifican, pero no determinan si son o no errores.

- **Comparación con otras variables:** un cliente con gasto muy alto pero que también tiene muchas transacciones probablemente no sea un error.

## **3.4 Guiar el modelado posterior**

El EDA sirve para tomar mejores decisiones en el modelado:

- Qué variables son relevantes.

- Qué transformaciones son necesarias: normalización, codificación de categorías, imputación de faltantes.

- Qué hipótesis vale la pena probar.

> *Ejemplo del material: si en el EDA se descubre que una variable tiene el 80% de valores faltantes, probablemente no sea útil en el modelo, o va a requerir una estrategia especial.*

# **4. Bloque 2 — Fases del EDA**

## **4.1 Inspección inicial del dataset**

**Objetivo:** construir un mapa mental del dataset antes de entrar en detalles.

- **Dimensiones:** cuántas filas (observaciones) y columnas (variables).

- **Nombres y significado de las variables:** qué mide cada una y en qué unidades o categorías.

- **Tipos de datos:** numéricos, categóricos, fechas o texto libre.

- **Formato y estructura:** CSV, Excel, base de datos, JSON, etc.

> *En el ejemplo del material (dataset de 1000 filas y 15 columnas), la salida de info() ya muestra dos variables con faltantes: generation con 966 valores no nulos y type_2 con solo 503.*

## **4.2 Análisis univariado**

**Objetivo:** detectar comportamientos atípicos analizando cada variable de forma aislada.

- **Variables numéricas:** tendencia central (mínimo, máximo, media, mediana), dispersión (desviación estándar, percentiles) y distribución (histograma, densidad, frecuencias, forma de la curva, asimetría, presencia de picos o huecos).

- **Variables categóricas:** balance de clases, es decir conteo de frecuencias, proporciones y categorías menos frecuentes.

### **Caso 1 — Ingresos mensuales**

| **Estadístico**     | **Valor / lectura**                                                                                                                                                                                                              |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mínimo / Máximo     | 300 / 50.000                                                                                                                                                                                                                     |
| Media / Mediana     | 3.500 / 2.200                                                                                                                                                                                                                    |
| Desviación estándar | 5.200                                                                                                                                                                                                                            |
| Asimetría           | +4,5 (cola a la derecha)                                                                                                                                                                                                         |
| Interpretación      | La media está inflada por valores muy altos, así que la mediana representa mejor al cliente típico. La gran dispersión indica una población heterogénea y aparece un posible segmento premium en los clientes de más de 10k USD. |

> *Ojo con la diapositiva: está titulada "Variable Categórica", pero los ingresos mensuales son una variable numérica. Parece un error de rótulo en el material original.*

### **Caso 2 — Método de pago**

| **Distribución** | **Tarjeta 85% · Efectivo 10% · Transferencia 5%**                                                                                                                                                               |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Interpretación   | El dataset está muy desbalanceado hacia tarjeta, por lo que un modelo sin ajuste siempre va a predecir 'tarjeta'. Además aparece una oportunidad de negocio: incentivar transferencias para reducir comisiones. |

## **4.3 Análisis bivariado**

**Objetivo:** estudiar relaciones entre dos variables para detectar:

- **Dependencias:** cómo cambia una variable respecto a otra.

- **Agrupamientos naturales:** diferencias entre categorías o segmentos.

- **Tendencias o correlaciones:** si hay relación positiva o negativa.

### **Caso 3 — Dos variables numéricas: edad vs. ingreso mensual**

- Resultado: a mayor edad, mayor ingreso hasta cierto punto (curva ascendente hasta los 50 años y luego se estabiliza).

- Insight de negocio: segmentar clientes por edad para productos premium, ya que el rango de 40 a 55 años concentra el mayor poder adquisitivo.

### **Caso 4 — Numérica vs. categórica: ventas promedio por región**

- Norte: 2.500 · Sur: 1.800 · Centro: 3.200.

- Insight de negocio: la Región Centro tiene ventas significativamente más altas, así que conviene reforzar la inversión en esa zona.

## **4.4 Análisis de calidad de datos**

**Objetivo:** definir estrategias de limpieza y preparación para el modelado.

- **Valores faltantes:** porcentaje, distribución y posibles causas.

- **Duplicados:** registros repetidos que no aportan información nueva.

- **Inconsistencias:** errores de codificación, cambios de nomenclatura, formatos mezclados.

- **Valores extremos:** decidir si son errores o casos válidos que requieren tratamiento especial.

## **4.5 Análisis temporal o secuencial**

**Objetivo:** detectar patrones dinámicos que no se ven en un análisis estático.

- **Tendencias generales:** aumento o disminución a lo largo del tiempo.

- **Estacionalidad:** patrones repetitivos en periodos definidos (semanales, mensuales, anuales).

- **Ciclos:** fluctuaciones de largo plazo no ligadas a la estacionalidad.

## **4.6 Generación de hipótesis**

El EDA no solo responde preguntas: ayuda a formular nuevas. Las tres preguntas guía son qué factores podrían explicar un patrón detectado, si hay relaciones inesperadas que valga la pena investigar, y qué supuestos iniciales se confirman o se contradicen.

El material desarrolla tres casos con la misma estructura: EDA inicial → observación → hipótesis → prevalidación → oportunidad de proyecto.

| **Caso**                                  | **Observación**                                                                                    | **Hipótesis**                                                                        | **Oportunidad de proyecto**                                                                                                                              |
|-------------------------------------------|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Edad y gasto premium                      | Las personas entre 35 y 50 años gastan más en productos premium.                                   | Los clientes de 35 a 50 años son más propensos a comprar productos premium.          | Modelo de recomendación de productos premium con features de edad, historial de compras y segmentación demográfica, para optimizar campañas y upselling. |
| Frecuencia de compra y programa de puntos | Los clientes de niveles de membresía más altos compran más seguido y tienen mayor ticket promedio. | Un programa de fidelidad más robusto incrementa la frecuencia y el valor de compra.  | Modelo de propensión de upgrade de membresía: predecir qué clientes pueden pasar al nivel superior si se los incentiva.                                  |
| Región y satisfacción del cliente         | Ciertas regiones muestran calificaciones consistentemente bajas o dispersas.                       | La satisfacción del cliente depende de factores logísticos específicos de la región. | Modelo de predicción de satisfacción con región, tiempos de entrega, tipo de producto y servicio al cliente, para priorizar mejoras y anticipar churn.   |

> *La prevalidación es el paso que suele saltearse: antes de armar el modelo, se chequean promedios por rango de edad, correlaciones entre nivel de membresía y frecuencia, o la correlación entre calificación y tiempo de entrega. Es lo que separa una hipótesis fundada de una corazonada.*

# **5. Bloque 3 — Herramientas conceptuales**

## **5.1 Estadística descriptiva**

Se enfoca en resumir y describir las características más importantes de los datos.

| **Grupo**                     | **Medidas**                                                                                                                                 |
|-------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| Numéricas · tendencia central | Media, mediana, moda.                                                                                                                       |
| Numéricas · dispersión        | Rango, varianza, desviación estándar, rango intercuartílico.                                                                                |
| Numéricas · forma             | Asimetría, curtosis.                                                                                                                        |
| Categóricas                   | Frecuencia absoluta (cuántas veces aparece cada categoría), frecuencia relativa (proporción o porcentaje) y moda (categoría más frecuente). |

## **5.2 Visualización exploratoria**

La visualización permite detectar relaciones, patrones y anomalías que no siempre son evidentes en tablas de números.

| **Gráfico**       | **Para qué sirve**                                            |
|-------------------|---------------------------------------------------------------|
| Histograma        | Distribución de valores y forma de la curva (numéricas).      |
| Boxplot           | Mediana, dispersión y outliers (numéricas).                   |
| Scatter plot      | Relación entre dos variables numéricas.                       |
| Gráfico de barras | Comparación de frecuencias entre categorías.                  |
| Gráfico circular  | Proporciones; menos recomendado cuando hay muchas categorías. |

# **6. Términos clave**

| **Término**          | **Definición**                                                                                                                                          |
|----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| EDA                  | Enfoque flexible y abierto para analizar datos antes de aplicar modelos predefinidos, buscando patrones, anomalías y relaciones.                        |
| Asimetría (skewness) | Medida de forma que indica hacia qué lado se estira la distribución. En el caso de ingresos, +4,5 significa una cola larga a la derecha.                |
| Curtosis             | Medida de forma asociada al peso de las colas de la distribución.                                                                                       |
| IQR                  | Rango intercuartílico: distancia entre el percentil 25 y el 75; se usa para detectar outliers.                                                          |
| Z-score              | Cuántos desvíos estándar separa un punto de la media; por convención se marcan los que superan 3.                                                       |
| Relación espuria     | Relación aparente entre variables que surge de un sesgo (por ejemplo, eliminar filas con faltantes no aleatorios) y no de un vínculo real.              |
| Balance de clases    | Distribución de frecuencias de una variable categórica. Si está muy desbalanceada, un modelo sin ajuste tiende a predecir siempre la clase mayoritaria. |
| RFM                  | Recencia, frecuencia y valor monetario: tabla usada para caracterizar clientes por nivel de membresía.                                                  |
| Imputación           | Transformación que consiste en completar valores faltantes en lugar de eliminar los registros.                                                          |

# **7. Repaso rápido**

Si tenés que retener cinco cosas de la unidad:

- El EDA se hace antes de modelar y su salida son decisiones: qué variables usar, qué transformar y qué hipótesis probar.

- Primero mirás el dataset entero (dimensiones, tipos, formato), después variable por variable, después de a pares.

- Media vs. mediana: cuando difieren mucho hay asimetría y outliers tirando del promedio.

- Un faltante o un outlier no se elimina por defecto; primero se pregunta por qué está ahí, y eso requiere conocimiento del dominio.

- Todo hallazgo del EDA debería poder escribirse como una hipótesis y prevalidarse antes de convertirse en un proyecto de modelado.
