---
titulo: "Unidad 1 — Introducción a Apache Airflow"
materia: "Ciencia de Datos · UTN FRM · Ciclo lectivo 2026"
fuente: "Resumen_Airflow_Unidad1_UTN_FRM_2026.docx"
convertido: "docx → md con pandoc, formato preservado"
---

**UNIDAD 1 · INGENIERÍA DE DATOS**

**Introducción a Apache Airflow**

Resumen ultra completo + banco de preguntas de examen

| **Materia**       | Ciencia de Datos · UTN FRM · Ciclo lectivo 2026                                        |
|-------------------|----------------------------------------------------------------------------------------|
| **Unidad**        | Unidad 1 — Ingeniería de datos                                                         |
| **Versiones**     | Airflow 3.3 · Astro Runtime 3.3-4                                                      |
| **Ejemplos**      | pokemon_api (API REST, ~60 líneas) y fifa_ingest (scraping, ~500 líneas, 18.936 filas) |
| **Qué se evalúa** | Conceptos de orquestación + entender por qué cada DAG está diseñado como está          |

# **Resumen ejecutivo**

El apunte introduce Apache Airflow como orquestador de flujos de trabajo: no procesa datos, decide qué se ejecuta, cuándo, en qué orden y qué hacer cuando algo falla. Todo el material se explica sobre dos DAGs reales que se corren en la máquina propia, elegidos porque representan las dos formas típicas de conseguir datos: una API REST amable y un scraping hostil.

La tesis del apunte es que ninguna diferencia de diseño entre esos dos DAGs es capricho: cada decisión (usar XCom o archivos, paralelismo fijo o dinámico, reintentos o degradación en tres niveles) responde a cómo es la fuente. Leer esa comparación preguntándose "por qué" es, según el propio texto, medio programa de la unidad.

Cierra con el entorno local (Astro CLI sobre Docker), una guía práctica de 7 pasos para ver los conceptos en vivo, y dos apéndices: la migración de Airflow 2 a 3 y los errores más frecuentes.

# **Los 12 puntos clave**

- **Airflow orquesta, no procesa.** Si el pipeline transforma un millón de filas, quien las transforma sigue siendo pandas. Airflow se ocupa del orden, los reintentos, los tiempos y los avisos.

- **El flujo se escribe en Python, no se dibuja.** Eso permite versionarlo con Git, generarlo programáticamente (un for en vez de cincuenta cajitas) y testearlo como cualquier código.

- **Un pipeline es un DAG:** grafo dirigido acíclico. Lo que no está conectado corre en paralelo; los ciclos hacen que Airflow rechace el DAG directamente.

- **Airflow no es un solo programa.** Son varios procesos (dag-processor, scheduler, api-server, triggerer) que se coordinan a través de la base de metadatos, nunca hablándose directo.

- **Airflow, providers y Astro son cosas distintas.** Airflow es el orquestador libre; los providers aportan integraciones; Astro Runtime y Astro CLI son de Astronomer y no son Airflow.

- **Si entre dos tareas viajan datos, la dependencia sale sola; si no viajan datos, hay que declararla** con \>\>.

- **Por XCom viajan metadatos, no datos.** Los XCom van a la base de metadatos: 20 filas está bien, 18.936 tira abajo el scheduler. Cuando el volumen crece, se escribe a disco y se devuelve la ruta.

- **El modelo medallón se ve en el grafo.** Bronce (land_bronze, HTML crudo, append-only) y plata (refine_silver + consolidate, filas tipadas y validadas) son dos tareas distintas, no una convención de nombres.

- **Las tareas dinámicas las decide la fuente.** .expand() crea N instancias en tiempo de ejecución: 52 ligas hoy, 51 en la versión anterior.

- **Un pipeline de producción no tiene una fuente: tiene un plan para cuando la fuente falla.** De ahí el sensor, el branching, el cortocircuito y los tres niveles de degradación.

- **Idempotencia es lo que hace seguros los reintentos.** Una tarea idempotente se relanza sin pensar; retries=2 sólo es seguro si la tarea lo es.

- **La mayoría de las corridas de un pipeline sano no hacen nada,** y eso está bien. Lo que no está bien es no darse cuenta.

# **1. Qué es Apache Airflow**

**Definición:** Airflow es un **orquestador de flujos de trabajo**. Su trabajo no es procesar datos: es decidir *qué* se ejecuta, *cuándo*, *en qué orden*, y qué hacer cuando algo falla.

No reemplaza a pandas ni a un motor de base de datos. Si el pipeline transforma un millón de filas, pandas las transforma; Airflow se encarga de que esa transformación arranque después de la descarga, de reintentarla si se cae, de registrar cuánto tardó y de avisar si no terminó.

## **1.1 Flujos de trabajo como código**

La idea central: **el flujo se escribe en Python**, no se dibuja en una interfaz. Un pipeline es un archivo .py como cualquier otro. Consecuencias prácticas:

- Se versiona con Git, con historial y revisión de cambios.

- Se puede generar programáticamente: si hay cincuenta tablas que migrar, no se dibujan cincuenta cajitas, se escribe un for.

- Se prueba con las mismas herramientas que cualquier código Python.

## **1.2 El modelo mental: DAGs**

Un pipeline en Airflow es un **DAG**: *Directed Acyclic Graph*, grafo dirigido acíclico. Cada palabra significa algo concreto:

| **Palabra**  | **Qué significa**                                                                                    |
|--------------|------------------------------------------------------------------------------------------------------|
| **Grafo**    | Hay tareas y hay relaciones entre ellas.                                                             |
| **Dirigido** | Las relaciones tienen sentido: A va antes que B, no al revés.                                        |
| **Acíclico** | No puede haber ciclos. Si A depende de B y B de A, no hay forma de empezar y Airflow rechaza el DAG. |

Las dependencias definen el orden. Lo que no está conectado, corre en paralelo.

> **Igual de importante:** lo que el DAG **no** define. No dice en qué máquina corre cada tarea, ni cuánto tarda, ni qué pasa si una falla. Todo eso es configuración y se resuelve aparte.

## **1.3 Quién hace qué (los procesos)**

Airflow no es un solo programa. Son varios procesos que se coordinan **a través de una base de datos**, nunca hablándose directo entre ellos.

| **Proceso**       | **Qué hace**                                                                                                                              |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| **dag-processor** | Lee los archivos .py de la carpeta dags/ y registra lo que encuentra. En Airflow 2 vivía dentro del scheduler; en 3 es un proceso aparte. |
| **scheduler**     | Decide qué tarea está lista para correr y la manda a ejecutar.                                                                            |
| **api-server**    | La interfaz web y la API. En Airflow 2 se llamaba *webserver*.                                                                            |
| **triggerer**     | Maneja las esperas asincrónicas (deferrable operators).                                                                                   |
| **metadata DB**   | El estado de todo: qué corrió, cuándo, con qué resultado.                                                                                 |

Que el dag-processor sea un proceso separado explica algo que se nota enseguida: cuando se crea un DAG nuevo, **tarda unos segundos en aparecer** en la interfaz. No está roto: está esperando a que el procesador vuelva a escanear la carpeta.

## **1.4 Airflow, providers, Astro: qué es cada cosa**

**Apache Airflow** es el proyecto de software libre: el scheduler, la base de metadatos, la interfaz. Lo mantiene la Apache Software Foundation y es gratis.

**Los providers** son paquetes que agregan integraciones. Airflow no sabe hablar con Postgres, S3 ni una API HTTP: eso lo aportan apache-airflow-providers-postgres, -amazon, -http. Traen operadores, hooks y tipos de conexión.

**Astronomer** es una empresa que vive de Airflow y publica dos cosas que se usan en la materia y que **no son** Airflow:

- **Astro Runtime**: imagen de Docker con Airflow ya armado y probado, con dependencias resueltas. Es lo que dice la primera línea del Dockerfile.

- **Astro CLI**: la herramienta de línea de comandos que levanta esa imagen. astro dev start no es un comando de Airflow, es de Astro.

Los **plugins** son otra cosa: extienden la propia interfaz de Airflow (agregar una pestaña, un menú, una vista). Son raros en la práctica y en la materia no se escribe ninguno.

| **Nombre**     | **Qué es**                             | **¿Se puede vivir sin?**            |
|----------------|----------------------------------------|-------------------------------------|
| Apache Airflow | El orquestador                         | No, es el corazón                   |
| Providers      | Integraciones con sistemas externos    | Sí, pero casi siempre querés alguno |
| Astro Runtime  | Imagen de Docker con Airflow listo     | Sí, se puede instalar a mano        |
| Astro CLI      | Comando para levantar el entorno local | Sí, se puede usar Docker directo    |
| Plugins        | Extensiones de la interfaz             | Sí, casi nadie escribe uno          |

# **2. Los dos ejemplos de la materia**

El proyecto trae dos DAGs. No es acumulación: son las dos formas de conseguir datos que aparecen al elegir la fuente del proyecto integrador.

## **2.1 pokemon_api — una API REST**

Consulta la PokéAPI, que devuelve JSON limpio, no pide autenticación y responde en menos de un segundo. Es el caso amable: alguien del otro lado publicó los datos para que los consumas. Son unas sesenta líneas, se lee de una sentada, y es el DAG que se usa para explicar los componentes. No se modifica en el TP.

## **2.2 fifa_ingest — scraping**

