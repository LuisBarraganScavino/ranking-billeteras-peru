# Ranking Mensual de Billeteras Digitales Perú — extractor automatizado

Script para Big Data S.A.C. que extrae mensualmente, de forma automática, el rating y nº de reseñas de las billeteras/apps financieras peruanas en Google Play y App Store, para alimentar el ranking mensual.

## Qué hace y qué NO hace

Este script **solo extrae datos crudos**. No calcula rating ponderado, tendencia, score compuesto, tercios ni hallazgos — eso se sigue generando en el proyecto de Claude "Ranking Mensual de Billeteras Digitales Perú", tomando el `datos_YYYY-MM.csv` que este script produce cada mes.

## Archivos

- `catalogo_billeteras_peru.csv` — las 61 apps a monitorear, con su app_id de Android e iOS (columna vacía si no aplica/no se encontró).
- `extract_ranking.py` — el script de extracción.
- `requirements.txt` — dependencias de Python.
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
3. **Verifica los permisos de Actions:** en tu repo, ve a *Settings → Actions → General → Workflow permissions* y marca **"Read and write permissions"**. Esto es necesario para que el workflow pueda hacer commit del CSV del mes automáticamente. Guarda los cambios.
4. **Prueba una corrida manual:** ve a la pestaña *Actions* de tu repo → selecciona "Ranking mensual de billeteras" → botón *"Run workflow"* → déjalo con el mes vacío (usa el mes actual) → *Run workflow*. Tarda unos minutos (hay una pausa de 1.5 segundos entre cada una de las 61 apps y sus 2 tiendas, para no saturar Google Play/App Store).
5. Al terminar, revisa que aparecieron dos archivos nuevos en la raíz del repo: `datos_YYYY-MM.csv` (Android) y `datos_YYYY-MM_ios.csv` (iOS). Ábrelos y confirma que la mayoría de filas tienen un rating numérico y no "s/d".

Desde ese momento, el workflow corre solo el día 1 de cada mes a las 9am hora Perú — no tienes que hacer nada más. También puedes lanzarlo manualmente cuando quieras desde la pestaña *Actions*.

## Cómo se usa el resultado cada mes

1. Entra al repo, abre `datos_YYYY-MM.csv` (y `..._ios.csv`) del mes que quieras procesar.
2. Descárgalo o copia su contenido.
3. Pégalo o súbelo en tu proyecto de Claude "Ranking Mensual de Billeteras Digitales Perú", junto con el ranking del mes anterior.
4. Claude genera la tabla de ranking, tendencia, tercios, top 5 subidas/caídas, hallazgos y el pie de página, listos para publicar.

## Notas y limitaciones

- **Android** usa `google-play-scraper`, una librería no oficial (lee el HTML público de Play Store). Es la más usada del ecosistema Python y estable, pero si Google cambia la estructura de su página podría dejar de funcionar para algunas apps — el script no se cae por eso, solo marca esa fila como "s/d" con el motivo del error en la columna `error`.
- **iOS** usa la API oficial y gratuita de Apple (`itunes.apple.com/lookup`), así que es más estable.
- **Instalaciones** solo existen para Android, y siempre en rangos (ej. "500,000+"), nunca como cifra exacta — así lo publica Google.
- Cualquier app con la columna `app_id_android` o `app_id_ios` vacía en el catálogo simplemente queda "s/d" en esa tienda — es intencional (apps que no tienen versión ahí, o que no se pudo confirmar su id con la evidencia disponible).
- Revisa de vez en cuando la columna `error` de los CSV generados — si una app empieza a fallar todos los meses, probablemente cambió de app_id o fue retirada de la tienda, y toca actualizar `catalogo_billeteras_peru.csv`.

## Actualizar el catálogo

Si una app cambia de nombre, sale una nueva, o se retira una: edita `catalogo_billeteras_peru.csv` directamente en GitHub (lápiz de edición en la página del archivo) y guarda el cambio (commit). La próxima corrida ya usará el catálogo actualizado.

---
Big Data S.A.C. — uso interno.
