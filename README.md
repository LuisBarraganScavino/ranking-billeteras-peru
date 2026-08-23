# Ranking Mensual de Billeteras Digitales Perú — extractor automatizado

Script para Big Data S.A.C. que extrae mensualmente, de forma automática, el rating, nº de reseñas, icono y otros datos de las billeteras/apps financieras peruanas en Google Play y App Store, para alimentar el ranking mensual.

## Qué hace y qué NO hace

Este script **solo extrae datos crudos**. No calcula rating ponderado, tendencia, score compuesto, tercios ni hallazgos — eso se sigue generando en el proyecto de Claude "Ranking Mensual de Billeteras Digitales Perú", tomando los archivos que este script produce cada mes.

## Archivos

- `catalogo_billeteras_peru.csv` — las apps a monitorear, con su app_id de Android e iOS (columna vacía si no aplica/no se encontró).
- `extract_ranking.py` — el script de extracción.
- `requirements.txt` — dependencias de Python (incluye Pillow, para procesar los iconos).
- `.github/workflows/ranking-mensual.yml` — el workflow que lo corre solo cada mes.

## Puesta en marcha (una sola vez)

1. **Crea un repositorio en tu cuenta de GitHub** (recomendado: privado). Por ejemplo `ranking-billeteras-peru`.
2. **Sube estos 4 archivos/carpetas** manteniendo la misma estructura de carpetas (el `.github/workflows/` debe quedar tal cual, GitHub lo detecta automáticamente):
   ```
   ranking-billeteras-peru/
   ├── catalogo_billeteras_peru.csv
   ├── extract_ranking.py
   ├── requirements.txt
   └── .github/workflows/ranking-mensual.yml
   ```
   Más fácil: arrastra los archivos a la página web de tu repo nuevo en github.com ("Add file" → "Upload files"), respetando la carpeta `.github/workflows/`.
3. **Verifica los permisos de Actions:** en tu repo, ve a *Settings → Actions → General → Workflow permissions* y marca **"Read and write permissions"**. Esto es necesario para que el workflow pueda hacer commit de los archivos del mes automáticamente. Guarda los cambios.
4. **Prueba una corrida manual:** ve a la pestaña *Actions* de tu repo → selecciona "Ranking mensual de billeteras" → botón *"Run workflow"* → déjalo con el mes vacío (usa el mes actual) → *Run workflow*. Tarda unos minutos (hay una pausa entre cada app y cada tienda, más la descarga de icono, para no saturar Google Play/App Store).
5. Al terminar, revisa que aparecieron **cuatro** archivos nuevos en la raíz del repo: `datos_YYYY-MM.csv` (Android), `datos_YYYY-MM_ios.csv` (iOS), `iconos_YYYY-MM.json` (iconos en base64) y `calidad_servicio_YYYY-MM.csv` (respuesta a reseñas de 1★, solo Android). Abre los CSV y confirma que la mayoría de filas tienen un rating numérico y no "s/d".

Desde ese momento, el workflow corre solo el día 1 de cada mes a las 9am hora Perú — no tienes que hacer nada más. También puedes lanzarlo manualmente cuando quieras desde la pestaña *Actions*.

## Cómo se usa el resultado cada mes

1. Entra al repo, abre `datos_YYYY-MM.csv`, `datos_YYYY-MM_ios.csv`, `iconos_YYYY-MM.json` **y `calidad_servicio_YYYY-MM.csv`** del mes que quieras procesar.
2. Descarga los cuatro (o copia su contenido).
3. Súbelos a tu proyecto de Claude "Ranking Mensual de Billeteras Digitales Perú", junto con el ranking del mes anterior.
4. Claude genera la tabla de ranking, tendencia, tercios, top 5 subidas/caídas, podio con iconos, ranking de Innovación, Calidad de Servicio, hallazgos y el pie de página, listos para publicar.

El archivo de iconos es opcional en la práctica: si por algún motivo no lo subes, el dashboard sigue funcionando igual, solo que usa un avatar con la inicial de cada app en vez del icono real.

## Datos que extrae cada mes

**Android:** rating, nº de reseñas, instalaciones (rango, ej. "500.000+"), **instalaciones reales** (cifra exacta que reporta Play Store internamente), categoría, desarrollador, **versión publicada**, si es gratis, fecha de lanzamiento, fecha de última actualización, e icono.

**iOS:** rating, nº de reseñas, categoría, desarrollador (seller), si es gratis, fecha de lanzamiento, fecha de última actualización de versión, e icono.

**Calidad de servicio (solo Android, `calidad_servicio_YYYY-MM.csv`):** de las 20 reseñas de 1★ más recientes de cada app, cuántas tiene respuesta del desarrollador (`resenas_1estrella_respondidas`), el % que representa (`pct_respondidas`) y el tiempo de respuesta promedio en días (`tiempo_respuesta_promedio_dias`). Es la base de la sección PRO "Calidad de Servicio" del dashboard. Solo Android: Apple no expone públicamente las respuestas de los desarrolladores a reseñas de apps de terceros — esa información solo es accesible al propio dueño de la app vía App Store Connect.

Con la **versión publicada** y la **fecha de última actualización**, a partir de la segunda corrida ya se puede comparar mes a mes si una app cambió de versión — la base del ranking PRO de "Innovación" (qué tan seguido cada institución actualiza su app).

## Notas y limitaciones

- **Android** usa `google-play-scraper`, una librería no oficial (lee el HTML público de Play Store). Es la más usada del ecosistema Python y estable, pero si Google cambia la estructura de su página podría dejar de funcionar para algunas apps — el script no se cae por eso, solo marca esa fila como "s/d" con el motivo del error en la columna `error`.
- **iOS** usa la API oficial y gratuita de Apple (`itunes.apple.com/lookup`), así que es más estable.
- **Instalaciones (rango)** solo existen para Android, y siempre en rangos (ej. "500,000+"); **instalaciones reales** también las publica Google internamente y el script ya las captura.
- **Iconos**: se descargan, se reducen a 128×128px y se guardan en base64 dentro de `iconos_YYYY-MM.json` — así el dashboard no depende de cargar imágenes externas al mostrarlo. Si falla la descarga de un icono puntual (red, imagen rota, etc.), esa app simplemente no aparece en el JSON y el dashboard usa un avatar de respaldo — nunca detiene la corrida completa.
- Cualquier app con la columna `app_id_android` o `app_id_ios` vacía en el catálogo simplemente queda "s/d" en esa tienda — es intencional (apps que no tienen versión ahí, o que no se pudo confirmar su id con la evidencia disponible).
- Revisa de vez en cuando la columna `error` de los CSV generados — si una app empieza a fallar todos los meses, probablemente cambió de app_id o fue retirada de la tienda, y toca actualizar `catalogo_billeteras_peru.csv`.
- **Calidad de servicio:** si una app tiene `resenas_1estrella_analizadas = 0` sin ningún `error`, puede significar que realmente no tiene reseñas de 1★ recientes (buena señal) o que Google Play no devolvió resultados en ese momento puntual — si ves varias apps grandes con 0 en el mismo mes, probablemente fue lo segundo y conviene volver a correr el workflow.
- Añadir la consulta de reseñas de 1★ suma una llamada más por app, así que la corrida completa tarda un poco más que antes — es normal.

## Actualizar el catálogo

Si una app cambia de nombre, sale una nueva, o se retira una: edita `catalogo_billeteras_peru.csv` directamente en GitHub (lápiz de edición en la página del archivo) y guarda el cambio (commit). La próxima corrida ya usará el catálogo actualizado.

---
Big Data S.A.C. — uso interno.