Construye el dataset canónico de la materia a partir del listado público de sofifa.com. Acá nadie publicó nada: hay que pedir HTML pensado para que lo lea una persona, parsearlo, y convivir con que el sitio puede bloquearte. Son unas quinientas líneas y produce 18.936 filas. Es el DAG que se modifica en el TP.

## **2.3 La comparación (tabla central de la unidad)**

|                        | **pokemon_api**                              | **fifa_ingest**                         |
|------------------------|----------------------------------------------|-----------------------------------------|
| **Fuente**             | API REST, JSON limpio                        | HTML que hay que parsear                |
| **Acceso**             | HttpOperator + HttpHook sobre una Connection | urllib a mano, sin provider             |
| **Cuándo corre**       | A demanda                                    | Programado, todos los días              |
| **Paralelismo**        | Fijo, dos ramas escritas a mano              | Dinámico, .expand() sobre 52 ligas      |
| **Datos entre tareas** | XCom, son 20 filas                           | Archivos en disco, son 18.936           |
| **Capas**              | Una sola: pide y guarda                      | Bronce y plata, separadas en dos tareas |
| **Ante fallos**        | Reintentos                                   | Degradación en tres niveles             |

> **Ojo:** ninguna de esas diferencias es capricho. Cada una responde a cómo es la fuente. Leer esa tabla de izquierda a derecha, preguntándose por qué, es medio programa de la unidad — y es material clásico de examen.

## **2.4 Bronce y plata: las capas en el grafo**

El **modelo medallón**: los datos no van de la fuente al análisis de un salto, sino que atraviesan capas, y cada capa tiene una regla distinta. fifa_ingest implementa las dos primeras **como dos tareas distintas que se ven en el grafo**.

| **Capa**   | **Tarea**                   | **Qué guarda**                      | **Regla**                                         |
|------------|-----------------------------|-------------------------------------|---------------------------------------------------|
| **Bronce** | land_bronze                 | El HTML tal como lo devolvió sofifa | Append-only: lo que ya está, no se vuelve a pedir |
| **Plata**  | refine_silver + consolidate | Filas tipadas, una por jugador      | Validada antes de publicarse                      |

¿Por qué guardar el HTML crudo si al final lo que querés es la tabla? Dos razones, y las dos aparecen apenas el pipeline vive más de una semana:

- **La fuente se toca una vez por dato, no una vez por corrida.** Si la página ya está en bronce, land_bronze no la pide. La segunda corrida sobre el mismo snapshot no genera una sola request.

- **Un bug en el parseo no obliga a volver a la fuente.** Si mañana descubrís que leías mal la columna de altura, corregís refine_silver y reprocesás lo que ya está en disco. Sin bronce, ese arreglo significa scrapear de nuevo — y si el sitio cambió en el medio, los datos viejos no se recuperan nunca más.

La tercera capa, **oro** (features derivadas, agregados por liga), no se construye acá: se arma en las unidades 3 y 4 sobre esta misma plata.

> **Confusión frecuente:** el **respaldo congelado** (load_frozen) *no* es bronce. Es plata ya parseada. Sirve para salvar la corrida de hoy, pero no permite reprocesar nada.

# **3. Estructura de un DAG**

## **3.1 El decorador @dag**

La forma actual de definir un DAG es decorando una función. Todo lo que se declare adentro forma parte del grafo.

> @dag(
>
> dag_id="pokemon_api",
>
> schedule=None,
>
> start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
>
> catchup=False,
>
> tags=\["ciencia-de-datos", "unidad-1"\],
>
> )
>
> def pokemon_api():
>
> ...
>
> pokemon_api()
>
> **Error clásico:** esa última línea, la llamada a la función, es la que **instancia** el DAG. Sin ella el archivo se parsea sin errores y no aparece nada en la interfaz. Es uno de los olvidos más comunes.

## **3.2 Los parámetros del DAG**

| **Parámetro**    | **Qué controla**                                                         |
|------------------|--------------------------------------------------------------------------|
| dag_id           | El identificador único. Es lo que se ve en la interfaz.                  |
| schedule         | Cada cuánto corre. None = sólo a demanda; "@daily", "0 8 \* \* \*", etc. |
| start_date       | Desde cuándo tiene sentido que corra.                                    |
| catchup          | Si al arrancar debe recuperar las corridas que se perdió.                |
| tags             | Etiquetas para filtrar en la interfaz.                                   |
| max_active_tasks | Cuántas tareas del DAG pueden correr a la vez.                           |

catchup **merece un párrafo aparte.** Si el DAG es @daily, arrancó el 1 de agosto y lo prendés el 20, con catchup=True Airflow va a intentar ejecutar las veinte corridas que faltan. A veces es exactamente lo que querés (reprocesar un histórico) y a veces es una avalancha inesperada. Los dos DAGs de la materia lo tienen en False.

## **3.3 Tareas con @task**

Una tarea es una unidad de trabajo. La forma moderna es decorar una función común:

> @task
>
> def traer_atributos(urls: list\[str\]) -\> list\[dict\]:
>
> ...
>
> return salida

**Si una tarea recibe como argumento el resultado de otra, Airflow deduce la dependencia solo:**

> combinar_y_guardar(traer_atributos(urls), traer_especies(urls))

Ahí no se declara ningún orden y el grafo queda armado: combinar espera a las dos, y las dos esperan a urls. Como traer_atributos y traer_especies no dependen entre sí, **corren en paralelo**.

## **3.4 La forma clásica (la que vas a encontrar googleando)**

> with DAG(dag_id="mi_dag", schedule=None, ...) as dag:
>
> a = PythonOperator(task_id="a", python_callable=funcion_a)
>
> b = PythonOperator(task_id="b", python_callable=funcion_b)
>
> a \>\> b

Sigue siendo válido y aparece en la mayoría de los tutoriales porque hay mucho material escrito para Airflow 2. Conviene saber leerlo, pero para código nuevo la forma con decoradores es más corta y evita declarar dependencias a mano.

## **3.5 El operador \>\>**

Cuando dos tareas **no se pasan datos** pero sí necesitan un orden, se declara a mano:

> espera \>\> rama
>
> rama \>\> \[novedad, congelado\]

Se lee "espera va antes que rama". La lista significa que rama va antes que las dos.

> **La regla:** si entre dos tareas viajan datos, la dependencia sale sola; si no viajan datos, hay que declararla. En fifa_ingest las únicas dependencias escritas a mano son las de las tareas de decisión, que no se pasan nada entre sí: sólo ordenan el flujo.

# **4. Operadores, hooks y funciones propias**

## **4.1 Qué es un operador**

Un **operador** es una plantilla de tarea: encapsula una acción frecuente para no escribirla. Hacer una petición HTTP, correr una consulta SQL, ejecutar un comando de shell, mover un archivo. Con un operador no se programa la acción, **se la configura**:

> listar = HttpOperator(
>
> task_id="listar_pokemon",
>
> http_conn_id="pokeapi",
>
> endpoint="api/v2/pokemon",
>
> method="GET",
>
> response_filter=lambda r: \[x\["url"\] for x in r.json()\["results"\]\],
>
> )

No hay una sola línea que abra una conexión, mande el pedido o maneje la respuesta. Todo eso lo pone el operador.

### **response_filter: qué se guarda de la respuesta**

Un operador HTTP recibe un objeto Response: código de estado, encabezados, cuerpo, la conexión. **Ese objeto no se puede guardar en XCom**, porque no es serializable.

response_filter es la función que decide **qué parte de la respuesta sobrevive**. Recibe el Response y devuelve lo que se quiere conservar:

> response_filter=lambda r: \[x\["url"\] for x in r.json()\["results"\]\]

Traducido: de todo lo que devolvió la API, quedate sólo con la lista de URLs. Eso es lo que va a XCom y lo que recibe la tarea siguiente.

Sin response_filter hay dos problemas. El obvio: error de serialización. El menos obvio: aun cuando funcione, estarías guardando el JSON entero en la base de Airflow cuando quizás sólo necesitás tres campos. Es la primera aparición de una idea que vuelve en la sección 7: **decidir conscientemente qué viaja entre tareas**.

## **4.2 Hooks: la capa de abajo**

Un operador no hace la magia solo: por dentro usa un **hook**, la pieza que sabe hablar con un sistema externo y sabe leer una conexión. Cuando el operador prefabricado no alcanza (hay que recorrer una lista, filtrar, decidir), se usa el hook directamente desde la función propia, sin perder la conexión:

> @task
>
> def traer_atributos(urls: list\[str\]) -\> list\[dict\]:
>
> hook = HttpHook(method="GET", http_conn_id="pokeapi")
>
> for url in urls:
>
> d = hook.run(endpoint=f"api/v2/pokemon/{pid}").json()

En resumen: HttpOperator usa un hook por dentro y vos sólo lo configurás; HttpHook lo usás vos cuando necesitás lógica propia.

## **4.3 Las tres opciones, y cuándo va cada una**

| **Escribís**              | **Cuándo**                                                                     | **Ejemplo en pokemon_api**   |
|---------------------------|--------------------------------------------------------------------------------|------------------------------|
| **Operador prefabricado** | La acción es estándar y alguien ya la resolvió bien                            | listar (líneas 65-73)        |
| **@task** + hook          | Necesitás lógica propia, pero querés reusar la conexión y el manejo de errores | traer_atributos (79-108)     |
| **@task** pelado          | No hay sistema externo de por medio: transformar, validar, guardar             | combinar_y_guardar (134-168) |

