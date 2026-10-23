# Publicación de Next.js + FastAPI

Configuración lista para publicar; **esta PR no publica servicios**. La web está en
`web/` y la inferencia en `api/`. El mismo artefacto que genera el notebook 04 sirve
las probabilidades y la duración: no se sustituye por una referencia más pequeña.

## Verificar la API en Docker

Desde la raíz, con `models/modelo_en_vivo.joblib` generado:

```bash
docker build -f deploy/api.Dockerfile -t ajedrez-api .
docker run --rm -p 7860:7860 -e CORS_ORIGINS=http://localhost:3000 ajedrez-api
curl --fail http://localhost:7860/salud
```

La imagen usa Python 3.12 y las versiones del entorno de entrenamiento. Sólo instala
las dependencias de inferencia de `api/requirements-serving.txt`. La aplicación corre
como usuario sin privilegios, escucha en 7860 y tiene un healthcheck en `/salud`.
`.dockerignore` excluye datos, credenciales, notebooks, cachés y modelos de experimentos.
El artefacto final se copia explícitamente y **no entra en Git**.

## API en un Space Docker de Hugging Face

1. Crear un Space con SDK Docker en la cuenta del grupo. Elegir un equipo con memoria
   suficiente para cargar el artefacto y sus historiales; verificar `/salud` antes de
   conectar la web. No crear varios workers, que duplicarían el modelo en memoria.
2. Preparar una carpeta independiente:

   ```bash
   python deploy/prepare_space.py --output /tmp/ajedrez-space
   ```

   El script incluye sólo `api/`, `src/`, `config/config.yaml`, el modelo final,
   el Dockerfile y el README de configuración del Space. Rechaza una carpeta no vacía.
   No copia `.env`, datos, notebooks, historial Git ni modelos de experimentos.
3. Subir el contenido de esa carpeta al repositorio del Space mediante la cuenta del
   grupo. El modelo de 132 MB requiere almacenamiento de archivos grandes de esa plataforma.
4. Configurar `CORS_ORIGINS` con el origen exacto de la web, sin barra final. Para
   varios orígenes, separarlos por comas. Los dominios de previews se agregan
   explícitamente; no se habilitan todos los dominios de Internet.
5. Comprobar `https://<dominio-del-space>/salud`: debe informar 40 columnas y el corte
   temporal del notebook 04. Guardar la URL real en el README al publicar.

El servicio puede necesitar arrancar después de un período de reposo. Antes de la
entrega, abrirlo y verificar una predicción; un arranque pendiente no sirve como demo.

## Web en Vercel

1. Importar el repositorio del grupo. Configurar **Root Directory = `web`**, framework
   Next.js, instalación `npm ci` y construcción `npm run build`.
2. Definir `NEXT_PUBLIC_API_URL=https://<dominio-del-space>`, sin barra final. Es una
   variable pública y se fija al construir la web; cambiarla requiere reconstruir.
3. Publicar y agregar su origen a `CORS_ORIGINS` de la API. No se necesita modificar
   el código ni subir datos o el modelo al frontend.
4. Abrir la URL desde otro dispositivo: portada → Proyecto → desplegables → Explorá
   (filtros y selección) → Trivia (tres respuestas y revelación) → Analizar / Jugar.
   Verificar que los casos fuera de rango muestren el aviso y que la predicción cambie
   al jugar. Probar además el mensaje de servicio no disponible.

Los JSON de `web/public/app/` permiten usar Proyecto, Explorá y Trivia sin llamar a la
API. Jugar y analizar partidas nuevas necesitan que la API esté disponible. El modelo
que publica el grupo debe ser el usado al ejecutar `python -m src.build_app`.
