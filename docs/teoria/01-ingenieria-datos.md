---
titulo: "Unidad 1 — Teoría: Ingeniería de Datos"
materia: "Ciencia de Datos · UTN FRM · Ciclo lectivo 2026"
fuente: "Teoria_u1.docx (clase 2, bloque teórico)"
convertido: "docx → md con pandoc, formato preservado"
---

**UTN — FACULTAD REGIONAL MENDOZA**

**Ingeniería de Datos**

Ciencia de Datos 2026 · Clase 2 · Bloque teórico

*Apuntes completos de la presentación*

# **Contenido**

1.  Bloque 1 — Rol del ingeniero de datos

2.  Bloque 2 — El ingeniero en la organización

3.  Bloque 3 — Ciclo de vida de la ingeniería de datos

4.  Bloque 4 — Orquestación y DataOps

5.  Bloque 5 — Calidad de datos

6.  Cierre — La idea que hay que llevarse

7.  Anexo A — Glosario de términos

8.  Anexo B — Mapa de herramientas por etapa

9.  Anexo C — Preguntas de repaso

# **Bloque 1 — Rol del ingeniero de datos**

*De dónde viene la disciplina, qué hace, por qué el rol existe hoy — y por qué el ciclo de vida es más importante que las herramientas.*

## **1.1 ¿Qué es la ingeniería de datos?**