Los tres casos están en un solo archivo de sesenta líneas.

## **4.4 Providers: qué viene y qué se instala**

Airflow trae un núcleo chico. Todo lo que sea "hablar con algo de afuera" vive en providers, paquetes de Python separados. Cada uno aporta tres cosas: operadores, hooks y tipos de conexión que aparecen en el desplegable de la interfaz.

**Sólo dos vienen instalados de fábrica:**

| **Provider**                        | **Qué trae**                                                      |
|-------------------------------------|-------------------------------------------------------------------|
| apache-airflow-providers-standard   | PythonOperator, BashOperator, EmptyOperator, los sensores básicos |
| apache-airflow-providers-common-sql | La base para todo lo que sea SQL                                  |

El resto se agrega al requirements.txt. Los que más se usan:

| **Provider**                       | **Para qué**                                        |
|------------------------------------|-----------------------------------------------------|
| -http                              | APIs REST. Es el que usa pokemon_api                |
| -postgres, -mysql                  | Bases relacionales: correr consultas, cargar tablas |
| -amazon, -google, -microsoft-azure | Las tres nubes: S3, BigQuery, Blob Storage          |
| -docker, -cncf-kubernetes          | Correr una tarea dentro de un contenedor            |
| -slack, -smtp                      | Avisar cuando algo falla                            |
| -sftp, -ftp                        | Mover archivos por los protocolos de siempre        |

Para agregar uno alcanza con la línea y reconstruir el entorno:

> apache-airflow-providers-http\>=6.0
>
> **Tropiezo clásico:** esa línea es la que hace que HttpOperator exista. Sin ella el import falla, y el error no dice "te falta un provider": dice ModuleNotFoundError.
>
> **En tu proyecto integrador:** antes de escribir código para hablar con tu fuente, fijate si hay un provider que ya lo resuelva. Si tu dato está en una base Postgres o en un bucket de S3, no escribas el cliente a mano.

# **5. Conexiones**

## **5.1 Qué problema resuelve**

Una **Connection** es configuración guardada fuera del código: un host, un puerto, un usuario, una contraseña, un token. Resuelve tres cosas:

- **No poner secretos en el repositorio.** Es la razón principal. Una API key hardcodeada en un .py termina en Git, y de ahí no se va nunca más.

- **Cambiar de entorno sin tocar código.** El mismo DAG apunta a la base de desarrollo o a la de producción según qué conexión encuentre.

- **Compartir configuración entre DAGs.** Si diez pipelines usan la misma base, la dirección se escribe una vez.

## **5.2 Dónde se definen**

Desde la interfaz web, desde variables de entorno, o —en desarrollo local— desde airflow_settings.yaml, que Astro lee al arrancar:

> airflow:
>
> connections:
>
> \- conn_id: pokeapi
>
> conn_type: http
>
> conn_host: pokeapi.co
>
> conn_schema: https

Por eso la conexión pokeapi ya existe la primera vez que se levanta el entorno: no hay que darla de alta a mano.

## **5.3 Cuándo NO hace falta una conexión**

Este punto se pasa por alto. fifa_ingest **no usa ninguna**, y no es un descuido:

- No hay secreto que guardar: sofifa es público.

- No hay destino que cambie entre entornos: siempre es el mismo sitio.

- Lo único que podría vivir en la conexión —la URL base— no es realmente configurable, porque el código que parsea el HTML está atado a ese sitio. Si apuntás la conexión a otro lado, el parseo se rompe igual.

Y en pokemon_api la conexión **tampoco guarda un secreto**: la PokéAPI es abierta. Ahí no está para proteger nada, sino porque HttpOperator está diseñado para recibir un http_conn_id.

> **La regla:** no hay que crear una conexión para todo. Hay que crearla cuando resuelve un problema que tenés. Si tu fuente pide API key, token o usuario y contraseña, esa credencial va en una Connection, nunca en el .py.

# **6. El contexto de ejecución**

## **6.1 Qué es**

Cuando Airflow ejecuta una tarea, le pasa información sobre **esa ejecución puntual**: qué DAG es, qué corrida, con qué parámetros, en qué fecha lógica. Eso es el contexto, y se accede declarando \*\*context en la función.

> @task
>
> def save(ruta: str, \*\*context) -\> str:
>
> dag_run = context\["dag_run"\]
>
> params = context\["params"\]

## **6.2 Las claves que más vas a usar**

| **Clave**          | **Qué trae**                                         |
|--------------------|------------------------------------------------------|
| ds                 | La fecha lógica como texto, 2026-08-19               |
| logical_date       | Lo mismo pero como datetime                          |
| run_id             | Identificador único de la corrida                    |
| dag_run            | El objeto de la corrida: tipo, estado, fechas        |
| ti / task_instance | La instancia de esta tarea. Por acá se accede a XCom |
| params             | Los parámetros con los que se disparó                |

## **6.3 Cuidado con ds**

ds **no siempre existe**. Sólo tiene sentido cuando el DAG tiene schedule y por lo tanto un intervalo de datos asociado. Si el DAG corre a demanda, pedir context\["ds"\] levanta KeyError.

La forma robusta es sacar la fecha del DagRun:

> dag_run = context\["dag_run"\]
>
> momento = dag_run.logical_date or dag_run.run_after
>
> ds = momento.date().isoformat()
>
> **Por qué es traicionero:** es un error clásico al pasar de Airflow 2 a 3 y **no aparece siempre**: un DAG con schedule lo trae, uno a demanda no. Por eso conviene no depender de ds y sacar la fecha del DagRun, que existe en los dos casos.

## **6.4 y 6.5 Plantillas Jinja vs. contexto**

Hay dos formas de que una tarea sepa algo de la corrida en la que está, y conviene no confundirlas.

**Desde el contexto:** la función recibe \*\*context y lee lo que necesita. Es Python común, corre cuando la tarea se ejecuta.

> @task
>
> def save(\*\*context):
>
> ds = context\["dag_run"\].logical_date.date().isoformat()

**Con una plantilla Jinja:** texto con {{ }} adentro.

> data={"limit": "{{ params.cantidad }}", "offset": "0"}

La diferencia de fondo es *cuándo* se resuelve cada una. Cuando Airflow lee el archivo .py para registrar el DAG, ejecuta el código de definición: crea el objeto HttpOperator con los argumentos que le pasaste. En ese momento **la corrida todavía no existe**: no hay fecha, no hay parámetros. La plantilla resuelve eso: se guarda como texto y **Airflow la reemplaza justo antes de ejecutar la tarea**.

|                        | **Contexto (\*\*context)**              | **Plantilla Jinja ({{ }})**            |
|------------------------|-----------------------------------------|----------------------------------------|
| **Dónde se usa**       | Adentro de una función @task            | En los argumentos de un operador       |
| **Cuándo se resuelve** | Al ejecutar, es código normal           | Al ejecutar, pero lo reemplaza Airflow |
| **Qué se puede hacer** | Cualquier cosa: if, cálculos, funciones | Interpolar valores y poco más          |

**La regla práctica.** Si estás escribiendo el cuerpo de un @task, usá el contexto: es Python y podés hacer lo que quieras. Si estás configurando un operador prefabricado, no tenés dónde poner código: ahí va la plantilla.

Las variables más usadas en plantillas: {{ ds }} para la fecha, {{ params.lo_que_sea }} para los parámetros, {{ ti.xcom_pull(...) }} para el resultado de otra tarea.

> **Un detalle que sorprende:** no todos los argumentos de un operador aceptan plantillas. Cada operador declara cuáles sí, en un atributo llamado template_fields. Si ponés {{ ds }} en un campo que no está en esa lista, no falla: te queda el texto literal {{ ds }} en el dato. Es de esos errores que cuesta ver.

# **7. XCom: pasar datos entre tareas**

## **7.1 Qué es**

Cada tarea corre en su propio proceso. No comparten memoria, así que no alcanza con una variable de Python. **XCom** es el mecanismo que provee Airflow: una tarea guarda un valor, otra lo lee.

Con TaskFlow es transparente: si una función decorada devuelve algo y otra lo recibe como argumento, eso viajó por XCom. También se puede usar explícitamente:

> context\["ti"\].xcom_push(key="meta", value=meta)
>
> meta = context\["ti"\].xcom_pull(task_ids="wait_for_source")

## **7.2 Cuándo NO usar XCom**

**Los XCom se guardan en la base de metadatos de Airflow.** Esa base está pensada para registrar el estado de las corridas, no para almacenar datos. Si una tarea devuelve dieciocho mil filas, esas filas se serializan y se escriben en la base. Con suficiente volumen, **el scheduler se cae**.

> **La regla práctica:** por XCom viajan **metadatos, no datos**. Rutas, identificadores, banderas, conteos. Cuando el volumen crece, la tarea escribe a disco y devuelve **la ruta**.

Los dos DAGs muestran los dos lados. pokemon_api pasa listas de diccionarios entre tareas, y está perfecto: son veinte filas. fifa_ingest escribe a disco y pasa rutas —dos veces, una por capa: land_bronze devuelve dónde quedaron las páginas crudas y refine_silver devuelve dónde quedó el CSV de su liga.

### **Los números que conviene recordar**

| **Dato**                      | **Valor**                                                       |
|-------------------------------|-----------------------------------------------------------------|
| Peso de una página de sofifa  | ≈ 760 KB                                                        |
| Páginas del catálogo completo | 345                                                             |
| Pasarlas por XCom sería…      | **260 MB** metidos en la base de metadatos, en una sola corrida |
| En disco y comprimidas ocupan | 16,5 MB                                                         |

# **8. Tareas dinámicas**

## **8.1 El problema**

Muchas veces **no sabés cuántas tareas vas a necesitar hasta que corrés**: depende de cuántos archivos haya, cuántas tablas, cuántas ligas. fifa_ingest tiene ese problema: sofifa publica un catálogo de ligas que cambia entre versiones del juego — la actualización de agosto de 2025 tenía 51 ligas y la de julio de 2026 tiene 52. Escribir 52 tareas a mano sería, además de tedioso, incorrecto.

## **8.2 .expand()**

La solución es el **dynamic task mapping**: se escribe *una* tarea y se le pide a Airflow que la instancie una vez por elemento de una lista.

> ligas = discover_leagues() \# devuelve 52 diccionarios
>
> bronces = land_bronze.expand(league=ligas) \# crea 52 instancias
>
> parciales = refine_silver.expand(lote=bronces) \# y otras 52, encadenadas

La segunda se expande sobre la salida de la primera: no hay que saber cuántas ligas hay para escribir ninguna de las dos. Airflow crea las instancias **en tiempo de ejecución**, cuando la tarea de arriba ya devolvió la lista.

## **8.3 Que el grafo se lea solo**

Por defecto las instancias mapeadas se numeran: 0, 1, 2… Poco útil cuando querés saber cuál falló. Con map_index_template se les da nombre:

> @task(map_index_template="{{ task.op_kwargs\['league'\]\['league_name'\] }}")
>
> def land_bronze(league: dict) -\> dict:

Con eso, en la interfaz se ve "Premier League" en verde y "Serie A" corriendo, en vez de offset=780.

## **8.4 Paralelismo**

Que haya 52 tareas listas no significa que corran las 52 a la vez. max_active_tasks en el DAG limita cuántas se ejecutan simultáneamente. En fifa_ingest está en **8**, y el número no es arbitrario: se midió contra sofifa. Más de ocho conexiones simultáneas no acelera nada porque el sitio empieza a frenar, y de paso es una descortesía con una fuente gratuita.

# **9. Ramificación y control de flujo**

## **9.1 Elegir el camino en tiempo de ejecución**

@task.branch es una tarea que, en lugar de devolver datos, **devuelve el nombre de la tarea que sigue**:

> @task.branch
>
> def check_source(\*\*context) -\> str:
>
> if meta:
>
> return "has_new_snapshot"
>
> return "load_frozen"

Airflow ejecuta la rama nombrada y marca la otra como skipped. En la interfaz se ve en gris: no falló, simplemente no correspondía.

## **9.2 Trigger rules**

Por defecto una tarea corre cuando **todas** sus tareas de arriba terminaron con éxito: la regla ALL_SUCCESS. Pero no siempre alcanza. validate recibe dos entradas: la de la fuente y la del respaldo, y una de las dos **siempre** viene de una rama salteada. Con la regla por defecto validate no se ejecutaría nunca.

> @task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
>
> def validate(desde_fuente, desde_snapshot):

Se lee: "que ninguna haya fallado y que al menos una haya tenido éxito". **Salteada no es fallada**, así que la condición se cumple.

Situación parecida con check_source, que usa ALL_DONE: corre pase lo que pase con la tarea de arriba, porque su trabajo es justamente manejar el caso en que esa tarea no consiguió nada.

| **Trigger rule**            | **Dónde se usa en fifa_ingest** | **Por qué**                                                           |
|-----------------------------|---------------------------------|-----------------------------------------------------------------------|
| ALL_SUCCESS                 | Por defecto en casi todo        | Todas las de arriba terminaron bien                                   |
| ALL_DONE                    | check_source                    | La tarea de arriba puede quedar en skipped y ese es el caso a manejar |
| NONE_FAILED_MIN_ONE_SUCCESS | validate                        | Recibe dos ramas y una siempre está salteada                          |

## **9.3 Sensores: esperar lo que no controlás**

Un **sensor** es una tarea que espera a que se cumpla una condición, sondeando cada tanto.

> **Malentendido frecuente:** poner un sensor que espere a que estén los 52 archivos parciales antes de consolidar **sería un error**. Esa espera ya está garantizada por la dependencia: consolidate(parciales) no arranca hasta que las 52 instancias terminaron bien. Un sensor ahí sería redundante y agregaría un modo de falla nuevo.

**Los sensores son para lo que está fuera del control del DAG:** un archivo que deja otro sistema, un proceso ajeno que termina, un sitio que vuelve. Adentro del DAG, para eso están las dependencias.

El sensor legítimo de fifa_ingest espera a que **sofifa esté disponible**:

> @task.sensor(poke_interval=300, timeout=1800, mode="reschedule", soft_fail=True)
>
> def wait_for_source(\*\*context) -\> PokeReturnValue:

Sondea cada cinco minutos durante media hora. Un corte de diez minutos ya no arruina la corrida del día. soft_fail=True hace que, al agotarse el tiempo, la tarea quede en skipped y no en failed: no responder no es un error del pipeline, es una condición que sabemos manejar.

## **9.4 poke contra reschedule**

Los dos parámetros que más importan de un sensor son poke_interval (cada cuánto revisa) y mode, que define qué hace **entre** revisión y revisión.

| **Modo**   | **Qué hace entre sondeos**                                                        | **Costo**                                                                                          |
|------------|-----------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| poke       | La tarea se queda ocupando un worker durante toda la espera                       | Con un sensor da igual; con cincuenta esperando, cincuenta workers durmiendo y el pipeline frenado |
| reschedule | La tarea se libera después de cada sondeo y Airflow la vuelve a encolar más tarde | La espera no cuesta un worker                                                                      |

Esa idea —esperar sin ocupar recursos— llevada al extremo son los **deferrable operators**, que delegan la espera a un proceso especializado. Ese proceso es el contenedor triggerer que se ve levantarse con el entorno.

## **9.5 Cortocircuito: no hacer nada, bien**

@task.short_circuit es una tarea que devuelve un booleano. Si devuelve False, **todo lo que está aguas abajo queda en** skipped **y la corrida termina en éxito**.

fifa_ingest corre todos los días, pero sofifa publica un parche cada una o dos semanas. Bajar 18.936 filas a diario sería rehacer el mismo trabajo seis de cada siete veces.

> ultimo = Variable.get("fifa_ultimo_roster", default=None)
>
> if str(actual) == str(ultimo):
>
> return False \# no hay nada que hacer
>
> **Frase para recordar:** la mayoría de las corridas de un pipeline sano **no hacen nada**, y eso está bien. Lo que no está bien es no darse cuenta.

Ahí aparece otra pieza: las **Variables**, valores con nombre guardados en Airflow. Sirven justo para esto: recordar algo entre una corrida y la siguiente.

El cortocircuito tiene **dos excepciones deliberadas**: force=True (se pide explícitamente) y roster fijado (se está pidiendo un snapshot puntual, así que "el último que vi" no es la pregunta correcta).

## **9.6 Diseñar la degradación**

Juntando branching, sensores y cortocircuito, fifa_ingest implementa **tres niveles de degradación**:

| **Nivel** | **Qué hace**                  | **Cuándo entra**                            | **¿Se ve en el grafo?**           |
|-----------|-------------------------------|---------------------------------------------|-----------------------------------|
| 1         | HTTP directo con urllib       | El camino normal, medio segundo por página  | No — dentro de una función Python |
| 2         | Playwright + Chromium         | Si Cloudflare devuelve 403                  | No — dentro de una función Python |
| 3         | Snapshot congelado en el repo | Si sofifa está caído o cambió de estructura | Sí — rama visible                 |

Y antes de degradar, **espera**: si la fuente no responde, el sensor reintenta durante media hora antes de darla por perdida.

> **La regla que ordena todo:** si el dato es **el mismo**, reintentá en silencio; si el dato es **distinto**, hacelo visible. Los dos primeros niveles son la misma página por otra puerta, así que el reintento es transparente. El tercero es una rama porque ahí el dato *es otro* —más viejo— y eso hay que avisarlo.

Una última cosa, que no es sobre Airflow: las decisiones de este DAG (usar urllib y no requests, pasar rutas y no filas, degradar en tres niveles) **no salieron de un libro**. Salieron de chocarse con la fuente: descubrir que Cloudflare filtra por librería, que el scheduler se cae con XCom grandes, que las fichas de jugador pasaron a exigir cuenta. Eso es ingeniería de datos.

# **10. Parámetros de corrida**

Un DAG puede declarar qué se le puede configurar al dispararlo, con Param:

> params={
>
> "mode": Param("subset", enum=\["subset", "full"\],
>
> title="Modo de corrida",
>
> description="subset: la primera página de cada liga..."),
>
> }

Eso hace dos cosas: **valida los valores** y **genera un formulario** en la interfaz. Al entrar al DAG y elegir **Trigger DAG w/ config**, Airflow arma los campos solo: desplegable para los enum, casilla para los booleanos, campo numérico para los enteros. El title y la description son lo que lee quien dispare el DAG, así que vale la pena escribirlos bien.