> **Definición (Reis & Housley):** «La ingeniería de datos es el desarrollo, implementación y mantenimiento de sistemas y procesos que toman datos crudos y los convierten en información consistente y de calidad para su uso posterior.» — Joe Reis & Matt Housley, *Fundamentals of Data Engineering* (O'Reilly, 2022).

La definición se desglosa en cuatro responsabilidades concretas:

- **Identificar y acceder a fuentes de datos.** Saber qué sistemas generan datos, cómo se accede a ellos y bajo qué condiciones (permisos, cuotas, formatos, frecuencia).

- **Mover datos entre sistemas, transformarlos, almacenarlos y validarlos.** Es el núcleo operativo del rol.

- **Servirlos a los consumidores:** análisis, BI, ciencia de datos y machine learning. El dato no existe para sí mismo, existe para ser consumido.

- **Mantener toda esa maquinaria funcionando en el tiempo.** No es un proyecto que termina: es un sistema que vive, se rompe y se repara.

La palabra clave de la definición es **"posterior"**: el ingeniero de datos no consume el dato final, lo habilita. Su producto es la posibilidad de que otro trabaje bien.

## **1.2 Evolución histórica del rol**

El rol no apareció de la nada: es la consolidación de varias tradiciones técnicas previas. Un dato de contexto: el término *"big data"* perdió tracción como búsqueda y como etiqueta profesional, mientras que *"data engineering"* viene creciendo de manera sostenida.

| **Período** | **Qué pasó**                                                                                      | **Qué dejó como herencia**                                                                                 |
|-------------|---------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| **80s–90s** | Aparecen los *data warehouses*. Bill Inmon y Ralph Kimball formalizan el modelado dimensional.    | Nace el **ETL developer** y el **ingeniero de BI**. Se instala la idea de una base separada para analizar. |
| **2000s**   | Google, Yahoo y Amazon enfrentan una escala sin precedentes. Aparecen **MapReduce** y **Hadoop**. | Procesamiento distribuido sobre hardware barato. El volumen deja de ser una barrera técnica infranqueable. |
| **2010s**   | Se populariza el *big data*. Spark, Hive, Cassandra. Explota el ecosistema open source.           | Herramientas maduras y accesibles para cualquier organización, no sólo para las grandes tecnológicas.      |
| **2020s**   | Del volumen a la **gestión integral**: gobernanza, privacidad, calidad y cloud.                   | El problema ya no es poder procesar, es hacerlo bien: confiable, seguro, gobernado y auditable.            |

> **Lectura del cuadro:** la línea de tiempo muestra un desplazamiento del foco desde **"cómo proceso tanto dato"** hacia **"cómo garantizo que este dato sea confiable, seguro y sostenible"**. Por eso el rol actual es mucho más amplio que el viejo ETL developer.

# **Bloque 2 — El ingeniero en la organización**

*Cómo se relaciona con la ciencia de datos, dónde vive en el ecosistema técnico, qué roles tocan lo mismo.*

## **2.1 Ingeniería de datos vs. ciencia de datos**

Ambos roles trabajan sobre los mismos datos, pero no hacen lo mismo. El ingeniero está **aguas arriba** (↑) y el científico **aguas abajo** (↓): el segundo consume lo que produce el primero.

|                         | **Ingeniero de datos (↑ aguas arriba)**                     | **Científico de datos (↓ aguas abajo)**            |
|-------------------------|-------------------------------------------------------------|----------------------------------------------------|
| **Qué produce**         | Pipelines, datasets confiables, infraestructura disponible. | Modelos, insights, decisiones informadas.          |
| **Herramientas**        | SQL · Airflow · Spark · dbt · cloud storage                 | pandas · scikit-learn · notebooks · matplotlib / R |
| **Qué significa éxito** | Datos correctos y a tiempo. El pipeline no se rompe.        | Modelo útil. Mejor decisión sobre el problema.     |

> **Dato central de la diapositiva:** entre un **70 y 80 % del tiempo del científico de datos se va en limpiar datos** cuando la ingeniería está mal resuelta. Cuando el rol del ingeniero se rompe, los tiempos del equipo entero se disparan. Esa cifra es el mejor argumento económico a favor de la disciplina.

## **2.2 Jerarquía de necesidades de la ciencia de datos**

Adaptado de **Monica Rogati**, *Data Science Hierarchy of Needs*. La idea es que cada capa se apoya en las de abajo, igual que en la pirámide de Maslow: no se puede hacer deep learning si la capa de recolección está rota. La mayoría de los proyectos de datos **no fracasan en la cima, fracasan en la base**.

De arriba hacia abajo:

| **Capa**            | **Nivel**               | **Qué incluye**                                                |
|---------------------|-------------------------|----------------------------------------------------------------|
| Ciencia de datos    | **AI · Deep learning**  | LLMs, modelos de difusión. La frontera de la disciplina.       |
| Ciencia de datos    | **Learn / Optimize**    | A/B testing, machine learning clásico.                         |
| Ciencia de datos    | **Aggregate / Label**   | Features, métricas, construcción del dataset de entrenamiento. |
| Ingeniería de datos | **Explore / Transform** | Limpieza, detección de anomalías, preparación.                 |
| Ingeniería de datos | **Move / Store**        | Pipelines, ETL, warehouses. La "plomería" del sistema.         |
| Ingeniería de datos | **Collect**             | Sensores, logs, apps, scraping.                                |

La **línea de trabajo** que divide ambas disciplinas cae entre *Aggregate / Label* y *Explore / Transform*. En la práctica esa frontera es porosa y depende del tamaño del equipo: en organizaciones chicas, la misma persona hace las seis capas.

## **2.3 Tipos de ingeniero: orientación interna vs. externa**

Los ingenieros de datos tienen dos orientaciones posibles según **quién es su cliente**. Muchas organizaciones tienen ambas conviviendo.

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Orientación interna</strong></th>
<th><strong>Orientación externa</strong></th>
</tr>
<tr class="odd">
<th><p><strong>Su cliente son los equipos internos</strong> — analistas, científicos de datos, áreas de negocio.</p>
<p>Construye plataformas de datos, warehouses, dashboards y pipelines de ML interno.</p>
<p>El pipeline <strong>no vuelve al producto</strong>: alimenta decisiones y reportes.</p></th>
<th><p><strong>Su cliente son los usuarios del producto</strong> — apps móviles, IoT, e-commerce.</p>
<p>Los datos vuelven al pipeline y regresan al producto como funcionalidad: recomendaciones, personalización, detección de fraude.</p>
<p>Es un <strong>ciclo cerrado</strong>.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

La diferencia práctica es la **latencia tolerada** y la **criticidad**: si el pipeline interno se atrasa cuatro horas, alguien mira un dashboard desactualizado; si el externo se cae, se rompe una funcionalidad que el usuario final está usando en ese momento.

## **2.4 Ecosistema técnico: con quién trabaja**

### **Aguas arriba · productores**

- **Ingenieros de software** — construyen las aplicaciones que generan los datos.

- **Arquitectos de datos** — tienen la visión global de la infraestructura.

- **DevOps / SRE** — generan datos operativos (logs, monitoreo, métricas de infraestructura).

### **Aguas abajo · consumidores**

- **Data analysts** — BI, reportes, insights para el negocio.

- **Data scientists** — modelan sobre lo que el ingeniero prepara.

- **ML engineers** — llevan sistemas de ML a producción. MLOps.

> **Consecuencia organizacional:** el ingeniero de datos es un rol **de interfaz**. Buena parte de su trabajo real es negociar contratos de datos con quienes están aguas arriba (que no le rinden cuentas) y gestionar expectativas de quienes están aguas abajo (que dependen de él).

# **Bloque 3 — Ciclo de vida de la ingeniería de datos**

*Cinco etapas y seis corrientes subyacentes. El marco mental que organiza toda la disciplina — y que no cambia aunque las herramientas sí.*

## **3.1 Panorama general**

El diagrama de referencia es la **Fig. 1-1** de *Fundamentals of Data Engineering*: cinco etapas más seis corrientes subyacentes (*undercurrents*).

Estructura del diagrama:

- **Generación** queda por fuera del recuadro principal, porque los sistemas fuente normalmente **no los controla el equipo de datos**.

- **Ingesta → Transformación → Disponibilización** forman la cadena central.

- **Almacenamiento** se dibuja como base de las tres, no como un paso más: atraviesa todas las etapas (se almacena al ingestar, al transformar y al servir).

- A la salida aparecen los tres consumos típicos: **Analytics**, **Machine Learning** y **Reverse ETL**.

- Debajo de todo, las **seis corrientes subyacentes**: seguridad, gestión de datos, DataOps, arquitectura de datos, orquestación e ingeniería de software.

> **Por qué importa el marco:** las herramientas cambian cada dos años; el ciclo de vida no. Sirve para **ubicar cualquier problema** ("esto es un problema de ingesta, no de transformación") y para comunicar decisiones con vocabulario compartido.

## **3.2 Etapa 1 · Generación — ¿de dónde vienen los datos?**

Los sistemas fuente **pocas veces están pensados "para el análisis"**: son subproductos del funcionamiento de aplicaciones. Esto explica la mayoría de los dolores de cabeza posteriores.

| **Tipo de fuente**                    | **Descripción y consideraciones**                                                                                                                     |
|---------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Archivos y datos no estructurados** | CSV, JSON, XML, imágenes, PDFs. Sin validación estructural: nada garantiza que el archivo de hoy tenga las mismas columnas que el de ayer.            |
| **APIs**                              | REST, GraphQL. Hay que manejar autenticación, cuotas (*rate limits*) y versionado. Es la fuente más común hoy.                                        |
| **Bases OLTP**                        | PostgreSQL, MySQL, Oracle. Optimizadas para escritura rápida y sin redundancia — es decir, exactamente lo contrario de lo que conviene para analizar. |
| **Logs**                              | Registros automáticos de actividad. Texto, cronológicos, alto volumen.                                                                                |
| **Mensajes y streams**                | Kafka, Pulsar, Kinesis. Tiempo real, arquitecturas orientadas a eventos (*event-driven*).                                                             |
| **Web scraping**                      | HTML público. Problemas típicos: medidas anti-bot, cambios de estructura de la página y consideraciones legales.                                      |

> **🔗 En el proyecto integrador · FIFA:** el caso canónico se genera en **sofifa.com**: sin API, con **Cloudflare que bloquea requests** y con HTML que cambia entre temporadas. Es decir, la fuente más frágil de las seis — y por eso mismo la más didáctica.

## **3.3 Etapa 2 · Almacenamiento — ¿dónde y cómo se guardan?**

No es "guardar archivos": es decidir **dónde, cómo y con qué garantías**. El almacenamiento se piensa en tres capas superpuestas.

| **Capa**            | **Contenido**                             | **Rol**                                                       |
|---------------------|-------------------------------------------|---------------------------------------------------------------|
| **Abstracciones**   | Warehouse · Lake · Lakehouse              | La capa con la que dialoga el ingeniero en el día a día.      |
| **Storage systems** | HDFS · RDBMS · Object storage · Streaming | Los motores que implementan esas abstracciones.               |
| **Raw ingredients** | HDD · SSD · RAM · red · compresión        | La capa física. Es donde vive el trade-off costo / velocidad. |

La lectura es de abajo hacia arriba: cada capa abstrae la anterior. Cuando alguien dice "guardamos en S3", está nombrando la capa del medio; cuando dice "usamos un lakehouse", la de arriba.

### **3.3.1 Warehouse, lake y lakehouse**

Las tres abstracciones viven sobre el mismo eje: **cuánta estructura le impongo a los datos antes de guardarlos**. Más estructura = más rápido consultar, menos flexible. Menos estructura = más versátil, más caro operar bien.

**Más estructurado → Warehouse → Lakehouse → Lake → Más flexible**

<table>
<colgroup>
<col style="width: 33%" />
<col style="width: 33%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Data Warehouse</strong></th>
<th><strong>Data Lakehouse</strong></th>
<th><strong>Data Lake</strong></th>
</tr>
<tr class="odd">
<th><p><strong>Schema-on-write.</strong> La estructura se define antes de cargar. Sólo entran datos limpios y transformados.</p>
<p><strong>Óptimo para:</strong> BI, reportes y dashboards que necesitan consultas rápidas y respuestas consistentes.</p>
<p><strong>Trade-off:</strong> cambiar el schema es caro. No sirve para datos que todavía no sabés cómo vas a usar.</p>
<p><em>BigQuery · Snowflake · Redshift · Synapse</em></p></th>
<th><p><strong>Lo mejor de los dos mundos.</strong> Datos crudos en un lake, pero con capa transaccional encima (ACID, versionado, schema).</p>
<p><strong>Ideal para:</strong> equipos que quieren un solo lugar para BI, ML y streaming, sin duplicar datos.</p>
<p><strong>Trade-off:</strong> tecnología joven, menos madura que un warehouse tradicional.</p>
<p><em>Databricks Delta · Apache Iceberg · Apache Hudi</em></p></th>
<th><p><strong>Schema-on-read.</strong> Datos en bruto, en cualquier formato (CSV, JSON, Parquet, imágenes, logs). La estructura se aplica al leer.</p>
<p><strong>Óptimo para:</strong> ML, análisis exploratorio y datos que aún no sabés cómo vas a usar.</p>
<p><strong>Trade-off:</strong> sin gobierno se convierte en un <em>data swamp</em> — nadie sabe qué hay ni en qué estado está.</p>
<p><em>S3 · Google Cloud Storage · Azure Blob · HDFS</em></p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## **3.4 Etapa 3 · Ingesta — mover datos con criterio**

Suena mecánico, pero es la etapa que define **latencia, confiabilidad e integridad**. Se resume en seis dimensiones de decisión, que hay que tomar explícitamente en cada pipeline.

| **Dimensión**                | **La pregunta que responde**                                                                                                         |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| **Batch vs. streaming**      | ¿Lotes cada X horas o eventos continuos? El streaming aparece cuando la latencia realmente importa — y cuesta bastante más operarlo. |
| **Push vs. pull**            | ¿La fuente empuja el dato (webhook) o vas vos a buscarlo (*poll* periódico)?                                                         |
| **Snapshot vs. diferencial** | ¿Copiás la tabla completa cada vez o sólo lo que cambió? Lo diferencial requiere algún mecanismo de *tracking*.                      |
| **ETL vs. ELT**              | ¿Transformás **antes** de cargar (enfoque clásico) o **después**, ya dentro del warehouse (enfoque moderno)?                         |
| **Bounded vs. unbounded**    | Un CSV finito vs. un feed continuo de sensores. Cambia todo el diseño del sistema.                                                   |
| **Conectores gestionados**   | Herramientas que resuelven la ingesta por vos: **Fivetran · Airbyte · Debezium (CDC)**.                                              |

> **🔗 En el proyecto integrador · FIFA:** el DAG del TP 1 toma explícitamente estas seis decisiones: **batch diario**, **pull** con un sensor que consulta cada 5 minutos, **diferencial** —compara el snapshot de sofifa contra la última corrida antes de bajar nada—, y **ETL** sobre datos **bounded**. Si la fuente no responde, cae a un **respaldo congelado** en lugar de fallar.

## **3.5 Etapa 4 · Transformación — de crudo a utilizable**

Transformar es hacer viajar los datos por **capas** hasta que estén listos para consumir. Cada capa tiene un propósito distinto: es la **medallion architecture** (arquitectura de medallas).

### **🥉 Bronze — datos crudos**

- **Estado:** como llegaron de la fuente. Nulos, duplicados, tipos raros, HTML sin parsear.

- **Regla:** *append-only*. **Nunca sobrescribir** — es la red de seguridad para poder regenerar todo desde cero.

- **Consumidor:** nadie directamente. Es la fuente de verdad para las capas de arriba.

- **Stack:** scripts de ingesta + object storage. Formato original (JSON, CSV, HTML).

- **🔗 FIFA:** el HTML de sofifa comprimido y particionado por snapshot. Lo escribe la tarea land_bronze.

### **🥈 Silver — datos limpios**

- **Estado:** tipado, deduplicado, validado. Una fila por entidad, sin ambigüedades.

- **Regla:** cada transformación **testeada**. Documentado qué se descartó y por qué.

- **Consumidor:** analistas y científicos que exploran o entrenan modelos.

- **Stack:** dbt, Spark, pandas. Formato Parquet columnar.

- **🔗 FIFA:** 1 jugador por fila, altura en cm, valor en euros, posición canónica. Es lo que se entrega en la **Entrega 1**.

### **🥇 Gold — datos listos**

- **Estado:** agregado, con features derivadas, modelado para el consumo final.

- **Regla:** **schema estable**. Los cambios se comunican al equipo consumidor.

- **Consumidor:** dashboards, ML en producción, reportes ejecutivos.

- **Stack:** warehouse (BigQuery, Snowflake). Tablas particionadas por fecha.

- **🔗 FIFA:** features para el clasificador de **U3**, agregados por liga para la app de **U4**. No se construye en la unidad 1.

> **Por qué capas y no una sola transformación:** porque si el resultado final está mal, con bronze intacto se puede **rehacer todo sin volver a la fuente** (que quizás ya cambió o ya no está disponible). Las capas compran capacidad de recuperación a cambio de espacio en disco, que es barato.

## **3.6 Etapa 5 · Disponibilización — entregar a quien lo usa**

Los datos preparados **no existen para sí mismos**: existen para ser consumidos. El "cómo" cambia radicalmente según quién los use.

| **Modo de consumo**    | **En qué consiste**                                                               | **Herramientas**                    |
|------------------------|-----------------------------------------------------------------------------------|-------------------------------------|
| **Business analytics** | Dashboards y reportes.                                                            | Power BI, Looker, Tableau, Metabase |
| **Análisis operativo** | Decisiones en tiempo real: monitoreo, alertas, respuesta a incidentes.            | —                                   |
| **Análisis embebido**  | Métricas dentro de otra aplicación — por ejemplo, un dashboard adentro de un CRM. | —                                   |
| **Machine learning**   | Datasets de entrenamiento o features en tiempo real.                              | Feast, Tecton                       |
| **Reverse ETL**        | Devolver datos del warehouse a herramientas operativas.                           | Hightouch, Census                   |

> **🔗 En el proyecto integrador:** la Entrega 1 termina con el dataset listo para servir a la Entrega 2 (EDA). Ahí se lo defiende contra los **siete criterios**, con los números a mano: filas, clave sin duplicados, nulos y por qué. La frase clave de la diapositiva: **"en agosto la calidad del dato era de quien publicó la fuente; ahora es tuya"**.

## **3.7 Cierre del ciclo — seis corrientes que atraviesan todo**

Las cinco etapas son lo visible del ciclo. Estas seis dimensiones lo cruzan **de punta a punta, en todas las etapas a la vez**, y son las que deciden si el pipeline es sólido o frágil.

| **Corriente**              | **De qué se ocupa**                                                                       |
|----------------------------|-------------------------------------------------------------------------------------------|
| **Orquestación**           | Coordinar las tareas: en qué orden corren, qué depende de qué, qué pasa si una falla.     |
| **DataOps**                | Automatización, testing y control de versiones aplicados al mundo de los datos.           |
| **Gestión de datos**       | Políticas de calidad, retención y ciclo de vida del dato. De acá sale el hilo de calidad. |
| **Seguridad**              | Quién accede a qué, cifrado en tránsito y en reposo, gestión de secretos.                 |
| **Arquitectura de datos**  | Las decisiones estructurales sobre el sistema completo, no sobre una etapa en particular. |
| **Ingeniería de software** | Testing, versionado, revisión de código, modularidad. **Un pipeline es software.**        |

> **Alcance de la clase:** de las seis corrientes se tiran **dos hilos**, los que más rinden para el proyecto: **orquestación y DataOps** (bloque 4) y **calidad** (bloque 5). Las otras cuatro quedan nombradas.

# **Bloque 4 — Orquestación y DataOps**

*Los pipelines son grafos, no scripts sueltos. Y como todo software, necesitan versionado, testing y monitoreo.*

## **4.1 Por qué hace falta un orquestador**

Un pipeline, salvo casos triviales, **no es una tarea: son muchas encadenadas**. Se scrapea, se limpia, se transforma, se carga, se testea, se notifica. La pregunta no es cómo escribir cada una, es **quién garantiza que corran en orden, que se recuperen solas y que después se pueda ver qué pasó**.

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Sin orquestador</strong></th>
<th><strong>Con orquestador</strong></th>
</tr>
<tr class="odd">
<th><p>Scripts que se llaman entre sí, <em>cron jobs</em> con horarios cruzados y reintentos hechos a mano.</p>
<p><strong>Anda hasta que no anda</strong> — y cuando no anda, no se sabe por qué.</p></th>
<th><p>Un <strong>DAG</strong>: <em>grafo dirigido acíclico</em>. Nodos = tareas, aristas = dependencias, sin ciclos.</p>
<p>Descargar → Validar → Transformar → Cargar → Notificar</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

Las tres garantías que aporta un orquestador:

- **Dependencias explícitas.** El sistema sabe que B necesita que A haya terminado bien. Si A falla, B no arranca.

- **Reintentos y recuperación.** Una red que se corta o una API que devuelve 500 no tiran abajo la corrida: reintenta solo y avisa si el problema persiste.

- **Observabilidad.** Un único lugar donde ver qué corrió, cuándo, en qué estado y con qué logs. Sin eso, depurar es a ciegas.

**Herramientas típicas:** Apache Airflow · Prefect · Dagster · Argo · Google Cloud Composer.

## **4.2 DataOps — tratar los datos como un producto**

DataOps traslada al pipeline la disciplina que el software ya tiene. Con una diferencia que lo cambia todo: **en software testeás tu código; acá también tenés que testear datos que no controlás**.

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Lo que se hereda del software</strong></th>
<th><strong>Lo que agrega el mundo de los datos</strong></th>
</tr>
<tr class="odd">
<th><p><strong>Automatización</strong> — nada se corre a mano: todo está en el DAG.</p>
<p><strong>Versionado y revisión</strong> — el pipeline vive en Git; los cambios se revisan.</p>
<p><strong>CI/CD</strong> — se prueba en un ambiente aparte antes de tocar producción.</p>
<p><strong>Documentación desde el código</strong> — dbt la genera sola.</p></th>
<th><p><strong>Tests en cada corrida</strong>, no una sola vez: sin player_id duplicados, overall entre 1 y 99, al menos 500 filas.</p>
<p><strong>Observabilidad</strong> — ¿el volumen de hoy se parece al de ayer?</p>
<p><strong>Linaje</strong> — de dónde salió cada número. OpenLineage.</p>
<p><strong>Versionado de datasets</strong> — DVC, LakeFS.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

> **El riesgo específico de los datos: el código no cambió, los datos sí.** La fuente agrega una columna, cambia un formato de fecha, el scraper devuelve la mitad de las filas. **El pipeline sigue en verde y el resultado ya es falso.** Ese es el modo de falla que el testing de software tradicional no detecta.
>
> **🔗 En el proyecto integrador:** la Entrega 1 se evalúa sobre un **DAG corriendo en la interfaz de Airflow**, no sobre un notebook que scrapea. El testing de datos ya está adentro: la tarea validate es exactamente eso.

# **Bloque 5 — Calidad de datos**

*Cinco dimensiones para nombrar los problemas, y por qué la validación es una tarea más del pipeline y no un chequeo posterior.*

## **5.1 Cinco dimensiones canónicas**

Un dashboard con datos malos **no es un dashboard imperfecto: es peligroso**, porque respalda una decisión equivocada con la autoridad de un número. Y "datos malos" no dice nada hasta aclarar **en qué** son malos: estas cinco dimensiones son el vocabulario para nombrarlo.

| **Dimensión**    | **Pregunta**       | **Detalle y cómo se mide**                                                                                                                                                                                                                   |
|------------------|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Completitud**  | *¿está todo?*      | ¿Están todos los datos que deberían estar? Pueden faltar filas enteras, una columna o valores sueltos. Se mide con el **% de nulos por columna** (df.isna().mean()). Ojo: un nulo puede significar "no aplica" y ser perfectamente correcto. |
| **Consistencia** | *¿se contradicen?* | ¿Los datos concuerdan entre sí, dentro de una misma tabla y entre tablas distintas? Cada dato puede ser plausible por separado; el problema aparece al cruzarlos: por ejemplo, una fecha de nacimiento posterior a la de alta.               |
| **Precisión**    | *¿es verdad?*      | ¿Los valores coinciden con la realidad que dicen describir? Un jugador de 300 cm no es un dato raro: es un error de captura. Es **la más difícil de verificar** — exige una referencia externa.                                              |
| **Actualidad**   | *¿de cuándo es?*   | ¿Reflejan el estado de hoy, o el de la última vez que el pipeline corrió sin fallar? Es la que **se rompe en silencio**: el número sigue apareciendo en el dashboard, sólo que ya no es cierto.                                              |
| **Unicidad**     | *¿hay repetidos?*  | ¿Hay registros repetidos donde la unidad de análisis dice que no puede haberlos? Es el **test operativo de la unidad de análisis** (df\["clave"\].is_unique): si la clave repite, o la unidad está mal definida o el pipeline duplica.       |

## **5.2 Dónde validar: la validación es una tarea más del grafo**

**Un criterio de calidad que no está escrito como código no protege nada.** Validar es convertir "el dataset tiene que estar bien" en una tarea que corre, mide y decide si el pipeline sigue.

**Consolidar → Validar → Guardar**

**✗ Si el chequeo no pasa, Guardar no corre.**

Esa es toda la diferencia entre validar adentro del pipeline y validar después: acá el dato malo **no llega a destino**.

Toda validación define tres cosas:

1.  **Qué se chequea.** El criterio traducido a una regla que una máquina pueda evaluar. "Completo" no es un chequeo; "la clave no repite" sí lo es.

2.  **Con qué umbral.** El número lo elige alguien: no sale del dato, sale de saber para qué se va a usar. **Un umbral heredado no protege nada.**

3.  **Qué pasa si falla.** Frenar; avisar y seguir; o degradar a una fuente de respaldo. Lo crítico frena; lo que es sólo observabilidad, avisa.

> **🔗 En el proyecto integrador:** lo primero al recibir el dataset es un **data profiling**: filas, columnas, tipos, nulos, duplicados. Es lo que indica **qué vale la pena chequear y con qué umbral**.

# **Cierre — La idea que hay que llevarse**

> **Idea central: La ingeniería de datos no es sobre herramientas. Es sobre el ciclo de vida** — el marco mental que permite ubicar cualquier problema, tomar decisiones informadas y comunicarlas.

Resumen operativo de la clase en cinco líneas:

1.  El rol existe porque **alguien tiene que garantizar que el dato llegue confiable y a tiempo**; si no, ese costo se lo come el científico de datos (70–80 % de su tiempo).

2.  El ciclo tiene **cinco etapas**: generación, almacenamiento, ingesta, transformación y disponibilización.

3.  Y **seis corrientes** que lo atraviesan: orquestación, DataOps, gestión de datos, seguridad, arquitectura e ingeniería de software.

4.  La **orquestación** convierte scripts sueltos en un grafo con dependencias, reintentos y observabilidad.

5.  La **calidad** se nombra con cinco dimensiones y se defiende con validaciones que son tareas del grafo, no chequeos posteriores.

**Segundo bloque de la clase:** se baja todo esto a código concreto — **Airflow**, el caso **FIFA** y la presentación del **TP 1**.

# **Anexo A — Glosario de términos**

| **Término**                   | **Significado**                                                                                                        |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------|
| **ACID**                      | Atomicidad, Consistencia, Aislamiento y Durabilidad. Garantías transaccionales; el lakehouse las aporta sobre un lake. |
| **Append-only**               | Regla de escritura que sólo permite agregar registros, nunca modificar ni borrar. Propia de la capa bronze.            |
| **Batch**                     | Procesamiento por lotes en intervalos definidos, en contraposición al streaming.                                       |
| **Bounded / unbounded**       | Datos con fin definido (un CSV) vs. flujo continuo sin fin (un feed de sensores).                                      |
| **CDC (Change Data Capture)** | Técnica para detectar y propagar sólo los cambios de una base fuente. Debezium es la herramienta típica.               |
| **DAG**                       | Grafo dirigido acíclico. Nodos = tareas, aristas = dependencias, sin ciclos. Es el modelo de un pipeline orquestado.   |
| **Data profiling**            | Inspección inicial de un dataset: filas, columnas, tipos, nulos, duplicados. Base para definir qué validar.            |
| **Data swamp**                | Data lake sin gobierno: nadie sabe qué hay ni en qué estado está.                                                      |
| **DataOps**                   | Aplicación de prácticas DevOps (automatización, CI/CD, versionado, monitoreo) al ciclo de vida del dato.               |
| **ETL / ELT**                 | Extraer-Transformar-Cargar vs. Extraer-Cargar-Transformar. El segundo transforma ya dentro del warehouse.              |
| **Feature store**             | Repositorio de features para ML, servibles en batch o en tiempo real. Feast, Tecton.                                   |
| **Linaje (lineage)**          | Trazabilidad del origen de cada dato a lo largo del pipeline. OpenLineage.                                             |
| **Medallion architecture**    | Organización de la transformación en capas bronze / silver / gold.                                                     |
| **OLTP**                      | Online Transaction Processing. Bases optimizadas para escritura rápida y sin redundancia (PostgreSQL, MySQL).          |
| **Parquet**                   | Formato de archivo columnar, comprimido y tipado. Estándar de facto para la capa silver.                               |
| **Reverse ETL**               | Devolver datos ya procesados desde el warehouse hacia herramientas operativas (CRM, marketing).                        |
| **Schema-on-write / on-read** | Definir la estructura antes de guardar (warehouse) vs. al momento de leer (lake).                                      |
| **Snapshot**                  | Copia del estado completo de una fuente en un momento dado.                                                            |
| **Streaming**                 | Procesamiento continuo de eventos a medida que ocurren. Kafka, Pulsar, Kinesis.                                        |
| **Undercurrents**             | Las seis corrientes subyacentes que atraviesan todas las etapas del ciclo de vida.                                     |

# **Anexo B — Mapa de herramientas por etapa**

Consolidado de todas las herramientas nombradas en la presentación, ordenadas por dónde aparecen en el ciclo.

| **Etapa / corriente**          | **Herramientas mencionadas**                                                            |
|--------------------------------|-----------------------------------------------------------------------------------------|
| **Generación**                 | APIs REST y GraphQL · PostgreSQL, MySQL, Oracle · Kafka, Pulsar, Kinesis · web scraping |
| **Almacenamiento — warehouse** | BigQuery · Snowflake · Redshift · Synapse                                               |
| **Almacenamiento — lakehouse** | Databricks Delta · Apache Iceberg · Apache Hudi                                         |
| **Almacenamiento — lake**      | S3 · Google Cloud Storage · Azure Blob · HDFS                                           |
| **Ingesta**                    | Fivetran · Airbyte · Debezium (CDC)                                                     |
| **Transformación**             | dbt · Spark · pandas · Parquet                                                          |
| **Disponibilización**          | Power BI · Looker · Tableau · Metabase · Feast · Tecton · Hightouch · Census            |
| **Orquestación**               | Apache Airflow · Prefect · Dagster · Argo · Google Cloud Composer                       |
| **DataOps**                    | Git · CI/CD · dbt docs · OpenLineage · DVC · LakeFS                                     |
| **Perfil del ingeniero**       | SQL · Airflow · Spark · dbt · cloud storage                                             |
| **Perfil del científico**      | pandas · scikit-learn · notebooks · matplotlib / R                                      |

# **Anexo C — Preguntas de repaso**

Para autoevaluar la comprensión de los cinco bloques.

### **Bloque 1 y 2**

1.  ¿Cuáles son las cuatro responsabilidades que se desprenden de la definición de Reis & Housley?

2.  ¿Qué cambió entre los 2000s y los 2020s en el foco de la disciplina?

3.  ¿Por qué "aguas arriba / aguas abajo" describe mejor la relación con el científico de datos que "más técnico / menos técnico"?

4.  ¿Qué implica que la mayoría de los proyectos de datos fracasan en la base de la pirámide de Rogati y no en la cima?

5.  ¿Cuál es la diferencia práctica entre un ingeniero de orientación interna y uno de orientación externa?

### **Bloque 3**

1.  ¿Por qué Generación se dibuja fuera del recuadro principal del ciclo de vida?

2.  ¿Por qué Almacenamiento no es una etapa más sino una base transversal?

3.  Elegí una fuente de datos de las seis y nombrá su principal riesgo operativo.

4.  Explicá el eje estructura/flexibilidad que ordena warehouse, lakehouse y lake.

5.  Enumerá las seis dimensiones de decisión de la ingesta y respondelas para un caso propio.

6.  ¿Por qué la capa bronze debe ser append-only?

7.  ¿Qué diferencia hay entre la capa silver y la gold en cuanto a consumidor y regla de gobierno?

8.  ¿Qué es reverse ETL y por qué se lo considera una forma de disponibilización?

### **Bloques 4 y 5**

1.  ¿Qué tres garantías aporta un orquestador que los cron jobs no dan?

2.  ¿Por qué un DAG no puede tener ciclos?

3.  ¿Cuál es el modo de falla propio del mundo de los datos que el testing de software no detecta?

4.  Nombrá las cinco dimensiones de calidad y dá un ejemplo de falla para cada una.

5.  ¿Por qué "actualidad" es la dimensión que se rompe en silencio?

6.  ¿Qué tres decisiones define toda validación, y por qué un umbral heredado no protege nada?