Es la forma recomendada de correr los DAGs de la materia: **desde la interfaz**. Es más difícil equivocarse que escribiendo un JSON a mano.

### **Los cuatro params de fifa_ingest**

| **Param** | **Valores**                | **Para qué**                                                                                                                         |
|-----------|----------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| mode      | subset / full              | subset: primera página de cada liga (~3.000 jugadores, ~30 s). full: catálogo completo, 18.936 jugadores de 52 ligas, ~1 min y medio |
| roster    | null / entero (ej. 260046) | Id del snapshot de sofifa. Vacío usa el más reciente. Fijarlo hace la corrida reproducible                                           |
| engine    | auto / http / browser      | auto prueba HTTP y cae a navegador si recibe 403                                                                                     |
| force     | booleano                   | Ignora todas las cachés: baja aunque el snapshot no haya cambiado y vuelve a pedir páginas que ya están en bronce                    |

> **Por qué importa roster:** resuelve la **reproducibilidad**. sofifa guarda 46 versiones de su base. Fijando el roster, el DAG produce el mismo dataset hoy que en noviembre.

# **11. Idempotencia**

Una tarea es **idempotente** cuando ejecutarla dos veces deja el mismo resultado que ejecutarla una.

Suena teórico hasta la primera vez que un pipeline se cae por la mitad y hay que volver a correrlo. Si las tareas son idempotentes, se relanza sin pensar. Si no lo son, hay que averiguar qué alcanzó a hacer antes de morir.

| **Tarea**   | **Por qué es idempotente**                                                                                                                                                                                                                                  |
|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| save        | Escribe siempre fifa_AAAA-MM-DD.csv, con la fecha de la corrida. Correrlo dos veces el mismo día **sobrescribe** el archivo; no deja dos. Si numerara los archivos, cada reintento agregaría uno nuevo y el conteo final dependería de cuántas veces falló. |
| land_bronze | La idempotencia sale de **no hacer nada**: chequea si la página ya está en disco antes de pedirla. Correrlo diez veces sobre el mismo snapshot deja exactamente el mismo bronce que correrlo una, y hace nueve veces menos requests.                        |

Es la diferencia entre una tarea que *puede* repetirse sin romper nada y una que además *no cuesta* repetir.

Los **reintentos** dependen de esto. retries=2 sólo es seguro si la tarea es idempotente:

> @task(retries=2, retry_delay=pendulum.duration(seconds=30))

# **12. El entorno local con Astro CLI**

## **12.1 Qué es**

Levantar Airflow a mano implica una base de datos, varios procesos y bastante configuración. **Astro CLI** empaqueta todo eso en un comando, apoyándose en Docker.

> astro dev start

La primera vez tarda varios minutos: descarga la imagen base y construye la propia. Después arranca en segundos.

## **12.2 La estructura del proyecto**

> airflow-fifa/
>
> ├── dags/ \# los .py que Airflow lee
>
> ├── include/ \# todo lo demás: módulos, datos, salidas
>
> ├── tests/ \# pruebas
>
> ├── Dockerfile \# la imagen
>
> ├── requirements.txt \# paquetes de Python
>
> ├── packages.txt \# paquetes del sistema (apt)
>
> └── airflow_settings.yaml \# conexiones, variables y pools locales
>
> **Por qué importa la separación:** el dag-processor parsea dags/ **cada pocos segundos**, así que ahí va sólo la definición del flujo. La lógica pesada vive en include/ y se importa.

## **12.3 Los comandos que vas a usar**

| **Comando**                | **Qué hace**                         |
|----------------------------|--------------------------------------|
| astro dev start            | Levanta el entorno                   |
| astro dev stop             | Lo para, conservando la base         |
| astro dev restart          | Reinicia **y reconstruye la imagen** |
| astro dev kill             | Elimina todo, incluida la base       |
| astro dev ps               | Estado de los contenedores           |
| astro dev logs -f          | Logs en vivo                         |
| astro dev bash --scheduler | Terminal adentro del contenedor      |

**Cuándo hace falta restart:** si tocaste requirements.txt, packages.txt o el Dockerfile. Si sólo cambiaste un DAG o algo de include/, no: esas carpetas están montadas y se recargan solas.

## **12.4 Requisitos de máquina**

Hace falta **Docker Desktop** corriendo y espacio en disco. Números medidos sobre el proyecto de la materia:

| **Qué**                                              | **Cuánto**                           |
|------------------------------------------------------|--------------------------------------|
| Imagen base de Astro Runtime                         | 1,5 GB                               |
| La imagen del proyecto, con Chromium para Playwright | 2,7 GB (comparte 1,2 GB con la base) |
| Base de datos Postgres                               | 0,45 GB                              |
| **Total de imágenes**                                | **≈ 3,5 GB**                         |

Con eso, **6 a 8 GB libres alcanzan cómodo**: las imágenes, las capas intermedias del build y algo de margen. Sacando el bloque de Chromium del Dockerfile, la imagen baja cerca de un giga.

# **13. Ahora abrilo vos (los 7 pasos)**

Parado en la carpeta del proyecto: astro dev start. Cuando termine, abrir localhost:8080 — usuario admin, contraseña admin.

| **\#** | **Qué hacer**                                               | **Qué concepto se ve**                                                                                                                             |
|--------|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| 1      | Despausar y disparar pokemon_api. Mirar la vista Graph.     | traer_atributos y traer_especies se ponen en verde al mismo tiempo. Nadie escribió que fueran en paralelo: salió de que ninguna depende de la otra |
| 2      | Abrir los logs de una tarea (clic en el cuadradito → Logs). | Ahí está todo: los pedidos, los reintentos, lo que imprimió tu código. Es el primer lugar a mirar cuando algo falla                                |
| 3      | fifa_ingest en modo subset, vía Trigger DAG w/ config.      | Aparecen **52 instancias de la misma tarea**, cada una con el nombre de su liga, corriendo de a ocho. Eso es .expand() en vivo                     |
| 4      | Dispararlo de nuevo sin cambiar nada.                       | Termina en segundos y casi todo queda en gris. No falló: has_new_snapshot se dio cuenta de que el snapshot no cambió y cortó                       |
| 5      | Modo full con roster=260046.                                | 18.936 jugadores de 52 ligas, ~1 min y medio. land_bronze y refine_silver se pisan: unas ligas bajan mientras otras ya se parsean                  |
| 6      | Volver a dispararlo igual.                                  | land_bronze termina casi al instante y en los logs se lee *0 pedidas a sofifa*. Eso es lo que compra guardar el crudo                              |
| 7      | Ir a include/output/.                                       | bronze/ con el HTML comprimido, silver/ con las filas tipadas, y el CSV fechado que produjo save                                                   |

# **Apéndice A · De Airflow 2 a Airflow 3**

Casi todo lo que se encuentra googleando es de Airflow 2. Esta es la traducción de lo que más aparece:

| **Airflow 2**                                       | **Airflow 3**                                               |
|-----------------------------------------------------|-------------------------------------------------------------|
| from airflow.decorators import dag, task            | from airflow.sdk import dag, task                           |
| from airflow.operators.python import PythonOperator | from airflow.providers.standard.operators.python import ... |
| from airflow.operators.bash import BashOperator     | from airflow.providers.standard.operators.bash import ...   |
| from airflow.operators.dummy import DummyOperator   | EmptyOperator (el módulo dummy ya no existe)                |
| from airflow.utils.trigger_rule import TriggerRule  | from airflow.task.trigger_rule import TriggerRule           |
| schedule_interval=...                               | schedule=...                                                |
| dag.schedule_interval                               | dag.schedule                                                |
| context\["execution_date"\]                         | context\["logical_date"\]                                   |
| context\["prev_ds"\], context\["next_ds"\]          | Ya no existen                                               |
| context\["conf"\]                                   | Ya no existe                                                |
| Servicio webserver                                  | Servicio api-server                                         |
| El scheduler parsea los DAGs                        | Lo hace el dag-processor, aparte                            |

# **Apéndice B · Errores frecuentes**

| **Síntoma**                                 | **Causa y solución**                                                                                                                                                                                                                                                                           |
|---------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **El DAG no aparece en la interfaz**        | Esperar unos segundos: el dag-processor escanea cada tanto. Si sigue sin aparecer es un error de parseo, y Airflow lo muestra en un banner rojo arriba de la lista de DAGs (clic ahí para ver el traceback). **La causa más común es que falte la llamada a la función al final del archivo.** |
| ModuleNotFoundError al importar un operador | Falta el provider en requirements.txt, y después astro dev restart.                                                                                                                                                                                                                            |
| Las tareas quedan en queued y no arrancan   | El scheduler se cayó. En Docker Desktop, mirar los logs del contenedor scheduler.                                                                                                                                                                                                              |
| KeyError: 'ds'                              | El DAG no tiene schedule. Sacar la fecha del DagRun.                                                                                                                                                                                                                                           |
| PermissionError al escribir en include/     | El contenedor corre como usuario astro y la carpeta puede ser de root. En Linux o WSL: chmod -R 777 include/output.                                                                                                                                                                            |
| **Todo se cuelga sin mensaje**              | Fijarse el espacio en disco. Docker se traba en silencio cuando no puede escribir.                                                                                                                                                                                                             |

# **Glosario mínimo**

| **Término**              | **Definición**                                                                                   |
|--------------------------|--------------------------------------------------------------------------------------------------|
| **DAG**                  | Directed Acyclic Graph. Un pipeline: tareas con dependencias dirigidas y sin ciclos              |
| **Tarea / task**         | Unidad de trabajo del DAG. Se define con @task o instanciando un operador                        |
| **Operador**             | Plantilla de tarea que encapsula una acción frecuente. Se configura, no se programa              |
| **Hook**                 | La capa de abajo del operador: sabe hablar con un sistema externo y leer una conexión            |
| **Provider**             | Paquete de Python que agrega integraciones (operadores, hooks, tipos de conexión)                |
| **Connection**           | Configuración guardada fuera del código: host, puerto, usuario, contraseña, token                |
| **Variable**             | Valor con nombre guardado en Airflow. Sirve para recordar algo entre corridas                    |
| **XCom**                 | Cross-communication. Mecanismo para pasar valores entre tareas, vía base de metadatos            |
| **Contexto**             | Información de la ejecución puntual que Airflow pasa a la tarea (\*\*context)                    |
| **Plantilla Jinja**      | Texto con {{ }} que Airflow reemplaza justo antes de ejecutar la tarea                           |
| **template_fields**      | Atributo del operador que declara qué argumentos aceptan plantillas                              |
| **Sensor**               | Tarea que espera a que se cumpla una condición externa, sondeando cada tanto                     |
| **Trigger rule**         | Regla que decide cuándo una tarea puede correr según el estado de las de arriba                  |
| **Branching**            | @task.branch: devuelve el nombre de la tarea que sigue; las otras quedan skipped                 |
| **Short circuit**        | @task.short_circuit: si devuelve False, todo aguas abajo queda skipped y la corrida termina bien |
| **Dynamic task mapping** | .expand(): una tarea en el código, N instancias en la corrida                                    |
| **Idempotencia**         | Ejecutar dos veces deja el mismo resultado que ejecutar una                                      |
| **Catchup**              | Si al arrancar el DAG debe recuperar las corridas que se perdió                                  |
| **Deferrable operator**  | Operador que delega la espera al proceso triggerer, sin ocupar un worker                         |
| **Modelo medallón**      | Bronce (crudo) → plata (tipado y validado) → oro (features y agregados)                          |

# **Banco de preguntas posibles**

Ordenado por tipo. Las respuestas están abajo de cada pregunta, así que si querés autoevaluarte tapá con la mano o borrá las líneas que empiezan con "R." antes de imprimir.

## **A · Conceptuales cortas**

**P1. ¿Qué es Airflow y qué NO es?**

> **R.** Es un orquestador de flujos de trabajo: decide qué se ejecuta, cuándo, en qué orden y qué hacer si algo falla. No es un motor de procesamiento: no reemplaza a pandas ni a una base de datos. Si el pipeline transforma un millón de filas, pandas las transforma; Airflow se ocupa del orden, los reintentos, los tiempos y los avisos.

**P2. ¿Qué significa cada palabra de "DAG" y qué implica?**

> **R.** Grafo: hay tareas y relaciones entre ellas. Dirigido: las relaciones tienen sentido (A antes que B). Acíclico: no puede haber ciclos — si A depende de B y B de A, no hay forma de empezar y Airflow rechaza el DAG directamente.

**P3. ¿Qué NO define un DAG?**

> **R.** En qué máquina corre cada tarea, cuánto tarda, y qué pasa si una falla. Todo eso es configuración y se resuelve aparte.

**P4. Nombrá los procesos de Airflow 3 y qué hace cada uno.**

> **R.** dag-processor (lee y parsea los .py de dags/), scheduler (decide qué tarea está lista y la manda a ejecutar), api-server (interfaz web y API), triggerer (esperas asincrónicas) y la metadata DB (el estado de todo). Se coordinan a través de la base de datos, nunca hablándose directo entre ellos.

**P5. ¿Por qué un DAG nuevo tarda unos segundos en aparecer en la interfaz?**

> **R.** Porque el dag-processor es un proceso separado que escanea la carpeta cada tanto. No está roto: está esperando el próximo escaneo.

**P6. Diferenciá Apache Airflow, providers, Astro Runtime, Astro CLI y plugins.**

> **R.** Airflow es el orquestador libre de la Apache Software Foundation. Los providers son paquetes de Python que agregan integraciones (operadores, hooks, tipos de conexión). Astro Runtime es una imagen de Docker con Airflow ya armado, y Astro CLI es la herramienta que la levanta — las dos son de Astronomer y no son Airflow. Los plugins extienden la interfaz de Airflow y son raros en la práctica.

**P7. ¿Qué es un operador y qué es un hook? ¿Cómo se relacionan?**

> **R.** El operador es una plantilla de tarea que encapsula una acción frecuente: no la programás, la configurás. Por dentro usa un hook, que es la pieza que sabe hablar con el sistema externo y leer la conexión. Cuando el operador prefabricado no alcanza, se usa el hook directamente desde una función propia, sin perder la conexión.

**P8. ¿Para qué sirve response_filter?**

> **R.** Decide qué parte de la respuesta HTTP sobrevive y va a XCom. El objeto Response entero no es serializable, así que sin response_filter hay error de serialización; y aun funcionando, guardaría el JSON completo en la base de metadatos cuando quizás sólo necesitás tres campos.

**P9. ¿Qué problemas resuelve una Connection?**

> **R.** Tres: no poner secretos en el repositorio (la principal), cambiar de entorno sin tocar código, y compartir configuración entre DAGs.

**P10. ¿Qué es XCom y cuál es su regla de oro?**

> **R.** Es el mecanismo para pasar valores entre tareas, que corren en procesos distintos y no comparten memoria. La regla: por XCom viajan metadatos, no datos — rutas, identificadores, banderas, conteos. Se guarda en la base de metadatos, que no está pensada para almacenar datos; con suficiente volumen el scheduler se cae.

**P11. ¿Qué es el contexto de ejecución y cómo se accede?**

> **R.** Es la información sobre esa ejecución puntual (qué DAG, qué corrida, qué parámetros, qué fecha lógica) que Airflow pasa a la tarea. Se accede declarando \*\*context en la función. Claves más usadas: ds, logical_date, run_id, dag_run, ti, params.

**P12. ¿Qué es un sensor y para qué se usa?**

> **R.** Una tarea que espera a que se cumpla una condición, sondeando cada tanto. Se usa para lo que está fuera del control del DAG: un archivo que deja otro sistema, un proceso ajeno, un sitio que vuelve. Para esperar a otra tarea del mismo DAG no hace falta un sensor: para eso están las dependencias.

**P13. ¿Qué diferencia hay entre mode="poke" y mode="reschedule"?**

> **R.** En poke la tarea ocupa un worker durante toda la espera. En reschedule se libera después de cada sondeo y Airflow la vuelve a encolar. Con un sensor da igual; con cincuenta esperando, es la diferencia entre un scheduler sano y uno tapado.

**P14. ¿Qué es idempotencia y por qué importa?**

> **R.** Una tarea es idempotente cuando ejecutarla dos veces deja el mismo resultado que ejecutarla una. Importa porque es lo que hace seguros los reintentos: si es idempotente, se relanza sin pensar; si no, hay que averiguar qué alcanzó a hacer antes de morir.

**P15. ¿Qué hace catchup=True?**

> **R.** Al arrancar, Airflow intenta recuperar todas las corridas que se perdió desde start_date. A veces es lo que querés (reprocesar un histórico) y a veces es una avalancha. Los dos DAGs de la materia lo tienen en False.

**P16. ¿Qué es .expand() y cuándo se usa?**

> **R.** Dynamic task mapping: se escribe una tarea y Airflow la instancia una vez por elemento de una lista, **en tiempo de ejecución**. Se usa cuando no sabés cuántas tareas vas a necesitar hasta que corrés — en fifa_ingest, 52 ligas hoy y 51 en la versión anterior.

**P17. ¿Qué es map_index_template?**

> **R.** Un template que le pone nombre a cada instancia mapeada. Sin él, la interfaz muestra 0, 1, 2…; con él muestra "Premier League", "Serie A", y el grafo se lee solo.

**P18. ¿Qué hace @task.branch y en qué estado quedan las ramas no elegidas?**

> **R.** Devuelve el nombre de la tarea que sigue en vez de datos. Airflow ejecuta esa rama y marca las otras como skipped — en gris en la interfaz. Skipped no es failed.

**P19. ¿Qué hace @task.short_circuit?**

> **R.** Devuelve un booleano. Si devuelve False, todo lo que está aguas abajo queda en skipped y la corrida termina **en éxito**. Es la forma correcta de "no hacer nada".

**P20. ¿Qué son las Variables de Airflow?**

> **R.** Valores con nombre guardados en Airflow. Sirven para recordar algo entre una corrida y la siguiente — por ejemplo fifa_ultimo_roster, que guarda el último snapshot procesado con éxito.

**P21. ¿Qué son las tres capas del modelo medallón y cuáles implementa fifa_ingest?**

> **R.** Bronce (crudo, sin interpretar), plata (filas tipadas y validadas) y oro (features derivadas, agregados). fifa_ingest implementa las dos primeras, y no como convención de nombres sino como dos tareas distintas que se ven en el grafo. El oro se construye en las unidades 3 y 4 sobre esa misma plata.

**P22. ¿Para qué sirve Param en un DAG?**

> **R.** Declara qué se puede configurar al dispararlo. Hace dos cosas: valida los valores y genera un formulario en la interfaz (desplegable para enum, casilla para booleanos, campo numérico para enteros), usando title y description.

## **B · De diseño y criterio (las de "por qué")**

Son las más probables en un oral: el apunte insiste en que ninguna decisión de diseño es capricho.

**P23. ¿Por qué pokemon_api usa XCom y fifa_ingest pasa rutas de archivos?**

> **R.** Por volumen. pokemon_api mueve 20 filas: entra cómodo en la base de metadatos. fifa_ingest mueve 18.936 filas y páginas de 760 KB: pasar las 345 páginas del catálogo por XCom serían 260 MB en la base en una sola corrida (en disco y comprimidas ocupan 16,5 MB). Con ese volumen el scheduler se cae.

**P24. ¿Por qué fifa_ingest NO usa ninguna Connection, si pokemon_api sí?**

> **R.** Porque no resuelve ningún problema ahí: no hay secreto que guardar (sofifa es público), no hay destino que cambie entre entornos, y la URL base no es realmente configurable porque el parseo está atado a ese sitio. En pokemon_api la conexión *tampoco* guarda un secreto: está porque HttpOperator está diseñado para recibir un http_conn_id.

**P25. ¿Por qué guardar el HTML crudo en bronce si al final lo que querés es la tabla?**

> **R.** Dos razones: (1) la fuente se toca una vez por dato, no una vez por corrida — la segunda corrida sobre el mismo snapshot no genera ni una request; (2) un bug en el parseo se arregla sin volver a la fuente — se corrige refine_silver y se reprocesa lo que ya está en disco. Sin bronce, si el sitio cambió en el medio, los datos viejos no se recuperan nunca más.

**P26. ¿Por qué el paralelismo está limitado a 8 y no a 52?**

> **R.** Porque se midió contra sofifa: más de ocho conexiones simultáneas no acelera nada, el sitio empieza a frenar. Y de paso es una descortesía con una fuente gratuita.

**P27. ¿Por qué los dos primeros niveles de degradación no se ven en el grafo y el tercero sí?**

> **R.** Porque los dos primeros (urllib y Playwright) son la misma página por otra puerta: el dato es el mismo, así que el reintento es transparente y no hay decisión que comunicar. El tercero (snapshot congelado) devuelve un dato distinto, más viejo, y eso hay que avisarlo. La regla: si el dato es el mismo, reintentá en silencio; si es distinto, hacelo visible.

**P28. ¿Por qué validate necesita NONE_FAILED_MIN_ONE_SUCCESS?**

> **R.** Porque recibe dos entradas (la de la fuente y la del respaldo) y una de las dos **siempre** viene de una rama salteada. Con ALL_SUCCESS nunca se ejecutaría. La regla dice "que ninguna haya fallado y al menos una haya tenido éxito", y skipped no es failed.

**P29. ¿Por qué check_source usa ALL_DONE?**

> **R.** Porque su tarea de arriba (el sensor) puede quedar en skipped, y ese es justamente el caso que tiene que manejar. Con la regla por defecto nunca correría cuando más falta hace.

**P30. ¿Por qué el DAG corre todos los días si sofifa publica un parche cada una o dos semanas?**

> **R.** Porque mirar la fuente es barato y bajarla no. El cortocircuito has_new_snapshot compara contra una Variable y, si el roster no cambió, corta: la corrida termina en éxito sin hacer nada. Bajar 18.936 filas a diario sería rehacer el mismo trabajo seis de cada siete veces.

**P31. ¿Por qué sería un error poner un sensor esperando los 52 parciales antes de consolidate?**

> **R.** Porque esa espera ya está garantizada por la dependencia: consolidate(parciales) no arranca hasta que las 52 instancias terminaron bien. El sensor sería redundante y agregaría un modo de falla nuevo. Los sensores son para lo que está fuera del control del DAG.

**P32. ¿Por qué fijar el param roster importa?**

> **R.** Por reproducibilidad. sofifa guarda 46 versiones de su base; fijando el roster, el DAG produce el mismo dataset hoy que en noviembre. Además es una de las dos excepciones deliberadas al cortocircuito: si pedís un snapshot puntual, "el último que vi" no es la pregunta correcta.

**P33. ¿Por qué el respaldo congelado NO es bronce?**

> **R.** Porque es plata: ya está parseado y tipado. Sirve para salvar la corrida de hoy, pero no permite reprocesar nada. Un respaldo de plata te salva la corrida; el bronce te salva de un bug en el parser.

**P34. ¿Por qué dags/ e include/ están separados?**

> **R.** Porque el dag-processor parsea dags/ cada pocos segundos. Ahí va sólo la definición del flujo; la lógica pesada vive en include/ y se importa.

## **C · Multiple choice**

Marcá una sola opción. La clave de respuestas está al final de esta sección.

**P35. El DAG no aparece en la interfaz y no hay banner de error. Lo más probable es que…**

> a\) falte un provider en requirements.txt
>
> b\) falte la llamada a la función al final del archivo
>
> c\) el scheduler esté caído
>
> d\) falte declarar las dependencias con \>\>

**P36. Una tarea devuelve un DataFrame de 18.936 filas y la siguiente lo recibe como argumento. ¿Qué pasa?**

> a\) Airflow lo pasa por memoria compartida
>
> b\) Se serializa y se escribe en la base de metadatos, con riesgo de tumbar el scheduler
>
> c\) Airflow lo guarda automáticamente en disco
>
> d\) Falla siempre por no ser serializable

**P37. Un DAG con schedule=None pide context\["ds"\]. Resultado:**

> a\) Devuelve la fecha de hoy
>
> b\) Devuelve None
>
> c\) Levanta KeyError
>
> d\) Devuelve la start_date

**P38. ¿Cuál de estas NO es responsabilidad de Airflow?**

> a\) Reintentar una tarea que falló
>
> b\) Registrar cuánto tardó cada tarea
>
> c\) Transformar un millón de filas
>
> d\) Decidir el orden de ejecución

**P39. Modificaste requirements.txt. ¿Qué comando corresponde?**

> a\) astro dev start
>
> b\) astro dev stop
>
> c\) astro dev restart
>
> d\) Ninguno, se recarga solo

**P40. Una tarea @task.branch devuelve "load_frozen". La rama "has_new_snapshot" queda en estado…**

> a\) failed
>
> b\) skipped
>
> c\) upstream_failed
>
> d\) queued

**P41. El propósito principal de una Connection es…**

> a\) Acelerar las peticiones HTTP
>
> b\) Evitar poner secretos en el repositorio
>
> c\) Definir el schedule del DAG
>
> d\) Limitar el paralelismo

**P42. Pusiste {{ ds }} en un argumento de un operador y en el dato aparece literalmente "{{ ds }}". Causa:**

> a\) El DAG no tiene schedule
>
> b\) Falta importar Jinja
>
> c\) Ese argumento no está en template_fields del operador
>
> d\) Hay que usar {% ds %}

**P43. mode="reschedule" en un sensor sirve para…**

> a\) Reintentar la tarea si falla
>
> b\) No ocupar un worker entre sondeo y sondeo
>
> c\) Reprogramar el DAG entero
>
> d\) Cambiar el poke_interval dinámicamente

**P44. land_bronze corre por segunda vez sobre el mismo snapshot. En los logs vas a ver…**

> a\) El doble de páginas guardadas
>
> b\) 0 páginas pedidas a sofifa
>
> c\) Un error de archivo duplicado
>
> d\) Las páginas se sobrescriben una por una

**P45. ¿Cuál de estos NO viene instalado de fábrica en Airflow?**

> a\) apache-airflow-providers-standard
>
> b\) apache-airflow-providers-common-sql
>
> c\) apache-airflow-providers-http
>
> d\) PythonOperator

**P46. En Airflow 3, el proceso que parsea los archivos .py es…**

> a\) el scheduler
>
> b\) el webserver
>
> c\) el dag-processor
>
> d\) el triggerer

**P47. La tarea save escribe siempre fifa_AAAA-MM-DD.csv. Eso la vuelve…**

> a\) más rápida
>
> b\) idempotente
>
> c\) paralelizable
>
> d\) reproducible entre snapshots

**P48. has_new_snapshot devuelve False. La corrida termina en estado…**

> a\) failed
>
> b\) success, con todo lo de abajo en skipped
>
> c\) upstream_failed
>
> d\) running indefinidamente
>
> **Clave de respuestas:** P35-b · P36-b · P37-c · P38-c · P39-c · P40-b · P41-b · P42-c · P43-b · P44-b · P45-c · P46-c · P47-b · P48-b

## **D · Verdadero o falso (justificá)**

**P49. Airflow reemplaza a pandas para transformar datos.**

> **R.** FALSO. Airflow orquesta; pandas transforma.

**P50. Si dos tareas no están conectadas, corren en paralelo.**

> **R.** VERDADERO. Las dependencias definen el orden; lo no conectado corre en paralelo (sujeto a max_active_tasks).

**P51. Los procesos de Airflow se comunican directamente entre sí.**

> **R.** FALSO. Todo pasa por la base de metadatos.

**P52. Astro CLI es parte de Apache Airflow.**

> **R.** FALSO. Es de Astronomer. astro dev start no es un comando de Airflow.

**P53. Una tarea skipped cuenta como fallada para ALL_SUCCESS.**

> **R.** FALSO en cuanto a "fallada", pero la tarea de abajo con ALL_SUCCESS no corre igual, porque exige éxito de todas. Skipped no es failed, y por eso existe NONE_FAILED_MIN_ONE_SUCCESS.

**P54. El respaldo congelado permite reprocesar el parseo.**

> **R.** FALSO. Es plata, ya parseada. Sólo el bronce permite reprocesar.

**P55. .expand() crea las instancias cuando Airflow parsea el archivo.**

> **R.** FALSO. Las crea en tiempo de ejecución, cuando la tarea de arriba devolvió la lista.

**P56. Toda fuente de datos necesita una Connection.**

> **R.** FALSO. Hay que crearla cuando resuelve un problema: secreto, cambio de entorno o configuración compartida.

**P57. Una corrida que no hace nada es un síntoma de que el DAG está mal.**

> **R.** FALSO. La mayoría de las corridas de un pipeline sano no hacen nada. Lo malo es no darse cuenta.

**P58. retries=2 es seguro en cualquier tarea.**

> **R.** FALSO. Sólo si la tarea es idempotente.

**P59. El objeto Response de una petición HTTP se puede guardar en XCom.**

> **R.** FALSO. No es serializable; para eso está response_filter.

**P60. En Airflow 3 el parámetro se sigue llamando schedule_interval.**

> **R.** FALSO. Ahora es schedule.

## **E · Código y práctica**

**P61. Escribí el esqueleto mínimo de un DAG con TaskFlow que corra a demanda y tenga dos tareas en serie.**

> import pendulum
>
> from airflow.sdk import dag, task
>
> @dag(
>
> dag_id="mi_dag",
>
> schedule=None,
>
> start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
>
> catchup=False,
>
> tags=\["ejemplo"\],
>
> )
>
> def mi_dag():
>
> @task
>
> def extraer() -\> list\[dict\]:
>
> return \[{"id": 1}\]
>
> @task
>
> def guardar(filas: list\[dict\]) -\> str:
>
> return "/ruta/al.csv"
>
> guardar(extraer()) \# la dependencia sale sola
>
> mi_dag() \# SIN esto el DAG no aparece

**P62. Dado este código, dibujá el grafo y decí qué corre en paralelo.**

> urls = listar.output
>
> combinar_y_guardar(traer_atributos(urls), traer_especies(urls))
>
> **R.** listar → (traer_atributos, traer_especies) → combinar_y_guardar. Las dos del medio corren en paralelo porque ninguna depende de la otra. Nadie declaró el paralelismo: salió de la ausencia de dependencia.

**P63. Escribí la forma robusta de obtener la fecha de la corrida, que funcione con y sin schedule.**

> @task
>
> def save(\*\*context) -\> str:
>
> dag_run = context\["dag_run"\]
>
> momento = dag_run.logical_date or dag_run.run_after
>
> ds = momento.date().isoformat()
>
> ...

**P64. Convertí este fragmento de Airflow 2 a Airflow 3.**

> \# Airflow 2
>
> from airflow.decorators import dag, task
>
> from airflow.operators.python import PythonOperator
>
> from airflow.utils.trigger_rule import TriggerRule
>
> with DAG(dag_id="x", schedule_interval="@daily") as dag:
>
> fecha = context\["execution_date"\]
>
> **R.** Se reemplazan los imports por airflow.sdk y airflow.providers.standard.operators.python; TriggerRule pasa a airflow.task.trigger_rule; schedule_interval pasa a schedule; execution_date pasa a logical_date.
>
> \# Airflow 3
>
> from airflow.sdk import dag, task
>
> from airflow.providers.standard.operators.python import PythonOperator
>
> from airflow.task.trigger_rule import TriggerRule
>
> with DAG(dag_id="x", schedule="@daily") as dag:
>
> fecha = context\["logical_date"\]

**P65. Tenés una tarea que baja un archivo pesado y otra que lo procesa. ¿Cómo las conectás sin romper el scheduler?**

> **R.** La primera escribe el archivo a disco y devuelve la ruta (un string). La segunda recibe esa ruta y lee del disco. Por XCom viaja sólo la ruta, que es un metadato.

**P66. Escribí un sensor que espere a que una fuente responda, sondeando cada 5 minutos hasta 30, sin ocupar un worker y sin marcar failed si se agota.**

> @task.sensor(poke_interval=300, timeout=1800, mode="reschedule", soft_fail=True)
>
> def wait_for_source(\*\*context) -\> PokeReturnValue:
>
> try:
>
> ...
>
> return PokeReturnValue(is_done=True, xcom_value=meta)
>
> except Exception:
>
> return PokeReturnValue(is_done=False)

**P67. Tenés que procesar N archivos y N no se sabe hasta correr. Escribí el patrón.**

> archivos = descubrir() \# devuelve una lista
>
> parciales = procesar.expand(item=archivos) \# N instancias
>
> consolidar(parciales) \# espera a las N

**P68. Declarás un Param de tipo enum. ¿Qué gana el usuario que dispara el DAG?**

> **R.** Validación de los valores permitidos y un formulario generado automáticamente en la interfaz (Trigger DAG w/ config) con un desplegable, más el title y la description como ayuda.

## **F · Preguntas trampa y errores frecuentes**

Estas son las que más se prestan a caer en el examen o en la defensa del TP.

**P69. Tu DAG no aparece y no ves ningún error. ¿Qué chequeás, en orden?**

> **R.** (1) Esperar unos segundos: el dag-processor escanea cada tanto. (2) Mirar el banner rojo arriba de la lista de DAGs — ahí está el traceback si hay error de parseo. (3) Verificar que esté la llamada a la función al final del archivo: es la causa más común.

**P70. Copiaste un ejemplo de un tutorial y te tira ModuleNotFoundError. ¿Qué pasó?**

> **R.** Falta el provider en requirements.txt. El error no dice "te falta un provider", pero es eso. Después de agregarlo hace falta astro dev restart (reconstruye la imagen).

**P71. Las tareas quedan en queued y no arrancan nunca.**

> **R.** El scheduler se cayó. En Docker Desktop hay que mirar los logs del contenedor scheduler. Una causa típica de que se caiga: XCom demasiado grandes.

**P72. Te tira KeyError: 'ds'.**

> **R.** El DAG no tiene schedule, así que no tiene intervalo de datos ni fecha lógica. Hay que sacar la fecha del DagRun.

**P73. PermissionError al escribir en include/.**

> **R.** El contenedor corre como usuario astro y la carpeta puede ser de root. En Linux o WSL: chmod -R 777 include/output.

**P74. Todo se cuelga sin ningún mensaje.**

> **R.** Espacio en disco. Docker se traba en silencio cuando no puede escribir. El proyecto pide ~3,5 GB de imágenes y conviene tener 6 a 8 GB libres.

**P75. Cambiaste un DAG y no ves el cambio. ¿Hace falta restart?**

> **R.** No. dags/ e include/ están montadas y se recargan solas (con unos segundos de demora del dag-processor). restart hace falta sólo si tocaste requirements.txt, packages.txt o el Dockerfile.

**P76. ¿Cuál es la diferencia entre astro dev stop y astro dev kill?**

> **R.** stop para el entorno conservando la base de datos; kill elimina todo, incluida la base (perdés conexiones creadas a mano, Variables, historial de corridas).

**P77. Corriste el DAG dos veces el mismo día. ¿Cuántos CSV hay en output?**

> **R.** Uno. save escribe siempre fifa_AAAA-MM-DD.csv con la fecha de la corrida, así que la segunda vez sobrescribe. Es idempotencia.

**P78. ¿En qué caso save NO refresca el respaldo?**

> **R.** En dos: si los datos vinieron del respaldo mismo (sería circular) y si el modo no es full — un subset es una corrida de desarrollo y pisar un respaldo entero con uno parcial sería un retroceso.

# **Checklist de autoevaluación**

Si podés responder cada punto sin mirar el apunte, estás listo.

- Explico en una frase qué hace Airflow y qué no hace.

- Nombro los cinco componentes de la arquitectura y digo cómo se coordinan.

- Distingo Airflow, provider, Astro Runtime, Astro CLI y plugin sin dudar.

- Reproduzco de memoria la tabla comparativa de la sección 2.3 y justifico cada fila.

- Digo cuándo una dependencia sale sola y cuándo hay que escribir \>\>.

- Explico la diferencia entre operador, hook y @task pelado, con un ejemplo de cada uno.

- Justifico cuándo crear una Connection y cuándo no hace falta.

- Explico por qué existen las plantillas Jinja además del contexto.

- Enuncio la regla de XCom y digo qué números la justifican.

- Explico bronce vs. plata y por qué el respaldo congelado no es bronce.

- Escribo el patrón de .expand() sin mirar.

- Explico las tres trigger rules que aparecen en fifa_ingest y por qué cada una.

- Distingo poke de reschedule y digo cuándo importa la diferencia.

- Explico los tres niveles de degradación y por qué sólo uno se ve en el grafo.

- Defino idempotencia y doy los dos ejemplos del apunte.

- Sé qué comando de Astro usar en cada situación.

- Traduzco un fragmento de Airflow 2 a Airflow 3.

- Diagnostico los seis errores frecuentes del apéndice B.

> **La frase de cierre del apunte:** la herramienta se aprende en un apunte; el resto se aprende peleándose con una fuente real, que es exactamente lo que van a hacer en el proyecto integrador.
